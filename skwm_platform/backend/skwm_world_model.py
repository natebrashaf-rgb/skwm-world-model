#!/usr/bin/env python3
"""
SKWM 世界模型内核 (DreamerV3/RSSM 精简实现)
补齐 skwm_aligned_v4.py 缺失的 T 维"动态预测未来"内核 g_θ

中阿文旅特色:
- 状态维度: [热度, 增速, 中心度, 连接数, 合作强度, 语言分布, 传播范围]
- 动作维度: 干预/策略编码 (主题投入 + 关系干预 + 语境权重)
- 数值稳健: symlog/symexp 压缩量级

对接: DataLayer(年度状态) + UnifiedStrategyAPI(干预编码) + 闭环controller
"""
from dataclasses import dataclass
from typing import Tuple, Dict, Optional
from pathlib import Path
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch 未安装，RSSM 世界模型不可用。运行: pip install torch")


# ═══════════════════════════════════════════════════════════════════
# 数值稳健 (原文 Eq.9)
# ═══════════════════════════════════════════════════════════════════

if TORCH_AVAILABLE:
    def symlog(x: torch.Tensor) -> torch.Tensor:
        """对称对数变换: 压缩大数值，保留符号"""
        return torch.sign(x) * torch.log1p(torch.abs(x))

    def symexp(x: torch.Tensor) -> torch.Tensor:
        """对称指数变换: symlog的逆变换"""
        return torch.sign(x) * torch.expm1(torch.abs(x))
else:
    def symlog(x):
        return np.sign(x) * np.log1p(np.abs(x))
    
    def symexp(x):
        return np.sign(x) * np.expm1(np.abs(x))


# ═══════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Config:
    """SKWM 世界模型配置"""
    # 状态/动作维度 (中阿文旅特色)
    x_dim: int = 7        # 状态维度 [热度,增速,中心度,连接数,合作强度,语言分布,传播范围]
    a_dim: int = 12       # 干预/策略编码维度 (主题投入×4 + 关系干预×4 + 语境权重×4)
    
    # 网络结构
    deter: int = 128      # h_t 维度 (GRU) - 缩小防过拟合
    stoch: int = 16       # z_t 维度 - 缩小防过拟合
    hidden: int = 128
    
    # 训练超参
    free_nats: float = 1.0    # KL free bits
    beta_pred: float = 1.0
    beta_dyn: float = 1.0
    beta_rep: float = 0.1
    
    # 中阿文旅语境
    context_dims: int = 4     # 语境维度数 (national_policy, regional_coop, school_direction, global_situation)
    user_types: int = 4       # 用户类型数 (teacher, student, librarian, manager)


# ═══════════════════════════════════════════════════════════════════
# 网络组件 (需要 PyTorch)
# ═══════════════════════════════════════════════════════════════════

if TORCH_AVAILABLE:

    class Encoder(nn.Module):
        """
        编码器: 观测 → 嵌入
        输入 symlog 变换，压缩量级
        """
        def __init__(self, c: Config):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(c.x_dim, c.hidden),
                nn.SiLU(),
                nn.Linear(c.hidden, c.hidden),
                nn.SiLU(),
                nn.Linear(c.hidden, c.hidden),
            )
        
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """x: [..., x_dim] → [..., hidden]"""
            return self.net(symlog(x))


    class Decoder(nn.Module):
        """
        解码器: (h, z) → 预测观测
        输出 symexp 变换，恢复原始量级
        """
        def __init__(self, c: Config):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(c.deter + c.stoch, c.hidden),
                nn.SiLU(),
                nn.Linear(c.hidden, c.hidden),
                nn.SiLU(),
                nn.Linear(c.hidden, c.x_dim),
            )
        
        def forward(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
            """(h, z) → x_hat"""
            return symexp(self.net(torch.cat([h, z], -1)))


    class RSSM(nn.Module):
        """
        Recurrent State-Space Model
        序列模型 f_φ + 后验 q_φ + 先验(动态预测器) p_φ
        """
        def __init__(self, c: Config):
            super().__init__()
            self.c = c
            
            self.cell = nn.GRUCell(c.stoch + c.a_dim, c.deter)
            
            self.prior = nn.Sequential(
                nn.Linear(c.deter, c.hidden),
                nn.SiLU(),
                nn.Linear(c.hidden, c.hidden),
                nn.SiLU(),
                nn.Linear(c.hidden, 2 * c.stoch),
            )
            
            self.post = nn.Sequential(
                nn.Linear(c.deter + c.hidden, c.hidden),
                nn.SiLU(),
                nn.Linear(c.hidden, c.hidden),
                nn.SiLU(),
                nn.Linear(c.hidden, 2 * c.stoch),
            )
        
        def _dist(self, params: torch.Tensor) -> torch.distributions.Normal:
            mean, std = params.chunk(2, -1)
            return torch.distributions.Normal(mean, F.softplus(std) + 0.1)
        
        def initial(self, batch_size: int, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
            h = torch.zeros(batch_size, self.c.deter, device=device)
            z = torch.zeros(batch_size, self.c.stoch, device=device)
            return h, z
        
        def step(self, h: torch.Tensor, z: torch.Tensor, a: torch.Tensor, 
                 embed: Optional[torch.Tensor] = None):
            h = self.cell(torch.cat([z, a], -1), h)
            prior = self._dist(self.prior(h))
            
            if embed is None:
                z = prior.rsample()
                return h, z, prior, None
            
            post = self._dist(self.post(torch.cat([h, embed], -1)))
            z = post.rsample()
            return h, z, prior, post


    def _sg(dist):
        """stop-gradient 一个分布"""
        return torch.distributions.Normal(dist.mean.detach(), dist.stddev.detach())


    class WorldModel(nn.Module):
        """
        SKWM 世界模型内核
        整合 Encoder + Decoder + RSSM
        """
        def __init__(self, c: Config = Config()):
            super().__init__()
            self.c = c
            self.enc = Encoder(c)
            self.dec = Decoder(c)
            self.rssm = RSSM(c)
        
        def observe(self, x_seq: torch.Tensor, a_seq: torch.Tensor):
            B, T, _ = x_seq.shape
            h, z = self.rssm.initial(B, x_seq.device)
            hs, zs, priors, posts = [], [], [], []
            
            for t in range(T):
                e = self.enc(x_seq[:, t])
                h, z, pr, po = self.rssm.step(h, z, a_seq[:, t], e)
                hs.append(h)
                zs.append(z)
                priors.append(pr)
                posts.append(po)
            
            return (torch.stack(hs, 1), torch.stack(zs, 1), priors, posts)
        
        def loss(self, x_seq: torch.Tensor, a_seq: torch.Tensor):
            hs, zs, priors, posts = self.observe(x_seq, a_seq)
            x_hat = self.dec(hs, zs)
            L_pred = ((symlog(x_hat) - symlog(x_seq)) ** 2).sum(-1).mean()
            
            fb = self.c.free_nats
            def kl(a, b):
                return torch.distributions.kl_divergence(a, b).sum(-1)
            
            L_dyn = torch.stack([kl(_sg(po), pr).clamp(min=fb).mean()
                                 for pr, po in zip(priors, posts)]).mean()
            L_rep = torch.stack([kl(po, _sg(pr)).clamp(min=fb).mean()
                                 for pr, po in zip(priors, posts)]).mean()
            
            L = self.c.beta_pred * L_pred + self.c.beta_dyn * L_dyn + self.c.beta_rep * L_rep
            logs = {"loss": L.item(), "pred": L_pred.item(), 
                    "dyn": L_dyn.item(), "rep": L_rep.item()}
            return L, logs
        
        @torch.no_grad()
        def imagine(self, x0: torch.Tensor, a_future: torch.Tensor) -> torch.Tensor:
            B = x0.shape[0]
            h, z = self.rssm.initial(B, x0.device)
            e0 = self.enc(x0)
            h, z, _, _ = self.rssm.step(h, z, torch.zeros(B, self.c.a_dim, device=x0.device), e0)
            
            preds = []
            for t in range(a_future.shape[1]):
                h, z, _, _ = self.rssm.step(h, z, a_future[:, t], embed=None)
                preds.append(self.dec(h, z))
            
            return torch.stack(preds, 1)
        
        def save(self, path: str):
            torch.save({"config": self.c, "state_dict": self.state_dict()}, path)
        
        @classmethod
        def load(cls, path: str) -> "WorldModel":
            checkpoint = torch.load(path, map_location="cpu")
            c = checkpoint["config"]
            model = cls(c)
            model.load_state_dict(checkpoint["state_dict"])
            return model


    def train_step(model, opt, x_seq, a_seq):
        L, logs = model.loss(x_seq, a_seq)
        opt.zero_grad()
        L.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 100.0)
        opt.step()
        return logs


    def train(model, data_loader, epochs=100, lr=4e-5, start_year=2000, end_year=2020):
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        x_seq, a_seq = data_loader.build_topic_trajectories(start_year, end_year)
        print(f"📊 训练数据: {x_seq.shape[0]}条轨迹, 长度{x_seq.shape[1]}")
        
        for epoch in range(epochs):
            logs = train_step(model, opt, x_seq, a_seq)
            if (epoch + 1) % 20 == 0:
                print(f"Epoch {epoch+1}/{epochs}: loss={logs['loss']:.4f}")
        
        return model

else:
    # PyTorch 不可用时的占位类
    class WorldModel:
        def __init__(self, c=None):
            self.c = c or Config()
        
        @classmethod
        def load(cls, path):
            raise RuntimeError("PyTorch 未安装，无法加载模型")
        
        def save(self, path):
            raise RuntimeError("PyTorch 未安装，无法保存模型")
    
    def train(model, data_loader, **kwargs):
        raise RuntimeError("PyTorch 未安装，无法训练模型")


# ═══════════════════════════════════════════════════════════════════
# 数据准备 (对接 DataLayer)
# ═══════════════════════════════════════════════════════════════════

class SKWMDataLoader:
    """
    从 DataLayer 加载数据，组装成训练格式
    把每个主题的逐年演化当作一条轨迹
    """
    
    def __init__(self, data_layer):
        self.data = data_layer
    
    def build_topic_trajectories(self, start_year: int, end_year: int,
                                 min_years: int = 5):
        """
        构建主题轨迹
        返回: x_seq [N_topics, T, x_dim], a_seq [N_topics, T, a_dim]
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch 未安装，无法构建轨迹")
        
        trajectories_x = []
        trajectories_a = []
        
        all_topics = set()
        for y in range(start_year, end_year + 1):
            entities = self.data.get_entities(y)
            all_topics.update(entities.keys())
        
        for topic in all_topics:
            traj_x = []
            traj_a = []
            valid_years = 0
            
            for y in range(start_year, end_year + 1):
                entities = self.data.get_entities(y)
                if topic in entities:
                    vec = entities[topic]
                    if isinstance(vec, (list, tuple)) and len(vec) >= 4:
                        x = np.zeros(7)
                        x[:4] = vec[:4]
                        x[4] = self.data._collab_intensity.get(topic, 0)
                        x[5] = 1.0 if self.data._detect_lang(topic) in ["中文", "中阿混合"] else 0.0
                        x[6] = len(self.data._entity_years.get(topic, {y}))
                        traj_x.append(x)
                        
                        a = np.zeros(12)
                        traj_a.append(a)
                        valid_years += 1
            
            if valid_years >= min_years:
                trajectories_x.append(np.stack(traj_x))
                trajectories_a.append(np.stack(traj_a))
        
        if not trajectories_x:
            return self._demo_trajectories()
        
        max_len = max(len(t) for t in trajectories_x)
        x_padded = np.zeros((len(trajectories_x), max_len, 7))
        a_padded = np.zeros((len(trajectories_a), max_len, 12))
        
        for i, (tx, ta) in enumerate(zip(trajectories_x, trajectories_a)):
            x_padded[i, :len(tx)] = tx
            a_padded[i, :len(ta)] = ta
        
        return torch.FloatTensor(x_padded), torch.FloatTensor(a_padded)
    
    def _demo_trajectories(self):
        """演示数据"""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch 未安装")
        B, T = 32, 20
        x_seq = torch.randn(B, T, 7) * 0.5
        x_seq[:, :, 0] = x_seq[:, :, 0].abs() * 100 + 50
        x_seq[:, :, 1] = x_seq[:, :, 1].abs() * 10
        x_seq[:, :, 2] = x_seq[:, :, 2].sigmoid()
        x_seq[:, :, 3] = x_seq[:, :, 3].abs() * 50 + 10
        a_seq = torch.randn(B, T, 12) * 0.1
        return x_seq, a_seq


# ═══════════════════════════════════════════════════════════════════
# 对接闭环控制器
# ═══════════════════════════════════════════════════════════════════

class TrainedWorldModel:
    """
    训练好的世界模型封装
    对接 SKWMClosedLoopController
    """
    
    def __init__(self, model, data_layer):
        self.model = model
        self.data = data_layer
        if TORCH_AVAILABLE and hasattr(model, 'eval'):
            self.model.eval()
    
    def predict_future(self, year: int, topic: str, horizon: int = 5,
                       intervention: Optional[np.ndarray] = None) -> np.ndarray:
        """预测某主题未来horizon年的状态"""
        if not TORCH_AVAILABLE:
            return self._fallback_predict(year, topic, horizon)
        
        entities = self.data.get_entities(year)
        if topic not in entities:
            return np.zeros((horizon, 7))
        
        vec = entities[topic]
        x0 = np.zeros(7)
        x0[:4] = vec[:4]
        x0[4] = self.data._collab_intensity.get(topic, 0)
        x0[5] = 1.0 if self.data._detect_lang(topic) in ["中文", "中阿混合"] else 0.0
        x0[6] = len(self.data._entity_years.get(topic, {year}))
        
        x0_tensor = torch.FloatTensor(x0).unsqueeze(0)
        
        if intervention is None:
            a_future = torch.zeros(1, horizon, 12)
        else:
            a_future = torch.FloatTensor(intervention).unsqueeze(0).unsqueeze(0)
            a_future = a_future.repeat(1, horizon, 1)
        
        with torch.no_grad():
            pred = self.model.imagine(x0_tensor, a_future)
        return pred.squeeze(0).numpy()
    
    def _fallback_predict(self, year: int, topic: str, horizon: int) -> np.ndarray:
        """降级预测 (无PyTorch时)"""
        entities = self.data.get_entities(year)
        if topic not in entities:
            return np.zeros((horizon, 7))
        
        vec = np.array(entities[topic][:4] + [0, 0, 0])
        result = np.zeros((horizon, 7))
        for t in range(horizon):
            result[t] = vec * (0.95 ** t)
        return result
    
    def counterfactual(self, year: int, remove_topic: str, horizon: int = 5) -> Dict:
        """反事实分析"""
        normal_pred = self.predict_future(year, remove_topic, horizon)
        
        intervention = np.zeros(12)
        intervention[0] = -1.0
        cf_pred = self.predict_future(year, remove_topic, horizon, intervention)
        
        impact = np.sum(normal_pred[:, 0] - cf_pred[:, 0])
        
        return {
            "topic": remove_topic,
            "year": year,
            "horizon": horizon,
            "normal_pred": normal_pred.tolist(),
            "counterfactual_pred": cf_pred.tolist(),
            "impact": float(impact),
            "conclusion": f"移除'{remove_topic}'后，热度累计下降{impact:.2f}",
        }


# ═══════════════════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    print("🧠 SKWM 世界模型内核 (DreamerV3/RSSM)")
    print("=" * 50)
    
    if not TORCH_AVAILABLE:
        print("\n⚠️ PyTorch 未安装，RSSM 世界模型不可用")
        print("运行: pip install torch")
        print("\n闭环控制器 (skwm_closed_loop.py) 仍可正常使用")
        sys.exit(0)
    
    c = Config()
    print(f"配置: x_dim={c.x_dim}, a_dim={c.a_dim}, deter={c.deter}, stoch={c.stoch}")
    
    model = WorldModel(c)
    print(f"模型参数量: {sum(p.numel() for p in model.parameters()):,}")
    
    try:
        from skwm_aligned_v4 import DataLayer
        data = DataLayer().load(verbose=False)
        loader = SKWMDataLoader(data)
        print("✅ 已加载真实数据")
    except Exception as e:
        print(f"⚠️ 无法加载真实数据: {e}")
        data = None
        loader = None
    
    print("\n📚 开始训练...")
    if data and loader:
        model = train(model, loader, epochs=50, start_year=2000, end_year=2020)
    else:
        demo_x, demo_a = torch.randn(16, 30, c.x_dim), torch.randn(16, 30, c.a_dim)
        opt = torch.optim.Adam(model.parameters(), lr=4e-5)
        for step in range(100):
            logs = train_step(model, opt, demo_x, demo_a)
            if (step + 1) % 25 == 0:
                print(f"Step {step+1}: loss={logs['loss']:.4f}")
    
    print("\n🔮 测试未来预测...")
    x0 = torch.randn(1, c.x_dim)
    a_future = torch.randn(1, 5, c.a_dim) * 0.1
    future = model.imagine(x0, a_future)
    print(f"预测未来5年状态: {future.shape}")
    print(f"热度轨迹: {future[0, :, 0].tolist()}")
    
    save_path = Path(__file__).parent / "world_model" / "skwm_rssm.pt"
    save_path.parent.mkdir(exist_ok=True)
    model.save(str(save_path))
    print(f"\n💾 模型已保存: {save_path}")
    
    print("\n✅ 完成")
