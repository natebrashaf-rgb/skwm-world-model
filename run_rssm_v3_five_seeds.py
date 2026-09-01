"""Run reproducible RSSM V3 experiments on the repository's real state vectors."""
import argparse
import importlib.util
import json
import os
import random
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr, t

SEEDS = [42, 123, 2026, 3407, 7777]
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "rssm_training_v3" / "five_seeds"

spec = importlib.util.spec_from_file_location("train_rssm_v3", ROOT / "train_rssm_v3.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(False)


def ndcg10(pred, actual, k=10):
    k = min(k, len(pred))
    order = np.argsort(-pred)[:k]
    gains = actual[order]
    discounts = np.log2(np.arange(2, k + 2))
    dcg = np.sum(gains / discounts)
    ideal = np.sort(actual)[::-1][:k]
    idcg = np.sum(ideal / discounts)
    return float(dcg / idcg) if idcg > 0 else 0.0


def rank_metrics(pred_growth, actual_growth, k=10):
    k = min(k, len(pred_growth))
    pred_order = np.argsort(-pred_growth)[:k]
    actual_order = np.argsort(-actual_growth)[:k]
    pred_set, actual_set = set(pred_order), set(actual_order)
    hit = len(pred_set & actual_set)
    rho = spearmanr(pred_growth, actual_growth).statistic
    return {
        "spearman": float(0.0 if not np.isfinite(rho) else rho),
        "p_at_10": float(hit / k) if k else 0.0,
        "recall_at_10": float(hit / k) if k else 0.0,
        "ndcg_at_10": ndcg10(pred_growth, actual_growth, k),
    }


def heat(kwm, topic, year):
    return float(kwm.get_state(year).vec[topic][0])


def evaluate(models, kwm, years, horizons=(1, 3, 5)):
    rows, aggregate = [], {}
    for h in horizons:
        eval_years = [y for y in years if y + h <= years[-1] and y >= years[0] + 8][-5:]
        per_year = []
        for ey in eval_years:
            preds, actuals, pred_growth, actual_growth, uncert = [], [], [], [], []
            for topic in kwm.topics:
                current = heat(kwm, topic, ey)
                x0 = torch.tensor(np.asarray([mod.encode_state(kwm.get_state(ey).vec[topic])]), dtype=torch.float32)
                actions = torch.zeros(1, h, 4)
                seed_preds = []
                with torch.no_grad():
                    for model in models:
                        # Stochastic prior rollout is intentional: uncertainty is estimated from samples.
                        z = model.imagine(x0, actions)[0, -1].numpy()
                        seed_preds.append(float(mod.decode_state(z)[0]))
                pred = float(np.mean(seed_preds))
                actual = heat(kwm, topic, ey + h)
                preds.append(pred)
                actuals.append(actual)
                pred_growth.append(pred - current)
                actual_growth.append(actual - current)
                uncert.append(float(np.std(seed_preds)))
            preds, actuals = np.asarray(preds), np.asarray(actuals)
            pred_growth, actual_growth = np.asarray(pred_growth), np.asarray(actual_growth)
            metrics = rank_metrics(pred_growth, actual_growth)
            metrics.update({
                "seed": None, "horizon": h, "eval_year": ey,
                "mae": float(np.mean(np.abs(preds - actuals))),
                "rmse": float(np.sqrt(np.mean((preds - actuals) ** 2))),
                "uncertainty": float(np.mean(uncert)),
                "n_topics": len(kwm.topics),
            })
            per_year.append(metrics)
            rows.append(metrics)
        aggregate[f"h{h}"] = {
            key: float(np.mean([r[key] for r in per_year]))
            for key in ("mae", "rmse", "spearman", "p_at_10", "recall_at_10", "ndcg_at_10", "uncertainty")
        }
        aggregate[f"h{h}"]["eval_years"] = eval_years
    return rows, aggregate


def train_one(seed, x_data, config, steps, batch):
    set_seed(seed)
    model = mod.ImprovedWorldModel(config)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr, weight_decay=1e-5)
    losses = []
    best = float("inf")
    finite = True
    for step in range(steps):
        idx = np.random.choice(len(x_data), min(batch, len(x_data)), replace=False)
        xb = torch.tensor(x_data[idx], dtype=torch.float32)
        ab = torch.zeros(xb.shape[0], xb.shape[1], config.a_dim)
        logs = mod.train_step_v3(model, optimizer, xb, ab, kl_weight=0.1 if step < steps // 2 else 0.5)
        if not np.all(np.isfinite(list(logs.values()))):
            finite = False
            raise FloatingPointError(f"non-finite training log at step {step}: {logs}")
        losses.append({"step": step, **logs})
        best = min(best, logs["loss"])
    summary = {
        "seed": seed,
        "steps_completed": steps,
        "finite": finite,
        "initial_loss": losses[0]["loss"],
        "final_loss": losses[-1]["loss"],
        "best_loss": best,
        "loss_reduction": losses[0]["loss"] - losses[-1]["loss"],
        "train_log": losses,
    }
    return model, summary


def ci(values):
    values = np.asarray(values, dtype=float)
    mean, sd = float(np.mean(values)), float(np.std(values, ddof=1))
    half = float(t.ppf(0.975, len(values) - 1) * sd / np.sqrt(len(values))) if len(values) > 1 else 0.0
    return {"mean": mean, "std": sd, "ci95_low": mean - half, "ci95_high": mean + half}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=1200)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    kwm = mod.load_real_data()
    years = list(range(1995, 2025))
    train_years = [y for y in years if y < 2020]
    x_data, topics, counts = mod.build_sequences_v3(kwm, train_years, T=8, target_topics=set())
    config = mod.WMConfig(x_dim=4, a_dim=4, deter=128, stoch=32, hidden=128, lr=1e-4)
    metadata = {
        "data_source": "data/state_vectors.json + data/B1_文献主表.json via BridgeKnowledgeWorldModel",
        "real_data": True, "years": years, "train_years": train_years,
        "split_year": 2020, "n_topics": len(topics), "n_sequences": int(len(x_data)),
        "T": 8, "steps": args.steps, "batch": args.batch, "seeds": args.seeds,
        "model": "ImprovedWorldModel (repository train_rssm_v3.py)",
    }
    (OUT / "experiment_config.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    all_seed_agg, all_rows, stability = [], [], []
    for seed in args.seeds:
        print(f"[seed {seed}] training on {len(x_data)} real-data sequences...")
        model, train_summary = train_one(seed, x_data, config, args.steps, args.batch)
        rows, agg = evaluate([model], kwm, years)
        for r in rows:
            r["seed"] = seed
        model_path = OUT / f"model_seed_{seed}.pt"
        torch.save({"model": model.state_dict(), "config": config.__dict__, "meta": metadata | {"seed": seed}}, model_path)
        (OUT / f"training_log_seed_{seed}.json").write_text(json.dumps(train_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUT / f"predictions_seed_{seed}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        all_seed_agg.append({"seed": seed, **{h: vals for h, vals in agg.items()}})
        all_rows.extend(rows)
        stability.append({k: train_summary[k] for k in ("seed", "steps_completed", "finite", "initial_loss", "final_loss", "best_loss", "loss_reduction")})
        print(f"[seed {seed}] final_loss={train_summary['final_loss']:.4f}; h1_mae={agg['h1']['mae']:.4f}")
    summary = {"metadata": metadata, "seed_results": all_seed_agg, "training_stability": stability, "metrics": {}}
    for h in (1, 3, 5):
        key = f"h{h}"
        summary["metrics"][key] = {}
        for metric in ("mae", "rmse", "spearman", "p_at_10", "recall_at_10", "ndcg_at_10", "uncertainty"):
            vals = [r[key][metric] for r in all_seed_agg]
            summary["metrics"][key][metric] = ci(vals)
        summary["metrics"][key]["best_seed"] = min(all_seed_agg, key=lambda x: x[key]["mae"])["seed"]
        summary["metrics"][key]["worst_seed"] = max(all_seed_agg, key=lambda x: x[key]["mae"])["seed"]
    (OUT / "all_predictions.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "five_seed_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary["metrics"], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
