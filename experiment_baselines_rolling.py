#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
experiment_baselines_rolling.py — 同窗口基线 + 多截点滚动时间回测
==============================================================================
口径（2026-09-01 拍板，与页 20 日志⑧⑨⑩一致）：
  - 数据：data/state_vectors_C1_20260827.json（C1，12,233 篇，SHA 见
    output/data_version_manifest_12233.json）
  - Part A 同窗口基线：与 experiment_model_c0c1.py 完全同一评测协议
    （同一 eval_plan 计算方式、同一批模型同训练截止/测试年/主题集/目标/指标），
    新增 Naive-last 与 Drift 两个惯性基线；
    若 output/experiment_model_c0c1/experiment_model_c0c1_results.json 存在，
    自动与 c0c1 结果对账（同名指标差异 >0.01 即 FAIL，不许静默）。
  - Part B 滚动回测：cutoffs 2014/2016/2018/2020 × h=1/3/5，
    每个截点只用 year <= cutoff 的数据训练；目标窗口 = (cutoff, cutoff+h]。
    RSSM 默认排除（预训练 checkpoint 见过全时间线，早截点构成泄漏；
    --with-rssm 可强制加入，结果只作对照并全程标注风险）。
  - 2026 为截至 8 月的部分年度：Part B 全程排除；缺失年份跳过（不补零、不插值）。
  - 逐样本 split_manifest.csv，逐行断言：history_end < target_year 且 target_year > train_cutoff。

v1.1（2026-09-01 晚，ds 验收第一轮后修）：2026 断言改为分部生效（A 保 c0c1 对账口径、B 强制排除）；
  metrics_block 改主题交集；Part B 缺失年按年偏移取预测（修错位）。

v1.2（2026-09-02 凌晨，对账 FAIL 18 格定性后修）：Part A 指标聚合与 c0c1 evaluate_one 逐行对齐
  ——MAE/RMSE/Spearman 逐主题窗向量误差跨年池化（原先逐年平均再平均，各评测年过滤后主题数
  不同产生 0.01 级系统差：h=1/h=3 FAIL、h=5 因窗口长主题数趋同而 PASS）；P@K/NDCG@K 逐年按窗口
  总和排名后跨年均值。根因＝聚合口径差，非数据错、非运行随机性。xgboost 残差属训练环境波动
  （范围已记录），rssm 若仍有残差看 n_topics 是否与 c0c1 的 n_topic_evals 逐格相等。

用法：
  python experiment_baselines_rolling.py            # 完整跑 Part A + Part B
  python experiment_baselines_rolling.py --selftest # 合成小数据冒烟（仅验证代码能跑，数字无意义，禁止引用）

输出（output/baselines_rolling/）：
  baselines_rolling_YYYYMMDD.json
  split_manifest.csv
  baselines_rolling_summary.md   （末尾固定有「我没查的部分」一节）
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from experiment_model_baseline import (
    M0Baseline, M1XGBoost, M2RSSM,
    build_topic_timeseries,
    compute_mae, compute_rmse, compute_spearman,
    compute_precision_at_k, compute_ndcg_at_k,
)
from experiment_model_c0c1 import M1XGBoostLeakFree, set_seed, SEED, HORIZONS, TOP_K, N_EVAL_YEARS

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
C1_PATH = DATA_DIR / "state_vectors_C1_20260827.json"
OUT_DIR = BASE / "output" / "baselines_rolling"
C0C1_RESULTS = BASE / "output" / "experiment_model_c0c1" / "experiment_model_c0c1_results.json"

CUTOFFS = [2014, 2016, 2018, 2020]
PARTIAL_YEAR = 2026          # 部分年度，排除
MIN_TRAIN_LEN = 3            # 滚动回测里主题历史少于此长度则跳过

# 本脚本模型名 → c0c1 结果文件里的模型名（对账用）
NAME_MAP = {
    "naive_last": "M0_last",
    "moving_avg": "M0_ma",
    "linear": "M0_linear",
    "xgboost": "M1_xgboost",
    "rssm": "M2_rssm",
}


# ---------------------------------------------------------------------------
# 新增基线：Drift（按历史平均年度变化外推）
# ---------------------------------------------------------------------------
class DriftBaseline:
    """Drift：最后可见值 + 历史平均年度斜率 × 向前步数。年份不连续时按实际年差算斜率。"""

    name = "drift"

    def predict(self, train_series, horizon):
        ys = [s["year"] for s in train_series]
        hs = [float(s["heat"]) for s in train_series]
        if not hs:
            return [0.0] * horizon
        if len(hs) < 2 or ys[-1] == ys[0]:
            return [hs[-1]] * horizon
        slope = (hs[-1] - hs[0]) / float(ys[-1] - ys[0])
        return [max(0.0, hs[-1] + slope * k) for k in range(1, horizon + 1)]


# ---------------------------------------------------------------------------
# 通用件
# ---------------------------------------------------------------------------
class Manifest:
    """逐样本审计表 + 断言。任何一行违反时间约束，脚本直接崩（不允许静默）。"""

    HEADER = ["part", "model", "origin", "history_start", "history_end",
              "train_cutoff", "target_year", "topic_id", "prediction", "actual"]

    def __init__(self):
        self.rows = []
        self.n_asserted = 0
        self.n_skipped_missing_year = 0
        self.n_skipped_short_history = 0
        self.n_errors = 0

    def add(self, part, model, origin, train_series, target_year, topic, prediction, actual,
            allow_partial_year=False):
        history_start = train_series[0]["year"]
        history_end = train_series[-1]["year"]
        train_cutoff = origin
        assert history_end <= train_cutoff, f"训练越界: {topic} history_end={history_end} > cutoff={train_cutoff}"
        assert history_end < target_year, f"泄漏: {topic} history_end={history_end} >= target={target_year}"
        assert target_year > train_cutoff, f"目标年未超过训练截止: {topic} target={target_year} cutoff={train_cutoff}"
        # Part A 与 c0c1 对账保留旧协议（目标年可含 2026）；Part B 正式口径强制排除 2026
        if not allow_partial_year:
            assert target_year != PARTIAL_YEAR, f"部分年度混入: {topic} target={target_year}"
        self.n_asserted += 1
        self.rows.append([part, model, origin, history_start, history_end,
                          train_cutoff, target_year, topic,
                          round(float(prediction), 6), round(float(actual), 6)])

    def write(self, path: Path):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(self.HEADER)
            w.writerows(self.rows)


def metrics_block(preds_map, actuals_map, top_k=TOP_K):
    """preds_map/actuals_map: {model或topic: [数值列表]}。返回 MAE/RMSE/Spearman/P@K/NDCG@K。"""
    maes, rmses, sps = [], [], []
    for topic, a in actuals_map.items():
        if topic not in preds_map:
            continue  # 该模型在此主题预测缺失（如 M2 个别主题失败），不计入该模型指标
        p = preds_map[topic]
        maes.append(compute_mae(p, a))
        rmses.append(compute_rmse(p, a))
        sps.append(compute_spearman(p, a))
    common = [t for t in actuals_map if t in preds_map]
    actual_ranking = sorted(common, key=lambda t: sum(actuals_map[t]), reverse=True)
    pred_ranking = sorted(common, key=lambda t: sum(preds_map[t]), reverse=True)
    return {
        "MAE": round(float(np.mean(maes)), 4) if maes else None,
        "RMSE": round(float(np.mean(rmses)), 4) if rmses else None,
        "Spearman": round(float(np.mean(sps)), 4) if sps else None,
        f"Precision@{top_k}": round(compute_precision_at_k(pred_ranking, actual_ranking, top_k), 4),
        f"NDCG@{top_k}": round(compute_ndcg_at_k(pred_ranking, actual_ranking, top_k), 4),
        "n_topics": len(actuals_map),
    }


# ---------------------------------------------------------------------------
# Part A：同窗口基线（协议与 c0c1 完全一致；缺失目标年补 0 —— 为与 c0c1 对账保留旧口径，
#         新口径「缺失年跳过」只用于 Part B，两处都在摘要里写明）
# ---------------------------------------------------------------------------
def part_a_same_window(all_ts, years, manifest, notes):
    eval_plan = {}
    for h in HORIZONS:
        max_eval = years[-1] - h
        cand = [y for y in years if y <= max_eval and y >= years[0] + 6]
        eval_plan[h] = cand[-N_EVAL_YEARS:] if len(cand) >= N_EVAL_YEARS else cand
    print(f"[Part A] 统一评测年（与 c0c1 同算法）: {eval_plan}")

    overall = {}   # horizon -> model -> metrics
    for h in HORIZONS:
        set_seed(SEED)
        models_m0 = {
            "naive_last": M0Baseline("last"),
            "moving_avg": M0Baseline("moving_avg"),
            "linear": M0Baseline("linear"),
            "drift": DriftBaseline(),
        }
        m1_cache = {}
        m2 = None
        try:
            m2 = M2RSSM()
            m2.train(all_ts, years)
        except Exception as e:
            notes.append(f"Part A：M2 初始化/加载失败（{e!r}），rssm 列记为 null")
        per_model_agg = defaultdict(lambda: defaultdict(list))

        for eval_year in eval_plan[h]:
            if eval_year not in m1_cache:
                m1 = M1XGBoostLeakFree()
                m1.train_until(all_ts, eval_year)
                m1_cache[eval_year] = m1
            m1 = m1_cache[eval_year]

            preds = defaultdict(dict)    # model -> topic -> [h 步预测]
            actuals = {}                 # topic -> [h 步真值]
            for topic, series in all_ts.items():
                train_series = [s for s in series if s["year"] <= eval_year]
                if not train_series:
                    continue
                a = []
                for hh in range(1, h + 1):
                    fut = [s for s in series if s["year"] == eval_year + hh]
                    a.append(fut[0]["heat"] if fut else 0)   # 与 c0c1 相同的补 0 口径
                if not any(x > 0 for x in a):
                    continue
                actuals[topic] = a
                for name, model in models_m0.items():
                    preds[name][topic] = model.predict(train_series, h)
                preds["xgboost"][topic] = m1.predict(train_series, h)
                if m2 is not None:
                    try:
                        preds["rssm"][topic] = m2.predict(train_series, h, topic)
                    except Exception as e:
                        manifest.n_errors += 1
                        notes.append(f"Part A：M2 预测失败 topic={topic!r}（{e!r}），该主题 rssm 记缺")
                # 逐样本审计（逐步一行）
                for name, p in preds.items():
                    if topic not in p:
                        continue
                    for hh in range(1, h + 1):
                        manifest.add("A_same_window", name, eval_year, train_series,
                                     eval_year + hh, topic, p[topic][hh - 1], a[hh - 1],
                                     allow_partial_year=True)  # 与 c0c1 对账口径：目标年可含 2026

            # v1.2：指标聚合与 c0c1 evaluate_one 逐行对齐——
            # MAE/RMSE/Spearman：逐主题窗向量误差，跨年【池化】（原先逐年平均再平均，
            # 各评测年过滤后主题数不同 → 与 c0c1 出 0.01 级系统差：h=1/h=3 FAIL、h=5 PASS）；
            # P@K/NDCG@K：逐年按窗口总和排名（universe=过滤后∩该模型有预测），跨年均值。
            for name in ["naive_last", "moving_avg", "linear", "drift", "xgboost"] + (["rssm"] if m2 is not None else []):
                if not preds.get(name):
                    continue
                common = [t for t in actuals if t in preds[name]]
                if not common:
                    continue
                actual_ranking = sorted(common, key=lambda t: sum(actuals[t]), reverse=True)
                pred_ranking = sorted(common, key=lambda t: sum(preds[name][t]), reverse=True)
                per_model_agg[name][f"Precision@{TOP_K}"].append(
                    compute_precision_at_k(pred_ranking, actual_ranking, TOP_K))
                per_model_agg[name][f"NDCG@{TOP_K}"].append(
                    compute_ndcg_at_k(pred_ranking, actual_ranking, TOP_K))
                for topic in common:
                    per_model_agg[name]["MAE"].append(compute_mae(preds[name][topic], actuals[topic]))
                    per_model_agg[name]["RMSE"].append(compute_rmse(preds[name][topic], actuals[topic]))
                    per_model_agg[name]["Spearman"].append(compute_spearman(preds[name][topic], actuals[topic]))
                per_model_agg[name]["n_topics"].append(len(common))

        overall[h] = {}
        for name, agg in per_model_agg.items():
            overall[h][name] = {
                k: (round(float(np.mean(v)), 4) if k != "n_topics" else int(sum(v)))
                for k, v in agg.items()
            }
        for name, v in overall[h].items():
            print(f"  h={h} {name:<12s} MAE={v.get('MAE')} P@{TOP_K}={v.get(f'Precision@{TOP_K}')}")
    return {"eval_plan": {str(k): v for k, v in eval_plan.items()}, "overall": {str(k): v for k, v in overall.items()}}


def crosscheck_c0c1(part_a, notes):
    """与 c0c1 既有结果对账。文件不在本地就明说，不编数。"""
    if not C0C1_RESULTS.exists():
        msg = ("c0c1 结果文件不在本地（未随仓库推送），对账跳过。"
               "拿到 experiment_model_c0c1_results.json 放入 output/experiment_model_c0c1/ 后重跑本脚本即可自动对账。")
        notes.append("Part A 对账：" + msg)
        return {"status": "skipped", "reason": msg}
    ref = json.loads(C0C1_RESULTS.read_text(encoding="utf-8"))
    rows = []
    try:
        c1 = ref["results"]["C1_包含阿语"]["horizons"]
    except KeyError:
        notes.append("Part A 对账：c0c1 结果文件结构不认识，跳过")
        return {"status": "skipped", "reason": "c0c1 结果文件结构不认识"}
    for h in HORIZONS:
        ref_h = c1.get(str(h), {}).get("overall", {})
        my_h = part_a["overall"].get(str(h), {})
        for my_name, ref_name in NAME_MAP.items():
            if my_name not in my_h or ref_name not in ref_h:
                continue
            for metric in ["MAE", "Spearman", f"Precision@{TOP_K}"]:
                a, b = my_h[my_name].get(metric), ref_h[ref_name].get(metric)
                if a is None or b is None:
                    continue
                diff = round(abs(float(a) - float(b)), 6)
                rows.append({"horizon": h, "model": my_name, "metric": metric,
                             "本脚本": a, "c0c1": b, "diff": diff,
                             "verdict": "PASS" if diff <= 0.01 else "FAIL"})
    n_fail = sum(1 for r in rows if r["verdict"] == "FAIL")
    print(f"[对账] 与 c0c1 比对 {len(rows)} 格，FAIL {n_fail} 格")
    if n_fail:
        notes.append(f"Part A 对账：{n_fail} 格与 c0c1 不一致（差异>0.01），发群/写论文前必须查明原因")
    return {"status": "done", "n_rows": len(rows), "n_fail": n_fail, "rows": rows}


# ---------------------------------------------------------------------------
# Part B：多截点滚动回测（缺失年跳过；2026 排除；RSSM 默认排除）
# ---------------------------------------------------------------------------
def part_b_rolling(all_ts, years, manifest, notes, with_rssm=False):
    # 排除部分年度：所有序列丢弃 >= 2026 的条目
    all_ts = {t: [s for s in series if s["year"] < PARTIAL_YEAR] for t, series in all_ts.items()}
    results = {}
    for cutoff in CUTOFFS:
        results[str(cutoff)] = {}
        m1 = M1XGBoostLeakFree()
        m1.train_until(all_ts, cutoff)
        m1_ok = getattr(m1, "fitted", False)
        if not m1_ok:
            notes.append(f"Part B：截点 {cutoff} xgboost 未成功训练（样本不足或未安装 xgboost），该截点 xgboost 记 null")
        m2 = None
        if with_rssm:
            try:
                m2 = M2RSSM()
                m2.train(all_ts, years)
                notes.append(f"⚠️ 截点 {cutoff}：RSSM 使用全时间线预训练 checkpoint，存在前瞻风险，结果只作对照")
            except Exception as e:
                notes.append(f"Part B：M2 初始化失败（{e!r}），rssm 列记为 null")
        for h in HORIZONS:
            window = [y for y in range(cutoff + 1, cutoff + h + 1) if y < PARTIAL_YEAR]
            preds = defaultdict(dict)
            actuals = {}
            for topic, series in all_ts.items():
                train_series = [s for s in series if s["year"] <= cutoff]
                if len(train_series) < MIN_TRAIN_LEN:
                    manifest.n_skipped_short_history += 1
                    continue
                fut_map = {s["year"]: s["heat"] for s in series if s["year"] in window}
                if not fut_map:
                    manifest.n_skipped_missing_year += 1
                    continue
                a_years = sorted(fut_map)
                a_vals = [fut_map[y] for y in a_years]
                actuals[topic] = a_vals
                full_pred = {}
                for name, model in [("naive_last", M0Baseline("last")),
                                    ("moving_avg", M0Baseline("moving_avg")),
                                    ("linear", M0Baseline("linear")),
                                    ("drift", DriftBaseline())]:
                    full_pred[name] = model.predict(train_series, h)
                if m1_ok:
                    full_pred["xgboost"] = m1.predict(train_series, h)
                if m2 is not None:
                    try:
                        full_pred["rssm"] = m2.predict(train_series, h, topic)
                    except Exception:
                        manifest.n_errors += 1
                for name, p in full_pred.items():
                    preds[name][topic] = [p[ty - cutoff - 1] for ty in a_years]  # 按年偏移取预测，缺失年不错位
                    for ty in a_years:
                        manifest.add("B_rolling", name, cutoff, train_series,
                                     ty, topic, p[ty - cutoff - 1], fut_map[ty])
            cell = {}
            for name in ["naive_last", "moving_avg", "linear", "drift"] + (["xgboost"] if m1_ok else []) + (["rssm"] if m2 is not None else []):
                if preds.get(name):
                    cell[name] = metrics_block(preds[name], actuals)
            results[str(cutoff)][f"h={h}"] = {"eval_window": window, "overall": cell}
            line = "  ".join(f"{n}={c['MAE']}" for n, c in cell.items())
            print(f"[Part B] cp={cutoff} h={h} 窗口{window}: {line}")
    return results


# ---------------------------------------------------------------------------
# 冒烟自测（合成数据，只验证代码能跑；数字无意义，禁止引用）
# ---------------------------------------------------------------------------
def selftest():
    print("=" * 70)
    print("  SELFTEST：合成数据冒烟，仅验证代码可运行，输出数字无意义，禁止引用")
    print("=" * 70)
    rng = np.random.RandomState(0)
    sv = {}
    for y in range(2000, 2021):
        sv[str(y)] = {f"topic_{i}": {"heat": float(rng.rand() * 100 + i)} for i in range(30)}
    all_ts, years = build_topic_timeseries(sv)
    manifest = Manifest()
    notes = []
    res_b = part_b_rolling(all_ts, years, manifest, notes, with_rssm=False)
    assert manifest.n_asserted > 0, "自测失败：manifest 一行都没有"
    assert any(res_b[c][f"h={h}"]["overall"].get("naive_last") for c in ["2014", "2016", "2018", "2020"] for h in HORIZONS), "自测失败：naive_last 缺格"
    print(f"  manifest 行数={len(manifest.rows)} 断言通过={manifest.n_asserted} 跳过={manifest.n_skipped_missing_year + manifest.n_skipped_short_history}")
    print("SELFTEST PASS（再次强调：以上数字来自合成数据，禁止引用）")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="合成数据冒烟自检（不碰真实数据）")
    ap.add_argument("--with-rssm", action="store_true", help="Part B 强制加入 RSSM（预训练 checkpoint，有前瞻风险，仅作对照）")
    ap.add_argument("--data", default=str(C1_PATH), help="状态向量 JSON 路径")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    set_seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    notes = []
    manifest = Manifest()

    data_path = Path(args.data)
    print("=" * 70)
    print("  同窗口基线 + 多截点滚动时间回测")
    print(f"  数据: {data_path}")
    print("=" * 70)
    sv = json.loads(data_path.read_text(encoding="utf-8"))
    all_ts, years = build_topic_timeseries(sv)
    print(f"  {len(all_ts)} 主题, {years[0]}-{years[-1]} ({len(years)} 个观测年)")
    print(f"  观测年说明：1912—2026 跨 115 个自然年，仅 {len(years)} 个有记录；缺失年跳过（不补零不插值）；{PARTIAL_YEAR} 为部分年度，Part B 已排除")

    print("\n[Part A] 同窗口基线（协议同 c0c1）...")
    part_a = part_a_same_window(all_ts, years, manifest, notes)
    crosscheck = crosscheck_c0c1(part_a, notes)

    print("\n[Part B] 多截点滚动回测...")
    part_b = part_b_rolling(all_ts, years, manifest, notes, with_rssm=args.with_rssm)

    from datetime import date
    stamp = date.today().strftime("%Y%m%d")
    res = {
        "meta": {
            "date": str(date.today()),
            "seed": SEED,
            "data": str(data_path),
            "data_sha256_note": "见 output/data_version_manifest_12233.json",
            "cutoffs": CUTOFFS,
            "horizons": HORIZONS,
            "top_k": TOP_K,
            "missing_year_policy": "Part A 与 c0c1 保持一致补 0（仅用于对账）；Part B 跳过（正式口径）",
            "excluded_years": [PARTIAL_YEAR],
            "rssm_in_rolling": bool(args.with_rssm),
            "rssm_note": "RSSM 预训练 checkpoint 见过全时间线，早截点有前瞻风险；Part B 默认排除",
            "manifest": {
                "n_rows": len(manifest.rows),
                "n_asserted": manifest.n_asserted,
                "n_skipped_missing_year": manifest.n_skipped_missing_year,
                "n_skipped_short_history": manifest.n_skipped_short_history,
                "n_errors": manifest.n_errors,
            },
            "notes": notes,
        },
        "partA_same_window": part_a,
        "partA_crosscheck_vs_c0c1": crosscheck,
        "partB_rolling": part_b,
    }
    res_path = OUT_DIR / f"baselines_rolling_{stamp}.json"
    res_path.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = OUT_DIR / "split_manifest.csv"
    manifest.write(manifest_path)

    # ---------------- 摘要 MD ----------------
    lines = ["# 同窗口基线 + 多截点滚动回测 摘要", "",
             f"- 日期: {date.today()} | SEED={SEED} | 数据: {data_path.name}",
             f"- Part A 协议与 experiment_model_c0c1.py 完全一致（用于对账）；Part B 为滚动截点 {CUTOFFS}，h={HORIZONS}",
             f"- 缺失年份：Part B 跳过（不补零不插值）；部分年度 {PARTIAL_YEAR} 已排除",
             f"- 逐样本审计 {manifest.n_asserted} 行，断言全过；跳过：缺目标年 {manifest.n_skipped_missing_year}、历史过短 {manifest.n_skipped_short_history}、预测异常 {manifest.n_errors}",
             ""]
    lines.append("\n## Part A 同窗口基线（C1）")
    for h in HORIZONS:
        lines.append(f"\n### h={h} 评测年={part_a['eval_plan'][str(h)]}")
        lines.append("| 模型 | MAE | RMSE | Spearman | P@10 | NDCG@10 | n主题 |")
        lines.append("|---|---|---|---|---|---|---|")
        for name, v in part_a["overall"].get(str(h), {}).items():
            lines.append(f"| {name} | {v.get('MAE')} | {v.get('RMSE')} | {v.get('Spearman')} "
                         f"| {v.get(f'Precision@{TOP_K}')} | {v.get(f'NDCG@{TOP_K}')} | {v.get('n_topics')} |")
    lines.append("\n## Part A 与 c0c1 对账")
    if crosscheck["status"] == "done":
        lines.append(f"\n比对 {crosscheck['n_rows']} 格，FAIL {crosscheck['n_fail']} 格（容差 0.01）。FAIL 明细：")
        for r in crosscheck["rows"]:
            if r["verdict"] == "FAIL":
                lines.append(f"- h={r['horizon']} {r['model']} {r['metric']}: 本脚本 {r['本脚本']} vs c0c1 {r['c0c1']}")
        if crosscheck["n_fail"] == 0:
            lines.append("\n全部 PASS。")
    else:
        lines.append(f"\n跳过：{crosscheck['reason']}")
    lines.append("\n## Part B 滚动回测（MAE / Spearman / P@10）")
    for cutoff, cells in part_b.items():
        lines.append(f"\n### 截点 {cutoff}")
        lines.append("| 视野 | 模型 | MAE | Spearman | P@10 | n主题 |")
        lines.append("|---|---|---|---|---|---|")
        for hk, cell in cells.items():
            for name, v in cell["overall"].items():
                lines.append(f"| {hk} | {name} | {v.get('MAE')} | {v.get('Spearman')} "
                             f"| {v.get(f'Precision@{TOP_K}')} | {v.get('n_topics')} |")
    lines.append("\n## 我没查的部分")
    lines.append("")
    lines.append("1. M2 预训练 checkpoint 的实际训练数据截止时间未核验（权重文件本身不可见训练集），Part A 的 rssm 数字沿用 c0c1 同一风险")
    lines.append("2. 早期截点（2014/2016）之前观测年稀疏，线性/drift 在短历史上的稳定性未单独分层")
    lines.append("3. xgboost 在各截点的实际样本量未逐格打印（样本不足时该格为 null 并在 notes 里说明）")
    lines.append("4. topic_year_heat.csv 与本脚本使用的 state_vectors 字段对应关系未核（本脚本直接读 state_vectors）")
    for n in notes:
        lines.append(f"5+. 运行备注：{n}")
    md_path = OUT_DIR / "baselines_rolling_summary.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n[OK] 结果 JSON: {res_path}")
    print(f"[OK] 逐样本审计: {manifest_path}（{len(manifest.rows)} 行）")
    print(f"[OK] 摘要 MD: {md_path}")
    if manifest.n_errors:
        print(f"[WARN] 预测异常 {manifest.n_errors} 次，见摘要「我没查的部分」")


if __name__ == "__main__":
    main()
