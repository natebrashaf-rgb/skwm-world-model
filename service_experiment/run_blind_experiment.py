#!/usr/bin/env python3
"""
run_blind_experiment.py — 生成盲评材料 + 汇总评价
=================================================
对应论文 §4.2 实验二
三组 (S0/S1/S2) 使用相同问题集，输出匿名盲评材料。
"""
import json
import csv
import os
import sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE.parent))

from experiment_service_baseline import (
    S0StaticService, S1TrendService, S2RSSMService, SERVICE_QUESTIONS,
)


def load_queries():
    """统一问题集：SERVICE_QUESTIONS（5题）——S0/S1/S2 三组必须同题"""
    return SERVICE_QUESTIONS


INTERNAL_FIELDS = {"level", "qid", "elapsed_seconds", "prediction_mode"}
# evidence 文案里的组别词，统一中性化（防泄漏）
EVIDENCE_NEUTRAL = {
    "S0基线 + 线性趋势外推": "基于历史数据的趋势外推",
    "S0基线 + RSSM多步预测 + 不确定性估计": "基于历史数据的多步预测与不确定性估计",
    "S0基线 + RSSM多步预测 + 不确定性估计 2": "基于历史数据的多步预测与不确定性估计",
    "S0基线": "基于历史数据",
    "基于state_vectors静态增速排序": "基于历史数据的静态增速排序",
    "基于历史热度排序，无预测": "基于历史热度排序",
    "静态数据汇总，无预测/置信度/风险提示": "静态数据汇总",
}


def _neutralize_evidence(text: str) -> str:
    for k, v in EVIDENCE_NEUTRAL.items():
        text = text.replace(k, v)
    # 兜底：去掉任何 "S0/S1/S2/RSSM/线性" 字样
    import re
    text = re.sub(r"(S0|S1|S2|RSSM|XGBoost|线性趋势)", "趋势", text)
    return text


def anonymize_answer(answer: dict, qid: str) -> dict:
    # 去除内部字段（防盲评者从 JSON 猜出组别）
    public = {k: v for k, v in answer.items() if k not in INTERNAL_FIELDS}
    # evidence 中性化
    if "evidence" in public:
        public["evidence"] = _neutralize_evidence(str(public["evidence"]))
    # sections 小标题中性化（RSSM趋势预测 → 趋势预测等）
    if "sections" in public and isinstance(public["sections"], list):
        public["sections"] = [_neutralize_evidence(str(s)) for s in public["sections"]]
    # 摘要优先展示差异内容（forecast/预测），再是 base topics
    summary = {}
    # 预测类内容优先（S1/S2 的差异核心）
    for key in ["forecast", "prediction", "uncertainty", "prediction_note"]:
        if key in public:
            summary[key] = public[key]
    # 再放基础内容
    for key in ["topics", "hotspots", "emerging", "sections", "papers_count",
                "total_papers", "arabic_papers", "sparse_topics", "evidence"]:
        if key in public and key not in summary:
            summary[key] = public[key]
    return {
        "编号": qid,
        "回答摘要": json.dumps(summary, ensure_ascii=False)[:800],
        "置信度": answer.get("confidence", "N/A"),
        "证据": _neutralize_evidence(str(answer.get("evidence", "")))[:200],
    }


def generate_blind_package(as_of_year: int = 2023):
    print("=" * 60)
    print("  服务增量盲评实验")
    print("=" * 60)
    print(f"  截止年份: {as_of_year}")

    queries = load_queries()
    print(f"  问题数: {len(queries)}")

    print("\n[1/3] 运行 S0 (静态基线)...")
    s0_service = S0StaticService(as_of_year)
    s0_results = {q["qid"]: s0_service.answer(q) for q in SERVICE_QUESTIONS}

    print("[2/3] 运行 S1 (趋势预测)...")
    s1_service = S1TrendService(as_of_year)
    s1_results = {q["qid"]: s1_service.answer(q) for q in SERVICE_QUESTIONS}

    print("[3/3] 运行 S2 (RSSM预测)...")
    s2_service = S2RSSMService(as_of_year)
    s2_results = {q["qid"]: s2_service.answer(q) for q in SERVICE_QUESTIONS}

    all_results = {"S0": s0_results, "S1": s1_results, "S2": s2_results}

    for condition in ["S0", "S1", "S2"]:
        out_dir = BASE / f"condition_{condition}"
        out_dir.mkdir(exist_ok=True)

        results = all_results[condition]
        anonymized = []
        for qid, answer in results.items():
            anon = anonymize_answer(answer, qid)
            anonymized.append(anon)

        out_path = out_dir / "blind_answers.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(anonymized, f, ensure_ascii=False, indent=2)
        print(f"  [{condition}] 盲评材料: {out_path}")

    summary = {
        "generated_at": datetime.now().isoformat(),
        "as_of_year": as_of_year,
        "n_queries": len(queries),
        "conditions": ["S0", "S1", "S2"],
        "description": {
            "S0": "Neo4j静态检索 + 当前科学计量",
            "S1": "S0 + 普通趋势/XGBoost预测",
            "S2": "S0 + RSSM多步预测 + 不确定性",
        },
    }

    summary_path = BASE / "experiment_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] 盲评材料已生成")
    print(f"     S0: {BASE / 'condition_S0' / 'blind_answers.json'}")
    print(f"     S1: {BASE / 'condition_S1' / 'blind_answers.json'}")
    print(f"     S2: {BASE / 'condition_S2' / 'blind_answers.json'}")
    print(f"     汇总: {summary_path}")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=int, default=2023)
    args = parser.parse_args()

    generate_blind_package(as_of_year=args.as_of)
