"""run.py — SKWM 世界模型：一键跑通全流程
=========================================
1. 训练 RSSM 内核 (使用真实文献数据)
2. 外壳闭环规划 (四类用户)
3. 回测命中率
4. 推理期缩放实验 (M/B ↑ → 成功率 ↑)

用法:
    python run.py                  # 完整跑一遍
    python run.py --quick          # 快速模式 (小模型+少步数)
"""
import sys, os, time, json
import numpy as np

# 确保能找到同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from real_data_layer import RealKnowledgeWorldModel
from skwm_closed_loop import (
    SKWMClosedLoopController, ProposalPolicy,
    RevisionPolicy, ClosedLoopEvaluator,
)

HAS_TORCH = False
try:
    import torch
    from skwm_world_model import WorldModel, WMConfig, train_step
    HAS_TORCH = True
except ImportError:
    print("⚠ torch 未安装，跳过 RSSM 训练")

# ============================================================
# 0. 加载真实数据
# ============================================================

print("=" * 60)
print("SKWM 世界模型 · 一键全流程")
print("=" * 60)

kwm = RealKnowledgeWorldModel()
print(f"  真实文献: {kwm.data['total']} 篇, "
      f"年份: {kwm.year_range[0]}-{kwm.year_range[1]}")
print()

# ============================================================
# 1. 训练 RSSM 内核
# ============================================================

if HAS_TORCH and "--quick" not in sys.argv:
    print("─" * 60)
    print("[1/4] 训练 RSSM 世界模型内核")
    print("─" * 60)

    c = WMConfig(deter=128, stoch=32, hidden=128, x_dim=4, a_dim=8)
    model = WorldModel(c)
    opt = torch.optim.Adam(model.parameters(), lr=c.lr)
    print(f"  参数: {sum(p.numel() for p in model.parameters()):,}")

    # 从真实数据构造训练序列
    B, T = 8, 16
    years = sorted(kwm.data["by_year"].keys())
    seq_starts = [y for y in years if y >= kwm.year_range[0] and y + T <= kwm.year_range[1]]

    n_epochs = 100
    for epoch in range(n_epochs):
        # 采样 batch
        x_batch = np.zeros((B, T, 4))
        a_batch = np.zeros((B, T, 8))
        for b in range(B):
            if seq_starts:
                start = np.random.choice(seq_starts)
                for t in range(T):
                    s = kwm.get_state(start + t)
                    topics = list(s.vec.keys())
                    vals = np.array([s.vec[t][0] for t in topics])
                    x_batch[b, t] = np.mean(vals, axis=0) if vals.ndim > 1 else vals[:4].flatten() if len(vals) >= 4 else np.zeros(4)
                    x_batch[b, t, 0] = np.mean([s.vec[t][0] for t in topics])
                    x_batch[b, t, 1] = np.mean([s.vec[t][1] for t in topics])
                    x_batch[b, t, 2] = np.mean([s.vec[t][2] for t in topics])
                    x_batch[b, t, 3] = np.mean([s.vec[t][3] for t in topics])

        x_t = torch.tensor(x_batch, dtype=torch.float32)
        a_t = torch.randn(B, T, 8)
        logs = train_step(model, opt, x_t, a_t)

        if epoch % 20 == 0 or epoch == n_epochs - 1:
            print(f"  step {epoch:3d}/{n_epochs}:  "
                  f"pred={logs['pred']:.4f}  dyn={logs['dyn']:.4f}  "
                  f"rep={logs['rep']:.4f}")

    # 预测未来 5 年
    x0 = x_t[0:1, -1]
    a_fut = torch.randn(1, 5, 8)
    with torch.no_grad():
        pred = model.imagine(x0, a_fut)
    print(f"  未来预测: [{list(pred.shape)}]  "
          f"年1→[{pred[0,0,0]:.2f},{pred[0,0,1]:.2f},...]  "
          f"年5→[{pred[0,-1,0]:.2f},{pred[0,-1,1]:.2f},...]")
    print()
else:
    print("  跳过 (无 torch 或 --quick 模式)")
    print()

# ============================================================
# 2. 闭环规划 (四类用户)
# ============================================================

print("─" * 60)
print("[2/4] 闭环规划 · 四类用户")
print("─" * 60)

ctrl = SKWMClosedLoopController(kwm, ProposalPolicy(), RevisionPolicy())

results = {}
for user in ["teacher", "student", "librarian", "manager"]:
    decisions = ctrl.run(t0=2020, T=2024, goal="前沿识别",
                         user=user, M=5, L=4, B=8)
    results[user] = decisions
    topics_fmt = ", ".join(
        kwm.topic_names.get(t.split("_", 1)[-1] if "_" in t else t, t)
        for t in decisions[0]["plan"].emphasis
    )
    avg_score = np.mean([d["score"] for d in decisions])
    print(f"  {user+':':12s} 推荐: {topics_fmt}")
    print(f"             年均评分: {avg_score:.1f}  "
          f"最高: {max(d['score'] for d in decisions):.1f}")
print()

# ============================================================
# 3. 回测命中率
# ============================================================

print("─" * 60)
print("[3/4] 回测命中率 (task success)")
print("─" * 60)

ev = ClosedLoopEvaluator(kwm)
for user in ["teacher", "student", "librarian", "manager"]:
    hr = ev.hit_rate(ctrl, eval_years=[2019, 2020, 2021],
                     user=user, L=4, M=5, B=8, k=10)
    print(f"  {user+':':12s} 命中率 = {hr:.3f}")
print()

# ============================================================
# 4. 推理期缩放实验 (发现③: M/B ↑ → 命中率 ↑)
# ============================================================

print("─" * 60)
print("[4/4] 推理期缩放实验 (发现③)")
print("─" * 60)

scale_results = []

# 固定 L=4, 变化 M 和 B
for M in [2, 4, 8]:
    for B in [2, 8, 16]:
        t0 = time.time()
        hr = ev.hit_rate(ctrl, eval_years=[2019, 2020],
                         user="teacher", L=4, M=M, B=B, k=10)
        elapsed = time.time() - t0
        scale_results.append({"M": M, "B": B, "hit_rate": hr, "time": round(elapsed, 2)})
        print(f"  M={M:2d}  B={B:2d}  → 命中率 {hr:.3f}  ({elapsed:.1f}s)")

# 趋势总结
print()
hr_by_m = {m: np.mean([r["hit_rate"] for r in scale_results if r["M"] == m]) for m in [2, 4, 8]}
hr_by_b = {b: np.mean([r["hit_rate"] for r in scale_results if r["B"] == b]) for b in [2, 8, 16]}
print("  趋势: M↑ → 命中率", end="")
if hr_by_m[8] > hr_by_m[4] > hr_by_m[2]:
    print(" 单调上升 ✓ (符合发现③)")
elif hr_by_m[8] >= hr_by_m[2]:
    print(" 总体上升 △")
else:
    print(" 无明显趋势")
print(f"     M=2 均值 {hr_by_m[2]:.3f}, M=8 均值 {hr_by_m[8]:.3f}")
print("  趋势: B↑ → 命中率", end="")
if hr_by_b[16] > hr_by_b[2]:
    print(" 上升 ✓")
else:
    print(" 平稳")

# 保存结果
out = {
    "data_source": f"真实文献 {kwm.data['total']} 篇",
    "year_range": list(kwm.year_range),
    "closed_loop_results": {
        user: [
            {"year": d["year"], "score": round(d["score"], 2), "note": d["plan"].note}
            for d in results[user]
        ] for user in results
    },
    "scaling_experiment": scale_results,
}
with open(os.path.join(os.path.dirname(__file__), "run_results.json"), "w",
          encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"\n  结果已保存: run_results.json")
print()
print("=" * 60)
print("✅ 全流程完成")
print("=" * 60)
