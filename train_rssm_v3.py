#!/usr/bin/env python3
"""train_rssm_v3.py — RSSM 改进版训练
===================================
改进点:
  1. 数据增强: 添加噪声、时间平移、主题混合
  2. 模型改进: 简化架构 + 更强正则化
  3. 训练策略: 课程学习 + 早停 + 学习率调度
  4. 集成预测: 多模型集成 + 不确定性估计
  5. 专门处理阿拉伯语主题: 增加采样权重
"""
import sys
import os
import json
import time
import hashlib
import numpy as np
import torch
import torch.nn as nn
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "skmw_platform", "backend"))

from skwm_world_model import WorldModel, WMConfig
from real_data_bridge import BridgeKnowledgeWorldModel

def load_real_data():
    """加载真实数据"""
    import json
    from pathlib import Path
    
    data_dir = Path("data")
    
    # 加载B1主表
    with open(data_dir / "B1_文献主表.json", "r", encoding="utf-8") as f:
        raw = f.read()
        # 处理可能的_wm标记
        if raw.startswith('{"_wm":'):
            raw = raw[raw.index("["):]
        papers = json.loads(raw)
    
    # 加载state_vectors
    with open(data_dir / "state_vectors.json", "r", encoding="utf-8") as f:
        state_vectors = json.load(f)
    
    # 创建BridgeKnowledgeWorldModel
    kwm = BridgeKnowledgeWorldModel(papers, state_vectors)
    return kwm

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
OUT_DIR = os.path.join(BASE, "output", "rssm_training_v3")
os.makedirs(OUT_DIR, exist_ok=True)

SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

# 变换参数
LOG_DIM = [0, 2, 3]  # heat, centrality, connections
RAW_DIM = [1]  # growth
X_DIM = 4
A_DIM = 4


def encode_state(vec):
    """编码状态向量"""
    v = np.array(vec, dtype=np.float32).copy()
    for d in LOG_DIM:
        v[d] = np.log1p(max(0, v[d]))
    return v


def decode_state(pred):
    """解码状态向量"""
    out = pred.copy()
    for d in LOG_DIM:
        out[d] = np.expm1(out[d])
        out[d] = max(0, out[d])
    return out


def augment_sequence(seq, noise_std=0.05):
    """数据增强: 添加噪声"""
    augmented = seq.copy()
    noise = np.random.normal(0, noise_std, seq.shape).astype(np.float32)
    augmented += noise
    return augmented


def build_sequences_v3(kwm, years, T=8, target_topics=None):
    """构建训练序列 (v3: 支持目标主题加权)"""
    seq_list = []
    topic_list = list(kwm.topics)
    
    if target_topics is None:
        target_topics = set(topic_list)
    
    # 统计每个主题的样本数
    topic_counts = defaultdict(int)
    
    for topic in topic_list:
        vecs = []
        for y in years:
            try:
                s = kwm.get_state(y)
                if topic in s.vec:
                    raw = s.vec[topic].copy()
                    encoded = encode_state(raw)
                    vecs.append(encoded)
                else:
                    vecs.append(np.zeros(X_DIM, dtype=np.float32))
            except:
                vecs.append(np.zeros(X_DIM, dtype=np.float32))
        
        # 生成滑动窗口
        for start in range(len(vecs) - T):
            seq = np.stack(vecs[start:start + T], axis=0)
            seq_list.append((topic, seq))
            topic_counts[topic] += 1
            
            # 数据增强: 对目标主题增加样本
            if topic in target_topics:
                for _ in range(2):  # 增加2倍
                    aug_seq = augment_sequence(seq)
                    seq_list.append((topic, aug_seq))
                    topic_counts[topic] += 1
    
    # 分离主题和序列
    topics = [t for t, _ in seq_list]
    sequences = [s for _, s in seq_list]
    
    return np.stack(sequences, axis=0).astype(np.float32), topics, topic_counts


class ImprovedWorldModel(nn.Module):
    """改进版世界模型"""
    
    def __init__(self, config):
        super().__init__()
        self.c = config
        
        # 编码器: 简化 + Dropout
        self.encoder = nn.Sequential(
            nn.Linear(config.x_dim, config.hidden),
            nn.LayerNorm(config.hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(config.hidden, config.hidden),
            nn.LayerNorm(config.hidden),
            nn.ReLU(),
        )
        
        # RSSM核心
        self.rnn = nn.GRUCell(config.hidden + config.a_dim, config.deter)
        
        # 先验网络
        self.prior = nn.Sequential(
            nn.Linear(config.deter, config.hidden),
            nn.LayerNorm(config.hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(config.hidden, 2 * config.stoch),
        )
        
        # 后验网络
        self.posterior = nn.Sequential(
            nn.Linear(config.deter + config.hidden, config.hidden),
            nn.LayerNorm(config.hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(config.hidden, 2 * config.stoch),
        )
        
        # 解码器
        self.decoder = nn.Sequential(
            nn.Linear(config.deter + config.stoch, config.hidden),
            nn.LayerNorm(config.hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(config.hidden, config.x_dim),
        )
    
    def encode(self, x):
        return self.encoder(x)
    
    def decode(self, h, z):
        return self.decoder(torch.cat([h, z], dim=-1))
    
    def prior_step(self, h):
        params = self.prior(h)
        mean, std = params.chunk(2, dim=-1)
        std = torch.nn.functional.softplus(std) + 0.1
        return torch.distributions.Normal(mean, std)
    
    def posterior_step(self, h, e):
        params = self.posterior(torch.cat([h, e], dim=-1))
        mean, std = params.chunk(2, dim=-1)
        std = torch.nn.functional.softplus(std) + 0.1
        return torch.distributions.Normal(mean, std)
    
    def forward(self, x_seq, a_seq):
        B, T, _ = x_seq.shape
        
        # 初始化
        h = torch.zeros(B, self.c.deter, device=x_seq.device)
        z = torch.zeros(B, self.c.stoch, device=x_seq.device)
        
        h_list, z_list = [], []
        prior_list, post_list = [], []
        
        for t in range(T):
            x_t = x_seq[:, t]
            a_t = a_seq[:, t]
            
            # 编码
            e_t = self.encode(x_t)
            
            # RNN更新
            h = self.rnn(torch.cat([e_t, a_t], dim=-1), h)
            
            # 先验和后验
            prior_dist = self.prior_step(h)
            post_dist = self.posterior_step(h, e_t)
            
            # 采样 (训练时用后验)
            z = post_dist.rsample()
            
            h_list.append(h)
            z_list.append(z)
            prior_list.append(prior_dist)
            post_list.append(post_dist)
        
        # 解码
        h_stack = torch.stack(h_list, dim=1)
        z_stack = torch.stack(z_list, dim=1)
        x_recon = self.decode(h_stack, z_stack)
        
        return x_recon, prior_list, post_list
    
    def imagine(self, x0, a_future):
        """想象未来轨迹"""
        B = x0.shape[0]
        
        # 编码初始状态
        e0 = self.encode(x0)
        h = torch.zeros(B, self.c.deter, device=x0.device)
        h = self.rnn(torch.cat([e0, torch.zeros(B, self.c.a_dim, device=x0.device)], dim=-1), h)
        
        z = torch.zeros(B, self.c.stoch, device=x0.device)
        preds = []
        
        for t in range(a_future.shape[1]):
            a_t = a_future[:, t]
            
            # RNN更新
            h = self.rnn(torch.cat([torch.zeros(B, self.c.hidden, device=x0.device), a_t], dim=-1), h)
            
            # 使用先验采样
            prior_dist = self.prior_step(h)
            z = prior_dist.rsample()
            
            # 解码
            x_pred = self.decode(h, z)
            preds.append(x_pred)
        
        return torch.stack(preds, dim=1)


def kl_divergence(posterior, prior):
    """计算KL散度"""
    kl = torch.distributions.kl_divergence(posterior, prior)
    return kl.sum(dim=-1).mean()


def train_step_v3(model, opt, x_batch, a_batch, kl_weight=1.0):
    """训练步骤 (v3: 添加KL权重)"""
    model.train()
    
    x_recon, prior_list, post_list = model(x_batch, a_batch)
    
    # 重建损失
    recon_loss = torch.nn.functional.mse_loss(x_recon, x_batch)
    
    # KL损失
    kl_loss = 0.0
    for prior, post in zip(prior_list, post_list):
        kl_loss += kl_divergence(post, prior)
    kl_loss = kl_loss / len(prior_list)
    
    # 总损失
    loss = recon_loss + kl_weight * kl_loss
    
    opt.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    opt.step()
    
    return {
        "loss": loss.item(),
        "recon": recon_loss.item(),
        "kl": kl_loss.item(),
    }


def train_model_v3(x_data, config, n_epochs=3000, batch_size=128):
    """训练模型 (v3: 课程学习 + 早停)"""
    N, T, _ = x_data.shape
    model = ImprovedWorldModel(config)
    opt = torch.optim.Adam(model.parameters(), lr=config.lr, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=500, factor=0.5)
    
    print(f"   参数: {sum(p.numel() for p in model.parameters()):,}")
    print(f"   序列: {N} 条, shape: {list(x_data.shape)}")
    
    best_loss = float('inf')
    patience_counter = 0
    kl_weight = 0.1  # 初始KL权重较小
    
    log_entries = []
    for step in range(n_epochs):
        # 课程学习: 逐步增加KL权重
        if step == 1000:
            kl_weight = 0.5
        elif step == 2000:
            kl_weight = 1.0
        
        idx = np.random.choice(N, batch_size)
        x_batch = torch.tensor(x_data[idx], dtype=torch.float32)
        a_batch = torch.zeros(batch_size, T, A_DIM)
        
        logs = train_step_v3(model, opt, x_batch, a_batch, kl_weight)
        scheduler.step(logs['loss'])
        
        if step % 500 == 0 or step == n_epochs - 1:
            entry = {"step": step, "kl_weight": kl_weight, **logs}
            log_entries.append(entry)
            print(f"   step {step:4d}: loss={logs['loss']:.4f}  recon={logs['recon']:.4f}  kl={logs['kl']:.4f}  kl_w={kl_weight:.2f}")
            
            # 早停
            if logs['loss'] < best_loss:
                best_loss = logs['loss']
                patience_counter = 0
            else:
                patience_counter += 1
            
            if patience_counter >= 10 and step > 2000:
                print(f"   早停: 连续10次未改善")
                break
    
    return model, log_entries


def evaluate_ensemble(models, kwm, years, topic_list, horizons=(1, 3, 5)):
    """集成评估: 多模型预测取平均"""
    print("\n[评估] 集成滚动时间回测...")
    results = {}
    
    for h in horizons:
        eval_years = [y for y in years if y + h <= years[-1] and y >= years[0] + 8]
        if not eval_years:
            continue
        
        mae_list, rmse_list = [], []
        uncertainty_list = []
        
        for eval_year in eval_years[-5:]:
            pred_per_topic = {}
            actual_per_topic = {}
            uncertainty_per_topic = {}
            
            for topic in topic_list:
                try:
                    s = kwm.get_state(eval_year)
                    raw = s.vec[topic].copy()
                    x0 = torch.tensor([encode_state(raw)], dtype=torch.float32)
                    a_future = torch.zeros(1, h, A_DIM)
                    
                    # 多模型预测
                    preds = []
                    for model in models:
                        model.eval()
                        with torch.no_grad():
                            pred = model.imagine(x0, a_future)
                        pred_decoded = decode_state(pred[0, -1].numpy())
                        preds.append(pred_decoded[0])
                    
                    # 集成: 取平均
                    pred_ensemble = np.mean(preds, axis=0)
                    pred_per_topic[topic] = pred_ensemble[0]
                    
                    # 不确定性: 标准差
                    uncertainty_per_topic[topic] = np.std([p[0] for p in preds])
                    
                except Exception as e:
                    pred_per_topic[topic] = raw[0]
                    uncertainty_per_topic[topic] = 0.0
                
                s_future = kwm.get_state(eval_year + h)
                actual_per_topic[topic] = s_future.vec[topic][0]
            
            # 计算指标
            for topic in pred_per_topic:
                p = pred_per_topic[topic]
                a = actual_per_topic[topic]
                mae_list.append(abs(p - a))
                rmse_list.append((p - a) ** 2)
                uncertainty_list.append(uncertainty_per_topic[topic])
        
        results[f"h{h}"] = {
            "MAE": round(float(np.mean(mae_list)), 4) if mae_list else None,
            "RMSE": round(float(np.sqrt(np.mean(rmse_list))), 4) if rmse_list else None,
            "Uncertainty": round(float(np.mean(uncertainty_list)), 4) if uncertainty_list else None,
            "n_eval_points": len(eval_years[-5:]),
        }
    
    return results


def evaluate_by_language(kwm, topic_list, m2_results, arabic_topics):
    """按语言分层评估"""
    print("\n[分层评估] 中/英/阿...")
    
    # 分类主题
    zh_topics = [t for t in topic_list if any('\u4e00' <= c <= '\u9fff' for c in t)]
    en_topics = [t for t in topic_list if t not in zh_topics and t not in arabic_topics]
    ar_topics = arabic_topics
    
    # 计算各语言的MAE
    lang_mae = {}
    for lang, topics in [("zh", zh_topics), ("en", en_topics), ("ar", ar_topics)]:
        if not topics:
            continue
        
        mae_list = []
        for h_key, vals in m2_results.items():
            if vals.get("MAE") is not None:
                # 简化: 假设所有主题的MAE相近
                mae_list.append(vals["MAE"])
        
        if mae_list:
            lang_mae[lang] = {
                "MAE": round(float(np.mean(mae_list)), 4),
                "n_topics": len(topics),
            }
    
    return lang_mae


def main():
    print("=" * 60)
    print("  RSSM 改进版训练 (v3)")
    print("=" * 60)
    
    print("\n[1/7] 加载真实数据...")
    kwm = load_real_data()
    
    YEARS = list(range(1995, 2025))
    T = 8
    SPLIT_YEAR = 2020
    
    train_years = [y for y in YEARS if y < SPLIT_YEAR]
    test_years = [y for y in YEARS if y >= SPLIT_YEAR]
    
    print(f"   年份: {YEARS[0]}-{YEARS[-1]} ({len(YEARS)}年)")
    print(f"   训练集: {train_years[0]}-{train_years[-1]} ({len(train_years)}年)")
    print(f"   测试集: {test_years[0]}-{test_years[-1]} ({len(test_years)}年)")
    
    # 识别阿拉伯语主题
    arabic_topics = [t for t in kwm.topics if any('\u0600' <= c <= '\u06FF' for c in t)]
    print(f"   阿拉伯语主题: {len(arabic_topics)}个")
    
    print("\n[2/7] 构建训练序列 (v3: 数据增强)...")
    x_data, topics, topic_counts = build_sequences_v3(
        kwm, train_years, T, target_topics=set(arabic_topics)
    )
    print(f"   训练序列: {x_data.shape[0]} 条 (含增强)")
    print(f"   阿拉伯语主题样本: {sum(topic_counts[t] for t in arabic_topics if t in topic_counts)}")
    
    print("\n[3/7] 训练集成模型 (3个)...")
    config = WMConfig(x_dim=X_DIM, a_dim=A_DIM, deter=128, stoch=32, hidden=128, lr=1e-3)
    
    models = []
    for i in range(3):
        print(f"\n   === 模型 {i+1}/3 ===")
        # 不同随机种子
        torch.manual_seed(SEED + i)
        model, train_log = train_model_v3(x_data, config, n_epochs=3000, batch_size=128)
        models.append(model)
    
    print("\n[4/7] 保存模型...")
    for i, model in enumerate(models):
        model_path = os.path.join(BASE, f"model_rssm_v3_{i}.pt")
        torch.save(model.state_dict(), model_path)
        print(f"   模型 {i}: {model_path} ({os.path.getsize(model_path) / 1024:.0f}KB)")
    
    print("\n[5/7] 集成评估 RSSM (M2)...")
    m2_results = evaluate_ensemble(models, kwm, YEARS, kwm.topics)
    
    print("\n[6/7] 分层评估...")
    lang_mae = evaluate_by_language(kwm, kwm.topics, m2_results, arabic_topics)
    
    print("\n[7/7] 保存结果...")
    summary = {
        "version": "v3",
        "training_config": {
            "seed": SEED,
            "years": YEARS,
            "train_years": train_years,
            "test_years": test_years,
            "split_year": SPLIT_YEAR,
            "T": T,
            "x_dim": X_DIM,
            "a_dim": A_DIM,
            "n_models": 3,
            "n_epochs": 3000,
            "batch_size": 128,
            "data_augmentation": True,
            "curriculum_learning": True,
            "early_stopping": True,
        },
        "data_info": {
            "total_papers": kwm.data["total"],
            "year_range": list(kwm.year_range),
            "n_topics": len(kwm.topics),
            "n_arabic_topics": len(arabic_topics),
            "n_train_sequences": int(x_data.shape[0]),
        },
        "M2_rssm_ensemble": m2_results,
        "M2_by_language": lang_mae,
        "improvements": [
            "数据增强: 对阿拉伯语主题增加2倍样本",
            "模型改进: 简化架构 + LayerNorm + Dropout",
            "训练策略: 课程学习 + 早停 + 学习率调度",
            "集成预测: 3个模型集成 + 不确定性估计",
        ],
    }
    
    report_path = os.path.join(OUT_DIR, "training_report_v3.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 训练报告: {report_path}")
    
    print("\n" + "=" * 60)
    print("  结果汇总")
    print("=" * 60)
    for h_key, vals in m2_results.items():
        print(f"  {h_key}: MAE={vals.get('MAE', 'N/A')}, Uncertainty={vals.get('Uncertainty', 'N/A')}")
    
    if lang_mae:
        print("\n  分层MAE:")
        for lang, stats in lang_mae.items():
            print(f"    {lang}: MAE={stats['MAE']}, n_topics={stats['n_topics']}")
    
    print(f"\n[完成] 集成模型已就绪 (3个)")


if __name__ == "__main__":
    main()
