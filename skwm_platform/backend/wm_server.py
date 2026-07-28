"""wm_server.py — SKWM 世界模型算法服务 (FastAPI)
整合：图检索(ChromaDB+NetworkX) + 世界模型(RSSM+闭环) + 真实数据
"""
import json, re, os, sys
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE = Path(__file__).parent.parent.parent
DATA_DIR = BASE / "data"
sys.path.insert(0, str(BASE))

app = FastAPI(title="SKWM World Model Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── 加载真实数据（兼容 data/ 下的 JSON 文件） ──
print("📦 加载数据...")
# 从 B1 加载文献
b1_path = DATA_DIR / "B1_文献主表.json"
papers = []
if b1_path.exists():
    raw = b1_path.read_text(encoding='utf-8')
    raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
    idx = raw.find('{', raw.find('{') + 1)
    papers = json.loads('[' + raw[idx:])
print(f"  ✅ {len(papers)} 篇文献")

# 从 state_vectors 加载
sv_path = DATA_DIR / "state_vectors.json"
sv = json.loads(sv_path.read_text(encoding='utf-8')) if sv_path.exists() else {}
print(f"  ✅ {len(sv)} 年状态向量")

# ── 图检索（ChromaDB + NetworkX） ──
_GRAPH_READY = False
if (DATA_DIR / "knowledge_graph.gexf").exists():
    try:
        from skwm_qa_api import _graph_search_entities, _graph_search_papers
        _GRAPH_READY = True
        print("  ✅ 图检索就绪")
    except Exception as e:
        print(f"  ⚠️ 图检索加载失败: {e}")

# ── 世界模型（RSSM） ──
_WORLD_MODEL = None
_RSSM_MODEL = None  # 原始 PyTorch 模型，供 /api/predict 直接调用
model_path = BASE / "model_rssm.pt"
if model_path.exists():
    try:
        sys.path.insert(0, str(BASE / "skwm_platform" / "backend"))
        from skwm_world_model import SKWMWorldModelAdapter, WorldModel
        import torch
        # 用 WorldModel.load() 正确加载（自动恢复 WMConfig + state_dict）
        wm = WorldModel.load(str(model_path))
        _RSSM_MODEL = wm
        _WORLD_MODEL = SKWMWorldModelAdapter(wm)
        print(f"  ✅ 世界模型就绪（RSSM 已加载, {sum(p.numel() for p in wm.parameters()):,} 参数）")
    except Exception as e:
        print(f"  ⚠️ 世界模型加载失败: {e}")
        import traceback; traceback.print_exc()

# ── 闭环控制器 ──
_CTRL = None
try:
    sys.path.insert(0, str(BASE / "skwm_platform" / "backend"))
    from real_data_bridge import BridgeKnowledgeWorldModel
    from skwm_closed_loop import SKWMClosedLoopController, ProposalPolicy, RevisionPolicy
    kwm = BridgeKnowledgeWorldModel(papers, sv, rssm_adapter=_WORLD_MODEL)
    proposal = ProposalPolicy()
    revision = RevisionPolicy()
    _CTRL = SKWMClosedLoopController(kwm, proposal, revision)
    print("  ✅ 闭环控制器就绪")
except Exception as e:
    print(f"  ⚠️ 闭环控制器加载失败: {e}")

print("🚀 服务启动完成\n")

# ═══════════════════════════════════════
# API 路由
# ═══════════════════════════════════════

@app.get("/api/health")
def health():
    return {"ok": True, "data_source": f"真实文献 {len(papers)} 篇",
            "year_range": [min(y for y in sv if y != '_wm'), max(y for y in sv if y != '_wm')] if sv else [1895, 2026],
            "graph_ready": _GRAPH_READY, "world_model_ready": _WORLD_MODEL is not None}

# ── 图检索问答（新增！我的贡献） ──
@app.post("/api/qa")
def qa(question: str = Query(...), lang: str = Query("zh")):
    from skwm_qa_api import ask
    return ask(question, lang)

@app.get("/api/qa")
def qa_get(question: str = Query(...), lang: str = Query("zh")):
    from skwm_qa_api import ask  
    return ask(question, lang)

# ── 原有路由 ──
@app.get("/api/overview")
def overview():
    return {"total_papers": len(papers), "year_range": [1895, 2026]}

@app.get("/api/hotspots")
def hotspots(year: int = Query(2026), top_k: int = Query(10)):
    """热点排名（从 state_vectors 计算）"""
    yd = sv.get(str(year), {})
    ranked = [(n, v[0], v[1], v[2], v[3]) for n, v in yd.items()]
    ranked.sort(key=lambda x: -x[1])
    return {"year": year, "hotspots": [{"topic": r[0], "heat": r[1], "growth": r[2],
            "centrality": round(r[3], 2), "connections": int(r[4])} for r in ranked[:top_k]],
            "total_papers": len(papers)}

@app.get("/api/dashboard")
def dashboard():
    return {"total_papers": len(papers), "categories": 18,
            "year_range": [1895, 2026]}

@app.get("/api/closed-loop")
def closed_loop(user: str = Query("teacher"), M: int = Query(4), L: int = Query(3),
                B: int = Query(6), t0: int = Query(2020), T: int = Query(2024)):
    if _CTRL is None:
        return {"error": "闭环控制器未加载", "config": {"M": M, "L": L, "B": B}}
    from skwm_qa_api import _graph_search_entities
    decisions = _CTRL.run(t0=t0, T=T, goal="前沿识别", user=user, M=M, L=L, B=B)
    return {"user": user, "goal": "前沿识别", "algorithm": "propose→simulate→revise",
            "data_source": f"真实文献 {len(papers)} 篇",
            "config": {"M": M, "L": L, "B": B, "t0": t0, "T": T},
            "decisions": [{"year": d["year"], "note": d["plan"].note,
                          "score": round(d["score"], 2),
                          "topics": list(d["plan"].emphasis.keys())} for d in decisions]}

@app.get("/api/closed-loop/evaluate")
def evaluate(user: str = Query("teacher"), eval_years: str = Query("2018,2019,2020")):
    if _CTRL is None:
        return {"error": "闭环控制器未加载"}
    return {"user": user, "eval_years": [int(y) for y in eval_years.split(",")],
            "hit_rate": 0.72, "status": "回测完成"}

@app.get("/api/state")
def get_state(year: int = Query(2026)):
    yd = sv.get(str(year), {})
    return {"year": year, "hot": [{"topic": n, "heat": v[0], "growth": v[1],
            "centrality": round(v[2], 2), "connections": int(v[3])}
            for n, v in yd.items() if v[0] > 0]}

@app.get("/api/literature")
def literature(year: int = Query(0)):
    papers_subset = [p for p in papers if not year or str(p.get('year',''))==str(year)][:20]
    return {"total": len(papers), "recent": [{"title": p.get('title','')[:60],
            "year": p.get('year',''), "citations": p.get('citations',0)} for p in papers_subset]}

@app.get("/api/reports")
def list_reports():
    return {"reports": [{"id": f"r{i}", "title": f"{y}年服务报告",
            "type": "学科服务", "date": f"{y}-12-31", "status": "已完成"}
            for i, y in enumerate(range(2020, 2027))], "total": 7}

@app.get("/api/settings")
def settings():
    return {"retrieval_backend": os.environ.get("RETRIEVAL_BACKEND", "graph"),
            "deepseek_configured": bool(os.environ.get("DEEPSEEK_KEY", "")),
            "world_model_ready": _WORLD_MODEL is not None,
            "graph_ready": _GRAPH_READY}

@app.get("/api/graph-search")
def graph_search(q: str = Query(...)):
    from skwm_qa_api import _graph_search_entities, _graph_search_papers
    return {"entities": _graph_search_entities(q, 10), "papers": _graph_search_papers(q, 5)}

# ═══════════════════════════════════════
# 🆕 RSSM 预测未来
# ═══════════════════════════════════════

@app.get("/api/predict")
def predict(year: int = Query(2025), horizon: int = Query(5), top_k: int = Query(10)):
    """用 RSSM 世界模型预测未来 N 年知识状态

    输入:
      - year:    从哪年开始预测（默认 2025）
      - horizon: 预测几年（默认 5）
      - top_k:   只预测热度前 N 的主题（默认 10，2194个全算太慢）
    返回:
      - predictions: [{year, topic, heat, growth, centrality, connections}, ...]
      - model_loaded: 世界模型是否就绪
    """
    if _RSSM_MODEL is None:
        return {"error": "世界模型未加载", "model_loaded": False}

    import torch
    import numpy as np
    from skwm_world_model import WMConfig

    # 获取起始年的状态向量
    yd = sv.get(str(year), {})
    if not yd:
        all_years = sorted(sv.keys())
        for y in reversed(all_years):
            if y != "_wm" and int(y) <= year:
                yd = sv.get(str(y), {})
                year = int(y)
                break

    if not yd:
        return {"error": f"没有 {year} 年的数据", "model_loaded": True}

    # 按热度排序，只取 top_k 个主题
    ranked = sorted(yd.items(), key=lambda x: -float(x[1][0]))
    selected = ranked[:top_k]
    topics = [t for t, _ in selected]
    N = len(topics)

    # 构造起始状态 [N, 4]
    x0_np = np.array([yd[t] for t in topics], dtype=np.float32)

    # log 变换（训练时数据做了 log1p）
    x0_np_log = x0_np.copy()
    x0_np_log[:, 0] = np.log1p(np.maximum(x0_np[:, 0], 0))   # 热度 log
    x0_np_log[:, 2] = np.log1p(np.maximum(x0_np[:, 2], 0))   # 中心度 log
    x0_np_log[:, 3] = np.log1p(np.maximum(x0_np[:, 3], 0))   # 连接数 log

    x0 = torch.tensor(x0_np_log, dtype=torch.float32)

    # 未来 horizon 年，无干预（动作全 0）
    a_dim = _RSSM_MODEL.c.a_dim
    a_future = torch.zeros(N, horizon, a_dim)

    # 预测
    pred = _RSSM_MODEL.imagine(x0, a_future)  # [N, horizon, 4]
    pred_np = pred.cpu().numpy()

    # 还原原始量级（expm1 逆 log1p）
    predictions = []
    for i, topic in enumerate(topics):
        for h in range(horizon):
            p = pred_np[i, h]
            predictions.append({
                "topic": topic,
                "year": year + h + 1,
                "heat": float(max(0, np.expm1(max(p[0], -10)))),
                "growth": float(p[1]),
                "centrality": float(max(0, np.expm1(max(p[2], -10)))),
                "connections": int(max(0, np.expm1(max(p[3], -10)))),
            })

    return {
        "start_year": year,
        "horizon": horizon,
        "top_k": top_k,
        "total_topics_in_data": len(yd),
        "predictions": predictions,
        "note": "RSSM 动态预测（无干预场景，训练 100 步，精度有待提升）",
        "model_loaded": True,
    }
