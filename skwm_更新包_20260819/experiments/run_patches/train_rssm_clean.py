#!/usr/bin/env python3
"""train_rssm_clean.py — 在清洗后的 state_vectors 上重训 RSSM
================================================================
与 train_rssm.py 相同的协议 (log1p 变换 / 滑动窗口 / 同损失), 但:
  1. 直接读 data/state_vectors.json (已过滤主题噪声)
  2. 无 real_data_layer 依赖, 可独立运行
  3. 输出 model_rssm_new.pt {'model', 'config', 'meta'}

用法:
    python train_rssm_clean.py [--steps 2000] [--batch 64] [--seed 42]
"""
import argparse
import json
import os
import sys
import time
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skwm_world_model import WorldModel, WMConfig, train_step  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
OUT_DIR = os.path.join(BASE, "output", "rssm_training")
os.makedirs(OUT_DIR, exist_ok=True)

LOG_DIM = [0, 2, 3]   # heat/centrality/connections: log1p
RAW_DIM = [1]         # growth: 原值
T = 8


def encode_state(vec):
    v = np.array(vec, dtype=np.float32).copy()
    for d in LOG_DIM:
        v[d] = np.log1p(max(0, v[d]))
    return v


def load_state_vectors():
    path = os.path.join(DATA_DIR, "state_vectors.json")
    return json.loads(open(path, encoding="utf-8").read())


def build_sequences(sv, years):
    """每个主题: 每年向量 → 滑动窗口 (T=8), 与 train_rssm.py 一致"""
    topics = set()
    for y in years:
        topics.update(sv[str(y)].keys())

    seq_list, topic_list = [], []
    for topic in sorted(topics):
        vecs = []
        for y in years:
            v = sv[str(y)].get(topic, [0, 0, 0, 0])
            if isinstance(v, (list, tuple)) and len(v) >= 4:
                vecs.append(encode_state(v))
            else:
                vecs.append(np.zeros(4, dtype=np.float32))
        if len(vecs) < T + 1:
            continue
        for start in range(len(vecs) - T):
            seq = np.stack(vecs[start:start + T], axis=0)
            # 跳过全零窗口(纯噪声序列)
            if seq[:, 0].max() <= 1e-6:
                continue
            seq_list.append(seq)
            topic_list.append(topic)
    return np.stack(seq_list, axis=0).astype(np.float32), topic_list


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=2000)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="model_rssm_new.pt")
    args = parser.parse_args()

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    print("=" * 60)
    print("  RSSM 重训 (清洗后 state_vectors)")
    print("=" * 60)

    sv = load_state_vectors()
    years = sorted(int(k) for k in sv if k != "_wm" and isinstance(sv[k], dict))
    print(f"[数据] {years[0]}-{years[-1]} ({len(years)}年)")

    x_data, topic_list = build_sequences(sv, years)
    print(f"[序列] {x_data.shape[0]} 条, shape {list(x_data.shape)}")

    config = WMConfig(x_dim=4, a_dim=4, deter=128, stoch=32, hidden=128)
    model = WorldModel(config)
    opt = torch.optim.Adam(model.parameters(), lr=config.lr)
    print(f"[模型] 参数: {sum(p.numel() for p in model.parameters()):,}")

    N = x_data.shape[0]
    t0 = time.time()
    for step in range(args.steps):
        idx = np.random.choice(N, args.batch)
        x_batch = torch.tensor(x_data[idx], dtype=torch.float32)
        a_batch = torch.zeros(args.batch, T, config.a_dim)
        logs = train_step(model, opt, x_batch, a_batch)
        if step % 500 == 0 or step == args.steps - 1:
            print(f"   step {step:4d}/{args.steps}  "
                  f"pred={logs['pred']:.4f} dyn={logs['dyn']:.4f} "
                  f"({time.time()-t0:.0f}s)")

    meta = {
        "trained_on": "state_vectors_clean (topic noise filtered)",
        "years": [years[0], years[-1]],
        "n_sequences": int(N),
        "steps": args.steps,
        "batch": args.batch,
        "seed": args.seed,
        "transform": {"log1p_dims": LOG_DIM, "raw_dims": RAW_DIM},
        "time_seconds": round(time.time() - t0, 1),
    }
    out_path = os.path.join(BASE, args.out)
    torch.save({"model": model.state_dict(),
                "config": vars(config),
                "meta": meta}, out_path)
    print(f"\n[OK] 已保存: {out_path} (meta: {meta['time_seconds']}s)")


if __name__ == "__main__":
    main()
