# -*- coding: utf-8 -*-
"""03_backtest.py — 实验1: 模型时间回测 (交付物 #4)
================================================
B0 持续性 / B1 XGBoost / B2 GRU / M RSSM
1年 / 3年 / 5年预测
指标: MAE, RMSE, Spearman, P@10, R@10, NDCG@10 (热度水平 + 增速两套)
多随机种子 → 均值±标准差 + 95%置信区间 (t 分布)
划分: 训练冻结<=2015; 验证目标年2016-2020; 测试目标年2021-2025
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import models as M  # noqa: E402

HORIZONS = [1, 3, 5]
K = 10


def build_model(name, seed):
    if name == "B0_last":
        return M.B0("last"), None
    if name == "B0_ma":
        return M.B0("ma"), None
    if name == "B0_linear":
        return M.B0("linear"), None
    if name == "B1":
        return M.B1(seed=seed), None
    if name == "B2":
        return M.B2GRU(seed=seed), None
    if name == "M":
        return M.load_rssm(C.RUN / f"model_rssm_frozen_s{seed}.pt"), None
    raise ValueError(name)


def compute_metrics(preds, raw, years, eval_year, h):
    """委托 common.compute_metrics (统一指标口径)"""
    return C.compute_metrics(preds, raw, years, eval_year, h, K)


def run(model_names, seeds_map, tag=""):
    sv = C.load_state_vectors()
    raw, enc, years = C.build_matrices(sv)
    results = {}          # (model, seed, h, eval) -> metrics
    predictions = {}      # 保存中间结果 (交付物: 中间结果)
    t0 = time.time()

    for name in model_names:
        for seed in seeds_map[name]:
            model, _ = build_model(name, seed)
            if hasattr(model, "fit"):
                print(f"[{tag}{name} seed={seed}] 训练...", flush=True)
                model.fit(raw, enc, years)
            for h in HORIZONS:
                for ey in C.eval_years_for(h):
                    preds = model.predict(raw, enc, years, ey, h)
                    predictions[f"{name}_s{seed}_h{h}_{ey}"] = {
                        t: [lv.tolist(), dt.tolist()] for t, (lv, dt) in preds.items()}
                    mtr = compute_metrics(preds, raw, years, ey, h)
                    if mtr:
                        results[(name, seed, h, ey)] = mtr
                    print(f"  [{tag}{name} s{seed} h={h} eval={ey}] "
                          f"n={mtr['n_topics'] if mtr else 0} "
                          f"MAE={mtr['level_MAE'] if mtr else '-'} "
                          f"ρl={mtr['level_Spearman'] if mtr else '-'}", flush=True)
            print(f"  [{tag}{name} s{seed}] 完成 ({time.time()-t0:.0f}s)", flush=True)

    # ---- 多种子聚合: 均值±std + 95%CI ----
    agg = {}
    for name in model_names:
        for h in HORIZONS:
            for split, tgt in (("val", C.VAL_YEARS), ("test", C.TEST_YEARS)):
                key = (name, h, split)
                per_seed = {}
                for seed in seeds_map[name]:
                    vals = [results[(name, seed, h, ey)]
                            for ey in C.eval_years_for(h)
                            if (name, seed, h, ey) in results and ey + h in tgt]
                    if vals:
                        per_seed[seed] = vals
                agg[key] = per_seed
    return results, agg, predictions, raw, enc, years


def summarize(agg, model_names):
    rows = []
    for name in model_names:
        for h in HORIZONS:
            for split in ("val", "test"):
                per_seed = agg.get((name, h, split), {})
                if not per_seed:
                    continue
                metrics = {}
                for mkey in ("level_MAE", "level_RMSE", "level_Spearman",
                             f"heat_P@{K}", f"heat_R@{K}", f"heat_NDCG@{K}",
                             "growth_Spearman", f"growth_P@{K}",
                             f"growth_R@{K}", f"growth_NDCG@{K}"):
                    vals = []
                    for seed, evals in per_seed.items():
                        for e in evals:
                            v = e.get(mkey)
                            if v is not None and v == v:
                                vals.append(v)
                    if vals:
                        mu, sd, ci = C.ci95(vals)
                        metrics[mkey] = {"mean": round(mu, 4),
                                         "std": round(sd, 4) if sd == sd else None,
                                         "ci95": [round(ci[0], 4), round(ci[1], 4)]}
                rows.append({"model": name, "horizon": h, "split": split,
                             "n_seeds": len(per_seed), "metrics": metrics})
    return rows


def fmt_table(rows):
    lines = []
    for r in rows:
        m = r["metrics"]
        def g(k):
            v = m.get(k, {})
            if not v:
                return "-"
            mu, sd, ci = v["mean"], v.get("std"), v.get("ci95")
            if sd is None:
                return f"{mu:.3f}"
            return f"{mu:.3f}±{sd:.3f}"
        lines.append(f"| {r['model']:<9} | {r['horizon']}年 | {r['split']:<4} | "
                     f"{g('level_MAE'):>14} | {g('level_Spearman'):>12} | "
                     f"{g('heat_P@10'):>10} | {g('heat_R@10'):>10} | "
                     f"{g('heat_NDCG@10'):>12} | {g('growth_P@10'):>12} | "
                     f"{g('growth_Spearman'):>12} |")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+",
                    default=["B0_last", "B0_ma", "B0_linear", "B1", "B2", "M"])
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    seeds_map = {
        "B0_last": [0], "B0_ma": [0], "B0_linear": [0],
        "B1": C.SEEDS_B1, "B2": C.SEEDS_B2, "M": C.SEEDS_M,
    }
    # 只跑指定模型
    seeds_map = {k: v for k, v in seeds_map.items() if k in args.models}

    results, agg, predictions, raw, enc, years = run(args.models, seeds_map, tag=args.tag)

    # 保存中间结果
    np.savez_compressed(str(C.OUT / "backtest" / f"predictions{args.tag}.npz"),
                        **{k: np.array(v, dtype=object) for k, v in predictions.items()})
    with open(C.OUT / "backtest" / f"results_raw{args.tag}.json", "w", encoding="utf-8") as f:
        json.dump({f"{k[0]}|{k[1]}|{k[2]}|{k[3]}": v for k, v in results.items()},
                  f, ensure_ascii=False, indent=1)

    rows = summarize(agg, args.models)
    with open(C.OUT / "backtest" / f"results_summary{args.tag}.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    print("\n" + "=" * 100)
    print("  实验1 汇总 (多种子均值±标准差, 95%CI 见 JSON)")
    print("=" * 100)
    print("| 模型 | 视野 | 划分 | level_MAE | level_ρ | heat_P@10 | heat_R@10 | heat_NDCG@10 | growth_P@10 | growth_ρ |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for l in fmt_table(rows):
        print(l)


if __name__ == "__main__":
    main()
