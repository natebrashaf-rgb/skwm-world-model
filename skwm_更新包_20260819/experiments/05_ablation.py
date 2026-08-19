# -*- coding: utf-8 -*-
"""05_ablation.py — 实验3: RSSM 消融 (交付物 #6)
================================================
A_full    : 完整 RSSM (model_rssm_frozen_s42.pt)
B_nostoch : stoch_std=0, 先验/后验退化为确定性潜状态 (model_rssm_ablation_nostoch.pt)
C_nodyn   : 前馈 MLP 窗口回归 (无循环动态状态转移)
D_gru     : 普通 GRU (即实验1 B2)

检验: ①RSSM vs 普通深度模型 ②随机潜状态贡献 ③动态转移贡献
      ④增量出现的视野 ⑤有效/失效主题类型 (与实验4分层联动)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import models as M  # noqa: E402

HORIZONS = [1, 3, 5]
K = 10


def run_variant(name, model, seed):
    sv = C.load_state_vectors()
    raw, enc, years = C.build_matrices(sv)
    if hasattr(model, "fit"):
        model.fit(raw, enc, years)
    rows = []
    for h in HORIZONS:
        for ey in C.eval_years_for(h):
            preds = model.predict(raw, enc, years, ey, h)
            mtr = C.compute_metrics(preds, raw, years, ey, h, K)
            if mtr:
                rows.append({"horizon": h, "eval_year": ey, **mtr})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+",
                    default=["A_full", "B_nostoch", "C_nodyn", "D_gru"])
    ap.add_argument("--train-nostoch", action="store_true",
                    help="训练 B_nostoch 变体 (需模型文件不存在时)")
    args = ap.parse_args()

    sv = C.load_state_vectors()
    raw, enc, years = C.build_matrices(sv)

    results = {}
    for v in args.variants:
        if v == "A_full":
            model = M.load_rssm(C.RUN / "model_rssm_frozen_s42.pt")
        elif v == "B_nostoch":
            model = M.load_rssm(C.RUN / "model_rssm_ablation_nostoch.pt")
        elif v == "C_nodyn":
            model = M.C_MLP(seed=42)
        elif v == "D_gru":
            model = M.B2GRU(seed=42)
        else:
            raise ValueError(v)
        print(f"[{v}] 评估中...", flush=True)
        results[v] = run_variant(v, model, 42)

    # 汇总表
    print("=" * 96)
    print("  实验3: RSSM 消融 (训练冻结<=2015, 验证+测试目标年均值)")
    print("=" * 96)
    print("| 变体 | 视野 | MAE | RMSE | level_ρ | heat_P@10 | heat_NDCG | growth_P@10 | growth_ρ |")
    print("|---|---|---|---|---|---|---|---|---|")
    summ = {}
    for v, rows in results.items():
        for h in HORIZONS:
            rs = [r for r in rows if r["horizon"] == h]
            if not rs:
                continue
            def m(kk):
                vals = [r[kk] for r in rs if r.get(kk) is not None]
                return round(float(np.mean(vals)), 4) if vals else None
            summ[f"{v}|{h}"] = {kk: m(kk) for kk in
                                ("level_MAE", "level_RMSE", "level_Spearman",
                                 f"heat_P@{K}", f"heat_NDCG@{K}",
                                 f"growth_P@{K}", "growth_Spearman")}
            print(f"| {v:<9} | {h}年 | {m('level_MAE'):>8} | {m('level_RMSE'):>7} | "
                  f"{m('level_Spearman'):>8} | {m(f'heat_P@{K}'):>9} | "
                  f"{m(f'heat_NDCG@{K}'):>10} | {m(f'growth_P@{K}'):>11} | "
                  f"{m('growth_Spearman'):>9} |")

    # 增量分析: A vs B (随机贡献), A vs C (动态贡献), A vs D (RSSM vs GRU)
    print("\n  增量分析 (A_full 减去对照):")
    def diff(v1, v2, kk, h):
        a, b = summ.get(f"{v1}|{h}", {}).get(kk), summ.get(f"{v2}|{h}", {}).get(kk)
        return None if a is None or b is None else round(a - b, 4)
    for h in HORIZONS:
        print(f"  h={h}年: 随机潜状态贡献 ΔMAE(A−B)={diff('A_full','B_nostoch','level_MAE',h)}, "
              f"动态转移贡献 ΔMAE(A−C)={diff('A_full','C_nodyn','level_MAE',h)}, "
              f"RSSM vs GRU ΔMAE(A−D)={diff('A_full','D_gru','level_MAE',h)}, "
              f"Δgrowth_P@10(A−D)={diff('A_full','D_gru','growth_P@10',h)}")

    out = {"summary": summ, "per_eval_year": results}
    (C.OUT / "ablation" / "ablation_results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[OK] 结果: {C.OUT / 'ablation' / 'ablation_results.json'}")


if __name__ == "__main__":
    main()
