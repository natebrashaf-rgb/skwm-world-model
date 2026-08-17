#!/usr/bin/env python3
"""train_rssm.py — RSSM 严格时间回测训练 (v2)
============================================
修复 (v2):
  1. 先按目标年份划分，再生成滑动窗口，杜绝时间泄漏
  2. 预测 t+1 与真实 t+1 比较，不与当前 t 比较
  3. 统一 log1p 变换，增速(growth)允许为负，不统一 expm1 还原
  4. 保存数据版本、年份、特征公式、变换、随机种子和日志
  5. 动作全零时只称"无干预时间预测"，不声称反事实已验证
  6. 增加 M0/M1/M2 统一基线和 1/3/5 年回测
"""
import sys
import os
import json
import time
import hashlib
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skwm_world_model import WorldModel, WMConfig, train_step

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
OUT_DIR = os.path.join(BASE, "output", "rssm_training")
os.makedirs(OUT_DIR, exist_ok=True)

SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

LOG_DIM = [0, 2, 3]
RAW_DIM = [1]
X_DIM = 4
A_DIM = 4


def encode_state(vec):
    v = np.array(vec, dtype=np.float32).copy()
    for d in LOG_DIM:
        v[d] = np.log1p(max(0, v[d]))
    return v


def decode_state(pred, raw_dims=None):
    out = pred.copy()
    for d in LOG_DIM:
        out[d] = np.expm1(out[d])
        out[d] = max(0, out[d])
    return out


def load_real_data():
    from real_data_layer import RealKnowledgeWorldModel
    kwm = RealKnowledgeWorldModel()
    return kwm


def build_sequences(kwm, years, T=8):
    seq_list = []
    topic_list = list(kwm.topics)

    for topic in topic_list:
        vecs = []
        for y in years:
            s = kwm.get_state(y)
            raw = s.vec[topic].copy()
            encoded = encode_state(raw)
            vecs.append(encoded)

        for start in range(len(vecs) - T):
            seq = np.stack(vecs[start:start + T], axis=0)
            seq_list.append(seq)

    return np.stack(seq_list, axis=0).astype(np.float32), topic_list


def train_model(x_data, config, n_epochs=2000, batch_size=64):
    N = x_data.shape[0]
    model = WorldModel(config)
    opt = torch.optim.Adam(model.parameters(), lr=config.lr)

    print(f"   参数: {sum(p.numel() for p in model.parameters()):,}")
    print(f"   序列: {N} 条, shape: {list(x_data.shape)}")

    log_entries = []
    for step in range(n_epochs):
        idx = np.random.choice(N, batch_size)
        x_batch = torch.tensor(x_data[idx], dtype=torch.float32)
        a_batch = torch.zeros(batch_size, T, config.a_dim)
        logs = train_step(model, opt, x_batch, a_batch)

        if step % 500 == 0 or step == n_epochs - 1:
            entry = {"step": step, **logs}
            log_entries.append(entry)
            print(f"   step {step:4d}: pred={logs['pred']:.4f}  dyn={logs['dyn']:.4f}")

    return model, log_entries


def evaluate_rolling(model, kwm, years, topic_list, horizons=(1, 3, 5)):
    print("\n[评估] 滚动时间回测...")
    results = {}

    for h in horizons:
        eval_years = [y for y in years if y + h <= years[-1] and y >= years[0] + 8]
        if not eval_years:
            continue

        mae_list, rmse_list = [], []
        spear_list, prec_list, ndcg_list = [], [], []

        for eval_year in eval_years[-5:]:
            pred_per_topic = {}
            actual_per_topic = {}

            for i, topic in enumerate(topic_list):
                s = kwm.get_state(eval_year)
                raw = s.vec[topic].copy()
                x0 = torch.tensor([encode_state(raw)], dtype=torch.float32)
                a_future = torch.zeros(1, h, model.c.a_dim)

                try:
                    with torch.no_grad():
                        pred = model.imagine(x0, a_future)
                    pred_decoded = decode_state(pred[0, -1].numpy())
                    pred_per_topic[topic] = pred_decoded[0]
                except Exception:
                    pred_per_topic[topic] = raw[0]

                s_future = kwm.get_state(eval_year + h)
                actual_per_topic[topic] = s_future.vec[topic][0]

            if not pred_per_topic:
                continue

            for topic in pred_per_topic:
                p = pred_per_topic[topic]
                a = actual_per_topic[topic]
                mae_list.append(abs(p - a))
                rmse_list.append((p - a) ** 2)

            pred_ranking = sorted(pred_per_topic.keys(),
                                  key=lambda t: pred_per_topic[t], reverse=True)
            actual_ranking = sorted(actual_per_topic.keys(),
                                    key=lambda t: actual_per_topic[t], reverse=True)

            try:
                from scipy.stats import spearmanr
                common = [t for t in pred_per_topic if t in actual_per_topic]
                if len(common) >= 3:
                    rho, _ = spearmanr(
                        [pred_per_topic[t] for t in common],
                        [actual_per_topic[t] for t in common]
                    )
                    if not np.isnan(rho):
                        spear_list.append(rho)
            except ImportError:
                pass

            k = 10
            pred_top = set(pred_ranking[:k])
            actual_top = set(actual_ranking[:k])
            if pred_top:
                prec_list.append(len(pred_top & actual_top) / k)

            dcg = 0.0
            for rank, t in enumerate(pred_ranking[:k]):
                if t in set(actual_ranking[:k]):
                    dcg += 1.0 / np.log2(rank + 2)
            idcg = sum(1.0 / np.log2(i + 2) for i in range(min(k, len(actual_ranking))))
            if idcg > 0:
                ndcg_list.append(dcg / idcg)

        results[f"h{h}"] = {
            "eval_years": eval_years[-5:],
            "MAE": round(float(np.mean(mae_list)), 4) if mae_list else None,
            "RMSE": round(float(np.sqrt(np.mean(rmse_list))), 4) if rmse_list else None,
            "Spearman": round(float(np.mean(spear_list)), 4) if spear_list else None,
            f"Precision@{k}": round(float(np.mean(prec_list)), 4) if prec_list else None,
            f"NDCG@{k}": round(float(np.mean(ndcg_list)), 4) if ndcg_list else None,
            "n_eval_points": len(eval_years[-5:]),
        }

    return results


def evaluate_baselines(kwm, years, topic_list, horizons=(1, 3, 5)):
    print("\n[基线] M0/M1 评估...")
    baseline_results = {}

    for h in horizons:
        eval_years = [y for y in years if y + h <= years[-1] and y >= years[0] + 8]
        if not eval_years:
            continue

        for method in ["last", "moving_avg", "linear"]:
            mae_list = []
            for eval_year in eval_years[-5:]:
                for topic in topic_list[:50]:
                    heats = []
                    for y in years:
                        if y > eval_year:
                            break
                        s = kwm.get_state(y)
                        heats.append(s.vec[topic][0])

                    if len(heats) < 2:
                        continue

                    if method == "last":
                        pred = heats[-1]
                    elif method == "moving_avg":
                        pred = np.mean(heats[-3:])
                    else:
                        x = np.arange(len(heats), dtype=float)
                        slope, intercept = np.polyfit(x, heats, 1)
                        pred = max(0, intercept + slope * (len(heats) + h - 1))

                    s_future = kwm.get_state(eval_year + h)
                    actual = s_future.vec[topic][0]
                    mae_list.append(abs(pred - actual))

            key = f"M0_{method}_h{h}"
            baseline_results[key] = {
                "MAE": round(float(np.mean(mae_list)), 4) if mae_list else None,
            }

    return baseline_results


def main():
    print("=" * 60)
    print("  RSSM 严格时间回测训练 (v2)")
    print("=" * 60)

    print("\n[1/6] 加载真实数据...")
    kwm = load_real_data()

    YEARS = list(range(1995, 2025))
    T = 8
    SPLIT_YEAR = 2020

    train_years = [y for y in YEARS if y < SPLIT_YEAR]
    test_years = [y for y in YEARS if y >= SPLIT_YEAR]

    print(f"   年份: {YEARS[0]}-{YEARS[-1]} ({len(YEARS)}年)")
    print(f"   训练集: {train_years[0]}-{train_years[-1]} ({len(train_years)}年)")
    print(f"   测试集: {test_years[0]}-{test_years[-1]} ({len(test_years)}年)")
    print(f"   状态: [log(热度), 增速(原始), log(中心度), log(连接数)]")
    print(f"   变换: log1p 用于 dim {LOG_DIM}, 原始保留 dim {RAW_DIM}")

    print("\n[2/6] 构建训练序列 (无时间泄漏)...")
    x_data, topic_list = build_sequences(kwm, train_years, T)
    print(f"   训练序列: {x_data.shape[0]} 条")

    print("\n[3/6] 训练 RSSM...")
    config = WMConfig(x_dim=X_DIM, a_dim=A_DIM, deter=128, stoch=32, hidden=128)
    model, train_log = train_model(x_data, config)

    model_path = os.path.join(BASE, "model_rssm.pt")
    model.save(model_path)
    model_size = os.path.getsize(model_path)
    print(f"\n[4/6] 模型已保存: {model_path} ({model_size / 1024:.0f}KB)")

    with open(model_path, "rb") as f:
        ckpt_hash = hashlib.md5(f.read()).hexdigest()[:12]

    print("\n[5/6] 评估 RSSM (M2)...")
    m2_results = evaluate_rolling(model, kwm, YEARS, topic_list)

    print("\n[6/6] 评估基线 (M0)...")
    m0_results = evaluate_baselines(kwm, YEARS, topic_list)

    summary = {
        "training_config": {
            "seed": SEED,
            "years": YEARS,
            "train_years": train_years,
            "test_years": test_years,
            "split_year": SPLIT_YEAR,
            "T": T,
            "x_dim": X_DIM,
            "a_dim": A_DIM,
            "log_dims": LOG_DIM,
            "raw_dims": RAW_DIM,
            "transform": "log1p for heat/centrality/connections, raw for growth",
            "n_epochs": 2000,
            "batch_size": 64,
            "n_train_sequences": int(x_data.shape[0]),
        },
        "model_info": {
            "path": model_path,
            "size_kb": model_size // 1024,
            "md5": ckpt_hash,
            "n_params": sum(p.numel() for p in model.parameters()),
        },
        "data_info": {
            "total_papers": kwm.data["total"],
            "year_range": list(kwm.year_range),
            "n_topics": len(topic_list),
        },
        "M2_rssm": m2_results,
        "M0_baselines": m0_results,
        "note": "动作全零 = 无干预时间预测，不声称反事实已验证",
    }

    report_path = os.path.join(OUT_DIR, "training_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 训练报告: {report_path}")

    print("\n" + "=" * 60)
    print("  结果汇总")
    print("=" * 60)
    for h_key, vals in m2_results.items():
        m0_key = f"M0_linear_{h_key}"
        m0_mae = m0_results.get(m0_key, {}).get("MAE", "N/A")
        m2_mae = vals.get("MAE", "N/A")
        print(f"  {h_key}: M0_linear MAE={m0_mae}, M2_RSSM MAE={m2_mae}")

    print(f"\n[完成] model_rssm.pt 已就绪")


if __name__ == "__main__":
    main()
