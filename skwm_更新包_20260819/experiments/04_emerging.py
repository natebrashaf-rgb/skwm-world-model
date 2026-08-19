# -*- coding: utf-8 -*-
"""04_emerging.py — 实验2: 新兴主题提前发现 (交付物 #5)
====================================================
新兴主题操作化定义 (避免把成熟主题当新兴):
  在冻结年 t:
    - 候选: heat(t) >= 2 且 heat(t) <= p60(当年活跃主题热度)  ← 排除已热门主题
    - 实际新兴 (未来验证): 存在 h ∈ {1,2,3} 使 heat(t+h) >= max(50, 3*heat(t))
                          且 heat(t+h) - heat(t) >= 30
模型新兴得分: 冻结年 t 的预测增速 (h=3 增量; h=1 增量单独报告)
指标: 命中率 / P@10 / R@10 / NDCG@10 / 虚假预警率 / 平均提前发现时间
输出: output/emerging/emerging_metrics.json + 案例清单 + md 表
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FREEZE_YEARS = list(range(2017, 2023))     # t+3 <= 2025
K = 10
EMERGED_MIN = 50       # 新兴判定: 未来热度下限
EMERGED_MULT = 3.0     # 新兴判定: 未来/当前 倍数
EMERGED_DELTA = 30     # 新兴判定: 绝对增量下限


def load_preds(tag):
    """从 backtest 预测 npz 读取 {key: {topic: [levels, deltas]}}"""
    path = C.OUT / "backtest" / f"predictions{tag}.npz"
    d = np.load(path, allow_pickle=True)
    return {k: dict(d[k].item()) for k in d.files}


def score_from_preds(preds, model, seed, h, t):
    """冻结年 t, 视野 h: 主题 -> 预测增量 (deltas 最后一期)"""
    key = f"{model}_s{seed}_h{h}_{t}"
    if key not in preds:
        return {}
    out = {}
    for topic, (lv, dt) in preds[key].items():
        if dt:
            out[topic] = float(dt[-1])
    return out


def emerged_label(raw, t):
    """冻结年 t: 返回 {topic: emerged(bool)} 与 emerged_topics 列表"""
    heat_t = {tpic: raw[tpic][t][0] for tpic in raw}
    active = [v for v in heat_t.values() if v >= 2]
    if not active:
        return {}, set()
    thr = sorted(active)[int(0.6 * len(active))]
    cand = {tpic: v for tpic, v in heat_t.items() if 2 <= v <= thr}
    emerged = set()
    for tpic, ht in cand.items():
        for h in (1, 2, 3):
            fut = raw[tpic].get(t + h, [0])[0]
            if fut >= max(EMERGED_MIN, EMERGED_MULT * ht) and fut - ht >= EMERGED_DELTA:
                emerged.add(tpic)
                break
    return cand, emerged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="_part1",
                    help="读取 predictions{tag}.npz (M 完成后用 --tag _all 重跑)")
    ap.add_argument("--models", nargs="+",
                    default=["B0_last", "B1", "B2"])
    args = ap.parse_args()

    sv = C.load_state_vectors()
    raw, enc, years = C.build_matrices(sv)
    preds = load_preds(args.tag)

    seeds = {"B0_last": [0], "B0_ma": [0], "B0_linear": [0],
             "B1": C.SEEDS_B1, "B2": C.SEEDS_B2, "M": C.SEEDS_M}

    rows = []
    for model in args.models:
        for h in (1, 3):
            for t in FREEZE_YEARS:
                # 多种子得分平均 → 稳定排序
                scores = {}
                for seed in seeds.get(model, [0]):
                    sc = score_from_preds(preds, model, seed, h, t)
                    for tp, v in sc.items():
                        scores[tp] = scores.get(tp, 0.0) + v / len(seeds.get(model, [0]))
                cand, emerged = emerged_label(raw, t)
                cand_scores = {tp: v for tp, v in scores.items() if tp in cand}
                if not cand_scores:
                    continue
                rank = sorted(cand_scores, key=cand_scores.get, reverse=True)[:K]
                hit = len(set(rank) & emerged)
                rows.append({
                    "model": model, "horizon": h, "freeze_year": t,
                    "n_candidates": len(cand_scores), "n_emerged": len(emerged),
                    "P@10": round(hit / K, 4),
                    "R@10": round(hit / max(1, len(emerged)), 4),
                    "NDCG@10": round(C.ndcg_at_k(rank, sorted(emerged)[:K], K), 4),
                    "hit_rate": 1.0 if hit > 0 else 0.0,
                    "false_alarm_rate": round((K - hit) / K, 4),
                    "top10": rank, "emerged": sorted(emerged)[:K],
                })

    # 汇总 (按模型×视野, 冻结年取均值)
    summ = {}
    for r in rows:
        k = (r["model"], r["horizon"])
        summ.setdefault(k, []).append(r)
    print("=" * 96)
    print("  实验2: 新兴主题提前发现 (冻结年 2017-2022 均值)")
    print("=" * 96)
    print("| 模型 | 视野 | P@10 | R@10 | NDCG@10 | 命中率 | 虚假预警率 | 平均新兴数 |")
    print("|---|---|---|---|---|---|---|---|")
    out_rows = []
    for (model, h), rs in sorted(summ.items()):
        n = len(rs)
        def m(kk):
            return round(float(np.mean([r[kk] for r in rs])), 4)
        out_rows.append({"model": model, "horizon": h,
                         "P@10": m("P@10"), "R@10": m("R@10"),
                         "NDCG@10": m("NDCG@10"), "hit_rate": m("hit_rate"),
                         "false_alarm_rate": m("false_alarm_rate"),
                         "n_emerged_avg": round(float(np.mean([r["n_emerged"] for r in rs])), 1)})
        print(f"| {model:<9} | {h}年 | {m('P@10'):.3f} | {m('R@10'):.3f} | "
              f"{m('NDCG@10'):.3f} | {m('hit_rate'):.3f} | {m('false_alarm_rate'):.3f} | "
              f"{out_rows[-1]['n_emerged_avg']} |")

    # 代表性案例 (h=3, 最后冻结年 2022)
    print("\n  代表性案例 (h=3, 冻结年 2022):")
    cases = {"success": {}, "miss": {}, "false_alarm": {}}
    for model in args.models:
        rs = [r for r in rows if r["model"] == model and r["horizon"] == 3
              and r["freeze_year"] == 2022]
        if not rs:
            continue
        r = rs[0]
        e_set = set(r["emerged"])
        t10 = r["top10"]
        cases["success"][model] = [t for t in t10 if t in e_set][:5]
        cases["miss"][model] = [t for t in e_set if t not in t10][:5]
        cases["false_alarm"][model] = [t for t in t10 if t not in e_set][:5]
        print(f"  [{model}] 成功: {cases['success'][model]}")
        print(f"          漏报: {cases['miss'][model]}")
        print(f"          误报: {cases['false_alarm'][model]}")

    out = {"definition": {
        "candidate": "heat(t) in [2, p60(active)]",
        "emerged": f"exists h in 1..3: heat(t+h) >= max({EMERGED_MIN}, "
                   f"{EMERGED_MULT}*heat(t)) and delta >= {EMERGED_DELTA}"},
        "freeze_years": FREEZE_YEARS, "summary": out_rows,
        "per_freeze_year": rows, "cases": cases}
    (C.OUT / "emerging" / "emerging_metrics.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[OK] 结果: {C.OUT / 'emerging' / 'emerging_metrics.json'}")


if __name__ == "__main__":
    main()
