# -*- coding: utf-8 -*-
"""02_models.py — 模型定义 (交付物 #3)
====================================
统一接口: predict(raw, enc, years, eval_year, horizon) -> {topic: (levels[h], deltas[h])}
  levels: 预测的 heat 水平序列 (h 步)
  deltas: 相对 eval_year 的增量序列 (h 步)

B0: 持续性基线 (去年值/移动平均/线性)      — 无训练
B1: XGBoost 回归 (冻结训练<=2015, 递归多步)
B2: GRU 时序模型 (冻结训练<=2015, 递归多步)
M : RSSM (delta 目标, imagine_from_history, deterministic)
消融变体 (实验3):
  A_full   = M (完整 RSSM)
  B_nostoch= RSSM 且 stoch_std=0 (无随机潜状态)
  C_nodyn  = 前馈 MLP 窗口回归 (无动态状态转移)
  D_gru    = B2 (普通 GRU)
"""
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# ---------------- B0: 持续性基线 ----------------
class B0:
    def __init__(self, method="last"):
        self.method = method

    def predict(self, raw, enc, years, eval_year, horizon):
        out = {}
        for t in raw:
            heats = [raw[t][y][0] for y in years if y <= eval_year]
            if not heats:
                continue
            if self.method == "last":
                lv = np.full(horizon, heats[-1])
            elif self.method == "ma":
                lv = np.full(horizon, np.mean(heats[-3:]))
            else:  # linear
                x = np.arange(len(heats))
                if len(heats) < 2:
                    lv = np.full(horizon, heats[-1])
                else:
                    slope, icept = np.polyfit(x, heats, 1)
                    lv = np.maximum(0, icept + slope * (len(heats) + np.arange(horizon)))
            cur = heats[-1]
            deltas = np.diff(np.concatenate([[cur], lv]))
            out[t] = (lv.astype(float), deltas.astype(float))
        return out


# ---------------- B1: XGBoost (冻结训练<=2015, 递归) ----------------
class B1:
    def __init__(self, seed=42):
        self.seed = seed
        self.model = None

    def fit(self, raw, enc, years):
        from xgboost import XGBRegressor
        X, Y = [], []
        train_years = [y for y in years if y <= C.TRAIN_END]
        for t in raw:
            for i in range(5, len(train_years)):
                ys = train_years[i - 5:i]
                f = []
                for y in ys:
                    f.extend(raw[t][y])
                f.append(ys[-1])
                X.append(f)
                Y.append(raw[t][train_years[i]][0])
        X, Y = np.array(X, dtype=np.float32), np.array(Y, dtype=np.float32)
        self.model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.08,
                                  subsample=0.8, colsample_bytree=0.8,
                                  random_state=self.seed, nthread=1, verbosity=0)
        self.model.fit(X, Y)
        return self

    def predict(self, raw, enc, years, eval_year, horizon):
        out = {}
        for t in raw:
            hist = {y: list(raw[t][y]) for y in years if y <= eval_year}
            preds = []
            for _ in range(horizon):
                ys = sorted(hist)[-5:]
                if len(ys) < 5:
                    break
                f = []
                for y in ys:
                    f.extend(hist[y])
                f.append(ys[-1])
                p = float(max(0, self.model.predict(np.array([f], dtype=np.float32))[0]))
                preds.append(p)
                hist[ys[-1] + 1] = [p, 0, 0, 0]
            if not preds:
                continue
            lv = np.array(preds)
            cur = raw[t][eval_year][0]
            deltas = np.diff(np.concatenate([[cur], lv]))
            out[t] = (lv.astype(float), deltas.astype(float))
        return out


# ---------------- B2: GRU (冻结训练<=2015) ----------------
class B2GRU:
    def __init__(self, seed=42, hidden=64, epochs=60, lr=1e-3):
        self.seed = seed
        self.hidden = hidden
        self.epochs = epochs
        self.lr = lr
        self.model = None

    def _windows(self, enc, years):
        train_years = [y for y in years if y <= C.TRAIN_END]
        X, Y = [], []
        for t in enc:
            vecs = np.stack([enc[t][y] for y in train_years])          # [n,4]
            deltas = np.diff(vecs, axis=0)                             # [n-1,4]
            for i in range(C.T - 1, len(deltas) - 1):
                X.append(deltas[i - C.T + 1:i + 1])
                Y.append(deltas[i + 1])
        X = np.stack(X).astype(np.float32) if X else np.zeros((0, C.T, 4), np.float32)
        Y = np.stack(Y).astype(np.float32) if Y else np.zeros((0, 4), np.float32)
        return X, Y

    def fit(self, raw, enc, years):
        import torch
        import torch.nn as nn
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        X, Y = self._windows(enc, years)
        print(f"    [B2] GRU 训练样本 {len(X)} 条")

        class GRU(nn.Module):
            def __init__(s):
                super().__init__()
                s.gru = nn.GRU(4, self.hidden, batch_first=True)
                s.fc = nn.Linear(self.hidden, 4)

            def forward(s, x):
                _, h = s.gru(x)
                return s.fc(h[-1])

        net = GRU()
        opt = torch.optim.Adam(net.parameters(), lr=self.lr)
        lossf = nn.MSELoss()
        Xt = torch.tensor(X)
        Yt = torch.tensor(Y)
        n = len(Xt)
        for ep in range(self.epochs):
            idx = np.random.choice(n, min(256, n))
            opt.zero_grad()
            loss = lossf(net(Xt[idx]), Yt[idx])
            loss.backward()
            opt.step()
        self.model = net
        return self

    def predict(self, raw, enc, years, eval_year, horizon):
        import torch
        out = {}
        for t in enc:
            hist_years = [y for y in years if y <= eval_year][-(C.T + 1):]
            if len(hist_years) < C.T + 1:
                continue
            es = np.stack([enc[t][y] for y in hist_years])
            deltas = np.diff(es, axis=0)[-C.T:]                        # [T,4]
            cur_e = enc[t][eval_year]
            preds = []
            with torch.no_grad():
                x = torch.tensor(deltas[None].astype(np.float32))
                for _ in range(horizon):
                    d = self.model(x).numpy()[0]
                    cur_e = cur_e + d
                    preds.append(float(np.expm1(max(0.0, cur_e[0]))))
                    x = torch.cat([x[:, 1:], torch.tensor(d[None, None].astype(np.float32))], dim=1)
            if not preds:
                continue
            lv = np.array(preds)
            cur = raw[t][eval_year][0]
            deltas_out = np.diff(np.concatenate([[cur], lv]))
            out[t] = (lv.astype(float), deltas_out.astype(float))
        return out


# ---------------- M: RSSM (delta 目标) ----------------
class M_RSSM:
    def __init__(self, model_path):
        import sys as _sys
        _sys.path.insert(0, str(C.RUN))   # skwm_world_model 在 run/ 目录
        import torch
        from skwm_world_model import WorldModel, WMConfig
        self.torch = torch
        data = torch.load(str(model_path), map_location="cpu", weights_only=False)
        c = WMConfig(**data["config"])
        self.model = WorldModel(c)
        self.model.load_state_dict(data["model"])
        self.model.eval()
        self.meta = data.get("meta", {})

    def predict(self, raw, enc, years, eval_year, horizon):
        torch = self.torch
        hist_years = [y for y in years if y <= eval_year][-(C.T + 1):]
        if len(hist_years) < C.T + 1:
            return {}
        topics = [t for t in enc
                  if raw[t][eval_year][0] >= C.MIN_HEAT_EVAL]
        H, valid = [], []
        for t in topics:
            es = np.stack([enc[t][y] for y in hist_years])
            H.append(np.diff(es, axis=0)[-C.T:])
            valid.append(t)
        if not H:
            return {}
        Ht = torch.tensor(np.stack(H).astype(np.float32))
        with torch.no_grad():
            pd = self.model.imagine_from_history(
                Ht, torch.zeros(len(valid), horizon, self.model.c.a_dim),
                deterministic=True).numpy()
        out = {}
        for i, t in enumerate(valid):
            last_e = enc[t][eval_year]
            pe = last_e[None, :] + np.cumsum(pd[i], axis=0)
            lv = np.maximum(0, np.expm1(pe[:, 0]))
            cur = raw[t][eval_year][0]
            deltas = np.diff(np.concatenate([[cur], lv]))
            out[t] = (lv.astype(float), deltas.astype(float))
        return out


# ---------------- 消融变体 (实验3) ----------------
class C_MLP:  # 无动态状态转移: 前馈 MLP 窗口回归
    def __init__(self, seed=42):
        self.seed = seed
        self.model = None

    def fit(self, raw, enc, years):
        import torch
        import torch.nn as nn
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        X, Y = [], []
        train_years = [y for y in years if y <= C.TRAIN_END]
        for t in enc:
            vecs = np.stack([enc[t][y] for y in train_years])
            deltas = np.diff(vecs, axis=0)
            for i in range(C.T - 1, len(deltas) - 1):
                X.append(deltas[i - C.T + 1:i + 1].reshape(-1))
                Y.append(deltas[i + 1])
        X = np.stack(X).astype(np.float32)
        Y = np.stack(Y).astype(np.float32)

        net = nn.Sequential(nn.Linear(C.T * 4, 128), nn.SiLU(),
                            nn.Linear(128, 128), nn.SiLU(), nn.Linear(128, 4))
        opt = torch.optim.Adam(net.parameters(), lr=1e-3)
        lossf = nn.MSELoss()
        Xt, Yt = torch.tensor(X), torch.tensor(Y)
        n = len(Xt)
        for _ in range(120):
            idx = np.random.choice(n, min(512, n))
            opt.zero_grad()
            loss = lossf(net(Xt[idx]), Yt[idx])
            loss.backward()
            opt.step()
        self.model = net
        return self

    def predict(self, raw, enc, years, eval_year, horizon):
        import torch
        out = {}
        for t in enc:
            hist_years = [y for y in years if y <= eval_year][-(C.T + 1):]
            if len(hist_years) < C.T + 1:
                continue
            es = np.stack([enc[t][y] for y in hist_years])
            deltas = np.diff(es, axis=0)[-C.T:]
            cur_e = enc[t][eval_year]
            preds = []
            with torch.no_grad():
                x = torch.tensor(deltas.reshape(1, -1).astype(np.float32))
                for _ in range(horizon):
                    d = self.model(x).numpy()[0]
                    cur_e = cur_e + d
                    preds.append(float(np.expm1(max(0.0, cur_e[0]))))
                    x = torch.cat([x[:, 4:], torch.tensor(d[None].astype(np.float32))], dim=1)
            if not preds:
                continue
            lv = np.array(preds)
            cur = raw[t][eval_year][0]
            deltas_out = np.diff(np.concatenate([[cur], lv]))
            out[t] = (lv.astype(float), deltas_out.astype(float))
        return out


def load_rssm(model_path):
    return M_RSSM(model_path)
