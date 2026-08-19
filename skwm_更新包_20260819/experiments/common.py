# -*- coding: utf-8 -*-
"""common.py — 流水线公共模块: 数据加载/编码/时间划分/指标
========================================================
统一约定 (实验1-4 全部遵守):
  - 观测数据: data/state_vectors.json (已清洗, 与 state_vectors_clean.json 一致)
  - 状态向量: [heat, growth, centrality, connections]
  - 编码:     log1p(heat), growth(原值), log1p(centrality), log1p(connections)
  - 时间划分: 训练 <= 2015 (冻结), 验证目标年 2016-2020, 测试目标年 2021-2025
  - 未来信息泄漏防护: 任何模型的训练/特征只使用 <= 评测年(eval_year) 的观测;
    训练冻结 <=2015 的模型在预测时也只用 <= eval_year 的历史窗口做推理。
  - 候选主题: 评测年 heat >= MIN_HEAT_EVAL (与 v3 一致, 排除死主题)
"""
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, t as t_dist

BASE = Path(__file__).resolve().parent
RUN = BASE.parent / "run"   # 数据/模型所在目录 (skwm_work/run)
DATA_PATH = RUN / "data" / "state_vectors.json"
OUT = BASE / "output"
for _d in ("check", "dataset", "backtest", "emerging", "ablation",
           "robustness", "service_materials", "figures", "logs"):
    (OUT / _d).mkdir(parents=True, exist_ok=True)

# ---- 时间划分 (用户协议) ----
TRAIN_END = 2015      # 训练只使用 <= 2015
VAL_YEARS = list(range(2016, 2021))   # 目标年 2016-2020
TEST_YEARS = list(range(2021, 2026))  # 目标年 2021-2025
YEAR_START = 1995
YEAR_END = 2025        # 2026 为不完整年, 不作为预测目标

LOG_DIMS = (0, 2, 3)   # heat/centrality/connections -> log1p
MIN_HEAT_EVAL = 5      # 评测候选: 评测年 heat >= 5
T = 8                  # 历史窗口长度 (RSSM/GRU 训练与推理)

SEEDS_B1 = [42, 43, 44, 45, 46]
SEEDS_B2 = [42, 43, 44]
SEEDS_M = [42, 43]


def load_state_vectors():
    sv = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return sv


def years_available(sv):
    return [int(k) for k in sv if k != "_wm" and isinstance(sv[k], dict)]


def encode_vec(vec):
    v = np.asarray(vec, dtype=np.float32).copy()
    for d in LOG_DIMS:
        v[d] = np.log1p(max(0.0, float(v[d])))
    return v


def build_matrices(sv, years=None):
    """返回:
      raw: {topic: {year: [heat, growth, cen, conn]}}  (原值)
      enc: {topic: {year: encoded[4]}}
      years: 排序后的年份列表
    主题按键排序 -> 跨进程可复现
    """
    if years is None:
        years = sorted(y for y in years_available(sv) if YEAR_START <= y <= YEAR_END)
    topics = set()
    for y in years:
        topics.update(sv.get(str(y), {}).keys())
    topics = sorted(topics)
    raw = {t: {y: list(sv.get(str(y), {}).get(t, [0, 0, 0, 0])) for y in years}
           for t in topics}
    enc = {t: {y: encode_vec(raw[t][y]) for y in years} for t in topics}
    return raw, enc, years


def topic_language(name):
    """主题名语言判定: ar / zh / en (用于稳健性分层)"""
    if any("\u0600" <= c <= "\u06FF" for c in name):
        return "ar"
    if any("\u4e00" <= c <= "\u9fff" for c in name):
        return "zh"
    return "en"


# ---------------- 指标 ----------------
def mae(pred, actual):
    n = min(len(pred), len(actual))
    return float(np.mean([abs(pred[i] - actual[i]) for i in range(n)])) if n else float("nan")


def rmse(pred, actual):
    n = min(len(pred), len(actual))
    return float(np.sqrt(np.mean([(pred[i] - actual[i]) ** 2 for i in range(n)]))) if n else float("nan")


def spearman(pred, actual):
    if len(pred) < 3 or len(actual) < 3:
        return float("nan")
    rho, _ = spearmanr(pred, actual)
    return float(rho) if not np.isnan(rho) else float("nan")


def topk_hits(pred_rank, actual_rank, k=10):
    """|pred@k ∩ actual@k| / k — 即 Precision@k; 当 relevant=actual@k 时 Recall@k 同值"""
    p = set(pred_rank[:k])
    a = set(actual_rank[:k])
    return len(p & a) / k


def recall_at_k(pred_rank, relevant, k=10):
    """Recall@k = |pred@k ∩ relevant| / |relevant| (relevant=实际新兴集合时才有意义)"""
    p = set(pred_rank[:k])
    r = set(relevant)
    return len(p & r) / max(1, len(r))


def ndcg_at_k(pred_rank, actual_rank, k=10):
    dcg = 0.0
    a_rank = {t: i for i, t in enumerate(actual_rank[:k])}
    for i, t in enumerate(pred_rank[:k]):
        if t in a_rank:
            dcg += 1.0 / np.log2(i + 2)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(k, len(actual_rank))))
    return dcg / max(idcg, 1e-10)


def ci95(vals):
    """均值 / 标准差 / 95% t 置信区间 (n>=2; n=1 时 CI 为 nan)"""
    vals = np.asarray([v for v in vals if v == v], dtype=float)
    if len(vals) == 0:
        return None, None, (None, None)
    mu = float(vals.mean())
    sd = float(vals.std(ddof=1)) if len(vals) > 1 else float("nan")
    if len(vals) > 1:
        se = sd / math.sqrt(len(vals))
        hw = t_dist.ppf(0.975, len(vals) - 1) * se
        return mu, sd, (mu - hw, mu + hw)
    return mu, sd, (None, None)


# ---------------- 实验1/3 共享的评测函数 ----------------
def eval_years_for(h, targets=None):
    """eval_year = target - h, target ∈ val∪test, 且 eval 有足够历史"""
    if targets is None:
        targets = VAL_YEARS + TEST_YEARS
    return [t - h for t in targets if t - h >= YEAR_START + T]


def compute_metrics(preds, raw, years, eval_year, h, k=10):
    """preds: {topic: (levels[h], deltas[h])} → 单评测年指标 (level + growth 两套)"""
    actual_lv, actual_g, pred_lv, pred_g = {}, {}, {}, {}
    for t, (lv, dt) in preds.items():
        a_lv = np.array([raw[t].get(eval_year + kk, [0])[0] for kk in range(1, h + 1)])
        if not np.any(a_lv > 0):
            continue
        cur = raw[t][eval_year][0]
        actual_lv[t] = a_lv[-1]
        actual_g[t] = a_lv[-1] - cur
        pred_lv[t] = lv[-1]
        pred_g[t] = dt[-1]

    pl = {t: pred_lv[t] for t in pred_lv if t in actual_lv}
    pg = {t: pred_g[t] for t in pred_g if t in actual_g}
    if not pl:
        return None
    keys = sorted(pl)
    r_lv = sorted(pl, key=pl.get, reverse=True)
    a_lv_r = sorted(pl, key=actual_lv.get, reverse=True)
    out = {"eval_year": eval_year, "n_topics": len(keys),
           "level_MAE": round(float(np.mean([abs(pl[t] - actual_lv[t]) for t in keys])), 4),
           "level_RMSE": round(float(np.sqrt(np.mean([(pl[t] - actual_lv[t]) ** 2 for t in keys]))), 4),
           "level_Spearman": round(C_spearman([pl[t] for t in keys], [actual_lv[t] for t in keys]), 4),
           f"heat_P@{k}": round(float(topk_hits(r_lv, a_lv_r, k)), 4),
           f"heat_R@{k}": round(float(recall_at_k(r_lv, a_lv_r[:k], k)), 4),
           f"heat_NDCG@{k}": round(float(ndcg_at_k(r_lv, a_lv_r, k)), 4)}
    if pg:
        keys_g = sorted(pg)
        r_g = sorted(pg, key=pg.get, reverse=True)
        a_g_r = sorted(pg, key=actual_g.get, reverse=True)
        out.update({
            "growth_Spearman": round(C_spearman([pg[t] for t in keys_g], [actual_g[t] for t in keys_g]), 4),
            f"growth_P@{k}": round(float(topk_hits(r_g, a_g_r, k)), 4),
            f"growth_R@{k}": round(float(recall_at_k(r_g, a_g_r[:k], k)), 4),
            f"growth_NDCG@{k}": round(float(ndcg_at_k(r_g, a_g_r, k)), 4)})
    return out


def C_spearman(a, b):
    v = spearman(a, b)
    return v if v == v else 0.0
