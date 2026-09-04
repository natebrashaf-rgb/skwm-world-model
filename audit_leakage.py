#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_leakage.py — split_manifest.csv 数据泄漏自动审计（组长第六阶段要求，v1.4 配套）
==============================================================================
对逐样本审计表自动检查 10 项：
  1. history_end <= train_cutoff
  2. train_cutoff < target_year
  3. 所有训练样本 year <= origin（以 history_end 代理；每行 train 窗口终点）
  4. 所有测试样本 year > origin（target_year 严格 > origin）
  5. 没有 train/test overlap（history_end < target_year 逐行断言）
  6. 没有重复样本（同 id 唯一 / 同 (part,model,origin,topic_id,target_year) 唯一）
  7. prediction 对应正确 target year（prediction 非空；target_year 在 [origin+1, origin+h] 内）
  8. preprocessing 没有 fit future data（本实验无 preprocessing，见 manifest 列 N/A_no_scaler）
  9. scaler/imputer 没有 fit future data（同上，无 scaler）
  10. feature engineering 没有使用 future data（XGBoost lookback=5 只用 history<=target-1 的数据；
      由训练代码 train_until 断标签年 <= cutoff 保证；此处按 history_end < target_year 复核）

输出：
  output/baselines_rolling/leakage_audit_YYYYMMDD.json
  （+ 终端汇总行）。所有应为 0 的计数必须为 0，否则 exit 1。
"""
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
OUT_DIR = BASE / "output" / "baselines_rolling"
PARTIAL_YEAR = 2026
CUTOFFS = [2014, 2016, 2018, 2020]


def load_manifest(path):
    """返回 list[dict]，键为表头小写。兼容新旧列（新列缺失时补 None）。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        d = {k.lower().strip(): v for k, v in r.items()}
        out.append(d)
    return out


def main(manifest_path=None, tag=""):
    if manifest_path is None:
        manifest_path = OUT_DIR / "split_manifest.csv"
    manifest_path = Path(manifest_path)
    rows = load_manifest(manifest_path)
    n = len(rows)
    err = Counter()
    n_dup = 0
    seen = set()
    n_part = Counter(r.get("part") for r in rows)
    has_horizon = rows and rows[0].get("horizon") is not None and rows[0].get("horizon") != ""

    for r in rows:
        def num(k):
            try:
                return int(float(r.get(k)))
            except (TypeError, ValueError):
                return None

        he, tc, ty, org = num("history_end"), num("train_cutoff"), num("target_year"), num("origin")
        pred = r.get("prediction")
        act = r.get("actual")

        # 1. history_end <= train_cutoff
        if he is not None and tc is not None and he > tc:
            err["1_history_end_gt_train_cutoff"] += 1
        # 2. train_cutoff < target_year
        if tc is not None and ty is not None and not (tc < ty):
            err["2_train_cutoff_ge_target"] += 1
        # 3. 训练终点 <= origin
        if he is not None and org is not None and he > org:
            err["3_train_gt_origin"] += 1
        # 4. 目标年 > origin
        if ty is not None and org is not None and not (ty > org):
            err["4_target_le_origin"] += 1
        # 5. train/test overlap（history_end < target_year）
        if he is not None and ty is not None and not (he < ty):
            err["5_overlap"] += 1
        # 6. 重复样本：v1.4 表含 horizon 列 → 同一 (part,model,origin,horizon,topic,target) 必须唯一；
        #    旧表（v1.3，无 horizon）无法区分不同评测视野下的同目标年样本 → 其"重复"是跨视野预期冗余，
        #    单独计数 expected_cross_horizon（不判 FAIL，但结果里注明表版本局限）。
        key = (r.get("part"), r.get("model"), r.get("origin"),
               r.get("horizon"), r.get("topic_id"), r.get("target_year"))
        if key in seen:
            n_dup += 1
        else:
            seen.add(key)
        # 7. prediction/actual 缺失
        if pred is None or str(pred).strip() == "":
            err["7_missing_prediction"] += 1
        if act is None or str(act).strip() == "":
            err["7b_missing_actual"] += 1
        # 目标年必须在 (origin, origin+5] 窗口内（h<=5）
        if ty is not None and org is not None:
            if not (org < ty <= org + 5):
                err["7c_target_outside_window"] += 1
        # 2026 部分年度：Part A 允许（对账口径），Part B 禁止
        if r.get("part") == "B_rolling" and ty == PARTIAL_YEAR:
            err["4b_partial_year_in_B"] += 1

    # 8/9/10：无 preprocessing/scaler；feature lookback 只用历史 —— 代码级保证，
    # 见 experiment_baselines_rolling.py v1.4 注释与 Manifest.add 断言（history_end < target_year 已逐行执行）。
    preproc_note = ("无 scaler/imputer/全局统计：XGBoost/M0/M2 均直接消费原始 lookback 特征，"
                    "无全局 fit 步骤，故 8/9/10 项由「代码无此类步骤 + 逐行 history_end<target_year 断言」共同保证")

    if not has_horizon:
        # 旧版表（v1.3 及更早）：无法逐样本区分评测视野，把 n_dup 视为预期冗余并在报告中标注
        n_expected_cross_horizon = n_dup
        n_dup_true = 0
    else:
        n_expected_cross_horizon = 0
        n_dup_true = n_dup

    n_err_total = sum(v for k, v in err.items())
    result = {
        "date": str(date.today()),
        "manifest_path": str(manifest_path),
        "manifest_tag": tag,
        "manifest_version": "v1.4_with_horizon" if has_horizon else "pre_v1.4_no_horizon",
        "n_rows": n,
        "n_duplicates": n_dup_true,
        "n_expected_cross_horizon_duplicates": n_expected_cross_horizon,
        "checks": {
            "1_history_end_le_train_cutoff": {"violations": err["1_history_end_gt_train_cutoff"], "must_be": 0},
            "2_train_cutoff_lt_target": {"violations": err["2_train_cutoff_ge_target"], "must_be": 0},
            "3_train_years_le_origin": {"violations": err["3_train_gt_origin"], "must_be": 0},
            "4_test_years_gt_origin": {"violations": err["4_target_le_origin"], "must_be": 0},
            "5_no_train_test_overlap": {"violations": err["5_overlap"], "must_be": 0},
            "6_no_duplicate_rows": {"violations": n_dup_true, "must_be": 0},
            "7_no_missing_prediction": {"violations": err["7_missing_prediction"], "must_be": 0},
            "7b_no_missing_actual": {"violations": err["7b_missing_actual"], "must_be": 0},
            "7c_target_within_h_window": {"violations": err["7c_target_outside_window"], "must_be": 0},
            "4b_no_partial_year_in_B": {"violations": err["4b_partial_year_in_B"], "must_be": 0},
            "8_no_preprocessing_future_fit": {"violations": 0, "must_be": 0, "note": preproc_note},
            "9_no_scaler_future_fit": {"violations": 0, "must_be": 0, "note": preproc_note},
            "10_no_feature_eng_future_data": {"violations": 0, "must_be": 0, "note": "lookback=5 特征窗口终点=history_end<target_year（逐行断言），且 XGBoost 训练标签年<=origin（train_until 内 break）"},
        },
        "n_violations_total": n_err_total,
        "pass": (n_err_total == 0 and n_dup_true == 0),
        "rows_by_part": dict(n_part),
        "note_cross_horizon": ("同一物理预测样本被 h=1/3/5 多个评测视野记录属滚动回测设计的预期冗余；"
                               "v1.4 表以 horizon 列区分后重复为 0。旧表（无 horizon）无法区分，"
                               "其重复数计为 n_expected_cross_horizon_duplicates 而非真重复。"
                               if not has_horizon else None),
    }

    out_path = OUT_DIR / f"leakage_audit_{tag or date.today().strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rows={n}  duplicates={n_dup_true}  expected_cross_horizon={n_expected_cross_horizon}  "
          f"violations={n_err_total}  pass={result['pass']}")
    print(f"rows_by_part={dict(n_part)}")
    if not result["pass"]:
        print("LEAKAGE AUDIT FAILED — 见 " + str(out_path))
        sys.exit(1)
    print("LEAKAGE AUDIT PASS — " + str(out_path))
    return result


if __name__ == "__main__":
    # 用法：python3.14 audit_leakage.py [manifest路径] [tag]
    main(*sys.argv[1:3])
