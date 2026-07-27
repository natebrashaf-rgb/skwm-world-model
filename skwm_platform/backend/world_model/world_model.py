"""
Looped World Model for Academic Knowledge Evolution
====================================================
Implements the core world model with:
  - Looped Transformer architecture for long-range simulation
  - Adaptive computation (shorter loop for near-term, deeper loop for long-term)
  - State transition: S(t) -> S(t+1) given actions/interventions
  - Sequence of state rollouts for forward simulation

Based on the Looped World Models concept (arXiv:2606.18208, 2026).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass


@dataclass
class WorldModelConfig:
    """Configuration for the world model."""
    state_dim: int = 128           # Dimension of encoded state
    hidden_dim: int = 256          # Transformer hidden dimension
    n_heads: int = 4               # Attention heads
    max_loops: int = 16            # Maximum loop iterations
    action_dim: int = 32           # Dimension of action/intervention encoding
    dropout: float = 0.1
    learning_rate: float = 1e-4


class AdaptiveLoopController(nn.Module):
    """
    Determines when to stop looping based on state convergence.
    Pass horizon info as a separate signal so the model can
    allocate compute budget accordingly.
    """
    def __init__(self, state_dim: int, hidden_dim: int):
        super().__init__()
        self.gate = nn.Sequential(
            nn.Linear(state_dim + 1, hidden_dim),   # +1 for horizon signal
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid()
        )

    def forward(self, state_vec: torch.Tensor, 
                horizon_frac: float,
                step: int) -> torch.Tensor:
        """Return stop probability [0,1]."""
        h = torch.cat([
            state_vec,
            torch.tensor([horizon_frac], device=state_vec.device).expand(state_vec.shape[0], 1)
        ], dim=-1)
        return self.gate(h)


class LoopedTransformerBlock(nn.Module):
    """A single transformer block used in the loop."""

    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1):
        super().__init__()
        self.self_attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout,
                                                batch_first=True)
        self.norm1 = nn.LayerNorm(d_model)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 4),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 4, d_model)
        )
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Self-attention with residual
        attn_out, _ = self.self_attn(x, x, x)
        x = self.norm1(x + self.dropout(attn_out))
        # FFN with residual
        ffn_out = self.ffn(x)
        x = self.norm2(x + self.dropout(ffn_out))
        return x


class LoopedWorldModel(nn.Module):
    """
    Looped World Model for academic knowledge evolution.
    
    Given a current knowledge state S(t) and optional action/intervention A,
    predicts S(t+1), S(t+2), ... by looping through a shared transformer block.
    """

    def __init__(self, config: WorldModelConfig):
        super().__init__()
        self.config = config
        
        # Input projection
        self.input_proj = nn.Linear(config.state_dim, config.hidden_dim)
        
        # Looped transformer block (shared weights, looped)
        self.loop_block = LoopedTransformerBlock(
            config.hidden_dim, config.n_heads, config.dropout
        )
        
        # Action encoding projection
        if config.action_dim > 0:
            self.action_proj = nn.Linear(config.action_dim, config.hidden_dim)
        
        # Output projection: back to state dimension
        self.output_proj = nn.Linear(config.hidden_dim, config.state_dim)
        
        # Loop controller
        self.loop_controller = AdaptiveLoopController(config.state_dim, config.hidden_dim)
        
        # Step embedding (informs the model which loop iteration we're on)
        self.step_embedding = nn.Embedding(config.max_loops + 1, config.hidden_dim)
        
        print(f"[LoopedWM] Model initialized: state_dim={config.state_dim}, "
              f"hidden_dim={config.hidden_dim}, max_loops={config.max_loops}")

    def forward(self, 
                state: torch.Tensor,
                horizon: int = 5,
                action: Optional[torch.Tensor] = None,
                return_all_states: bool = True) -> Dict:
        """
        Forward simulation of knowledge state evolution.
        
        Args:
            state: Current state vector [batch, state_dim]
            horizon: Number of steps to simulate
            action: Optional intervention/action vector [batch, action_dim]
            return_all_states: Whether to return all intermediate states
            
        Returns:
            Dict with:
              - 'predicted_states': [batch, horizon, state_dim] if return_all_states
              - 'loop_steps': [batch] number of loops used per step
              - 'convergence': [batch, horizon] convergence signal
        """
        batch_size = state.shape[0]
        device = state.device
        
        # Project to hidden dim
        h = self.input_proj(state).unsqueeze(1)  # [batch, 1, hidden_dim]
        
        # Add action if provided
        if action is not None:
            action_h = self.action_proj(action).unsqueeze(1)
            h = h + action_h
        
        predicted_states = []
        convergence_scores = []
        loop_steps_used = []
        
        for step in range(horizon):
            # Adaptive loop: determine how many loop iterations to run
            horizon_frac = step / max(horizon - 1, 1)
            
            # Step embedding
            step_emb = self.step_embedding(
                torch.tensor([min(step, self.config.max_loops)], device=device)
            ).unsqueeze(1)  # [1, 1, hidden]
            
            h_step = h + step_emb
            
            # Run loop iterations (each iteration = one transformer block pass)
            loop_count = 0
            for loop_i in range(self.config.max_loops):
                h_step = self.loop_block(h_step)
                loop_count += 1
                
                # Check if we should stop looping (adaptive compute)
                h_state = self.output_proj(h_step.squeeze(1))
                stop_prob = self.loop_controller(h_state, horizon_frac, loop_i)
                
                if stop_prob.mean().item() > 0.5 and loop_i > 1:
                    break
            
            # Decode to state space
            next_state = self.output_proj(h_step.squeeze(1))  # [batch, state_dim]
            
            if return_all_states:
                predicted_states.append(next_state)
            
            convergence_scores.append(stop_prob.mean().item())
            loop_steps_used.append(loop_count)
            
            # Prepare for next step
            h = self.input_proj(next_state).unsqueeze(1)
        
        result = {
            'loop_steps': loop_steps_used,
            'convergence': convergence_scores,
        }
        
        if return_all_states and predicted_states:
            result['predicted_states'] = torch.stack(predicted_states, dim=1)
        
        return result

    def simulate_trajectory(self, 
                            initial_state: torch.Tensor,
                            horizon: int = 10,
                            action_fn: Optional[Callable] = None) -> Dict:
        """
        Simulate a full trajectory, optionally applying actions at each step.
        
        Args:
            initial_state: Starting state [state_dim]
            horizon: Number of steps
            action_fn: Optional function that takes (step, state) -> action vector
            
        Returns:
            Dict with trajectory data
        """
        state = initial_state.unsqueeze(0)  # [1, state_dim]
        all_states = [state]
        
        for step in range(horizon):
            action = None
            if action_fn is not None:
                action = action_fn(step, state.squeeze(0))
                action = action.unsqueeze(0)
            
            with torch.set_grad_enabled(False):
                result = self.forward(state, horizon=1, action=action, return_all_states=True)
            state = result['predicted_states'][:, -1, :]
            all_states.append(state)
        
        return {
            'states': torch.cat(all_states, dim=0),  # [horizon+1, state_dim]
        }


class WorldModelTrainer:
    """Simple trainer for the world model."""

    def __init__(self, model: LoopedWorldModel, lr: float = 1e-4):
        self.model = model
        self.optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
        self.loss_fn = nn.MSELoss()

    def train_step(self, 
                   state_seq: torch.Tensor,
                   horizon: int = 1) -> float:
        """
        Train on a random transition from the state sequence.
        Each call processes exactly one (state, next_state) pair.
        """
        self.model.train()
        self.optimizer.zero_grad()
        
        seq_len = state_seq.shape[0]
        idx = torch.randint(0, seq_len - 1, (1,)).item()
        
        current = state_seq[idx:idx+1]  # [1, state_dim]
        target = state_seq[idx+1:idx+2]  # [1, state_dim]
        
        pred = self.model.forward(current, horizon=1, return_all_states=True)
        pred_state = pred['predicted_states'][:, -1, :]
        
        loss = self.loss_fn(pred_state, target)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()
        
        return loss.item()


# ============================================================================
# Quick test
# ============================================================================

if __name__ == "__main__":
    config = WorldModelConfig(state_dim=128, hidden_dim=256, max_loops=8)
    model = LoopedWorldModel(config)
    
    # Test forward pass
    state = torch.randn(1, 128)
    result = model.forward(state, horizon=5)
    print(f"Forward pass: {result['predicted_states'].shape}")
    print(f"Loop steps used: {result['loop_steps']}")
    print(f"Convergence: {[f'{c:.3f}' for c in result['convergence']]}")
    
    # Test trajectory simulation
    traj = model.simulate_trajectory(state.squeeze(0), horizon=8)
    print(f"Trajectory: {traj['states'].shape}")
    print("[OK] LoopedWorldModel works")
