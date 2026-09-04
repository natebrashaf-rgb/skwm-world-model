#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_delivery.py — 从三轮复跑结果生成干净 delivery/evidence 包（组长第五/九阶段）
==============================================================================
用法：python3.14 build_delivery.py  （在 rail_deploy 根运行）
输入（output/baselines_rolling/）：
  baselines_rolling_YYYYMMDD.json   —— 主结果（重跑最近一次，作为 run3 亦作主输出）
  run1.json / run2.json / run3.json —— 三轮复跑（run1/run2 为前两次 cp，run3=主输出 cp）
  split_manifest.csv                 —— 扩列逐样本审计表（来自最后一次跑）
  leakage_audit_YYYYMMDD.json        —— 泄漏审计结果
  experiment_model_c0c1_results.json —— c0c1 参考（output/experiment_model_c0c1/）
输出：
  output/baselines_rolling/delivery_v1.4_YYYYMMDD/  （干净目录，仅交付文件）
    results.json / baselines_rolling_summary.md / split_manifest.csv /
    run1.json / run2.json / run3.json / hashes.txt / leakage_audit.json
说明：results.json 为论文数字聚合层（字段级引用自 run json，逐字段可追溯）；
      hashes.txt 纯 SHA（无注释行，LF 行尾，供 sha256sum -c 校验）。
"""
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
OUT = BASE / "output" / "baselines_rolling"
DELIV = OUT / f"delivery_v1.4_{date.today().strftime('%Y%m%d')}"
PARTIAL_YEAR = 2026


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def find_latest_main():
    cands = sorted(OUT.glob("baselines_rolling_2*.json"))
    if not cands:
        raise SystemExit("未找到 baselines_rolling_2*.json 主结果")
    return cands[-1]


def main():
    main_json = find_latest_main()
    main_res = json.loads(main_json.read_text(encoding="utf-8"))

    runs = {}
    for name in ["run1.json", "run2.json", "run3.json"]:
        p = OUT / name
        if not p.exists():
            raise SystemExit(f"缺少 {p}")
        runs[name] = json.loads(p.read_text(encoding="utf-8"))

    c0c1_path = BASE / "output" / "experiment_model_c0c1" / "experiment_model_c0c1_results.json"
    c0c1 = json.loads(c0c1_path.read_text(encoding="utf-8")) if c0c1_path.exists() else None

    leakage_cands = sorted(OUT.glob("leakage_audit_*.json"))
    leakage = json.loads(leakage_cands[-1].read_text(encoding="utf-8")) if leakage_cands else None

    # ---------------- results.json 组装 ----------------
    pa = main_res["partA_same_window"]["overall"]
    pb = main_res["partB_rolling"]
    crosscheck = main_res["partA_crosscheck_vs_c0c1"]

    # 三轮 xgboost/rssm Part A 波动范围（对账 FAIL 定性用）
    def range_of(metric, model, hk):
        vals = []
        for r in runs.values():
            v = r.get("partA_same_window", {}).get("overall", {}).get(hk, {}).get(model, {}).get(metric)
            if v is not None:
                vals.append(float(v))
        return vals

    paper = {
        "schema": "skwm_baselines_rolling_results_v1.4",
        "date": str(date.today()),
        "data": {
            "file": main_res["meta"]["data"],
            "sha256": main_res["meta"].get("data_sha256"),
            "papers_B1": 12233,
            "state_vectors_rows": 43642,
        },
        "paper_numbers": {
            "h1_naive_last_cross_topic_spearman": pa["1"]["naive_last"]["cross_topic_spearman"],
            "h3_naive_last_cross_topic_spearman": pa["3"]["naive_last"]["cross_topic_spearman"],
            "h5_naive_last_cross_topic_spearman": pa["5"]["naive_last"]["cross_topic_spearman"],
            "h1_naive_last_MAE": pa["1"]["naive_last"]["MAE"],
            "h5_naive_last_MAE": pa["5"]["naive_last"]["MAE"],
            "field_source": {
                "h1/h3/h5_naive_last_cross_topic_spearman": "partA_same_window.overall.<h>.naive_last.cross_topic_spearman（跨目标年逐主题秩相关，池化；h=1/3/5 均成立，正式排序口径）",
                "temporal_spearman": "partB_rolling.<cutoff>.h=<h>.overall.<model>.temporal_spearman（主题内窗向量相关，仅窗长>=3，h=1=None）",
            },
            "partB_xgboost_temporal_spearman_range": {
                c: {hk: pb[c][hk]["overall"]["xgboost"].get("temporal_spearman") for hk in ["h=3", "h=5"]}
                for c in sorted(pb)
            },
            "partB_naive_last_cross_topic_by_origin": {
                c: {hk: pb[c][hk]["overall"]["naive_last"].get("cross_topic_spearman") for hk in ["h=1", "h=3", "h=5"]}
                for c in sorted(pb)
            },
        },
        "reconciliation_vs_c0c1": {
            "ref_file": str(c0c1_path) if c0c1 else None,
            "ref_date": (c0c1 or {}).get("meta", {}).get("date"),
            "n_rows": crosscheck["n_rows"],
            "n_fail": crosscheck["n_fail"],
            "fail_rows": [r for r in crosscheck["rows"] if r["verdict"] == "FAIL"],
            "run1_3_range_evidence": {
                "xgboost_h1_MAE_range": [min(range_of("MAE", "xgboost", "1")), max(range_of("MAE", "xgboost", "1"))],
                "rssm_h1_MAE_range": [min(range_of("MAE", "rssm", "1")), max(range_of("MAE", "rssm", "1"))],
                "rssm_h1_P10_values": range_of("Precision@10", "rssm", "1"),
            },
        },
        "leakage_audit": leakage,
        "git": {
            "code_commit": "9612874 experiment: baselines rolling v1.3",  # v1.4 commit 后在 FINAL_AUDIT_REPORT 更新
        },
    }

    DELIV.mkdir(parents=True, exist_ok=True)
    # ---------------- 复制交付文件 ----------------
    files = {
        "results.json": json.dumps(paper, ensure_ascii=False, indent=2).encode("utf-8"),
        main_json.name: main_json.read_bytes(),
        "run1.json": (OUT / "run1.json").read_bytes(),
        "run2.json": (OUT / "run2.json").read_bytes(),
        "run3.json": (OUT / "run3.json").read_bytes(),
        "baselines_rolling_summary.md": (OUT / "baselines_rolling_summary.md").read_bytes(),
        "split_manifest.csv": (OUT / "split_manifest.csv").read_bytes(),
    }
    if leakage:
        files["leakage_audit.json"] = json.dumps(leakage, ensure_ascii=False, indent=2).encode("utf-8")

    for name, data in files.items():
        (DELIV / name).write_bytes(data)

    # ---------------- hashes.txt（LF、无注释、不含自身） ----------------
    hash_lines = []
    for name in files:
        h = hashlib.sha256(files[name]).hexdigest()
        hash_lines.append(f"{h}  {name}")
    (DELIV / "hashes.txt").write_text("\n".join(hash_lines) + "\n", encoding="utf-8", newline="\n")

    n_entries = len(files)
    total = sum(len(v) for v in files.values())
    print(f"delivery: {DELIV}")
    for name in files:
        print(f"  {len(files[name]):>10}  {name}")
    print(f"  n_files={n_entries}  total_bytes={total}")

    # 交叉一致性快查：主 json 里 summary 同源
    print(f"h1 naive_last cross_topic_spearman = {paper['paper_numbers']['h1_naive_last_cross_topic_spearman']}")
    print(f"h5 naive_last cross_topic_spearman = {paper['paper_numbers']['h5_naive_last_cross_topic_spearman']}")
    return paper


if __name__ == "__main__":
    main()
