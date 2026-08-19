# -*- coding: utf-8 -*-
"""06_robustness.py — 实验4: 适用边界与稳健性 (交付物 #7)
========================================================
按主题/时期子集切片报告: 语言 / 频率 / 密度 / 成熟度 / 跨领域 / 稳定vs事件期 / 视野
子集划分全部只用 <= 评测年的信息 (无未来泄漏)
输出: output/robustness/robustness_results.json + md 表
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

K = 10


def slice_topics(raw, eval_year, meta):
    """动态分层: 返回 {slice_name: [topics]} (只用<=eval_year信息)"""
    sv_active = {t: raw[t][eval_year][0] for t in raw if raw[t][eval_year][0] >= C.MIN_HEAT_EVAL}
    if not sv_active:
        return {}
    heats = sorted(sv_active.values())
    p25, p60, p75 = (heats[int(q * len(heats))] for q in (0.25, 0.60, 0.75))

    def by_lang(l):
        return [t for t in sv_active if meta[t]["lang"] == l]

    slices = {}
    slices["lang_zh"] = by_lang("zh")
    slices["lang_en"] = by_lang("en")
    slices["lang_ar"] = by_lang("ar")
    slices["freq_high"] = [t for t in sv_active if meta[t]["freq_class"] == "high"]
    slices["freq_low"] = [t for t in sv_active if meta[t]["freq_class"] == "low"]
    slices["dense"] = [t for t in sv_active if meta[t]["density_class"] == "dense"]
    slices["sparse"] = [t for t in sv_active if meta[t]["density_class"] == "sparse"]
    slices["mature"] = [t for t in sv_active if sv_active[t] >= p75]
    slices["emerging_cand"] = [t for t in sv_active
                               if sv_active[t] <= p60 and raw[t][eval_year][1] > 0]
    cross = [t for t in sv_active if raw[t][eval_year][3] >= np.median(
        [raw[x][eval_year][3] for x in sv_active])]
    slices["cross_domain"] = cross
    slices["single_domain"] = [t for t in sv_active if t not in set(cross)]
    return slices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="_part1")
    ap.add_argument("--models", nargs="+", default=["B0_last", "B1", "B2"])
    args = ap.parse_args()

    sv = C.load_state_vectors()
    raw, enc, years = C.build_matrices(sv)
    meta = json.loads((C.OUT / "dataset" / "topics_meta.json").read_text(encoding="utf-8"))
    npz = np.load(C.OUT / "backtest" / f"predictions{args.tag}.npz", allow_pickle=True)
    preds = {k: dict(npz[k].item()) for k in npz.files}

    seeds = {"B0_last": [0], "B0_ma": [0], "B0_linear": [0],
             "B1": C.SEEDS_B1, "B2": C.SEEDS_B2, "M": C.SEEDS_M}
    periods = {"stable_2016_2019": set(range(2016, 2020)),
               "covid_2020_2021": {2020, 2021},
               "recovery_2022_2025": set(range(2022, 2026))}

    rows = []
    for model in args.models:
        for h in (1, 3, 5):
            for ey in C.eval_years_for(h):
                # 多种子平均得分
                scores = {}
                for seed in seeds.get(model, [0]):
                    key = f"{model}_s{seed}_h{h}_{ey}"
                    if key not in preds:
                        continue
                    for t, (lv, dt) in preds[key].items():
                        if dt:
                            scores[t] = scores.get(t, 0.0) + float(dt[-1]) / len(seeds.get(model, [0]))
                if not scores:
                    continue
                sl = slice_topics(raw, ey, meta)
                for sname, topics in sl.items():
                    if len(topics) < 10:
                        continue
                    p = {t: scores.get(t, 0.0) for t in topics}
                    a = {t: raw[t].get(ey + h, [0])[0] - raw[t][ey][0] for t in topics}
                    rho = C.spearman([p[t] for t in topics], [a[t] for t in topics])
                    mae = float(np.mean([abs(p[t] - a[t]) for t in topics]))
                    r_g = sorted(p, key=p.get, reverse=True)[:K]
                    a_g = sorted(p, key=a.get, reverse=True)[:K]
                    p10 = C.topk_hits(r_g, a_g, K)
                    rows.append({"model": model, "horizon": h, "eval_year": ey,
                                 "slice": sname, "n": len(topics),
                                 "MAE": round(mae, 4),
                                 "Spearman": round(rho, 4) if rho == rho else None,
                                 f"growth_P@{K}": round(float(p10), 4)})

    # 汇总: 模型×切片×视野 (+ 按时期过滤 eval 年)
    summ = {}
    for r in rows:
        for pname, yrs in periods.items():
            if r["eval_year"] + r["horizon"] in yrs:
                key = (r["model"], r["slice"], r["horizon"], pname)
                summ.setdefault(key, []).append(r)
    print("=" * 110)
    print("  实验4: 稳健性分层 (均值; n<10 的子集跳过; 阿语主题数为0 → 数据缺失)")
    print("=" * 110)
    print("| 模型 | 切片 | 视野 | 时期 | n均值 | MAE | Spearman | growth_P@10 |")
    print("|---|---|---|---|---|---|---|---|")
    out = []
    for (model, sname, h, pname), rs in sorted(summ.items()):
        def m(kk):
            vals = [r[kk] for r in rs if r.get(kk) is not None]
            return round(float(np.mean(vals)), 4) if vals else None
        row = {"model": model, "slice": sname, "horizon": h, "period": pname,
               "n_mean": round(float(np.mean([r["n"] for r in rs])), 1),
               "MAE": m("MAE"), "Spearman": m("Spearman"),
               f"growth_P@{K}": m(f"growth_P@{K}")}
        out.append(row)
        print(f"| {model:<9} | {sname:<14} | {h}年 | {pname:<14} | "
              f"{row['n_mean']:>6} | {str(row['MAE']):>7} | {str(row['Spearman']):>9} | "
              f"{str(row[f'growth_P@{K}']):>12} |")

    (C.OUT / "robustness" / "robustness_results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[OK] 结果: {C.OUT / 'robustness' / 'robustness_results.json'}")
    print("\n注: 'lang_ar' 阿语主题数为 0 (状态向量中无阿语主题) → 阿语稀疏在主题层完全缺失,"
          "建议论文中作为数据边界写入 RQ4")


if __name__ == "__main__":
    main()
