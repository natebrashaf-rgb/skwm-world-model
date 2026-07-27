"""skwm_world_model.py — SKWM 世界模型内核 (DreamerV3/RSSM)
====================================================================
补齐 skwm_aligned_v4.py 缺失的 T 维"动态预测未来"内核 g_θ。

从 DreamerV3 (Hafner et al., arXiv:2301.04104) 提取 RSSM 核心:
  - Encoder: symlog 变换 + MLP
  - RSSM: GRU序列模型 + 后验q_φ + 先验p_φ (动态预测器)
  - Decoder: symexp 读出
  - 训练损失: L_pred + β_dyn·L_dyn + β_rep·L_rep (KL balance + free bits)
  - imagine(): 脱离真实数据的多步 rollout

与外壳的接线:
  内核 WorldModel.imagine(x0, a_future) → 外壳 KnowledgeWorldModel.rollout()

依赖: PyTorch (torch>=2.0)
安装: pip install torch numpy

用法:
    python skwm_world_model.py          # 空跑验证维度
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from dataclasses import dataclass

# ============================================================
# 数值稳健变换 (原文 Eq.9)
# ============================================================

def symlog(x: torch.Tensor) -> torch.Tensor:
    """压缩量级、保留符号: sign(x)·ln(|x|+1)"""
    return torch.sign(x) * torch.log1p(torch.abs(x))

def symexp(x: torch.Tensor) -> torch.Tensor:
    """逆变换: sign(x)·(exp(|x|)-1)"""
    return torch.sign(x) * torch.expm1(torch.abs(x))


# ============================================================
# 配置
# ============================================================

@dataclass
class WMConfig:
    x_dim: int = 4          # 状态维度 [热度, 增速, 中心度, 连接数]; 扩展图特征则调大
    a_dim: int = 8          # 干预/策略编码维度 (接 UnifiedStrategyAPI.encode 输出)
    deter: int = 256        # h_t 维度 (GRU 循环状态)
    stoch: int = 32         # z_t 维度 (随机潜变量)
    hidden: int = 256       # MLP 隐藏层
    free_nats: float = 1.0  # free bits: KL 低于此值不再压
    beta_pred: float = 1.0  # 预测损失权重
    beta_dyn: float = 1.0   # 动态 KL 权重
    beta_rep: float = 0.1   # 表征 KL 权重
    lr: float = 4e-5        # 学习率 (论文量级)


# ============================================================
# Encoder: 观测 → 嵌入
# ============================================================

class Encoder(nn.Module):
    """将观测 x_t 编码为嵌入向量 (输入 symlog 变换)"""

    def __init__(self, c: WMConfig):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(c.x_dim, c.hidden),
            nn.SiLU(),
            nn.Linear(c.hidden, c.hidden),
            nn.SiLU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(symlog(x))          # 输入 symlog 变换


# ============================================================
# Decoder: (h, z) → 预测观测
# ============================================================

class Decoder(nn.Module):
    """从潜状态解码回预测观测 (symexp 读出)"""

    def __init__(self, c: WMConfig):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(c.deter + c.stoch, c.hidden),
            nn.SiLU(),
            nn.Linear(c.hidden, c.hidden),
            nn.SiLU(),
            nn.Linear(c.hidden, c.x_dim),
        )

    def forward(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        return symexp(self.net(torch.cat([h, z], -1)))  # symexp 读出


# ============================================================
# RSSM — Recurrent State-Space Model (原文 Eq.1)
# ============================================================

class RSSM(nn.Module):
    """序列模型 f_φ + 后验 q_φ + 先验(动态预测器) p_φ

    三个子网络:
      - cell (GRU):      h_t = f_φ(h_{t-1}, z_{t-1}, a_{t-1})
      - prior (MLP):     ẑ_t ~ p_φ(ẑ_t | h_t)     ★ 不看观测也能预测
      - post  (MLP):     z_t ~ q_φ(z_t | h_t, x_t)
    """

    def __init__(self, c: WMConfig):
        super().__init__()
        self.c = c
        self.cell = nn.GRUCell(c.stoch + c.a_dim, c.deter)       # h_t = f_φ(h,z,a)
        self.prior = nn.Sequential(                               # p_φ(z|h)
            nn.Linear(c.deter, c.hidden),
            nn.SiLU(),
            nn.Linear(c.hidden, 2 * c.stoch),
        )
        self.post = nn.Sequential(                                # q_φ(z|h,x)
            nn.Linear(c.deter + c.hidden, c.hidden),
            nn.SiLU(),
            nn.Linear(c.hidden, 2 * c.stoch),
        )

    @staticmethod
    def _dist(params: torch.Tensor) -> torch.distributions.Normal:
        """从 MLP 输出构建高斯分布 (均值 + softplus 标准差)"""
        mean, std = params.chunk(2, -1)
        return torch.distributions.Normal(mean, F.softplus(std) + 0.1)

    def initial(self, batch_size: int, device: torch.device
                ) -> tuple[torch.Tensor, torch.Tensor]:
        """返回初始 (h_0, z_0)"""
        h = torch.zeros(batch_size, self.c.deter, device=device)
        z = torch.zeros(batch_size, self.c.stoch, device=device)
        return h, z

    def step(self, h: torch.Tensor, z: torch.Tensor, a: torch.Tensor,
             embed: torch.Tensor | None = None
             ) -> tuple[torch.Tensor, torch.Tensor,
                        torch.distributions.Normal,
                        torch.distributions.Normal | None]:
        """单步递推

        Args:
            h: 上一时刻循环状态
            z: 上一时刻潜变量
            a: 当前动作/干预
            embed: 当前观测嵌入 (None = imagine 模式, 用先验)
        Returns:
            (h_new, z_new, prior_dist, post_dist_or_None)
        """
        h = self.cell(torch.cat([z, a], -1), h)      # 递推 h_t

        prior = self._dist(self.prior(h))             # 先验 p_φ(z|h)

        if embed is None:
            # imagine 模式: 不用观测, 用先验采样
            z = prior.rsample()
            return h, z, prior, None

        # observe 模式: 后验 q_φ(z|h,x)
        post = self._dist(self.post(torch.cat([h, embed], -1)))
        z = post.rsample()
        return h, z, prior, post


# ============================================================
# WorldModel — 完整世界模型 (内核 g_θ)
# ============================================================

class WorldModel(nn.Module):
    """SKWM 世界模型内核

    - observe():   沿真实序列走后验 (训练)
    - imagine():   脱离真实数据, 用先验 rollout (预测未来)
    - loss():      计算训练损失 L_pred + β_dyn·L_dyn + β_rep·L_rep
    """

    def __init__(self, c: WMConfig = WMConfig()):
        super().__init__()
        self.c = c
        self.enc = Encoder(c)
        self.dec = Decoder(c)
        self.rssm = RSSM(c)

    def observe(self, x_seq: torch.Tensor, a_seq: torch.Tensor
                ) -> tuple[torch.Tensor, torch.Tensor,
                           list[torch.distributions.Normal],
                           list[torch.distributions.Normal]]:
        """沿真实序列走后验 (训练用)

        Args:
            x_seq: [B, T, x_dim] 真实观测序列
            a_seq: [B, T, a_dim] 动作序列
        Returns:
            (hs, zs, priors, posts) 各步潜状态
        """
        B, T = x_seq.shape[:2]
        h, z = self.rssm.initial(B, x_seq.device)
        hs, zs, priors, posts = [], [], [], []

        for t in range(T):
            e = self.enc(x_seq[:, t])                    # 编码观测
            h, z, pr, po = self.rssm.step(h, z, a_seq[:, t], e)
            hs.append(h)
            zs.append(z)
            priors.append(pr)
            posts.append(po)

        return (torch.stack(hs, 1), torch.stack(zs, 1),
                priors, posts)

    def loss(self, x_seq: torch.Tensor, a_seq: torch.Tensor
             ) -> tuple[torch.Tensor, dict[str, float]]:
        """训练损失 (原文 Eq.2-3)

        Returns:
            (loss_tensor, {pred, dyn, rep} 各项日志)
        """
        hs, zs, priors, posts = self.observe(x_seq, a_seq)
        x_hat = self.dec(hs, zs)                          # [B, T, x_dim]

        # L_pred: 重建损失 (MSE in symlog space)
        L_pred = ((symlog(x_hat) - symlog(x_seq)) ** 2).sum(-1).mean()

        fb = self.c.free_nats
        def kl(a, b):
            return torch.distributions.kl_divergence(a, b).sum(-1)

        # L_dyn: 先验追后验 (先验应能预测后验)
        L_dyn = torch.stack([
            kl(_sg(po), pr).clamp(min=fb).mean()
            for pr, po in zip(priors, posts)
        ]).mean()

        # L_rep: 后验更可预测 (防止后验过度灵活)
        L_rep = torch.stack([
            kl(po, _sg(pr)).clamp(min=fb).mean()
            for pr, po in zip(priors, posts)
        ]).mean()

        L = (self.c.beta_pred * L_pred +
             self.c.beta_dyn * L_dyn +
             self.c.beta_rep * L_rep)

        return L, {
            "pred": L_pred.item(),
            "dyn": L_dyn.item(),
            "rep": L_rep.item(),
        }

    @torch.no_grad()
    def imagine(self, x0: torch.Tensor, a_future: torch.Tensor
                ) -> torch.Tensor:
        """Algorithm 3: 潜在想象 rollout = 预测未来 / 反事实

        Args:
            x0: [B, x_dim] 起始观测
            a_future: [B, L, a_dim] 未来 L 年的干预序列
        Returns:
            [B, L, x_dim] 未来 L 年预测状态
        """
        B = x0.shape[0]
        h, z = self.rssm.initial(B, x0.device)

        # 用已知起始观测初始化潜状态
        h, z, _, _ = self.rssm.step(
            h, z, torch.zeros(B, self.c.a_dim, device=x0.device),
            self.enc(x0))

        preds = []
        L = a_future.shape[1]
        for t in range(L):
            h, z, _, _ = self.rssm.step(
                h, z, a_future[:, t], embed=None)    # ★用先验→脱离数据
            preds.append(self.dec(h, z))

        return torch.stack(preds, 1)                  # [B, L, x_dim]


def _sg(dist: torch.distributions.Normal) -> torch.distributions.Normal:
    """stop-gradient 一个分布: 阻断梯度流, 保持均值和方差"""
    return torch.distributions.Normal(
        dist.mean.detach(), dist.stddev.detach()
    )


# ============================================================
# 训练步骤
# ============================================================

def train_step(model: WorldModel, opt: torch.optim.Optimizer,
               x_seq: torch.Tensor, a_seq: torch.Tensor
               ) -> dict[str, float]:
    """单步训练"""
    L, logs = model.loss(x_seq, a_seq)
    opt.zero_grad()
    L.backward()
    nn.utils.clip_grad_norm_(model.parameters(), 100.0)   # 梯度裁剪
    opt.step()
    return logs


# ============================================================
# 与外壳的接线辅助
# ============================================================

class SKWMWorldModelAdapter:
    """桥接: 内核 WorldModel → 外壳 KnowledgeWorldModel.rollout()

    把外壳的 rollout 调用转成内核的 imagine() 调用。
    """

    def __init__(self, wm: WorldModel, device: torch.device | None = None):
        self.wm = wm
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.wm.to(self.device)
        self.wm.eval()

    def rollout(self, o: "KnowledgeState", control: dict,
                horizon: int) -> "KnowledgeState":
        """替代外壳 KnowledgeWorldModel.rollout 的实现"""
        from skwm_closed_loop import KnowledgeState

        # 从 KnowledgeState 构造 x0 向量
        topics = list(o.vec.keys())
        x0_np = np.array([o.vec[t] for t in topics])           # [N, 4]
        x0 = torch.tensor(x0_np, dtype=torch.float32,
                          device=self.device).unsqueeze(0)      # [1, N, 4]

        # 构造 a_future (如果 control 中有 feature_shift)
        a_dim = self.wm.c.a_dim
        a_future = torch.zeros(1, horizon, a_dim,
                               device=self.device)
        for i, (topic, w) in enumerate(control.get("feature_shift", {}).items()):
            if i < a_dim:
                a_future[0, :, i] = w                          # 将强调权重编码到动作维度

        # imagine 预测
        with torch.no_grad():
            pred = self.wm.imagine(x0, a_future)                # [1, L, N, 4]
            last_pred = pred[0, -1].cpu().numpy()               # [N, 4] 最后一年预测

        vec = {t: last_pred[i] for i, t in enumerate(topics)}
        return KnowledgeState(o.year + horizon, vec)


# ============================================================
# 主入口 (空跑验证)
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SKWM 世界模型内核 (RSSM) · 空跑验证")
    print("=" * 60)

    c = WMConfig()
    model = WorldModel(c)
    opt = torch.optim.Adam(model.parameters(), lr=c.lr)

    print(f"\n配置: x_dim={c.x_dim}, a_dim={c.a_dim}, "
          f"deter={c.deter}, stoch={c.stoch}, hidden={c.hidden}")
    print(f"参数总数: {sum(p.numel() for p in model.parameters()):,}")

    # 模拟数据: [B, T, dim]
    B, T = 16, 64
    x_seq = torch.randn(B, T, c.x_dim)
    a_seq = torch.randn(B, T, c.a_dim)

    print(f"\n训练数据: x_seq [{B}, {T}, {c.x_dim}], "
          f"a_seq [{B}, {T}, {c.a_dim}]")

    # 训练 200 步
    print(f"\n训练 {200} 步...")
    for step in range(200):
        logs = train_step(model, opt, x_seq, a_seq)
        if step % 50 == 0:
            print(f"  step {step:3d}:  pred={logs['pred']:.4f}, "
                  f"dyn={logs['dyn']:.4f}, rep={logs['rep']:.4f}")

    # 预测未来 5 年
    x0 = torch.randn(B, c.x_dim)
    a_future = torch.randn(B, 5, c.a_dim)
    future = model.imagine(x0, a_future)
    print(f"\n未来 5 年预测: {list(future.shape)}  [{B}轨迹, {5}年, {c.x_dim}维]")
    print(f"  第一年均值: {future[0, 0].detach().numpy()}")
    print(f"  第五年均值: {future[0, -1].detach().numpy()}")

    print(f"\n✅ 内核实现完成。接外壳步骤:")
    print(f"  1. wm = WorldModel(WMConfig())")
    print(f"  2. adapter = SKWMWorldModelAdapter(wm)")
    print(f"  3. 外壳 KnowledgeWorldModel.rollout = adapter.rollout")
    print(f"  4. 安装 PyTorch 后: python skwm_world_model.py")
