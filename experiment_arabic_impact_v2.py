#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility entry point for the corrected Task C experiment."""

from pathlib import Path

from task_cd_handover import run_task_c, write_json


def run_experiment() -> dict:
    results = run_task_c()
    write_json(Path("output/experiment_c/experiment_c_results_v3.json"), results)
    return results


if __name__ == "__main__":
    result = run_experiment()
    print(
        "Task C v3 complete: "
        f"Jaccard={result['conclusions']['q1_average_jaccard']}, "
        f"new_topics={result['conclusions']['q2_new_topics_count']}"
    )
