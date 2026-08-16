#!/usr/bin/env python3
"""
temporal_baseline_service.py — S1: S0 + 普通趋势/XGBoost
=========================================================
定位: S1 服务条件
在 S0 基础上增加线性趋势或 XGBoost 预测，但不使用 RSSM。
用于区分"有预测"与"有世界模型"。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiment_service_baseline import S1TrendService, SERVICE_QUESTIONS


def run_s1(as_of_year: int = 2023):
    service = S1TrendService(as_of_year=as_of_year)
    results = {}

    for q in SERVICE_QUESTIONS:
        answer = service.answer(q)
        answer["condition"] = "S1"
        answer["prediction_mode"] = "linear_trend"
        results[q["qid"]] = answer

    return results


if __name__ == "__main__":
    import json
    results = run_s1()
    print(json.dumps(results, ensure_ascii=False, indent=2))
