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

from neo4j_static_service import run_s0
from temporal_baseline_service import run_s1
from rssm_prediction_service import run_s2


def load_queries():
    queries = []
    csv_path = BASE / "service_queries.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append(row)
    return queries


def anonymize_answer(answer: dict, qid: str) -> dict:
    return {
        "编号": qid,
        "回答摘要": json.dumps(answer, ensure_ascii=False)[:500],
        "置信度": answer.get("confidence", "N/A"),
        "是否有预测": answer.get("has_prediction", answer.get("prediction_mode") != "static_baseline"),
        "是否有不确定性": answer.get("has_uncertainty", False),
        "是否有风险提示": answer.get("has_risk_warning", False),
        "证据": answer.get("evidence", "")[:200],
    }


def generate_blind_package(as_of_year: int = 2023):
    print("=" * 60)
    print("  服务增量盲评实验")
    print("=" * 60)
    print(f"  截止年份: {as_of_year}")

    queries = load_queries()
    print(f"  问题数: {len(queries)}")

    print("\n[1/3] 运行 S0 (静态基线)...")
    s0_results = run_s0(as_of_year)

    print("[2/3] 运行 S1 (趋势预测)...")
    s1_results = run_s1(as_of_year)

    print("[3/3] 运行 S2 (RSSM预测)...")
    s2_results = run_s2(as_of_year)

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
