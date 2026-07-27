#!/usr/bin/env python3
"""
api.py —— 把 SKWMController 包成 HTTP 服务，供 Next.js 前端调用。

运行：
    pip install fastapi uvicorn requests xgboost numpy
    uvicorn api:app --reload --port 8000

健康检查：  GET  http://localhost:8000/api/health
交互文档：  http://localhost:8000/docs   (FastAPI 自动生成)

依赖你已有的 skwm_aligned_v4.py（同目录），并叠加本升级包的
    skwm_context.py (C)  与  skwm_service.py (P)。
"""
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from skwm_aligned_v4 import DataLayer, DeepSeekClient, SKWMController, SKWM
from skwm_context import ContextEngine
from skwm_service import ServiceRules

# ── 新增模块 ──────────────────────────────────────────
from vector_store import VectorStore
from knowledge_graph import KnowledgeGraph
from graph_rag import GraphRAG
from feishu_bot import FeishuBot
from report_generator import ReportGenerator
from obsidian_sync import ObsidianSync
# ──────────────────────────────────────────────────────

# ── 启动时加载一次（重用）─────────────────────────────────
print("🚀 启动 SKWM API … 加载世界模型数据")
DATA = DataLayer().load(verbose=True)
DS = DeepSeekClient()
CTRL = SKWMController(DATA, DS)
CTX = ContextEngine()
SVC = ServiceRules(data=DATA)
print("✅ 就绪")

# ── 跨语言世界模型适配器（新融合）───────────────────────────
print("🚀 初始化跨语言世界模型...")
try:
    from world_model_adapter import WorldModelAdapter
    WM = WorldModelAdapter(DATA)
    WM.initialize()
    print("✅ 跨语言世界模型就绪")
except Exception as e:
    WM = None
    print(f"⚠️ 跨语言世界模型未加载: {e}")
# ──────────────────────────────────────────────────────

# ── 新增模块初始化 ──────────────────────────────────
print("🚀 加载扩展模块...")
VS = VectorStore()
VS.load_skwm_data(DATA)
KG = KnowledgeGraph(DATA)
GRAG = GraphRAG(DATA, VS, KG, SVC)
FEISHU = FeishuBot()
REPORTER = ReportGenerator()
OBSIDIAN = ObsidianSync()
print("✅ 扩展模块就绪")
# ──────────────────────────────────────────────────────

app = FastAPI(title="SKWM API", version="1.0",
              description="科学知识世界模型驱动的中阿文旅智能学科服务")

# 允许 Next.js 开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"], allow_headers=["*"],
)


def _latest():
    return max(DATA.year_range) if DATA.year_range else 2026


# ── 1. 健康 / 概览（修正前端写死的假数据）─────────────────────
@app.get("/api/health")
def health():
    return {"ok": True, "llm": DS.cost_str()}


@app.get("/api/overview")
def overview():
    """首页真实指标（替换 ModelStats.tsx 里的 1,284/4,672/210）"""
    total_nodes = sum(s.get("n_nodes", 0) for s in DATA.snapshots.values())
    total_edges = sum(s.get("n_edges", 0) for s in DATA.snapshots.values())
    return {
        "entities": total_nodes,
        "relations": total_edges,
        "state_vectors": DATA.n_state_vectors,
        "snapshots": DATA.n_snapshots,
        "year_range": DATA.year_range,
    }


# ── 2. 热点分析 S（已叠加 C 语境加权）───────────────────────
@app.get("/api/hotspots")
def hotspots(year: int = Query(default=None), user: str = "teacher", top_k: int = 10):
    y = year or _latest()
    raw = DATA.get_hot_topics(y, top_k * 2)
    reweighted = CTX.reweight(raw, y, user, score_key="heat")  # C 介入
    return {"year": y, "user": user, "hotspots": reweighted[:top_k],
            "active_context_dims": CTX.active_dims(y)}


# ── 3. 前沿识别 + 预测 T ─────────────────────────────────
@app.get("/api/frontier")
def frontier(year: int = Query(default=None), top_k: int = 10):
    y = year or _latest()
    return CTRL.metrics.frontier_identification(y, top_k)


@app.get("/api/predict")
def predict(year: int = Query(default=None), delta: int = 5):
    y = year or _latest()
    return CTRL.metrics.predict_trend(y, delta)


@app.get("/api/counterfactual")
def counterfactual(bridge: str, year: int = Query(default=None)):
    y = year or _latest()
    return CTRL.metrics.counterfactual_analysis(bridge, y)


# ── 4. 知识图谱 E+R ──────────────────────────────────
@app.get("/api/graph")
def graph(entity: str = None, year: int = Query(default=None)):
    y = year or _latest()
    if entity:
        return CTRL.kg.relation_query(entity, y)
    return CTRL.kg.knowledge_overview(y)


# ── 5. RAG 智能问答（真调用世界模型 + 推荐 + 审核）──────────────
class QueryReq(BaseModel):
    question: str
    user: str = "teacher"
    context: Optional[str] = "default"


@app.post("/api/query")
def query(req: QueryReq):
    CTRL.set_user(req.user)
    if req.context:
        CTRL.set_context(req.context)
    result = CTRL.process(req.question)   # 真实世界模型输出 {E,R,S,T,C,U,P}
    # P: 对热点做推荐排序
    hot = result["skwm"]["S"]["hot_topics"]
    result["skwm"]["P"]["recommendations"] = SVC.recommend(hot, req.user, top_k=5)
    return result


# ── 6. 报告生成 + 审核 + 推送 + 沉淀（P 四规则全链路）────────────
class ReportReq(BaseModel):
    topic: str = "中阿文旅"
    user: str = "librarian"
    year: Optional[int] = None
    push: bool = False
    sediment: bool = True


@app.post("/api/report")
def report(req: ReportReq):
    y = req.year or _latest()
    rep = CTRL.report.generate_report(req.topic, req.user, y)
    rep = SVC.audit(rep)                       # P.audit
    out = {"report": rep}
    if req.sediment:
        out["sediment"] = SVC.sediment(rep)    # P.sediment
    if req.push:
        summary = f"**{rep['title']}**\n数据：{rep.get('data_scale','')}\n审核：{rep['audit']['status']}"
        out["push"] = SVC.push(rep["title"], summary)  # P.push
    return out


# ── 7. 年度时间线 T（真实 per-year 节点/边）──────────────────────
@app.get("/api/timeline")
def timeline():
    rows = []
    for y, s in sorted(DATA.snapshots.items(), key=lambda kv: int(kv[0])):
        rows.append({"year": int(y), "nodes": s.get("n_nodes", 0),
                     "edges": s.get("n_edges", 0)})
    return {"timeline": rows}


# ── 8. 报告列表（读取已沉淀的 Markdown）───────────────────────
@app.get("/api/reports")
def list_reports():
    vault = SVC.obsidian_vault
    items = []
    if vault.exists():
        for fp in sorted(vault.glob("*.md"), reverse=True):
            meta = {"id": fp.stem, "title": fp.stem, "date": "",
                    "type": "SKWM报告", "status": "已沉淀",
                    "size": f"{fp.stat().st_size} B"}
            try:
                for line in fp.read_text(encoding="utf-8")[:400].splitlines():
                    if line.startswith("title:"):
                        meta["title"] = line.split(":", 1)[1].strip()
                    elif line.startswith("created:"):
                        meta["date"] = line.split(":", 1)[1].strip()
                    elif line.startswith("user_type:"):
                        meta["type"] = line.split(":", 1)[1].strip() or meta["type"]
            except Exception:
                pass
            items.append(meta)
    return {"reports": items, "total": len(items)}


# ═══════════════════════════════════════════════════════════
#  新增扩展 API 路由（不修改已有路由）
# ═══════════════════════════════════════════════════════════

# ── 9. 知识图谱增强 ──
@app.get("/api/graph/kg")
def graph_kg():
    return KG.overview()

@app.get("/api/graph/search")
def graph_search(keyword: str = Query(default="")):
    return {"results": KG.search(keyword)}

# ── 10. 向量检索 ──
@app.get("/api/retrieve")
def retrieve(q: str = Query(default=""), top_k: int = 5):
    return {"query": q, "results": VS.search(q, top_k)}

# ── 11. GraphRAG 问答 ──
class GraphRAGReq(BaseModel):
    question: str
    user: str = "teacher"

@app.post("/api/query/kg")
def query_kg(req: GraphRAGReq):
    result = GRAG.answer(req.question, req.user)
    OBSIDIAN.save_qa(req.question, result)
    return result

# ── 12. 飞书机器人 Webhook ──
@app.post("/api/feishu/webhook")
async def feishu_webhook(request: Request):
    body = await request.json()
    return FEISHU.handle(body, GRAG)

# ── 13. 报告生成（新模板版）──
class ReportReq(BaseModel):
    topic: str
    type: str = "学科分析报告"

@app.post("/api/report/new")
def report_new(req: ReportReq):
    hotspots = DATA.get_hot_topics(_latest(), 10)
    report = REPORTER.generate(req.topic, req.type, {"hotspots": hotspots, "timeline": DATA.snapshots})
    OBSIDIAN.save_report(report)
    return report

# ── 14. Obsidian 知识沉淀 ──
@app.get("/api/obsidian/list")
def obsidian_list(days: int = 7):
    return {"notes": OBSIDIAN.list_recent(days)}

@app.post("/api/obsidian/snapshot")
def obsidian_snapshot():
    hotspots = DATA.get_hot_topics(_latest(), 10)
    total_nodes = sum(s.get("n_nodes", 0) for s in DATA.snapshots.values())
    total_edges = sum(s.get("n_edges", 0) for s in DATA.snapshots.values())
    fp = OBSIDIAN.save_snapshot(hotspots, total_nodes, total_edges)
    return {"status": "saved", "path": str(fp)}

# ── 15. 系统统计 ──
@app.get("/api/stats")
def stats():
    return {
        "entities": sum(s.get("n_nodes", 0) for s in DATA.snapshots.values()),
        "relations": sum(s.get("n_edges", 0) for s in DATA.snapshots.values()),
        "state_vectors": DATA.n_state_vectors,
        "snapshots": DATA.n_snapshots,
        "vectors_in_db": VS.count(),
        "obsidian_notes": len(list(Path(OBSIDIAN.vault_dir).rglob("*.md"))),
    }


# ═══════════════════════════════════════════════════════════
#  跨语言世界模型 API（融合 crosslingual_world_model）
# ═══════════════════════════════════════════════════════════

# ── 16. 知识演化预测 ──
@app.get("/api/wm/predict")
def wm_predict(year: int = Query(default=None), horizon: int = 5):
    """世界模型预测知识状态演化（替代原简单趋势）"""
    if WM is None:
        return {"error": "world model not loaded"}
    return WM.predict_next_state(year, horizon=horizon)

# ── 17. 跨语言对齐 ──
@app.get("/api/wm/alignment")
def wm_alignment(year: int = Query(default=None)):
    """跨语言（中/英/阿）知识对齐分析"""
    if WM is None:
        return {"error": "world model not loaded"}
    return WM.get_alignment(year)

# ── 18. 因果干预 ──
@app.get("/api/wm/intervene")
def wm_intervene(year: int = Query(default=None),
                  concept: str = Query(default=""),
                  type: str = Query(default="concept_boost")):
    """反事实因果干预分析"""
    if WM is None:
        return {"error": "world model not loaded"}
    return WM.counterfactual(year, boost_concept=concept, intervention_type=type)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
