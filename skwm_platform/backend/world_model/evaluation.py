"""
Evaluation Metrics & Academic Visualization
=============================================
Provides:
  - Alignment accuracy metrics
  - Prediction error per language
  - Academic-quality charts (matplotlib)
  - Comprehensive evaluation report generation

All charts use PingFang HK for Chinese labels on macOS.
"""

import numpy as np
import torch
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Matplotlib setup for Chinese
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# Chinese font
plt.rcParams['font.family'] = 'PingFang HK'
plt.rcParams['axes.unicode_minus'] = False

FIGS_DIR = Path(__file__).parent.parent / "figures"
FIGS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Evaluation Metrics
# ============================================================================

class WorldModelEvaluator:
    """Comprehensive evaluation of the world model."""

    @staticmethod
    def compute_alignment_accuracy(sim_matrix: np.ndarray, 
                                    ground_truth: np.ndarray = None) -> Dict:
        """
        Evaluate cross-lingual alignment quality.
        
        Args:
            sim_matrix: [n_lang, n_lang] similarity matrix
            ground_truth: gold-standard similarity (if available)
            
        Returns:
            metrics dict
        """
        metrics = {}
        
        # Average pairwise similarity (higher = better aligned overall)
        n = sim_matrix.shape[0]
        pairwise = []
        for i in range(n):
            for j in range(i+1, n):
                pairwise.append(sim_matrix[i, j])
        metrics['mean_pairwise_sim'] = float(np.mean(pairwise))
        metrics['std_pairwise_sim'] = float(np.std(pairwise))
        
        # Maximum alignment gap (largest dissimilarity)
        if pairwise:
            metrics['max_gap'] = float(max(pairwise)) - float(min(pairwise))
        
        # Alignment stability (variance over time, if multiple timestamps)
        if ground_truth is not None:
            metrics['alignment_mse'] = float(np.mean((sim_matrix - ground_truth) ** 2))
        
        return metrics

    @staticmethod
    def compute_prediction_metrics(ground_truth: np.ndarray,
                                    predictions: np.ndarray,
                                    language_weights: Dict[int, str] = None
                                    ) -> Dict:
        """
        Comprehensive prediction evaluation.
        
        Args:
            ground_truth: [n_steps, state_dim]
            predictions: [n_steps, state_dim]
            language_weights: {lang_idx: lang_name}
            
        Returns:
            metrics dict
        """
        metrics = {}
        
        # Overall MSE
        mse = np.mean((ground_truth - predictions) ** 2)
        metrics['mse'] = float(mse)
        metrics['rmse'] = float(np.sqrt(mse))
        
        # Cosine similarity per step (direction accuracy)
        n_steps = ground_truth.shape[0]
        cos_sims = []
        for t in range(n_steps):
            gt = ground_truth[t]
            pred = predictions[t]
            cos = np.dot(gt, pred) / (np.linalg.norm(gt) * np.linalg.norm(pred) + 1e-8)
            cos_sims.append(cos)
        metrics['mean_cosine_sim'] = float(np.mean(cos_sims))
        
        # Per-language error decomposition
        if language_weights:
            lang_mse = {}
            dim = ground_truth.shape[1]
            n_lang = len(language_weights)
            dims_per_lang = dim // n_lang
            
            for idx, lang_name in language_weights.items():
                start = idx * dims_per_lang
                end = (idx + 1) * dims_per_lang if idx < n_lang - 1 else dim
                gt_lang = ground_truth[:, start:end]
                pred_lang = predictions[:, start:end]
                lang_mse[lang_name] = float(np.mean((gt_lang - pred_lang) ** 2))
            
            metrics['per_language_mse'] = lang_mse
        
        return metrics

    @staticmethod
    def compute_frontier_hit_rate(predicted_states: np.ndarray,
                                   actual_states: np.ndarray,
                                   top_k: int = 3) -> Dict:
        """
        Compute 'frontier hit rate': how often the predicted direction
        matches the actual direction of knowledge state change.
        """
        pred_delta = np.diff(predicted_states, axis=0)
        actual_delta = np.diff(actual_states, axis=0)
        
        # Direction similarity
        dir_sims = []
        for t in range(len(pred_delta)):
            cos = np.dot(pred_delta[t], actual_delta[t]) / (
                np.linalg.norm(pred_delta[t]) * np.linalg.norm(actual_delta[t]) + 1e-8
            )
            dir_sims.append(cos)
        
        return {
            'mean_direction_similarity': float(np.mean(dir_sims)),
            'direction_accuracy': float(np.mean([s > 0 for s in dir_sims])),
        }


# ============================================================================
# Academic Visualization
# ============================================================================

class AcademicVisualizer:
    """Generate publication-quality charts for the world model analysis."""

    @staticmethod
    def plot_loss_curve(losses: List[float], save_path: str = "loss_curve.pdf"):
        """Training loss curve."""
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(losses, color='#1a73e8', linewidth=1.5, label='Training Loss')
        ax.set_xlabel('Training Step', fontsize=12)
        ax.set_ylabel('MSE Loss', fontsize=12)
        ax.set_title('World Model Training Convergence', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        plt.tight_layout()
        plt.savefig(FIGS_DIR / save_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  [Chart] Saved {save_path}")

    @staticmethod
    def plot_state_trajectory(ground_truth: np.ndarray,
                               predictions: np.ndarray = None,
                               years: List[int] = None,
                               save_path: str = "state_trajectory.pdf"):
        """
        Plot knowledge state evolution (PCA-reduced to 2D).
        """
        from sklearn.decomposition import PCA
        
        # Concatenate for PCA fitting
        all_data = ground_truth.copy()
        if predictions is not None:
            all_data = np.vstack([all_data, predictions])
        
        pca = PCA(n_components=2)
        all_2d = pca.fit_transform(all_data)
        
        n_gt = ground_truth.shape[0]
        gt_2d = all_2d[:n_gt]
        
        fig, ax = plt.subplots(figsize=(9, 6))
        
        # Ground truth trajectory
        ax.plot(gt_2d[:, 0], gt_2d[:, 1], 'o-', color='#1a73e8', 
                linewidth=2, markersize=8, label='Ground Truth', zorder=5)
        
        # Add year labels
        if years:
            for i, (x, y) in enumerate(gt_2d):
                year_idx = i if i < len(years) else -1
                ax.annotate(str(years[year_idx]), (x, y), textcoords="offset points",
                           xytext=(0, 10), ha='center', fontsize=9, color='#1a73e8')
    
        # Predictions
        if predictions is not None:
            pred_2d = all_2d[n_gt:]
            ax.plot(pred_2d[:, 0], pred_2d[:, 1], 's--', color='#e8710a',
                    linewidth=1.5, markersize=6, label='World Model Prediction', zorder=4)
            if years:
                start_idx = 1  # predictions start from year[1:]
                for i, (x, y) in enumerate(pred_2d):
                    year_idx = start_idx + i
                    if year_idx < len(years):
                        ax.annotate(str(years[year_idx]), (x, y), textcoords="offset points",
                                   xytext=(0, -12), ha='center', fontsize=9, color='#e8710a')
        
        ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%})', fontsize=12)
        ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%})', fontsize=12)
        ax.set_title('Academic Knowledge State Evolution', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(FIGS_DIR / save_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  [Chart] Saved {save_path}")
        
        return {'explained_var': sum(pca.explained_variance_ratio_)}

    @staticmethod
    def plot_alignment_drift(alignment_history: Dict[int, Dict[str, float]],
                              save_path: str = "alignment_drift.pdf"):
        """
        Plot cross-lingual alignment drift over time.
        
        Args:
            alignment_history: {year: {lang_pair: similarity}}
        """
        years = sorted(alignment_history.keys())
        pairs = list(alignment_history[years[0]].keys())
        
        fig, ax = plt.subplots(figsize=(9, 5))
        
        colors = ['#1a73e8', '#e8710a', '#34a853']
        for i, pair in enumerate(pairs):
            values = [alignment_history[y][pair] for y in years]
            ax.plot(years, values, 'o-', color=colors[i % len(colors)],
                    linewidth=2, markersize=6, label=pair)
        
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Cross-lingual Similarity', fontsize=12)
        ax.set_title('Cross-lingual Alignment Drift Over Time', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(FIGS_DIR / save_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  [Chart] Saved {save_path}")

    @staticmethod
    def plot_intervention_comparison(intervention_results: Dict[str, np.ndarray],
                                      baseline_name: str = "Baseline",
                                      save_path: str = "intervention_effects.pdf"):
        """
        Bar chart comparing intervention effect magnitudes.
        """
        names = list(intervention_results.keys())
        magnitudes = [float(np.linalg.norm(v)) for v in intervention_results.values()]
        
        fig, ax = plt.subplots(figsize=(8, 5))
        
        bars = ax.bar(names, magnitudes, color=['#1a73e8', '#e8710a', '#34a853', '#9c27b0'])
        ax.set_ylabel('Effect Magnitude (L2 norm)', fontsize=12)
        ax.set_title('Causal Intervention Effect Comparison', fontsize=14)
        
        # Add value labels on bars
        for bar, mag in zip(bars, magnitudes):
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
                    f'{mag:.2f}', ha='center', va='bottom', fontsize=10)
        
        ax.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=15)
        plt.tight_layout()
        plt.savefig(FIGS_DIR / save_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  [Chart] Saved {save_path}")

    @staticmethod
    def plot_language_distribution_evolution(year_dist: Dict[int, Dict[str, int]],
                                              save_path: str = "language_evolution.pdf"):
        """
        Stacked area chart showing language distribution change over time.
        """
        years = sorted(year_dist.keys())
        langs = ['zh', 'en', 'ar']
        colors = ['#e8710a', '#1a73e8', '#34a853']
        
        data = {lang: [] for lang in langs}
        for y in years:
            total = sum(year_dist[y].values()) or 1
            for lang in langs:
                data[lang].append(year_dist[y].get(lang, 0) / total * 100)
        
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.stackplot(years, data['zh'], data['en'], data['ar'],
                     labels=['Chinese', 'English', 'Arabic'],
                     colors=colors, alpha=0.8)
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Percentage (%)', fontsize=12)
        ax.set_title('Language Distribution in Academic Corpus', fontsize=14)
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)
        plt.tight_layout()
        plt.savefig(FIGS_DIR / save_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  [Chart] Saved {save_path}")

    @staticmethod
    def plot_per_language_error(lang_mse: Dict[str, float],
                                 save_path: str = "per_language_error.pdf"):
        """
        Bar chart of prediction error per language.
        """
        fig, ax = plt.subplots(figsize=(7, 4))
        langs = list(lang_mse.keys())
        errors = [lang_mse[l] for l in langs]
        
        colors = ['#e8710a', '#1a73e8', '#34a853']
        bars = ax.bar(langs, errors, color=colors[:len(langs)])
        ax.set_ylabel('MSE', fontsize=12)
        ax.set_title('Prediction Error by Language', fontsize=14)
        
        for bar, err in zip(bars, errors):
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.001,
                    f'{err:.4f}', ha='center', va='bottom', fontsize=10)
        
        ax.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(FIGS_DIR / save_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  [Chart] Saved {save_path}")


# ============================================================================
# Report Generator
# ============================================================================

class EvaluationReport:
    """Generate comprehensive evaluation report."""

    @staticmethod
    def generate(report_data: Dict, output_path: str = "evaluation_report.md"):
        """Generate markdown evaluation report."""
        lines = []
        lines.append("# 🌍 Cross-lingual Academic World Model — Evaluation Report")
        lines.append(f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("\n---\n")
        
        # Corpus summary
        kg = report_data.get('kg')
        if kg:
            lines.append("## 📊 Corpus Summary")
            lines.append(f"- Total papers: {len(kg.papers)}")
            for lang in ['zh', 'en', 'ar']:
                n = sum(1 for p in kg.papers.values() if p.lang == lang)
                lines.append(f"  - {lang}: {n} papers")
            lines.append(f"- Concepts: {len(kg.concepts)}")
            lines.append(f"- Time span: {report_data.get('year_span', 'N/A')}")
        
        # Training
        losses = report_data.get('losses', [])
        if losses:
            lines.append(f"\n## 🧠 Training")
            lines.append(f"- Final loss: {losses[-1]:.6f}")
            lines.append(f"- Initial loss: {losses[0]:.6f}")
            lines.append(f"- Improvement: {(1 - losses[-1]/max(losses[0], 1e-8))*100:.1f}%")
        
        # Prediction
        metrics = report_data.get('metrics', {})
        if metrics:
            lines.append(f"\n## 🔮 Prediction Performance")
            lines.append(f"- MSE: {metrics.get('mse', 'N/A'):.4f}")
            lines.append(f"- RMSE: {metrics.get('rmse', 'N/A'):.4f}")
            lines.append(f"- Mean cosine similarity: {metrics.get('mean_cosine_sim', 'N/A'):.4f}")
            lines.append(f"- Direction accuracy: {metrics.get('direction_accuracy', 'N/A'):.2%}")
            
            lang_mse = metrics.get('per_language_mse', {})
            if lang_mse:
                lines.append("\n### Per-language Error")
                for lang, err in sorted(lang_mse.items(), key=lambda x: x[1]):
                    lines.append(f"- {lang}: {err:.4f}")
        
        # Alignment
        alignment = report_data.get('alignment_metrics', {})
        if alignment:
            lines.append(f"\n## 🔗 Cross-lingual Alignment")
            lines.append(f"- Mean pairwise similarity: {alignment.get('mean_pairwise_sim', 'N/A'):.4f}")
            lines.append(f"- Alignment stability: {alignment.get('std_pairwise_sim', 'N/A'):.4f}")
        
        # Interventions
        interventions = report_data.get('interventions', {})
        if interventions:
            lines.append(f"\n## 🔬 Causal Interventions")
            for name, mag in sorted(interventions.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- **{name}**: effect magnitude = {mag:.4f}")
        
        lines.append("\n---")
        lines.append(f"\n*Report generated by AcademicVisualizer*")
        
        report = "\n".join(lines)
        report_path = FIGS_DIR.parent / output_path
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"  [Report] Saved to {report_path}")
        return report


# ============================================================================
# Quick test
# ============================================================================

if __name__ == "__main__":
    # Test charts
    vis = AcademicVisualizer()
    
    # Loss curve
    losses = np.exp(-np.linspace(0, 3, 100)) + np.random.randn(100) * 0.05
    vis.plot_loss_curve(losses, "test_loss.pdf")
    
    # State trajectory
    gt = np.random.randn(9, 128)
    pred = gt + np.random.randn(9, 128) * 0.3
    vis.plot_state_trajectory(gt, pred, years=[2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026],
                              save_path="test_trajectory.pdf")
    
    # Alignment drift
    hist = {y: {'ZH-EN': np.random.randn()*0.1, 'ZH-AR': np.random.randn()*0.1, 'EN-AR': np.random.randn()*0.1}
            for y in range(2018, 2027)}
    vis.plot_alignment_drift(hist, "test_drift.pdf")
    
    print("[OK] AcademicVisualizer works")
