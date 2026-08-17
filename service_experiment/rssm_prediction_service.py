#!/usr/bin/env python3
"""
rssm_prediction_service.py — S2: S0 + RSSM 多步预测 + 不确定性
===============================================================
定位: S2 服务条件
在 S0 基础上增加 RSSM 多步预测和不确定性估计。
用于检验世界模型服务增量。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiment_service_baseline import S2RSSMService, SERVICE_QUESTIONS


def run_s2(as_of_year: int = 2023):
    service = S2RSSMService(as_of_year=as_of_year)
    results = {}

    for q in SERVICE_QUESTIONS:
        answer = service.answer(q)
        answer["condition"] = "S2"
        answer["prediction_mode"] = "rssm_prediction"
        results[q["qid"]] = answer

    return results


if __name__ == "__main__":
    import json
    results = run_s2()
    print(json.dumps(results, ensure_ascii=False, indent=2))
