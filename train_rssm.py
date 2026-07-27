"""train_rssm.py — 用真实文献训练 RSSM (v3)
状态格式与 real_data_layer.get_state() 完全一致:
  [热度(论文数), 增速, 中心度(log引用+1), 连接数(累计论文数)]
"""
import sys, os, numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from real_data_layer import RealKnowledgeWorldModel
from skwm_world_model import WorldModel, WMConfig, train_step, symlog, symexp

# ====== 1. 直接用 real_data_layer 的状态 ======
print("[1/5] 加载真实文献...")
kwm = RealKnowledgeWorldModel()

YEARS = list(range(1995, 2026))  # 31年
T = 8

seq_list = []
for topic in kwm.topics:
    vecs = []
    for y in YEARS:
        s = kwm.get_state(y)
        v = s.vec[topic].copy()  # [热度, 增速, 中心度, 连接数]
        v[0] = np.log1p(v[0])    # 论文数取 log
        v[2] = np.log1p(v[2])    # 中心度取 log
        v[3] = np.log1p(v[3])    # 连接数取 log
        vecs.append(v)
    for start in range(len(vecs) - T):
        seq_list.append(np.stack(vecs[start:start+T], axis=0))

x_data = np.stack(seq_list, axis=0).astype(np.float32)
N = x_data.shape[0]
print(f"   年份: {YEARS[0]}-{YEARS[-1]}, 主题: {len(kwm.topics)}")
print(f"   状态: [log论文数, 增速, log中心度, log连接数]")
print(f"   序列: {N} 条, shape: {list(x_data.shape)}")
print(f"   值域: [{x_data.min():.3f}, {x_data.max():.3f}]")

# ====== 2. 训练 ======
print(f"\n[2/5] 训练 RSSM ({N} 序列)...")
c = WMConfig(x_dim=4, a_dim=4, deter=128, stoch=32, hidden=128)
model = WorldModel(c)
opt = torch.optim.Adam(model.parameters(), lr=c.lr)
print(f"   参数: {sum(p.numel() for p in model.parameters()):,}")

B = 64
n_epochs = 2000
for step in range(n_epochs):
    idx = np.random.choice(N, B)
    x_batch = torch.tensor(x_data[idx], dtype=torch.float32)
    a_batch = torch.zeros(B, T, c.a_dim)
    logs = train_step(model, opt, x_batch, a_batch)
    if step % 500 == 0 or step == n_epochs - 1:
        print(f"   step {step:4d}: pred={logs['pred']:.4f}  dyn={logs['dyn']:.4f}")

# ====== 3. 保存 ======
model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_rssm.pt")
model.save(model_path)
print(f"\n[3/5] 已保存 ({os.path.getsize(model_path)/1024:.0f}KB)")

# ====== 4. 验证预测 ======
print(f"\n[4/5] 验证...")
model.eval()
with torch.no_grad():
    test_x = torch.tensor(x_data[-16:], dtype=torch.float32)  # 16条
    x0 = test_x[:, -1, :]
    a_fut = torch.zeros(16, 2, c.a_dim)
    pred = model.imagine(x0, a_fut)  # [16, 2, 4]
    
    real = test_x[:, -1, :]  # 真实下一步
    err = float(torch.abs(pred[:, 0] - real).mean())
    print(f"   1步预测误差 (log空间): {err:.4f}")
    
    for i in range(3):
        r = real[i].numpy()
        p = pred[i, 0].numpy()
        names = ["论文数","增速","中心度","连接数"]
        diffs = ", ".join(f"{names[j]}: {np.expm1(r[j]):.0f}→{np.expm1(p[j]):.0f}" for j in range(4))
        print(f"   例{i+1}: {diffs}")

# ====== 5. 桥接闭环 ======
print(f"\n[5/5] 桥接闭环...")
from skwm_closed_loop import SKWMClosedLoopController, ProposalPolicy, RevisionPolicy
from skwm_world_model import SKWMWorldModelAdapter

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
adapter = SKWMWorldModelAdapter(model, device)
kwm.rollout = lambda o, control, horizon: adapter.rollout(o, control, horizon)

ctrl = SKWMClosedLoopController(kwm, ProposalPolicy(), RevisionPolicy())
for user in ["teacher", "student", "manager"]:
    decisions = ctrl.run(t0=2020, T=2022, goal="前沿识别", user=user, M=4, L=2, B=4)
    print(f"   {user}: {len(decisions)}年, 均分{np.mean([d['score'] for d in decisions]):.0f}")

print(f"\n[OK] model_rssm.pt 已就绪")
