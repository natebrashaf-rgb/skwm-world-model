#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility entry point for the corrected Task D experiment."""

from pathlib import Path

from task_cd_handover import render_task_d_report, run_task_d as compute_task_d, write_json


def run_task_d_experiment() -> dict:
    results = compute_task_d()
    write_json(Path("output/experiment_d/experiment_d_results_v3.json"), results)
    report = Path("output/experiment_d/experiment_d_report_v3.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_task_d_report(results), encoding="utf-8")
    return results


# Preserve the historical public function name.
run_task_d = run_task_d_experiment


if __name__ == "__main__":
    result = run_task_d_experiment()
    print(
        "Task D v3 complete: "
        f"tourism={result['summary']['tourism_related']}, "
        f"extracted={result['summary']['text_extracted']}"
    )
