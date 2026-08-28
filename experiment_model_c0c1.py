#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
experiment_model_c0c1.py — 实验第三+四步：M0/M1/M2 × C0/C1 对照 + 分层统计
==============================================================================
拍板口径（2026-08-28）：
  - 数据：同一 12,233 版本生成的 C0（排除27条阿语）/ C1（包含27条阿语）状态向量
    （data/state_vectors_C0_20260827.json / data/state_vectors_C1_20260827.json，
     SHA 见 output/data_version_manifest_12233.json）
  - 模型：M0（last/移动平均/线性）、M1（XGBoost）、M2（RSSM 世界模型）
  - 相同时间划分：C0/C1 共用同一组评测年（horizon=1/3/5，各取最后 3 个可评测年）
  - 相同随机种子：SEED=42（numpy/torch/xgboost 全部固定）
  - 防泄漏：M1 每个评测年只用 ≤ 该年的数据重新训练；M2 用预训练 checkpoint 不训练

分层统计（第四步）：
  - 高频/低频主题：按评测年可见期内主题累计热度，中位数切分
  - 中文/英文/阿语主题：按 topic 字符串 Unicode 区间判定
  - 1/3/5 年预测：horizon 本身即分层

输出:
  output/experiment_model_c0c1/experiment_model_c0c1_results.json
  output/experiment_model_c0c1/experiment_model_c0c1_summary.md
"""
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from experiment_model_baseline import (
    M0Baseline, M1XGBoost, M2RSSM,
    build_topic_timeseries,
    compute_mae, compute_rmse, compute_spearman,
    compute_precision_at_k, compute_ndcg_at_k,
)

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output" / "experiment_model_c0c1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEED = 42
HORIZONS = [1, 3, 5]
TOP_K = 10
N_EVAL_YEARS = 3

DATASETS = {
    "C0_排除阿语": DATA_DIR / "state_vectors_C0_20260827.json",
    "C1_包含阿语": DATA_DIR / "state_vectors_C1_20260827.json",
}


def set_seed(seed: int = SEED):
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
    except ImportError:
        pass


def topic_language(topic: str) -> str:
    """按 Unicode 区间判定主题语言：阿语 > 中文 > 英文"""
    if re.search(r"[\u0600-\u06FF]", topic):
        return "ar"
    if re.search(r"[\u4e00-\u9fff]", topic):
        return "zh"
    return "en"


# ---------------------------------------------------------------------------
# M1 防泄漏版：每个评测年只用 cutoff 之前的数据训练
# ---------------------------------------------------------------------------
class M1XGBoostLeakFree(M1XGBoost):
    def train_until(self, all_series: dict, cutoff_year: int):
        """只用 target_year <= cutoff_year 的样本训练（防止看见未来）"""
        try:
            from xgboost import XGBRegressor
        except ImportError:
            self.fitted = False
            return
        X_all, y_all = [], []
        for topic, series in all_series.items():
            for i in range(5, len(series) - 1):
                if series[i + 1]["year"] > cutoff_year:
                    break  # series 按年升序，之后的目标年都超界
                feats = self._build_features(series, i)
                if feats is not None:
                    X_all.append(feats)
                    y_all.append(series[i + 1]["heat"])
        if len(X_all) < 50:
            self.fitted = False
            return
        X = np.array(X_all, dtype=np.float32)
        y = np.array(y_all, dtype=np.float32)
        self.model = XGBRegressor(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8,
            random_state=SEED, verbosity=0)
        self.model.fit(X, y)
        self.fitted = True
        self.lookback = 5


# ---------------------------------------------------------------------------
# 单数据集单 horizon 评测
# ---------------------------------------------------------------------------
def evaluate_one(all_ts, years, horizon, eval_years, top_k=TOP_K):
    """返回 (overall_metrics_per_model, per_topic_records)
    per_topic_records: list of dict(topic, model, horizon, eval_year, mae, rmse, spearman)
    """
    models_m0 = {
        "M0_last": M0Baseline("last"),
        "M0_ma": M0Baseline("moving_avg"),
        "M0_linear": M0Baseline("linear"),
    }
    m1_cache = {}   # cutoff_year -> trained model
    m2 = M2RSSM()
    m2.train(all_ts, years)

    model_names = ["M0_last", "M0_ma", "M0_linear", "M1_xgboost", "M2_rssm"]
    agg = {m: defaultdict(list) for m in model_names}   # metric -> [values]
    per_topic = []

    for eval_year in eval_years:
        # M1 按评测年防泄漏训练（同 cutoff 复用）
        if eval_year not in m1_cache:
            m1m = M1XGBoostLeakFree()
            m1m.train_until(all_ts, eval_year)
            m1_cache[eval_year] = m1m
        m1 = m1_cache[eval_year]

        pred_per_topic = {m: {} for m in model_names}
        actual_per_topic = {}

        for topic, series in all_ts.items():
            train_series = [s for s in series if s["year"] <= eval_year]
            actual_heats = []
            for hh in range(1, horizon + 1):
                fut = [s for s in series if s["year"] == eval_year + hh]
                actual_heats.append(fut[0]["heat"] if fut else 0)
            if not any(a > 0 for a in actual_heats):
                continue
            actual_per_topic[topic] = actual_heats
            for name, model in [("M1_xgboost", m1), ("M2_rssm", m2)]:
                pred_per_topic[name][topic] = (
                    model.predict(train_series, horizon, topic)
                    if name == "M2_rssm" else model.predict(train_series, horizon))
            for name, model in models_m0.items():
                pred_per_topic[name][topic] = model.predict(train_series, horizon)

        if not actual_per_topic:
            continue

        actual_ranking = sorted(actual_per_topic.keys(),
                                key=lambda t: sum(actual_per_topic[t]), reverse=True)
        for m in model_names:
            preds = pred_per_topic[m]
            pred_ranking = sorted(preds.keys(),
                                  key=lambda t: sum(preds[t]), reverse=True)
            agg[m]["P@K"].append(compute_precision_at_k(pred_ranking, actual_ranking, top_k))
            agg[m]["NDCG@K"].append(compute_ndcg_at_k(pred_ranking, actual_ranking, top_k))
            for topic, a in actual_per_topic.items():
                p = preds[topic]
                mae = compute_mae(p, a)
                rmse = compute_rmse(p, a)
                sp = compute_spearman(p, a)
                agg[m]["MAE"].append(mae)
                agg[m]["RMSE"].append(rmse)
                agg[m]["Spearman"].append(sp)
                per_topic.append({
                    "topic": topic, "model": m, "horizon": horizon,
                    "eval_year": eval_year, "mae": mae, "rmse": rmse, "spearman": sp,
                    "pred_sum": float(sum(p)), "actual_sum": float(sum(a)),
                })

    overall = {}
    for m in model_names:
        overall[m] = {
            "MAE": round(float(np.mean(agg[m]["MAE"])), 4) if agg[m]["MAE"] else None,
            "RMSE": round(float(np.mean(agg[m]["RMSE"])), 4) if agg[m]["RMSE"] else None,
            "Spearman": round(float(np.mean(agg[m]["Spearman"])), 4) if agg[m]["Spearman"] else None,
            f"Precision@{top_k}": round(float(np.mean(agg[m]["P@K"])), 4) if agg[m]["P@K"] else None,
            f"NDCG@{top_k}": round(float(np.mean(agg[m]["NDCG@K"])), 4) if agg[m]["NDCG@K"] else None,
            "n_topic_evals": len(agg[m]["MAE"]),
        }
    return overall, per_topic


# ---------------------------------------------------------------------------
# 分层统计
# ---------------------------------------------------------------------------
def stratify(per_topic, all_ts, years):
    """按 频率层 × 语言层 聚合 per-topic 指标"""
    # 主题累计热度（全期可见，用于频率分层；按 eval_year 截断在 evaluate 内做会更严，
    # 此处为分层稳定性用全期，仅作分组不进入模型）
    total_heat = {t: sum(s["heat"] for s in series) for t, series in all_ts.items()}
    heats = np.array(sorted(total_heat.values()))
    median_heat = float(np.median(heats)) if len(heats) else 0.0

    def tier(t):
        return "high_freq" if total_heat.get(t, 0) >= median_heat else "low_freq"

    strata = defaultdict(list)   # (stratum_type, stratum_key, model, horizon) -> [records]
    for r in per_topic:
        t = r["topic"]
        for stype, skey in [("freq_tier", tier(t)), ("language", topic_language(t))]:
            strata[(stype, skey, r["model"], r["horizon"])].append(r)

    rows = []
    for (stype, skey, model, horizon), recs in sorted(strata.items()):
        rows.append({
            "stratum_type": stype,
            "stratum": skey,
            "model": model,
            "horizon": horizon,
            "n_topic_evals": len(recs),
            "n_topics": len({r["topic"] for r in recs}),
            "MAE": round(float(np.mean([r["mae"] for r in recs])), 4),
            "RMSE": round(float(np.mean([r["rmse"] for r in recs])), 4),
            "Spearman": round(float(np.mean([r["spearman"] for r in recs])), 4),
        })
    return rows, {"median_total_heat": median_heat}


# ---------------------------------------------------------------------------
def main():
    set_seed(SEED)
    print("=" * 70)
    print("  实验三+四步：M0/M1/M2 × C0/C1 对照（相同时间划分/随机种子）+ 分层统计")
    print("=" * 70)
    print(f"  SEED={SEED} | horizons={HORIZONS} | top_k={TOP_K} | eval_years/horizon={N_EVAL_YEARS}")

    # 先确定统一时间划分（C0/C1 年份范围一致 1912-2026，用 C1 计算一次，两边共用）
    sv_first = json.loads(DATASETS["C1_包含阿语"].read_text(encoding="utf-8"))
    _, years_ref = build_topic_timeseries(sv_first)
    del sv_first
    eval_plan = {}
    for h in HORIZONS:
        max_eval = years_ref[-1] - h
        cand = [y for y in years_ref if y <= max_eval and y >= years_ref[0] + 6]
        eval_plan[h] = cand[-N_EVAL_YEARS:] if len(cand) >= N_EVAL_YEARS else cand
    print(f"  统一评测年: {eval_plan}")

    all_results = {}
    for ds_name, sv_path in DATASETS.items():
        print(f"\n{'='*70}\n  数据集: {ds_name} ({sv_path.name})\n{'='*70}")
        sv = json.loads(sv_path.read_text(encoding="utf-8"))
        all_ts, years = build_topic_timeseries(sv)
        print(f"  {len(all_ts)} 主题, {years[0]}-{years[-1]} ({len(years)}年)")
        assert years == years_ref, "C0/C1 年份轴不一致，无法共用时间划分！"

        ds_results = {"n_topics": len(all_ts), "horizons": {}}
        all_per_topic = []
        for h in HORIZONS:
            ey = eval_plan[h]
            print(f"\n  [horizon={h}] 评测年={ey}")
            set_seed(SEED)   # 每个 horizon 重置种子，保证 C0/C1 完全同种子
            overall, per_topic = evaluate_one(all_ts, years, h, ey)
            ds_results["horizons"][str(h)] = {"eval_years": ey, "overall": overall}
            all_per_topic.extend(per_topic)
            for m, v in overall.items():
                print(f"    {m:<10s} MAE={v['MAE']!s:>10s} RMSE={v['RMSE']!s:>10s} "
                      f"Sp={v['Spearman']!s:>8s} P@{TOP_K}={v[f'Precision@{TOP_K}']!s:>8s} "
                      f"NDCG@{TOP_K}={v[f'NDCG@{TOP_K}']!s:>8s}")

        print(f"\n  [分层统计] {ds_name} ...")
        strata_rows, tier_info = stratify(all_per_topic, all_ts, years)
        ds_results["strata"] = strata_rows
        ds_results["tier_info"] = tier_info
        all_results[ds_name] = ds_results

    # ---------------- 汇总输出 ----------------
    out = {
        "meta": {
            "date": "2026-08-28",
            "seed": SEED,
            "horizons": HORIZONS,
            "top_k": TOP_K,
            "eval_plan": {str(k): v for k, v in eval_plan.items()},
            "datasets": {k: str(v) for k, v in DATASETS.items()},
            "data_manifest": "output/data_version_manifest_12233.json",
            "leak_control": "M1 每个评测年仅用 ≤ 该年样本重训；M2 预训练 checkpoint；M0 无训练",
            "tier_rule": "主题全期累计热度中位数切分 high/low",
            "language_rule": "topic 字符串含阿语Unicode→ar，含CJK→zh，否则 en",
        },
        "results": all_results,
    }
    res_path = OUT_DIR / "experiment_model_c0c1_results.json"
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 结果 JSON: {res_path}")

    # ---------------- Markdown 摘要 ----------------
    lines = ["# M0/M1/M2 × C0/C1 对照实验摘要", "",
             f"- 日期: 2026-08-28 | SEED={SEED} | 统一评测年: {eval_plan}",
             f"- C0=排除27条阿语(12,206篇) | C1=包含27条阿语(12,233篇)",
             f"- 数据基线 SHA: 见 output/data_version_manifest_12233.json", ""]
    for ds_name, ds in all_results.items():
        lines.append(f"\n## {ds_name}（{ds['n_topics']} 主题）")
        for h in HORIZONS:
            ov = ds["horizons"][str(h)]["overall"]
            lines.append(f"\n### horizon={h} 评测年={ds['horizons'][str(h)]['eval_years']}")
            lines.append("| 模型 | MAE | RMSE | Spearman | P@10 | NDCG@10 |")
            lines.append("|---|---|---|---|---|---|")
            for m, v in ov.items():
                lines.append(f"| {m} | {v['MAE']} | {v['RMSE']} | {v['Spearman']} "
                             f"| {v[f'Precision@{TOP_K}']} | {v[f'NDCG@{TOP_K}']} |")
        lines.append(f"\n### 分层（频率层中位数={ds['tier_info']['median_total_heat']:.1f}）")
        lines.append("| 层 | 模型 | horizon | n主题 | MAE | RMSE | Spearman |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in ds["strata"]:
            lines.append(f"| {r['stratum_type']}={r['stratum']} | {r['model']} | {r['horizon']} "
                         f"| {r['n_topics']} | {r['MAE']} | {r['RMSE']} | {r['Spearman']} |")
    md_path = OUT_DIR / "experiment_model_c0c1_summary.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] 摘要 MD: {md_path}")


if __name__ == "__main__":
    main()
