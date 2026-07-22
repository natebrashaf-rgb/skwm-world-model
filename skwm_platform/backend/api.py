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
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from skwm_aligned_v4 import DataLayer, DeepSeekClient, SKWMController, SKWM, ArabicAgent
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

# 允许跨域（Railway 前端域名不固定）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)


def _latest():
    return max(DATA.year_range) if DATA.year_range else 2026


# ── 0. 根路由：服务前端 SPA ──────────────────────────────
@app.get("/")
def root():
    idx = Path(__file__).parent / "index.html"
    if idx.exists():
        return HTMLResponse(content=idx.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse("<h1>SKWM API</h1><p>前端页面未生成。运行 generate_frontend.py 生成 index.html</p>", status_code=200)


_INDEX_HTML = None


@app.on_event("startup")
def _cache_index():
    global _INDEX_HTML
    idx = Path(__file__).parent / "index.html"
    if idx.exists():
        _INDEX_HTML = idx.read_text(encoding="utf-8")
        print(f"✅ 前端页面已加载 ({len(_INDEX_HTML)} bytes)")
    else:
        print("⚠️ 未找到 index.html — 只有 API 可用")


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

# ── 12. 飞书机器人（被动Webhook + 主动推送） ──
@app.post("/api/feishu/webhook")
async def feishu_webhook(request: Request):
    body = await request.json()
    return FEISHU.handle(body, GRAG)


class PushReq(BaseModel):
    topic: str = "中阿文旅"
    user: str = "librarian"
    year: Optional[int] = None


@app.post("/api/feishu/push-report")
def push_report(req: PushReq):
    """推送学科服务报告到飞书群"""
    y = req.year or _latest()
    rep = CTRL.report.generate_report(req.topic, req.user, y)
    rep = SVC.audit(rep)
    data_summary = f"{DATA.n_snapshots}年切片 × {DATA.n_state_vectors:,}条向量"
    result = FEISHU.push_report(
        title=rep["title"],
        content=rep.get("content", rep.get("summary", "")),
        data_summary=data_summary,
        user_type=req.user,
    )
    if result.get("status") == "fallback_log":
        # 也记到 push_outbox
        SVC.push(rep["title"], f"**{rep['title']}**\n数据：{data_summary}\n审核：{rep['audit']['status']}")
    return {"push": result, "report": rep["title"]}


@app.post("/api/feishu/push-hotspot")
def push_hotspot():
    """推送热点排行榜到飞书群"""
    y = _latest()
    hot = DATA.get_hot_topics(y, 10)
    result = FEISHU.push_hotspot_alert(hot, y)
    return {"push": result, "year": y}


@app.post("/api/feishu/push-frontier")
def push_frontier():
    """推送新兴前沿到飞书群"""
    y = _latest()
    em = DATA.get_emerging(y, 10)
    result = FEISHU.push_frontier_alert(em, y)
    return {"push": result, "year": y}


@app.post("/api/feishu/push-briefing")
def push_briefing():
    """推送每日简报到飞书群"""
    y = _latest()
    hot = DATA.get_hot_topics(y, 3)
    em = DATA.get_emerging(y, 3)
    total_nodes = sum(s.get("n_nodes", 0) for s in DATA.snapshots.values())
    total_edges = sum(s.get("n_edges", 0) for s in DATA.snapshots.values())
    result = FEISHU.push_daily_briefing(hot, em, total_nodes, total_edges)
    return {"push": result}


@app.get("/api/feishu/test")
def feishu_test():
    """测试飞书连接"""
    result = FEISHU.push_test()
    return result


@app.get("/api/feishu/status")
def feishu_status():
    """飞书配置状态"""
    return {
        "configured": FEISHU.is_configured(),
        "webhook_url": FEISHU.webhook_url[:30] + "..." if FEISHU.webhook_url else None,
        "push_count": FEISHU.push_count,
    }

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
#  合并补充：知识图谱可视化 + 阿文智能体 + 科学地图
# ═══════════════════════════════════════════════════════════

import re as _re
from collections import defaultdict as _dd


def _has_zh(s: str) -> bool:
    return bool(_re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', s))


_ETYPE_KEYWORDS = {
    "主题": ["研究","分析","理论","方法","模型","系统","技术","应用",
             "旅游","文旅","文化","遗产","数字","元宇宙","知识图谱",
             "tourism","tour","travel","culture","heritage","digital",
             "health","disease","gene","cell","education","social",
             "knowledge","data","network","policy","strategy"],
    "机构": ["大学","学院","研究所","研究院","中心","实验室","图书馆",
             "university","college","institute","lab","center"],
    "地点": ["中国","北京","阿拉伯","沙特","阿联酋","埃及","卡塔尔",
             "china","arab","saudi","emirates","dubai","egypt",
             "gulf","middle east","非洲","亚洲","欧洲"],
    "政策": ["政策","倡议","规划","战略","法规","标准",
             "policy","standard","regulation","initiative",
             "一带一路","belt and road"],
    "项目": ["项目","工程","基金","课题","project","program","fund"],
    "事件": ["会议","论坛","展览","峰会","conference","forum","summit"],
    "术语": ["本体","术语","词表","ontology","taxonomy","terminology"],
    "作者": [], "文献": [],
}


def _classify_entity(name: str) -> str:
    name_lower = name.lower()
    for etype, keywords in _ETYPE_KEYWORDS.items():
        if etype in ("作者","文献"): continue
        for kw in keywords:
            if kw.lower() in name_lower: return etype
    return "主题"


@app.get("/api/graph-data")
def graph_data(year: int = Query(default=None), limit: int = Query(default=500, ge=10, le=1000),
               min_heat: float = Query(default=0.0, ge=0.0),
               lang: str = Query(default="zh", pattern=r"^(zh|en|all)$")):
    """力导向图数据"""
    y = year or _latest()
    snapshot = DATA.snapshots.get(str(y), {})
    node_names = snapshot.get("nodes", [])
    real_edges = snapshot.get("edges", [])
    state_vecs = DATA.get_entities(y)
    nodes = []
    for name in node_names:
        vec = state_vecs.get(name)
        d, g, c, n = vec if vec else (0,0,0,0)
        if d < min_heat: continue
        is_zh = _has_zh(name)
        if lang == "zh" and not is_zh: continue
        if lang == "en" and is_zh: continue
        group = 3 if c >= 0.66 else (2 if c >= 0.33 else 1)
        nodes.append({"id":name,"label":name,"value":max(5,round(d*100)),
                      "group":group,"heat":round(d,4),"growth":round(g,4),
                      "centrality":round(c,4),"connections":int(n),
                      "entity_type":_classify_entity(name)})
        if len(nodes) >= limit: break
    node_ids = {n["id"] for n in nodes}
    edges, seen = [], set()
    for e in real_edges:
        src, tgt = e.get("u",""), e.get("v","")
        if src in node_ids and tgt in node_ids:
            pair = (src,tgt)
            if pair not in seen:
                seen.add(pair); seen.add((tgt,src))
                edges.append({"source":src,"target":tgt,"label":"共现",
                              "weight":max(0.1,float(e.get("w",1)))})
    return {"year":y,"nodes":nodes,"edges":edges[:limit*3],
            "stats":{"total_entities":max(len(node_names),len(state_vecs)),
                     "nodes_rendered":len(nodes),"edges_rendered":len(edges),
                     "year_range":DATA.year_range,
                     "real_edges_in_snapshot":len(real_edges)},
            "library_total":DATA.n_state_vectors}


@app.get("/api/graph-clusters")
def graph_clusters(year: int = Query(default=None),
                   lang: str = Query(default="zh",pattern=r"^(zh|en|all)$"),
                   min_heat: float = Query(default=0.0,ge=0.0)):
    """按实体类型聚簇总览"""
    if year == -1:  # 全库模式
        all_entities = {}
        for y_str, snap in DATA.snapshots.items():
            if not y_str.isdigit(): continue
            for name in snap.get("nodes",[]):
                if name in all_entities: continue
                is_zh = _has_zh(name)
                if lang == "zh" and not is_zh: continue
                if lang == "en" and is_zh: continue
                sv = DATA.state_vectors.get(y_str,{})
                vec = sv.get(name,[0,0,0,0])
                all_entities[name] = {"name":name,"heat":vec[0],"growth":vec[1],
                                       "centrality":vec[2],"connections":int(vec[3])}
        clusters = _dd(list)
        for name, item in all_entities.items():
            clusters[_classify_entity(name)].append(item)
        year_label = f"全库({DATA.year_range[0]}~{DATA.year_range[1]})"
        total_unique = len(all_entities)
    else:
        y = year or _latest()
        entities = DATA.get_entities(y)
        clusters = _dd(list)
        for name, vec in entities.items():
            d,g,c,n = vec
            if d < min_heat: continue
            is_zh = _has_zh(name)
            if lang == "zh" and not is_zh: continue
            if lang == "en" and is_zh: continue
            clusters[_classify_entity(name)].append(
                {"name":name,"heat":d,"growth":g,"centrality":c,"connections":int(n)})
        year_label = str(y)
        total_unique = sum(len(v) for v in clusters.values())
    result = []
    for etype in ["主题","机构","地点","政策","项目","事件","术语","作者","文献"]:
        items = clusters.get(etype,[])
        if not items: continue
        items.sort(key=lambda x:-x["heat"])
        result.append({"type":etype,"count":len(items),
                       "avg_heat":round(sum(it["heat"] for it in items)/len(items),2),
                       "top_entities":[it["name"] for it in items[:5]],
                       "year":year_label})
    return {"year":year_label,"clusters":result,"total_entities":total_unique,
            "total_types":len(result),"library_total":DATA.n_state_vectors,
            "library_years":DATA.year_range}


# ── 16. 阿文智能体（策划案第72条） ──────────────────────────
AR = ArabicAgent()


@app.get("/api/arabic/detect")
def arabic_detect(text: str = Query(default="السلام عليكم")):
    return AR.detect_arabic(text)


@app.get("/api/arabic/translate")
def arabic_translate(term: str = Query(...),
                     source_lang: str = Query(default="auto",pattern=r"^(auto|en|cn|ar)$"),
                     target_lang: str = Query(default="cn",pattern=r"^(en|cn|ar)$")):
    return AR.translate_term(term, source_lang, target_lang)


@app.post("/api/arabic/align")
def arabic_align(req: "ArabicAlignReq"):
    return AR.align_terms(req.terms, req.source_lang, req.target_lang)


class ArabicAlignReq(BaseModel):
    terms: list[str]
    source_lang: str = "auto"
    target_lang: str = "cn"


@app.get("/api/arabic/entity")
def arabic_entity(entity: str = Query(default="文化遗产")):
    return AR.entity_arabic_names(entity)


# ── 17. 科学地图（第四阶段） ──────────────────────────────
@app.get("/api/science-map/publication-trends")
def publication_trends():
    rows = []
    for y, s in sorted(DATA.snapshots.items(), key=lambda kv: int(kv[0])):
        rows.append({"year":int(y),"nodes":s.get("n_nodes",0),"edges":s.get("n_edges",0)})
    return {"trends":rows,"total_years":len(rows),"year_range":DATA.year_range}


@app.get("/api/science-map/entity-types")
def entity_types(year: int = Query(default=None)):
    y = year or _latest()
    entities = DATA.get_entities(y)
    clusters = _dd(int)
    for name in entities:
        clusters[_classify_entity(name)] += 1
    result = [{"type":t,"count":c} for t,c in sorted(clusters.items(),key=lambda x:-x[1])]
    return {"year":y,"types":result,"total_entities":sum(r["count"] for r in result)}


@app.get("/api/science-map/collaboration")
def collaboration_network(year: int = Query(default=None)):
    y = year or _latest()
    snapshot = DATA.snapshots.get(str(y), {})
    edges = snapshot.get("edges", [])
    return {"year":y,"total_edges":len(edges),"sample_edges":edges[:30]}


# ── 18. 机构画像（第三层） ─────────────────────────────
@app.get("/api/profiles/institutions")
def institution_profiles(top_k: int = Query(default=20)):
    """机构画像"""
    inst = DATA._institutions
    result = []
    for name, info in inst.items():
        result.append({
            "name": name,
            "heat": info["heat"],
            "centrality": round(info["centrality"], 3),
            "connections": info["connections"],
            "years_active": len(info["years"]),
        })
    result.sort(key=lambda x: -x["heat"])
    return {"institutions": result[:top_k], "total": len(inst)}


# ── 19. 作者画像（第三层） ─────────────────────────────
@app.get("/api/profiles/authors")
def author_profiles(top_k: int = Query(default=20)):
    """作者画像"""
    authors = DATA._authors
    result = []
    for name, info in authors.items():
        result.append({
            "name": name,
            "collab_count": info["collab_count"],
        })
    result.sort(key=lambda x: -x["collab_count"])
    total_collab = sum(a["collab_count"] for a in result)
    return {"authors": result[:top_k], "total": len(authors),
            "total_collaborations": total_collab}


# ── 20. 完整服务流程（论文核心流程10步骤） ──────────────────
@app.get("/api/pipeline")
def full_pipeline(query: str = Query(default="中阿文旅研究热点"), 
                  user: str = Query(default="teacher")):
    """执行完整服务流程（10步），返回每一步状态"""
    y = _latest()
    steps = []
    
    # Step 1: 用户提交
    steps.append({"step": 1, "name": "用户提交", "agent": "飞书/Web入口",
                  "status": "✅", "input": query, "user": user})
    
    # Step 2: 总控识别
    task_type = "hotspot" if any(k in query for k in ["热点","热门","趋势","hot"]) else "general"
    steps.append({"step": 2, "name": "任务识别", "agent": "总控智能体",
                  "status": "✅", "task_type": task_type})
    
    # Step 3: 多模块调用
    hot = DATA.get_hot_topics(y, 10) if task_type == "hotspot" else DATA.get_hot_topics(y, 5)
    em = DATA.get_emerging(y, 5)
    steps.append({"step": 3, "name": "模块调用", "agent": "文献库/术语库/图谱/向量库/计量",
                  "status": "✅", "hotspots_loaded": len(hot), "frontier_loaded": len(em)})
    
    # Step 4: GraphRAG 生成答案
    grag_result = GRAG.answer(query, user)
    steps.append({"step": 4, "name": "GraphRAG 答案生成", "agent": "GraphRAG问答智能体",
                  "status": "✅", "confidence": f"{int(grag_result.get('confidence',0)*100)}%",
                  "rule_triggered": grag_result.get("rule_triggered", False)})
    
    # Step 5: 报告生成
    topic_clean = query[:20].replace("什么","").replace("怎么","").strip()
    report = generate_report_simple(topic_clean, user, y)
    steps.append({"step": 5, "name": "结构化报告", "agent": "报告生成智能体",
                  "status": "✅", "sections": len(report.get("sections", [])),
                  "title": report.get("title", "")})
    
    # Step 6: 馆员审核（风险标注）
    known = set(DATA.get_entities(y).keys())
    audited = SVC.audit(report, known_terms=known)
    audit_info = audited.get("audit", {})
    steps.append({"step": 6, "name": "审核风险标注", "agent": "馆员审核智能体",
                  "status": "⚠️" if audit_info.get("review_required") else "✅",
                  "safe": len(audit_info.get("safe", [])),
                  "warn": len(audit_info.get("warn", [])),
                  "danger": len(audit_info.get("danger", [])),
                  "action": audit_info.get("review_action", "无需复核")})
    
    # Step 7: 馆员人工复核（模拟）
    steps.append({"step": 7, "name": "馆员人工复核", "agent": "学科馆员",
                  "status": "⏳ 待复核" if audit_info.get("review_required") else "✅ 自动通过",
                  "note": "高风险项需驳回重生成" if audit_info.get("danger") else ("低风险项建议复核" if audit_info.get("warn") else "可信结果")})
    
    # Step 8: 推送
    push_result = SVC.push(report.get("title", "SKWM报告"), 
                           f"用户: {user}\n查询: {query}\n审核: {audit_info.get('status','')}")
    steps.append({"step": 8, "name": "结果推送", "agent": "飞书推送智能体",
                  "status": "📨 已推送" if push_result.get("sent") else "📝 已记日志",
                  "detail": "飞书" if push_result.get("sent") else "日志回退"})
    
    # Step 9: Obsidian 沉淀
    sed = SVC.sediment(report)
    steps.append({"step": 9, "name": "知识沉淀", "agent": "Obsidian沉淀智能体",
                  "status": "✅", "path": sed.get("filename", "")})
    
    # Step 10: KG回写
    wb = SVC.writeback([{
        "question": query, "answer": grag_result.get("answer", "")[:500],
        "entities": [h.get("name","") for h in hot[:3]],
        "confidence": grag_result.get("confidence", 0.8),
        "reviewed_by": "system_auto"
    }])
    steps.append({"step": 10, "name": "知识回写图谱", "agent": "知识回写闭环",
                  "status": "✅", "entries_written": wb.get("written", 0),
                  "total_entries": wb.get("total", 0)})
    
    completed = sum(1 for s in steps if s["status"].startswith("✅"))
    warnings = sum(1 for s in steps if "⚠️" in s["status"] or "⏳" in s["status"])
    
    return {
        "pipeline": steps,
        "summary": {
            "total_steps": len(steps),
            "completed": completed,
            "warnings": warnings,
            "progress": f"{completed}/{len(steps)}",
            "audit_required": audit_info.get("review_required", False),
        },
        "answer": grag_result.get("answer", "")[:1000],
        "report_title": report.get("title", ""),
    }


def generate_report_simple(topic: str, user: str, year: int) -> dict:
    """简化版报告生成（供 pipeline 调用）"""
    hot = DATA.get_hot_topics(year, 10)
    em = DATA.get_emerging(year, 8)
    user_labels = {"teacher":"教师科研","student":"学生学习","librarian":"馆员服务","manager":"科研管理"}
    sections = [
        {"name": f"{year}年研究热点 TOP 10",
         "data": [{"name": h["name"], "heat": h["heat"], "growth": h["growth"],
                    "evidence": f"状态向量 {year}年"} for h in hot[:10]]},
        {"name": "新兴前沿 TOP 8",
         "data": [{"name": e["name"], "growth": e.get("growth",0),
                    "evidence": f"突现检测 {year}年"} for e in em[:8]]},
        {"name": "数据规模",
         "data": [f"{DATA.n_snapshots}年时间切片", f"{DATA.n_state_vectors:,}条状态向量",
                  f"21,042条三语术语", f"XGBoost AUC=0.9408"]},
    ]
    return {
        "title": f"{topic}学科服务报告 ({year})",
        "user_type": user_labels.get(user, user),
        "data_scale": f"{DATA.n_snapshots}年 × {DATA.n_state_vectors:,}向量",
        "sections": sections,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 SKWM API 启动于 http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
