"""
Causal Intervention Interface
==============================
Implements the causal reasoning layer for the academic knowledge world model.

Allows counterfactual queries:
  - "What if Language X had more papers?"
  - "What if Paper Y was removed from the corpus?"
  - "What if Concept Z became more prominent in Language A?"

Uses the do-operator framework: P(S_{t+1} | do(intervention), S_t)
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass


@dataclass
class InterventionResult:
    """Result of a causal intervention experiment."""
    description: str
    original_trajectory: np.ndarray      # [horizon+1, state_dim]
    intervened_trajectory: np.ndarray     # [horizon+1, state_dim]
    difference: np.ndarray                # [horizon+1, state_dim]
    effect_magnitude: float               # scalar: ||difference||
    per_language_effect: Dict[str, float] # effect per language


class CausalInterventionEngine:
    """
    Causal intervention engine for the academic knowledge world model.
    
    Enables counterfactual reasoning through the do-operator framework.
    Each intervention modifies the state before simulation and compares
    the resulting trajectory with the original (unintervened) trajectory.
    """

    def __init__(self, world_model, state_encoder, aligner):
        """
        Args:
            world_model: LoopedWorldModel instance
            state_encoder: KnowledgeStateEncoder instance
            aligner: CrossLingualAligner instance
        """
        self.world_model = world_model
        self.state_encoder = state_encoder
        self.aligner = aligner
        self.languages = ['zh', 'en', 'ar']

    def intervene_on_language_weight(self,
                                     state: torch.Tensor,
                                     lang_dist: Dict[str, int],
                                     target_lang: str,
                                     new_weight: float,
                                     horizon: int = 5
                                     ) -> InterventionResult:
        """
        Intervention: "What if Language X had more/less presence?"
        
        Modifies the language distribution in the state before simulation.
        """
        # Save original lang_dist
        original_dist = lang_dist.copy()
        
        # Create intervened language distribution
        intervened_dist = original_dist.copy()
        total = sum(intervened_dist.values()) or 1
        
        if target_lang in intervened_dist:
            # Change the target language's count to achieve desired weight
            current_weight = intervened_dist[target_lang] / total
            scale = new_weight / (current_weight + 1e-8)
            intervened_dist[target_lang] = int(intervened_dist[target_lang] * scale)
            # Renormalize other languages
            other_total = sum(v for k, v in intervened_dist.items() if k != target_lang)
            if other_total > 0:
                for k in intervened_dist:
                    if k != target_lang:
                        intervened_dist[k] = int(intervened_dist[k] * (total / other_total))
        
        # Original trajectory
        original_result = self.world_model.forward(
            state.unsqueeze(0), horizon=horizon, return_all_states=True
        )
        orig_traj = original_result['predicted_states'].squeeze(0).detach().numpy()
        
        # Create a modified state by adjusting the language encoding component
        device = state.device
        lang_embedding_dim = 3  # zh, en, ar
        
        # Create intervention vector for language weight adjustment
        intervention_vec = torch.zeros(self.world_model.config.action_dim)
        lang_idx = self.languages.index(target_lang)
        intervention_vec[lang_idx] = new_weight
        intervention_vec[lang_idx + len(self.languages)] = new_weight - (original_dist.get(target_lang, 0) / total)
        
        # Intervened trajectory
        intervened_result = self.world_model.forward(
            state.unsqueeze(0), horizon=horizon, 
            action=intervention_vec.unsqueeze(0),
            return_all_states=True
        )
        inter_traj = intervened_result['predicted_states'].squeeze(0).detach().numpy()
        
        # Compute difference
        diff = inter_traj - orig_traj
        
        # Effect magnitude
        effect_mag = np.linalg.norm(diff)
        
        # Per-language effect (decompose by analyzing state dimensions)
        per_lang_effect = {}
        for i, lang in enumerate(self.languages):
            lang_dim_start = i * (state.shape[-1] // len(self.languages))
            lang_dim_end = (i + 1) * (state.shape[-1] // len(self.languages))
            per_lang_effect[lang] = float(np.linalg.norm(
                diff[:, lang_dim_start:lang_dim_end]
            ))
        
        description = f"Intervention: Set {target_lang} language weight to {new_weight:.2f}"
        
        return InterventionResult(
            description=description,
            original_trajectory=orig_traj,
            intervened_trajectory=inter_traj,
            difference=diff,
            effect_magnitude=effect_mag,
            per_language_effect=per_lang_effect
        )

    def intervene_on_concept_prominence(self,
                                        state: torch.Tensor,
                                        concept_name: str,
                                        boost_amount: float = 0.3,
                                        horizon: int = 5
                                        ) -> InterventionResult:
        """
        Intervention: "What if Concept X became more prominent?"
        
        Boosts the concept's representation in the state.
        """
        device = state.device
        
        # Original trajectory
        original_result = self.world_model.forward(
            state.unsqueeze(0), horizon=horizon, return_all_states=True
        )
        orig_traj = original_result['predicted_states'].squeeze(0).detach().numpy()
        
        # Concept intervention vector
        intervention_vec = torch.zeros(self.world_model.config.action_dim)
        # Use the last few dimensions for concept boost
        intervention_vec[-1] = boost_amount
        
        # Intervened trajectory
        intervened_result = self.world_model.forward(
            state.unsqueeze(0), horizon=horizon,
            action=intervention_vec.unsqueeze(0),
            return_all_states=True
        )
        inter_traj = intervened_result['predicted_states'].squeeze(0).detach().numpy()
        
        diff = inter_traj - orig_traj
        effect_mag = np.linalg.norm(diff)
        
        description = f"Intervention: Boost concept '{concept_name}' by {boost_amount:.2f}"
        
        return InterventionResult(
            description=description,
            original_trajectory=orig_traj,
            intervened_trajectory=inter_traj,
            difference=diff,
            effect_magnitude=effect_mag,
            per_language_effect={}
        )

    def intervene_remove_papers(self,
                                state: torch.Tensor,
                                paper_ids: List[str],
                                n_removed: int,
                                horizon: int = 5
                                ) -> InterventionResult:
        """
        Intervention: "What if certain papers were removed (not published)?"
        
        Simulates reduced knowledge state by perturbing the state vector.
        """
        device = state.device
        
        # Original trajectory
        original_result = self.world_model.forward(
            state.unsqueeze(0), horizon=horizon, return_all_states=True
        )
        orig_traj = original_result['predicted_states'].squeeze(0).detach().numpy()
        
        # Removal intervention vector
        intervention_vec = torch.zeros(self.world_model.config.action_dim)
        removal_ratio = n_removed / max(len(paper_ids), 1)
        intervention_vec[-2] = -removal_ratio  # negative = removal
        
        # Intervened trajectory
        intervened_result = self.world_model.forward(
            state.unsqueeze(0), horizon=horizon,
            action=intervention_vec.unsqueeze(0),
            return_all_states=True
        )
        inter_traj = intervened_result['predicted_states'].squeeze(0).detach().numpy()
        
        diff = inter_traj - orig_traj
        effect_mag = np.linalg.norm(diff)
        
        description = f"Intervention: Remove {n_removed} papers (ratio={removal_ratio:.2f})"
        
        return InterventionResult(
            description=description,
            original_trajectory=orig_traj,
            intervened_trajectory=inter_traj,
            difference=diff,
            effect_magnitude=effect_mag,
            per_language_effect={}
        )

    def compare_interventions(self, 
                              state: torch.Tensor,
                              interventions: List[Dict],
                              horizon: int = 5
                              ) -> Dict[str, InterventionResult]:
        """
        Run multiple intervention experiments and return comparative results.
        
        Args:
            state: Current state vector
            interventions: List of dicts with keys 'type', 'params'
            horizon: Simulation horizon
            
        Returns:
            {intervention_name: InterventionResult}
        """
        results = {}
        
        for iv in interventions:
            iv_type = iv.get('type', '')
            params = iv.get('params', {})
            
            if iv_type == 'language_weight':
                name = f"lang_{params['target_lang']}_{params['new_weight']:.1f}"
                results[name] = self.intervene_on_language_weight(
                    state, params['lang_dist'], params['target_lang'],
                    params['new_weight'], horizon
                )
            elif iv_type == 'concept_boost':
                name = f"concept_{params['concept']}_{params['boost']:.1f}"
                results[name] = self.intervene_on_concept_prominence(
                    state, params['concept'], params['boost'], horizon
                )
            elif iv_type == 'remove_papers':
                name = f"remove_{params['n_removed']}"
                results[name] = self.intervene_remove_papers(
                    state, params['paper_ids'], params['n_removed'], horizon
                )
        
        return results

    def summarize_effects(self, results: Dict[str, InterventionResult]) -> str:
        """Generate a human-readable summary of intervention effects."""
        lines = ["=" * 60]
        lines.append("CAUSAL INTERVENTION ANALYSIS")
        lines.append("=" * 60)
        
        for name, result in results.items():
            lines.append(f"\n--- {result.description} ---")
            lines.append(f"  Overall effect magnitude: {result.effect_magnitude:.4f}")
            
            if result.per_language_effect:
                lines.append("  Per-language effect:")
                for lang, mag in sorted(result.per_language_effect.items(), 
                                        key=lambda x: x[1], reverse=True):
                    lines.append(f"    {lang}: {mag:.4f}")
            
            # Trajectory shape
            lines.append(f"  Trajectory shape: original={result.original_trajectory.shape}, "
                        f"intervened={result.intervened_trajectory.shape}")
        
        return "\n".join(lines)


# ============================================================================
# Quick test
# ============================================================================

if __name__ == "__main__":
    from world_model import LoopedWorldModel, WorldModelConfig
    
    config = WorldModelConfig(state_dim=128, action_dim=32)
    model = LoopedWorldModel(config)
    
    class DummyEncoder:
        pass
    
    class DummyAligner:
        pass
    
    engine = CausalInterventionEngine(model, DummyEncoder(), DummyAligner())
    
    state = torch.randn(128)
    lang_dist = {'zh': 30, 'en': 30, 'ar': 15}
    
    # Test language weight intervention
    result = engine.intervene_on_language_weight(
        state, lang_dist, 'ar', 0.35, horizon=5
    )
    print(result.description)
    print(f"  Effect magnitude: {result.effect_magnitude:.4f}")
    
    # Test concept boost
    result2 = engine.intervene_on_concept_prominence(
        state, 'CLIR', 0.5, horizon=5
    )
    print(result2.description)
    print(f"  Effect magnitude: {result2.effect_magnitude:.4f}")
    
    print("[OK] CausalInterventionEngine works")
