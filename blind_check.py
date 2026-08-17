# -*- coding: utf-8 -*-
"""
盲评材料自检表 — 防排版泄漏
============================
同一题下 S0/S1/S2 三份报告必须无法区分组别。
检查项：
  1. 字数差异（<15%）
  2. 小标题一致性
  3. 字段顺序一致性
  4. 敏感词扫描（组名/模型名/版本号/内部字段）
  5. 置信度方差（恒值=泄漏风险）
  6. 内容差异提示（同题三组回答是否过度雷同/过度不同）
用法：py -3.14 blind_check.py [--dir service_experiment]
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent


def load_condition(cond_dir: Path, cond: str):
    path = cond_dir / f"condition_{cond}" / "blind_answers.json"
    if not path.exists():
        return []
    return json.load(open(path, encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, default=str(BASE / "service_experiment"))
    args = parser.parse_args()
    cond_dir = Path(args.dir)

    s0 = load_condition(cond_dir, "S0")
    s1 = load_condition(cond_dir, "S1")
    s2 = load_condition(cond_dir, "S2")

    if not (s0 and s1 and s2):
        print("❌ 盲评材料缺失，先运行 run_blind_experiment.py")
        sys.exit(1)

    n = min(len(s0), len(s1), len(s2))
    print(f"三组题数: S0={len(s0)} S1={len(s1)} S2={len(s2)} (比对前{n}题)")
    print("=" * 70)

    issues = []

    # 1) 题数一致性
    if len(s0) != len(s1) or len(s1) != len(s2):
        issues.append(f"❌ 题数不一致: {len(s0)}/{len(s1)}/{len(s2)}")
    else:
        print(f"✅ 题数一致 ({n}题)")

    # 2) 字段顺序一致性
    for i in range(n):
        keys0 = list(s0[i].keys())
        keys1 = list(s1[i].keys())
        keys2 = list(s2[i].keys())
        if keys0 != keys1 or keys1 != keys2:
            issues.append(f"❌ 题{i+1} 字段顺序不一致: {keys0} vs {keys1} vs {keys2}")
        else:
            print(f"✅ 题{i+1} 字段顺序一致: {keys0}")

    # 3) 字数差异
    for i in range(n):
        l0 = len(s0[i].get("回答摘要", ""))
        l1 = len(s1[i].get("回答摘要", ""))
        l2 = len(s2[i].get("回答摘要", ""))
        lens = [l0, l1, l2]
        mx, mn = max(lens), min(lens)
        if mx > 0 and (mx - mn) / mx > 0.15:
            issues.append(f"❌ 题{i+1} 字数差异>15%: {lens}")
        else:
            print(f"✅ 题{i+1} 字数差异OK: {lens}")

    # 4) 敏感词扫描
    SENSITIVE = ["S0", "S1", "S2", "RSSM", "rssm", "model_rssm", "XGBoost",
                 "linear", "linear_trend", "rssm_prediction", "static_baseline",
                 "level", "prediction_mode", "term_map_v", "term_map"]
    for i in range(n):
        for cond, data in [("S0", s0), ("S1", s1), ("S2", s2)]:
            text = json.dumps(data[i], ensure_ascii=False)
            for w in SENSITIVE:
                if w in text:
                    issues.append(f"❌ 题{i+1} 组{cond} 含敏感词[{w}]")
    if not any("敏感词" in x for x in issues):
        print("✅ 无敏感词泄漏")

    # 5) 置信度方差（恒值=泄漏风险）
    for cond, data in [("S0", s0), ("S1", s1), ("S2", s2)]:
        confs = [x.get("置信度", "N/A") for x in data[:n]]
        uniq = set(confs)
        if len(uniq) <= 1:
            issues.append(f"⚠️ 组{cond} 置信度无方差({confs}) → 可据此猜组别")
        else:
            print(f"✅ 组{cond} 置信度有区分度: {confs}")

    # 6) 内容差异提示（同题三组回答摘要的相似度）
    for i in range(n):
        a0 = s0[i].get("回答摘要", "")
        a1 = s1[i].get("回答摘要", "")
        a2 = s2[i].get("回答摘要", "")
        # 用字符级Jaccard粗估
        def jacc(x, y):
            sx, sy = set(x[:300]), set(y[:300])
            return len(sx & sy) / max(1, len(sx | sy))
        j01 = jacc(a0, a1)
        j12 = jacc(a1, a2)
        j02 = jacc(a0, a2)
        if j01 > 0.9 or j12 > 0.9:
            issues.append(f"⚠️ 题{i+1} 三组回答过度相似(J={j01:.2f}/{j12:.2f}) → 可能看不出差异")
        elif j02 < 0.1 and j01 < 0.1 and j12 < 0.1:
            issues.append(f"⚠️ 题{i+1} 三组回答过度不同(J={j02:.2f}) → 可能是不同题")

    print("=" * 70)
    if issues:
        print(f"发现 {len(issues)} 个问题：")
        for it in issues:
            print(f"  {it}")
        sys.exit(2)
    else:
        print("✅ 自检通过：盲评材料无法从排版猜出组别")


if __name__ == "__main__":
    main()
