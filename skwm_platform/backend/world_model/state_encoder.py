"""
Multilingual Knowledge State Encoder
=====================================
Encodes the academic knowledge state into vector representations
using LaBSE multilingual embeddings + graph structure encoding.

Each knowledge state snapshot is encoded as:
  - Paper embedding matrix (LaBSE)
  - Graph structural encoding (citation network)
  - Language distribution encoding
  - Concept distribution encoding
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
from transformers import AutoTokenizer, AutoModel


class LaBSEEncoder:
    """LaBSE-based multilingual text encoder (transformers, not sentence-transformers)."""

    def __init__(self, model_name: str = "sentence-transformers/LaBSE",
                 device: str = "cpu"):
        self.device = device
        print(f"[LaBSE] Loading {model_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.to(device)
        self.model.eval()
        self.dim = self.model.config.hidden_size  # 768
        print(f"[LaBSE] Loaded. Dim={self.dim}, Device={device}")

    def encode(self, texts: List[str], batch_size: int = 16) -> np.ndarray:
        """Encode texts into multilingual embeddings."""
        all_embs = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            encoded = self.tokenizer(
                batch, padding=True, truncation=True, 
                max_length=128, return_tensors='pt'
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            with torch.no_grad():
                outputs = self.model(**encoded)
                # Mean pool over tokens
                attention_mask = encoded['attention_mask']
                token_embeddings = outputs.last_hidden_state
                input_mask_expanded = attention_mask.unsqueeze(-1).expand(
                    token_embeddings.size()).float()
                emb = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
                    input_mask_expanded.sum(1), min=1e-9)
                all_embs.append(emb.cpu().numpy())
        return np.vstack(all_embs)


class GraphStructureEncoder:
    """Encodes citation network structure using spectral features."""

    def __init__(self, max_dim: int = 32):
        self.max_dim = max_dim

    def encode(self, adj_matrix: np.ndarray) -> np.ndarray:
        """
        Encode graph structure via eigen decomposition.
        
        Args:
            adj_matrix: [n, n] adjacency matrix
            
        Returns:
            structural_features: [n, max_dim]
        """
        n = adj_matrix.shape[0]
        if n == 0:
            return np.zeros((0, self.max_dim))
        
        # Degree features
        in_deg = adj_matrix.sum(axis=0)  # citation in-degree
        out_deg = adj_matrix.sum(axis=1)  # citation out-degree
        
        # Normalized Laplacian eigenfeatures
        lap = np.diag(in_deg + out_deg) - (adj_matrix + adj_matrix.T)
        
        try:
            eigvals, eigvecs = np.linalg.eigh(lap)
            # Take top-k eigenvectors (or pad)
            k = min(self.max_dim, n)
            top_vecs = eigvecs[:, -k:] if k > 0 else np.zeros((n, 1))
            if k < self.max_dim:
                pad = np.zeros((n, self.max_dim - k))
                features = np.hstack([top_vecs, pad])
            else:
                features = top_vecs[:, :self.max_dim]
        except np.linalg.LinAlgError:
            features = np.zeros((n, self.max_dim))
        
        # Concatenate degree features
        deg_feat = np.column_stack([
            in_deg / (in_deg.max() + 1e-8),
            out_deg / (out_deg.max() + 1e-8)
        ])
        
        return features


class LanguageDistributionEncoder:
    """Encodes language distribution of the knowledge state."""

    def __init__(self, languages: List[str] = None):
        self.languages = languages or ['zh', 'en', 'ar']

    def encode(self, lang_dist: Dict[str, int]) -> np.ndarray:
        """Encode language distribution as a fixed vector."""
        vec = np.zeros(len(self.languages))
        total = sum(lang_dist.values()) or 1
        for i, lang in enumerate(self.languages):
            vec[i] = lang_dist.get(lang, 0) / total
        return vec


class ConceptDistributionEncoder:
    """Encodes concept/topic distribution of the state."""

    def __init__(self, concept_names: List[str]):
        self.concept_names = concept_names

    def encode(self, concept_matrix: np.ndarray) -> np.ndarray:
        """Encode concept distribution. [n_papers, n_concepts] -> [n_concepts]"""
        if concept_matrix.size == 0:
            return np.zeros(len(self.concept_names))
        return concept_matrix.mean(axis=0)


class KnowledgeStateEncoder(nn.Module):
    """
    Complete knowledge state encoder.
    Combines multilingual paper embeddings, graph structure, language and concept distributions.
    """

    def __init__(self, 
                 paper_dim: int = 768,
                 graph_dim: int = 32,
                 concept_dim: int = 10,
                 lang_dim: int = 3,
                 hidden_dim: int = 256,
                 output_dim: int = 128):
        super().__init__()
        
        self.paper_dim = paper_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        
        total_input_dim = paper_dim + graph_dim + concept_dim + lang_dim
        
        # State projection network
        self.state_encoder = nn.Sequential(
            nn.Linear(total_input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim),
            nn.LayerNorm(output_dim)
        )
        
        # Sub-encoders
        self.graph_encoder = GraphStructureEncoder(max_dim=graph_dim)
        self.lang_encoder = LanguageDistributionEncoder()
        
    def encode_state(self,
                     paper_embeddings: np.ndarray,
                     citation_matrix: np.ndarray,
                     lang_dist: Dict[str, int],
                     concept_dist: np.ndarray,
                     concept_names: List[str] = None) -> torch.Tensor:
        """
        Encode a full knowledge state into a single vector.
        
        Args:
            paper_embeddings: [n_papers, paper_dim]
            citation_matrix: [n_papers, n_papers]
            lang_dist: {lang: count}
            concept_dist: [n_concepts] or [n_papers, n_concepts]
            concept_names: list of concept names
            
        Returns:
            state_vector: [output_dim]
        """
        n = paper_embeddings.shape[0]
        if n == 0:
            return torch.zeros(self.output_dim)
        
        # 1. Aggregate paper embeddings (mean pooling)
        paper_agg = paper_embeddings.mean(axis=0)  # [paper_dim]
        
        # 2. Graph structure features
        graph_feat = self.graph_encoder.encode(citation_matrix)  # [n, graph_dim]
        graph_agg = graph_feat.mean(axis=0)  # [graph_dim]
        
        # 3. Language distribution
        lang_vec = self.lang_encoder.encode(lang_dist)  # [lang_dim]
        
        # 4. Concept distribution
        if concept_dist.ndim == 2:
            concept_agg = concept_dist.mean(axis=0)  # [n_concepts]
        else:
            concept_agg = concept_dist
        
        # Concatenate all features
        combined = np.concatenate([
            paper_agg, graph_agg, lang_vec, concept_agg
        ])
        
        # Project to output dimension
        combined_tensor = torch.FloatTensor(combined).unsqueeze(0)
        state_vector = self.state_encoder(combined_tensor).squeeze(0)
        
        return state_vector


# ============================================================================
# Quick test
# ============================================================================

if __name__ == "__main__":
    # Quick test with random data
    encoder = KnowledgeStateEncoder()
    paper_embs = np.random.randn(20, 768)
    cit_mat = np.random.randint(0, 2, (20, 20))
    lang_dist = {'zh': 8, 'en': 7, 'ar': 5}
    concept_dist = np.random.randn(10)
    
    state_vec = encoder.encode_state(paper_embs, cit_mat, lang_dist, concept_dist)
    print(f"State vector shape: {state_vec.shape}")
    print(f"State vector norm: {state_vec.norm().item():.4f}")
    print("[OK] KnowledgeStateEncoder works")
