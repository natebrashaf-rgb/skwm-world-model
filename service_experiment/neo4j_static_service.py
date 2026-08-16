#!/usr/bin/env python3
"""
neo4j_static_service.py — S0: Neo4j 静态检索 + 当前科学计量
===========================================================
定位: S0 静态学科服务基线
只使用历史数据，不做任何预测。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j_service_query import Neo4jServiceQuery, LIBRARIAN_QUESTIONS


def run_s0(as_of_year: int = 2023):
    sq = Neo4jServiceQuery(as_of_year=as_of_year)
    results = {}

    for q in LIBRARIAN_QUESTIONS:
        answer = sq.answer_question(q)
        answer["condition"] = "S0"
        answer["prediction_mode"] = "static_baseline"
        answer["confidence"] = 0.3
        results[q["qid"]] = answer

    return results


if __name__ == "__main__":
    import json
    results = run_s0()
    print(json.dumps(results, ensure_ascii=False, indent=2))
