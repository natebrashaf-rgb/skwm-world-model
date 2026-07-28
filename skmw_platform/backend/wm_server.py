"""wm_server.py — SKWM 世界模型算法服务 (FastAPI)
极速启动：先响应健康检查，数据后台懒加载
"""
import json, re, os, sys, threading
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

BASE = Path(__file__).parent.parent.parent
DATA_DIR = BASE / "data"
FRONTEND_DIR = BASE / "skwm_platform" / "frontend_new" / "dist"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "skmw_platform" / "backend"))

app = FastAPI(title="SKWM World Model Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── 服务前端静态文件 ──
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

# ── 全局状态：懒加载 ──
_data = {"papers": [], "sv": {}, "graph_ready": False, "wm_ready": False, "ctrl": None, "loading_error": None}
_loading_done = threading.Event()

def _load_data():
    """后台加载数据"""
    print("📦 后台加载数据...")
    b1_path = DATA_DIR / "B1_文献主表.json"
    if b1_path.exists():
        raw = b1_path.read_text(encoding='utf-8')
        raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
        idx = raw.find('{', raw.find('{') + 1)
        _data["papers"] = json.loads('[' + raw[idx:])
    print(f"  ✅ {len(_data['papers'])} 篇文献")

    sv_path = DATA_DIR / "state_vectors.json"
    if sv_path.exists():
        _data["sv"] = json.loads(sv_path.read_text(encoding='utf-8'))
    print(f"  ✅ {len(_data['sv'])} 年状态向量")

    # 图检索
    if (DATA_DIR / "knowledge_graph.gexf").exists():
        try:
            from skwm_qa_api import _graph_search_entities, _graph_search_papers
            _data["graph_ready"] = True
            print("  ✅ 图检索就绪")
        except Exception as e:
            print(f"  ⚠️ 图检索失败: {e}")

    # RSSM 世界模型
    model_path = BASE / "model_rssm.pt"
    if model_path.exists():
        try:
            import torch
            from skwm_world_model import SKWMWorldModelAdapter, WorldModel, WMConfig
            state = torch.load(str(model_path), map_location='cpu', weights_only=False)
            c = WMConfig(**state['config'])
            wm = WorldModel(c)
            wm.load_state_dict(state['model'])
            _data["wm"] = SKWMWorldModelAdapter(wm)
            _data["wm_ready"] = True
            print(f"  ✅ 世界模型就绪")
        except Exception as e:
            _data["loading_error"] = f"世界模型失败: {e}"
            print(f"  ⚠️ 世界模型失败: {e}")
            import traceback; traceback.print_exc()

    # 闭环控制器
    try:
        from real_data_bridge import BridgeKnowledgeWorldModel
        from skwm_closed_loop import SKWMClosedLoopController, ProposalPolicy, RevisionPolicy
        kwm = BridgeKnowledgeWorldModel(_data["papers"], _data["sv"], rssm_adapter=_data.get("wm"))
        proposal = ProposalPolicy()
        revision = RevisionPolicy()
        _data["ctrl"] = SKWMClosedLoopController(kwm, proposal, revision)
        print("  ✅ 闭环控制器就绪")
    except Exception as e:
        print(f"  ⚠️ 闭环控制器失败: {e}")

    _loading_done.set()
    print("🚀 数据加载完成")

# 启动后台加载线程
threading.Thread(target=_load_data, daemon=True).start()

# ═══════════════════ 路由 ═══════════════════

@app.get("/api/health")
def health():
    return {"ok": True, "status": "loading" if not _loading_done.is_set() else "ready",
            "papers": len(_data["papers"]), "loading_done": _loading_done.is_set(),
            "graph_ready": _data["graph_ready"], "wm_ready": _data["wm_ready"],
            "loading_error": _data.get("loading_error")}

# QA: GET 用 Query，POST 用 JSON body
@app.get("/api/qa")
def qa_get(question: str = Query(...), lang: str = Query("zh")):
    _loading_done.wait(timeout=30)
    from skwm_qa_api import ask
    return ask(question, lang)

@app.post("/api/qa")
def qa_post(body: dict):
    _loading_done.wait(timeout=30)
    from skwm_qa_api import ask
    return ask(body.get("question",""), body.get("lang","zh"))

@app.get("/api/predict")
def predict(topic: str = Query("旅游"), horizon: int = Query(5), top_k: int = Query(10)):
    """RSSM 世界模型预测未来

    输入:
      - topic:   起始主题（预测该主题及相关趋势，默认"旅游"）
      - horizon: 预测几年（默认 5）
      - top_k:   返回前 N 个热点（默认 10）
    返回:
      - predictions: [{topic, heat, growth}, ...]
    """
    _loading_done.wait(timeout=30)
    if not _data.get("wm"):
        return {"error": "世界模型未加载"}
    from skwm_closed_loop import KnowledgeState
    latest = max(int(k) for k in _data["sv"] if k != '_wm')
    vec = {}
    for yr in range(latest - horizon, latest + 1):
        yd = _data["sv"].get(str(yr), {})
        for t, v in yd.items():
            if t not in vec:
                vec[t] = [float(x) for x in v]
    o = KnowledgeState(vec=vec, year=latest - horizon)
    fut = _data["wm"].rollout(o, {"feature_shift": {topic: 0.3}}, horizon=horizon)
    result = [{"topic": t, "heat": round(float(fut.vec[t][0]), 1),
               "growth": round(float(fut.vec[t][1]), 4)} for t in fut.hot_topics(top_k)]
    return {
        "start_topic": topic,
        "horizon": horizon,
        "top_k": top_k,
        "predictions": result,
        "model_loaded": True
    }

@app.get("/api/hotspots")
def hotspots(year: int = Query(2026), top_k: int = Query(10)):
    _loading_done.wait(timeout=30)
    yd = _data["sv"].get(str(year), {})
    ranked = sorted([(n, v[0], v[1], v[2], v[3]) for n, v in yd.items()], key=lambda x: -x[1])
    return {"year": year, "hotspots": [{"topic": r[0], "heat": r[1], "growth": r[2],
            "centrality": round(r[3], 2), "connections": int(r[4])} for r in ranked[:top_k]],
            "total_papers": len(_data["papers"])}

@app.get("/api/overview")
def overview():
    return {"total_papers": len(_data["papers"]) if _data["papers"] else 0, "year_range": [1895, 2026]}

@app.get("/api/dashboard")
def dashboard():
    return {"total_papers": len(_data["papers"]) if _data["papers"] else 0, "categories": 18, "year_range": [1895, 2026]}

@app.get("/api/closed-loop")
def closed_loop(user: str = Query("teacher"), M: int = Query(4), L: int = Query(3),
                B: int = Query(6), t0: int = Query(2020), T: int = Query(2024)):
    _loading_done.wait(timeout=30)
    if not _data.get("ctrl"):
        return {"error": "闭环控制器未加载"}
    decisions = _data["ctrl"].run(t0=t0, T=T, goal="前沿识别", user=user, M=M, L=L, B=B)
    return {"user": user, "decisions": [{"year": d["year"], "note": d["plan"].note,
            "score": round(d["score"], 2), "topics": list(d["plan"].emphasis.keys())} for d in decisions]}

# SPA fallback
@app.get("/{path:path}")
async def spa(path: str):
    if path.startswith("api/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    if FRONTEND_DIR.exists():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
    return JSONResponse({"error": "前端未构建"}, status_code=500)
