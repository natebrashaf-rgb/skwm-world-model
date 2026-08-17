#!/usr/bin/env python3
"""
experiment_model_baseline.py — 实验一：模型预测增量
====================================================
M0: 上一年延续 / 移动平均 / 线性趋势
M1: XGBoost 或普通时序模型
M2: RSSM (世界模型内核)

比较 1/3/5 年预测
指标: MAE, RMSE, Spearman, Precision@K, NDCG@K

用法:
    python experiment_model_baseline.py
    python experiment_model_baseline.py --horizons 1 3 5
    python experiment_model_baseline.py --top-k 10
"""
import json
import os
import sys
import time
import argparse
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output" / "experiment_model"
OUT_DIR.mkdir(parents=True, exist_ok=True)

warnings.filterwarnings("ignore")


def load_state_vectors():
    path = DATA_DIR / "state_vectors.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_topic_timeseries(sv: dict) -> dict:
    years = sorted(
        int(k) for k in sv.keys()
        if k != "_wm" and isinstance(sv[k], dict)
    )
    if not years:
        return {}, []

    all_topics = set()
    for y in years:
        all_topics.update(sv[str(y)].keys())

    ts = {}
    for topic in all_topics:
        series = []
        for y in years:
            vec = sv[str(y)].get(topic, [0, 0, 0, 0])
            if isinstance(vec, (list, tuple)) and len(vec) >= 4:
                series.append({
                    "year": y,
                    "heat": vec[0],
                    "growth": vec[1],
                    "centrality": vec[2],
                    "connections": vec[3],
                })
            else:
                series.append({
                    "year": y, "heat": 0, "growth": 0,
                    "centrality": 0, "connections": 0,
                })
        ts[topic] = series

    return ts, years


# ============================================================
# M0: 朴素基线
# ============================================================

class M0Baseline:
    """上一年延续 / 移动平均 / 线性趋势"""

    def __init__(self, method: str = "linear"):
        self.method = method

    def predict(self, series: list, horizon: int) -> list:
        if not series:
            return [0.0] * horizon

        heats = np.array([s["heat"] for s in series], dtype=float)

        if self.method == "last":
            last_val = heats[-1]
            return [float(last_val)] * horizon

        elif self.method == "moving_avg":
            window = min(3, len(heats))
            avg = np.mean(heats[-window:])
            return [float(avg)] * horizon

        elif self.method == "linear":
            if len(heats) < 2:
                return [float(heats[-1])] * horizon
            x = np.arange(len(heats), dtype=float)
            slope = np.polyfit(x, heats, 1)[0]
            predictions = []
            last = heats[-1]
            for h in range(1, horizon + 1):
                predictions.append(float(max(0, last + slope * h)))
            return predictions

        return [0.0] * horizon


# ============================================================
# M1: XGBoost 时序预测
# ============================================================

class M1XGBoost:
    """XGBoost 多步预测"""

    def __init__(self):
        self.models = {}
        self.fitted = False

    def _build_features(self, series: list, idx: int, lookback: int = 5):
        if idx < lookback:
            return None
        feats = []
        for i in range(idx - lookback, idx):
            feats.extend([
                series[i]["heat"],
                series[i]["growth"],
                series[i]["centrality"],
                series[i]["connections"],
            ])
        feats.append(idx)
        return feats

    def train(self, all_series: dict, years: list):
        try:
            from xgboost import XGBRegressor
        except ImportError:
            print("  [!] xgboost 未安装，M1 降级为线性回归")
            self.fitted = False
            return

        X_all, y_all = [], []
        for topic, series in all_series.items():
            for i in range(5, len(series) - 1):
                feats = self._build_features(series, i)
                if feats is not None:
                    X_all.append(feats)
                    y_all.append(series[i + 1]["heat"])

        if len(X_all) < 50:
            print(f"  [!] 训练样本不足 ({len(X_all)})，M1 降级")
            self.fitted = False
            return

        X = np.array(X_all, dtype=np.float32)
        y = np.array(y_all, dtype=np.float32)

        self.model = XGBRegressor(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbosity=0
        )
        self.model.fit(X, y)
        self.fitted = True
        self.lookback = 5

    def predict(self, series: list, horizon: int) -> list:
        if not self.fitted:
            fallback = M0Baseline("linear")
            return fallback.predict(series, horizon)

        predictions = []
        current_series = list(series)
        for h in range(horizon):
            feats = self._build_features(current_series, len(current_series) - 1)
            if feats is None:
                predictions.append(current_series[-1]["heat"])
                continue
            X = np.array([feats], dtype=np.float32)
            pred = float(self.model.predict(X)[0])
            pred = max(0, pred)
            predictions.append(pred)
            next_entry = dict(current_series[-1])
            next_entry["heat"] = pred
            next_entry["year"] = current_series[-1]["year"] + 1
            current_series.append(next_entry)

        return predictions


# ============================================================
# M2: RSSM (世界模型内核)
# ============================================================

class M2RSSM:
    """RSSM 多步预测"""

    def __init__(self):
        self.model = None
        self.fitted = False

    def train(self, all_series: dict, years: list):
        model_path = BASE / "model_rssm.pt"
        if model_path.exists():
            try:
                import torch
                from skwm_world_model import WorldModel
                self.model = WorldModel.load(str(model_path))
                self.model.eval()
                self.fitted = True
                print(f"  [OK] RSSM 模型已加载: {model_path}")
            except Exception as e:
                print(f"  [!] RSSM 加载失败: {e}，M2 降级为 M0")
                self.fitted = False
        else:
            print(f"  [!] model_rssm.pt 不存在，M2 降级为 M0")
            self.fitted = False

    def predict(self, series: list, horizon: int, topic_name: str = "") -> list:
        if not self.fitted:
            fallback = M0Baseline("linear")
            return fallback.predict(series, horizon)

        import torch
        from skwm_world_model import WMConfig

        c = WMConfig(x_dim=4, a_dim=4, deter=128, stoch=32, hidden=128)
        if hasattr(self.model, 'c'):
            c = self.model.c

        if len(series) < 8:
            fallback = M0Baseline("linear")
            return fallback.predict(series, horizon)

        recent = series[-8:]
        vecs = []
        for s in recent:
            v = np.array([
                np.log1p(s["heat"]),
                s["growth"],
                np.log1p(s["centrality"]),
                np.log1p(s["connections"]),
            ], dtype=np.float32)
            vecs.append(v)

        x_seq = torch.tensor(np.stack(vecs), dtype=torch.float32).unsqueeze(0)
        x0 = x_seq[:, -1, :]
        a_future = torch.zeros(1, horizon, c.a_dim)

        try:
            with torch.no_grad():
                pred = self.model.imagine(x0, a_future)
            pred_np = pred[0].numpy()
            predictions = []
            for t in range(horizon):
                heat_pred = float(np.expm1(pred_np[t, 0]))
                predictions.append(max(0, heat_pred))
            return predictions
        except Exception:
            fallback = M0Baseline("linear")
            return fallback.predict(series, horizon)


# ============================================================
# 评测指标
# ============================================================

def compute_mae(preds: list, actuals: list) -> float:
    if not preds or not actuals:
        return float("inf")
    n = min(len(preds), len(actuals))
    return float(np.mean([abs(preds[i] - actuals[i]) for i in range(n)]))


def compute_rmse(preds: list, actuals: list) -> float:
    if not preds or not actuals:
        return float("inf")
    n = min(len(preds), len(actuals))
    return float(np.sqrt(np.mean([(preds[i] - actuals[i]) ** 2 for i in range(n)])))


def compute_spearman(preds: list, actuals: list) -> float:
    try:
        from scipy.stats import spearmanr
    except ImportError:
        return 0.0
    if len(preds) < 3 or len(actuals) < 3:
        return 0.0
    n = min(len(preds), len(actuals))
    rho, _ = spearmanr(preds[:n], actuals[:n])
    return float(rho) if not np.isnan(rho) else 0.0


def compute_precision_at_k(pred_topics: list, actual_topics: list, k: int) -> float:
    if not pred_topics or not actual_topics:
        return 0.0
    pred_top = set(pred_topics[:k])
    actual_top = set(actual_topics[:k])
    if not pred_top:
        return 0.0
    return len(pred_top & actual_top) / k


def compute_ndcg_at_k(pred_topics: list, actual_topics: list, k: int) -> float:
    if not pred_topics or not actual_topics:
        return 0.0
    actual_rank = {t: i for i, t in enumerate(actual_topics[:k])}
    dcg = 0.0
    for i, t in enumerate(pred_topics[:k]):
        if t in actual_rank:
            dcg += 1.0 / np.log2(i + 2)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(k, len(actual_topics))))
    return dcg / max(idcg, 1e-10)


# ============================================================
# 主实验
# ============================================================

def run_experiment(horizons: list, top_k: int):
    print("=" * 60)
    print("  实验一：模型预测增量 (M0 vs M1 vs M2)")
    print("=" * 60)

    sv = load_state_vectors()
    if not sv:
        print("[!] state_vectors.json 不存在")
        return {}

    all_ts, years = build_topic_timeseries(sv)
    if not all_ts or len(years) < 10:
        print(f"[!] 数据不足: {len(all_ts)} 主题, {len(years)} 年")
        return {}

    print(f"\n[数据] {len(all_ts)} 主题, {years[0]}-{years[-1]} ({len(years)}年)")

    eval_years = []
    for h in horizons:
        max_eval = years[-1] - h
        candidates = [y for y in years if y <= max_eval and y >= years[0] + 6]
        eval_years.append((h, candidates[-3:] if len(candidates) >= 3 else candidates))

    print(f"[评测年] {eval_years}")

    m0_last = M0Baseline("last")
    m0_ma = M0Baseline("moving_avg")
    m0_lin = M0Baseline("linear")
    m1 = M1XGBoost()
    m2 = M2RSSM()

    print("\n[训练] M1 (XGBoost)...")
    m1.train(all_ts, years)
    print("[训练] M2 (RSSM)...")
    m2.train(all_ts, years)

    models = {
        "M0_last": m0_last,
        "M0_ma": m0_ma,
        "M0_linear": m0_lin,
        "M1_xgboost": m1,
        "M2_rssm": m2,
    }

    results = {}
    for h, ey in eval_years:
        print(f"\n[预测] horizon={h}年, 评测年={ey}")
        for model_name, model in models.items():
            mae_list, rmse_list, spear_list = [], [], []
            prec_list, ndcg_list = [], []

            for eval_year in ey:
                eval_idx = years.index(eval_year) if eval_year in years else -1
                if eval_idx < 0:
                    continue

                pred_per_topic = {}
                actual_per_topic = {}

                for topic, series in all_ts.items():
                    train_series = [s for s in series if s["year"] <= eval_year]
                    actual_heats = []
                    for hh in range(1, h + 1):
                        target_year = eval_year + hh
                        future = [s for s in series if s["year"] == target_year]
                        if future:
                            actual_heats.append(future[0]["heat"])
                        else:
                            actual_heats.append(0)

                    if not any(a > 0 for a in actual_heats):
                        continue

                    if isinstance(model, M2RSSM):
                        preds = model.predict(train_series, h, topic)
                    elif isinstance(model, M1XGBoost):
                        preds = model.predict(train_series, h)
                    else:
                        preds = model.predict(train_series, h)

                    pred_per_topic[topic] = preds
                    actual_per_topic[topic] = actual_heats

                if not pred_per_topic:
                    continue

                for topic in pred_per_topic:
                    p = pred_per_topic[topic]
                    a = actual_per_topic[topic]
                    mae_list.append(compute_mae(p, a))
                    rmse_list.append(compute_rmse(p, a))
                    spear_list.append(compute_spearman(p, a))

                pred_ranking = sorted(
                    pred_per_topic.keys(),
                    key=lambda t: sum(pred_per_topic[t]), reverse=True
                )
                actual_ranking = sorted(
                    actual_per_topic.keys(),
                    key=lambda t: sum(actual_per_topic[t]), reverse=True
                )
                prec_list.append(compute_precision_at_k(pred_ranking, actual_ranking, top_k))
                ndcg_list.append(compute_ndcg_at_k(pred_ranking, actual_ranking, top_k))

            key = f"h{h}_{eval_year}" if len(ey) == 1 else f"h{h}"
            results[f"{model_name}_{key}"] = {
                "model": model_name,
                "horizon": h,
                "eval_years": ey,
                "MAE": round(float(np.mean(mae_list)), 4) if mae_list else None,
                "RMSE": round(float(np.mean(rmse_list)), 4) if rmse_list else None,
                "Spearman": round(float(np.mean(spear_list)), 4) if spear_list else None,
                f"Precision@{top_k}": round(float(np.mean(prec_list)), 4) if prec_list else None,
                f"NDCG@{top_k}": round(float(np.mean(ndcg_list)), 4) if ndcg_list else None,
                "n_topics_evaluated": len(pred_per_topic) if pred_per_topic else 0,
            }

    print("\n" + "=" * 60)
    print("  实验一结果汇总")
    print("=" * 60)

    summary = defaultdict(dict)
    for key, vals in results.items():
        model = vals["model"]
        h = vals["horizon"]
        summary[h][model] = {
            "MAE": vals["MAE"],
            "RMSE": vals["RMSE"],
            "Spearman": vals["Spearman"],
            f"Precision@{top_k}": vals.get(f"Precision@{top_k}"),
            f"NDCG@{top_k}": vals.get(f"NDCG@{top_k}"),
        }

    for h in sorted(summary.keys()):
        print(f"\n  ── Horizon = {h}年 ──")
        print(f"  {'模型':<15s} {'MAE':>8s} {'RMSE':>8s} {'Spearman':>10s} "
              f"{'Prec@'+str(top_k):>10s} {'NDCG@'+str(top_k):>10s}")
        for model in ["M0_last", "M0_ma", "M0_linear", "M1_xgboost", "M2_rssm"]:
            if model in summary[h]:
                v = summary[h][model]
                mae_s = f"{v['MAE']:.2f}" if v['MAE'] is not None else "N/A"
                rmse_s = f"{v['RMSE']:.2f}" if v['RMSE'] is not None else "N/A"
                sp_s = f"{v['Spearman']:.4f}" if v['Spearman'] is not None else "N/A"
                pr_s = f"{v.get(f'Precision@{top_k}', 0):.4f}" if v.get(f'Precision@{top_k}') is not None else "N/A"
                nd_s = f"{v.get(f'NDCG@{top_k}', 0):.4f}" if v.get(f'NDCG@{top_k}') is not None else "N/A"
                print(f"  {model:<15s} {mae_s:>8s} {rmse_s:>8s} {sp_s:>10s} {pr_s:>10s} {nd_s:>10s}")

    report_path = OUT_DIR / "experiment_model_results.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "summary": dict(summary),
                   "config": {"horizons": horizons, "top_k": top_k,
                              "years": years, "n_topics": len(all_ts)}},
                  f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 结果已保存: {report_path}")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizons", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    run_experiment(horizons=args.horizons, top_k=args.top_k)


if __name__ == "__main__":
    main()
