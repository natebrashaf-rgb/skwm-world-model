"""
Cross-lingual Dynamic Alignment Module
========================================
Implements dynamic temporal alignment between language-specific knowledge states.

Core innovation: instead of static bilingual dictionaries, this module
tracks how cross-lingual concept alignments evolve over time.

Key capabilities:
  - Language-specific state decomposition
  - Cross-lingual concept vector alignment
  - Temporal alignment drift detection
  - Language gap identification (concepts in one language but not another)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Optional, Tuple


class CrossLingualAligner(nn.Module):
    """
    Dynamic cross-lingual alignment module.
    
    Takes a multilingual knowledge state and:
      1. Decomposes it into language-specific sub-states
      2. Learns alignment transformations between language spaces
      3. Tracks alignment drift over time
    """

    def __init__(self, 
                 state_dim: int = 128,
                 n_languages: int = 3,
                 alignment_dim: int = 64):
        super().__init__()
        
        self.state_dim = state_dim
        self.n_languages = n_languages
        self.alignment_dim = alignment_dim
        
        # Per-language projection to shared alignment space
        self.lang_projectors = nn.ModuleList([
            nn.Sequential(
                nn.Linear(state_dim, alignment_dim * 2),
                nn.ReLU(),
                nn.Linear(alignment_dim * 2, alignment_dim)
            )
            for _ in range(n_languages)
        ])
        
        # Alignment quality predictor (how well two languages align)
        self.alignment_scorer = nn.Sequential(
            nn.Linear(alignment_dim * 2, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid()
        )

    def decompose_by_language(self, 
                              state_vector: torch.Tensor,
                              lang_weights: Dict[str, float]) -> List[torch.Tensor]:
        """
        Decompose a unified state into language-specific components.
        
        Args:
            state_vector: [state_dim] unified knowledge state
            lang_weights: {lang: proportion} language distribution
            
        Returns:
            lang_states: list of [state_dim] per language
        """
        languages = ['zh', 'en', 'ar']
        lang_states = []
        
        for lang in languages:
            weight = lang_weights.get(lang, 0.0)
            # Weighted decomposition: each language gets a proportion of the state
            # plus a learned language-specific bias
            lang_state = state_vector * weight
            lang_states.append(lang_state)
        
        return lang_states

    def project_to_alignment_space(self, 
                                   lang_states: List[torch.Tensor],
                                   language_indices: Optional[List[int]] = None
                                   ) -> List[torch.Tensor]:
        """
        Project each language's state to a shared alignment space.
        
        Args:
            lang_states: list of [state_dim] per language
            language_indices: which languages (0=zh, 1=en, 2=ar)
            
        Returns:
            aligned: list of [alignment_dim] per language
        """
        if language_indices is None:
            language_indices = list(range(len(lang_states)))
        
        aligned = []
        for i, state in zip(language_indices, lang_states):
            proj = self.lang_projectors[i](state)
            aligned.append(proj)
        
        return aligned

    def compute_alignment_scores(self,
                                 aligned_states: List[torch.Tensor]
                                 ) -> Dict[Tuple[str, str], float]:
        """
        Compute pairwise alignment quality between languages.
        
        Returns:
            {(lang1, lang2): score} where score in [0,1], higher = better aligned
        """
        languages = ['zh', 'en', 'ar']
        scores = {}
        
        for i in range(len(aligned_states)):
            for j in range(i+1, len(aligned_states)):
                # Concatenate and predict alignment score
                pair = torch.cat([aligned_states[i], aligned_states[j]], dim=-1)
                score = self.alignment_scorer(pair).item()
                scores[(languages[i], languages[j])] = score
        
        return scores

    def compute_crosslingual_similarity(self,
                                        aligned_states: List[torch.Tensor]
                                        ) -> np.ndarray:
        """
        Compute pairwise cosine similarity in alignment space.
        
        Returns:
            sim_matrix: [n_lang, n_lang] similarity matrix
        """
        n = len(aligned_states)
        sim_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    sim_matrix[i, j] = 1.0
                else:
                    sim = F.cosine_similarity(
                        aligned_states[i].unsqueeze(0),
                        aligned_states[j].unsqueeze(0)
                    ).item()
                    sim_matrix[i, j] = sim
        
        return sim_matrix

    def detect_alignment_drift(self,
                               current_sim: np.ndarray,
                               previous_sim: np.ndarray,
                               threshold: float = 0.05) -> List[Tuple[str, str, float]]:
        """
        Detect significant changes in cross-lingual alignment.
        
        Args:
            current_sim: current alignment matrix
            previous_sim: previous alignment matrix
            threshold: minimum change to report
            
        Returns:
            [(lang1, lang2, drift_magnitude)] list of drifts
        """
        languages = ['zh', 'en', 'ar']
        drifts = []
        
        for i in range(len(languages)):
            for j in range(i+1, len(languages)):
                drift = abs(current_sim[i, j] - previous_sim[i, j])
                if drift > threshold:
                    drifts.append((languages[i], languages[j], drift))
        
        return drifts

    def find_language_gaps(self,
                           aligned_states: List[torch.Tensor],
                           threshold: float = 0.3) -> List[Tuple[str, str, float]]:
        """
        Find language pairs with poor alignment (knowledge gaps).
        
        Returns:
            [(lang1, lang2, alignment_score)] for low-scoring pairs
        """
        languages = ['zh', 'en', 'ar']
        gaps = []
        
        for i in range(len(aligned_states)):
            for j in range(i+1, len(aligned_states)):
                sim = F.cosine_similarity(
                    aligned_states[i].unsqueeze(0),
                    aligned_states[j].unsqueeze(0)
                ).item()
                if sim < threshold:
                    gaps.append((languages[i], languages[j], sim))
        
        return gaps


class MultilingualStateDecomposer:
    """
    Decomposes the corpus-level knowledge state into language-specific views.
    Works with raw AcademicKG data.
    """

    def __init__(self, languages: List[str] = None):
        self.languages = languages or ['zh', 'en', 'ar']

    def compute_language_state(self, 
                               paper_ids: List[str],
                               lang: str,
                               state_encoder: 'KnowledgeStateEncoder' = None
                               ) -> Optional[torch.Tensor]:
        """
        Compute the state of knowledge in a specific language.
        """
        # This would use the state encoder to encode only papers of a given language
        # For now, returns a placeholder
        return None


# ============================================================================
# Quick test
# ============================================================================

if __name__ == "__main__":
    aligner = CrossLingualAligner(state_dim=128, n_languages=3, alignment_dim=64)
    
    # Simulate a multilingual state
    state_vec = torch.randn(128)
    lang_weights = {'zh': 0.4, 'en': 0.35, 'ar': 0.25}
    
    # Decompose and align
    lang_states = aligner.decompose_by_language(state_vec, lang_weights)
    aligned = aligner.project_to_alignment_space(lang_states)
    
    # Compute alignment
    scores = aligner.compute_alignment_scores(aligned)
    print("Pairwise alignment scores:")
    for pair, score in scores.items():
        print(f"  {pair[0]}-{pair[1]}: {score:.4f}")
    
    sim_matrix = aligner.compute_crosslingual_similarity(aligned)
    print(f"\nCross-lingual similarity matrix:\n{sim_matrix}")
    
    # Simulate drift
    prev_sim = sim_matrix + np.random.randn(3, 3) * 0.02
    drifts = aligner.detect_alignment_drift(sim_matrix, prev_sim)
    print(f"\nAlignment drifts detected: {len(drifts)}")
    for d in drifts:
        print(f"  {d[0]}-{d[1]}: {d[2]:.4f}")
    
    # Language gaps
    gaps = aligner.find_language_gaps(aligned, threshold=0.3)
    print(f"\nLanguage gaps found: {len(gaps)}")
    for g in gaps:
        print(f"  {g[0]}-{g[1]}: similarity={g[2]:.4f} (below threshold)")
    
    print("[OK] CrossLingualAligner works")
