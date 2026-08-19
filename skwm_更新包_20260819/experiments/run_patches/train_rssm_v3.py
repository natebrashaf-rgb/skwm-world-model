#!/usr/bin/env python3
"""train_rssm_v3.py — RSSM 增量(delta)重训 + 严格时间划分
============================================================
相对 train_rssm_clean.py 的修复:
  1. 恢复时间划分: 只用 <= SPLIT_YEAR-1 的年份训练 (clean版丢失, 全期训练=泄漏)
  2. 预测目标改为 delta (e_t - e_{t-1}): 持久性由残差连接提供,
     不再要求 GRU 维持高热度水平 -> 治"均值回归塌陷"的病根
  3. 训练主题过滤: 仅训训练期内 max_heat >= MIN_HEAT 的主题 (长尾近零主题
     会把先验拉向"什么都归零")
  4. 训练步数 2000 -> --steps (默认 12000), lr 1e-4
  5. 推理用 imagine_from_history: 先消化 T 步历史再 rollout
     (旧 imagine 只用单帧 x0, 丢弃全部历史)

用法:
    python train_rssm_v3.py                    # 训练 + 快速回测
    python train_rssm_v3.py --steps 20000
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skwm_world_model import WorldModel, WMConfig, train_step

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE, "data", "state_vectors_clean.json")
OUT_DIR = os.path.join(BASE, "output", "rssm_v3")
os.makedirs(OUT_DIR, exist_ok=True)

SEED = 42
LOG_DIMS = (0, 2, 3)   # heat/centrality/connections 做 log1p
RAW_DIMS = (1,)        # growth 保留原值 (可为负)
X_DIM = 4
A_DIM = 4
T = 8                  # 历史窗口
SPLIT_YEAR = 2020      # 训练只用 < SPLIT_YEAR 的年份
MIN_HEAT = 10          # 训练主题过滤: 训练期内 max_heat >= 10
YEAR_START = 1995      # 1995 年后数据密度才够


def encode_vec(vec):
    """[heat, growth, centrality, connections] -> 编码空间"""
    v = np.asarray(vec, dtype=np.float32).copy()
    for d in LOG_DIMS:
        v[d] = np.log1p(max(0.0, float(v[d])))
    return v


def decode_heat(e_heat):
    """编码空间的 log1p(heat) -> 原始热度 (非负)"""
    return float(max(0.0, np.expm1(e_heat)))


def load_series(min_year=YEAR_START, max_year=2026):
    """返回 {topic: {year: encoded_vec}}, 年份连续 zero-fill"""
    sv = json.load(open(DATA_PATH, encoding="utf-8"))
    years = list(range(min_year, max_year + 1))
    topics = set()
    for y in years:
        topics.update(sv.get(str(y), {}).keys())
    series = {}
    for t in topics:
        s = {}
        for y in years:
            raw = sv.get(str(y), {}).get(t, [0, 0, 0, 0])
            s[y] = encode_vec(raw)
        series[t] = s
    return series, years, sv


def build_delta_windows(series, years, topics):
    """{topic: {year: e}} -> delta 滑窗序列 [N, T, 4]"""
    deltas = {}
    for t in topics:
        es = np.stack([series[t][y] for y in years])       # [Y, 4]
        deltas[t] = np.diff(es, axis=0)                    # [Y-1, 4]
    seqs = []
    n_d = len(years) - 1
    for t in topics:
        d = deltas[t]
        for start in range(n_d - T + 1):
            seqs.append(d[start:start + T])
    return np.stack(seqs).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=12000)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--out", type=str, default="model_rssm_v3.pt")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--split-year", type=int, default=SPLIT_YEAR)
    ap.add_argument("--stoch-std", type=float, default=1.0, help="消融: 0=无随机潜状态")
    args = ap.parse_args()

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    split_year = args.split_year

    print("=" * 64)
    print("  RSSM v3 训练  (delta目标 + 时间划分 + 历史窗口推理)")
    print("=" * 64)

    print("\n[1/4] 加载并编码状态向量 ...")
    series, years, sv = load_series()

    train_years = [y for y in years if y < split_year]
    print(f"      全部年份: {years[0]}-{years[-1]} | 训练年份: "
          f"{train_years[0]}-{train_years[-1]} (严格 < {split_year})")

    # 主题过滤: 只看训练期 (不用未来信息)
    topics = [t for t in series
              if max(sv.get(str(y), {}).get(t, [0])[0] for y in train_years)
              >= MIN_HEAT]
    print(f"      训练主题: {len(topics)} 个 (训练期 max_heat>={MIN_HEAT})")

    print("\n[2/4] 构建 delta 滑窗 (T=%d) ..." % T)
    x_data = build_delta_windows(series, train_years, topics)
    print(f"      训练序列: {x_data.shape[0]} 条, shape={list(x_data.shape)}")

    print("\n[3/4] 训练 RSSM (lr=1e-4) ...")
    config = WMConfig(x_dim=X_DIM, a_dim=A_DIM, deter=128, stoch=32,
                      hidden=128, lr=1e-4, stoch_std=args.stoch_std)
    model = WorldModel(config)
    opt = torch.optim.Adam(model.parameters(), lr=config.lr)
    print(f"      参数: {sum(p.numel() for p in model.parameters()):,}")

    N = x_data.shape[0]
    log_entries = []
    t0 = time.time()
    for step in range(args.steps):
        idx = np.random.choice(N, min(args.batch, N))
        xb = torch.tensor(x_data[idx], dtype=torch.float32)
        ab = torch.zeros(xb.shape[0], T, A_DIM)
        logs = train_step(model, opt, xb, ab)
        if step % 1000 == 0 or step == args.steps - 1:
            log_entries.append({"step": step, **logs})
            print(f"      step {step:5d}: pred={logs['pred']:.4f} "
                  f"dyn={logs['dyn']:.4f} rep={logs['rep']:.4f} "
                  f"({time.time()-t0:.0f}s)")

    model_path = os.path.join(BASE, args.out)
    payload = {
        "model": model.state_dict(),
        "config": config.__dict__,
        "meta": {
            "version": "v3",
            "target": "delta (e_t - e_{t-1}, 编码空间)",
            "encode": "log1p for dims (0,2,3); raw for dim 1",
            "split_year": split_year,
            "train_years": [train_years[0], train_years[-1]],
            "year_start": YEAR_START,
            "min_heat_train": MIN_HEAT,
            "n_topics_train": len(topics),
            "n_sequences": int(N),
            "T": T,
            "steps": args.steps,
            "batch": args.batch,
            "seed": args.seed,
            "stoch_std": args.stoch_std,
            "inference": "imagine_from_history (先验均值=点估计; 采样xB=不确定性)",
            "train_log": log_entries,
        },
    }
    torch.save(payload, model_path)
    md5 = hashlib.md5(open(model_path, "rb").read()).hexdigest()[:12]
    print(f"\n[4/4] 模型已保存: {model_path} "
          f"({os.path.getsize(model_path)//1024}KB, md5={md5})")

    # ---------------- 快速自检回测 (严格样本外) ----------------
    print("\n[自检] 样本外回测 (eval年 > 2019, 模型未见) ...")
    model.eval()
    check = {}
    for h in (1, 3):
        eval_years = [y for y in (2021, 2022, 2023, 2024) if y + h <= 2026]
        level_mae, g_prec = [], []
        for ey in eval_years:
            hist_years = [y for y in years if y <= ey][-(T + 1):]
            cand = [t for t in series
                    if sv.get(str(ey), {}).get(t, [0])[0] >= 5]
            if len(hist_years) < T + 1 or not cand:
                continue
            H = np.stack([np.diff(np.stack([series[t][y] for y in hist_years]),
                                  axis=0)[-T:] for t in cand]).astype(np.float32)
            with torch.no_grad():
                pd = model.imagine_from_history(
                    torch.tensor(H), torch.zeros(len(cand), h, A_DIM),
                    deterministic=True).numpy()          # [N, h, 4] delta
            last_e = np.stack([series[t][ey] for t in cand])   # [N, 4]
            pred_e = last_e[:, None, :] + np.cumsum(pd, axis=1)
            pred_heat = np.maximum(0, np.expm1(pred_e[:, :, 0]))  # [N, h]
            cur_heat = np.array([sv.get(str(ey), {}).get(t, [0])[0]
                                 for t in cand])
            act_heat = np.array([[sv.get(str(ey + k), {}).get(t, [0])[0]
                                  for k in range(1, h + 1)] for t in cand])
            level_mae.append(np.abs(pred_heat - act_heat).mean())
            # 增速榜 P@10: 预测累计增量 vs 实际累计增量
            pg = pred_heat[:, -1] - cur_heat
            ag = act_heat[:, -1] - cur_heat
            p10 = set(np.argsort(-pg)[:10])
            a10 = set(np.argsort(-ag)[:10])
            g_prec.append(len(p10 & a10) / 10)
        check[f"h{h}"] = {
            "eval_years": eval_years,
            "level_MAE": round(float(np.mean(level_mae)), 3),
            "growth_P@10": round(float(np.mean(g_prec)), 3),
        }
        print(f"      h={h}: level_MAE={check[f'h{h}']['level_MAE']}, "
              f"growth榜P@10={check[f'h{h}']['growth_P@10']}  (eval={eval_years})")

    with open(os.path.join(OUT_DIR, "v3_selfcheck.json"), "w",
              encoding="utf-8") as f:
        json.dump({"meta": payload["meta"], "selfcheck": check,
                   "md5": md5}, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 自检报告: {os.path.join(OUT_DIR, 'v3_selfcheck.json')}")


if __name__ == "__main__":
    main()
