# -*- coding: utf-8 -*-
"""08_analysis_template.py — 专家评分导入与统计分析 (交付物 #9)
================================================================
输入: output/service_materials/评分表.csv (真人填写, AI 不生成评分)
输出: 描述统计 + A/B 配对检验 (Wilcoxon signed-rank + 配对t + Cohen's d) + 图表

用法:
  python 08_analysis_template.py                          # 有评分数据时
评分数据未就绪时, 本脚本只打印等待提示并退出 (不产生任何虚构结果)。
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

RATING_CSV = C.OUT / "service_materials" / "评分表.csv"
NUMERIC_DIMS = ["前沿识别准确性(1-5)", "前瞻性(1-5)", "新颖性(1-5)",
                "证据充分性(1-5)", "证据可追溯性(1-5)",
                "对学科服务决策的帮助(1-5)", "纳入学科前沿报告的意愿(1-5)",
                "评价者信心(1-5)"]


def main():
    if not RATING_CSV.exists():
        print(f"[等待] {RATING_CSV} 不存在 → 先运行 07_service_materials.py")
        return
    rows = list(csv.DictReader(open(RATING_CSV, encoding="utf-8-sig")))
    filled = [r for r in rows if r.get("条件(A/B, 随机化后填写)")]
    if not filled:
        print("[等待] 评分表为空 — 必须由 5-7 名真实评价者填写后才能分析。")
        print("       AI 不模拟专家评分; 请将评分表发给评价者。")
        return

    try:
        from scipy.stats import wilcoxon, ttest_rel
    except ImportError:
        print("[错误] 需要 scipy")
        return

    print(f"[分析] 已导入 {len(filled)} 条真实评分 (评价者 "
          f"{len(set(r['评价者编号'] for r in filled))} 名)\n")

    results = {}
    for dim in NUMERIC_DIMS:
        a_vals, b_vals = [], []
        for r in filled:
            try:
                v = float(r[dim])
            except (ValueError, TypeError):
                continue
            (a_vals if r["条件(A/B, 随机化后填写)"].strip().upper() == "A" else b_vals).append(v)
        if len(a_vals) < 3 or len(b_vals) < 3:
            continue
        # 配对: 按 (评价者, 任务) 对齐
        pairs = {}
        for r in filled:
            try:
                v = float(r[dim])
            except (ValueError, TypeError):
                continue
            key = (r["评价者编号"], r["任务ID"])
            cond = r["条件(A/B, 随机化后填写)"].strip().upper()
            pairs.setdefault(key, {})[cond] = v
        paired = [(d["A"], d["B"]) for d in pairs.values() if "A" in d and "B" in d]
        if len(paired) < 3:
            continue
        a = [x[0] for x in paired]
        b = [x[1] for x in paired]
        import numpy as np
        d_mean = float(np.mean([x[1] - x[0] for x in paired]))
        d_std = float(np.std([x[1] - x[0] for x in paired], ddof=1))
        cohen_d = d_mean / d_std if d_std > 0 else float("nan")
        try:
            w_stat, w_p = wilcoxon(a, b)
        except ValueError:
            w_stat, w_p = float("nan"), float("nan")
        t_stat, t_p = ttest_rel(a, b)
        results[dim] = {
            "n_pairs": len(paired),
            "A_mean": round(float(np.mean(a)), 3), "B_mean": round(float(np.mean(b)), 3),
            "B_minus_A": round(d_mean, 3),
            "cohen_d": round(cohen_d, 3),
            "wilcoxon_p": round(float(w_p), 4),
            "paired_t_p": round(float(t_p), 4),
            "B_better": bool(d_mean > 0 and w_p < 0.05),
        }
        print(f"  {dim}: A={results[dim]['A_mean']} vs B={results[dim]['B_mean']} "
              f"(Δ={d_mean:+.3f}, d={cohen_d:+.3f}, Wilcoxon p={w_p:.4f}, "
              f"t p={t_p:.4f})")

    (C.OUT / "service_materials" / "expert_analysis.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    if not results:
        print("[等待] 数值维度数据不足 (需每条件至少 3 条配对评分)")


if __name__ == "__main__":
    main()
