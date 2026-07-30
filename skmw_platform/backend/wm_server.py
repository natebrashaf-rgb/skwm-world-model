"""wm_server.py — 世界模型算法服务 (FastAPI)
每次请求真正执行 propose→simulate→revise 闭环规划。
数据源: 真实文献资料库 (1958篇文献)
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from real_data_layer import RealKnowledgeWorldModel
from skwm_closed_loop import (
    SKWMClosedLoopController, ProposalPolicy, RevisionPolicy
)
import json
from pathlib import Path

app = FastAPI(title="SKWM World Model Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 启动时加载真实数据
kwm = RealKnowledgeWorldModel()
proposal = ProposalPolicy()
revision = RevisionPolicy()
ctrl = SKWMClosedLoopController(kwm, proposal, revision)

# 尝试加载 RSSM 内核 (如果 model_rssm.pt 存在)
_rssm_loaded = False
_rssm_adapter = None
_rssm_model_path = Path(__file__).parent / "model_rssm.pt"
if _rssm_model_path.exists():
    try:
        from skwm_world_model import WorldModel, SKWMWorldModelAdapter
        import torch
        _rssm_model = WorldModel.load(str(_rssm_model_path))
        _rssm_adapter = SKWMWorldModelAdapter(_rssm_model)
        # 替换 rollout 为 RSSM 预测
        kwm.rollout = lambda o, c, h: _rssm_adapter.rollout(o, c, h)
        _rssm_loaded = True
        print(f"  RSSM 内核已加载 ({_rssm_model_path.name})")
    except Exception as e:
        print(f"  RSSM 加载失败: {e}")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "algorithm": "propose→simulate→revise",
        "data_source": f"真实文献 {kwm.data['total']} 篇",
        "year_range": list(kwm.year_range),
    }


@app.get("/api/closed-loop")
def closed_loop(
    user: str = Query("teacher", description="用户类型"),
    M: int = Query(4, description="束宽(提议数)"),
    L: int = Query(3, description="视野(预测年数)"),
    B: int = Query(6, description="推理预算(rollout次数)"),
    t0: int = Query(2020, description="起始年"),
    T: int = Query(2024, description="结束年"),
):
    """实时执行闭环规划算法"""
    decisions = ctrl.run(t0=t0, T=T, goal="前沿识别", user=user, M=M, L=L, B=B)
    return {
        "user": user,
        "goal": "前沿识别",
        "algorithm": "propose→simulate→revise",
        "data_source": f"真实文献 {kwm.data['total']} 篇",
        "config": {"M": M, "L": L, "B": B, "t0": t0, "T": T},
        "decisions": [
            {"year": d["year"],
             "note": d["plan"].note,
             "score": round(d["score"], 2),
             "topics": list(d["plan"].emphasis.keys())}
            for d in decisions
        ],
    }


@app.get("/api/closed-loop/evaluate")
def evaluate(
    user: str = Query("teacher"),
    eval_years: str = Query("2018,2019,2020"),
):
    """回测命中率"""
    from skwm_closed_loop import ClosedLoopEvaluator
    ev = ClosedLoopEvaluator(kwm)
    years = [int(y) for y in eval_years.split(",")]
    hr = ev.hit_rate(ctrl, eval_years=years, user=user, L=4, M=5, B=8, k=10)
    return {
        "user": user,
        "eval_years": years,
        "hit_rate": round(hr, 4),
        "data_source": f"真实文献 {kwm.data['total']} 篇",
    }


@app.get("/api/overview")
def overview():
    """数据总览"""
    return {
        "total_papers": kwm.data["total"],
        "year_range": list(kwm.year_range),
        "categories": len(kwm.topics),
        "topic_names": {t: kwm.topic_names[t] for t in kwm.topics},
    }


@app.get("/api/state")
def get_state(year: int = Query(2024)):
    """某年真实知识状态"""
    s = kwm.get_state(year)
    return {
        "year": year,
        "hot": [{"topic": kwm.topic_names[t], "heat": float(s.vec[t][0]),
                 "growth": float(s.vec[t][1]), "centrality": float(s.vec[t][2]),
                 "connections": float(s.vec[t][3])}
                for t in kwm.topics if s.vec[t][0] > 0],
    }


# ============ Dashboard 数据 ============

@app.get("/api/dashboard")
def dashboard():
    """工作台总览"""
    by_cat = kwm.data["by_category"]
    by_year = kwm.data["by_year"]

    # 各分类统计
    cat_stats = {}
    for cat in kwm.topics:
        papers = by_cat.get(cat, [])
        total = len(papers)
        cites = sum(p["citations"] for p in papers)
        years = [p["year"] for p in papers if p["year"] >= 2000]
        cat_stats[kwm.topic_names[cat]] = {
            "total": total, "cites": cites,
            "year_min": min(years) if years else 0,
            "year_max": max(years) if years else 0,
        }

    # 年度趋势
    years_range = range(max(kwm.year_range[0], 2015), kwm.year_range[1] + 1)
    trend = []
    for y in years_range:
        papers = by_year.get(y, [])
        trend.append({"year": y, "count": len(papers),
                      "cites": sum(p["citations"] for p in papers)})

    return {
        "total_papers": kwm.data["total"],
        "categories": len(kwm.topics),
        "year_range": list(kwm.year_range),
        "category_stats": cat_stats,
        "trend": trend,
    }


# ============ 热点/科学计量 ============

@app.get("/api/hotspots")
def hotspots(year: int = Query(2024), top_k: int = Query(10)):
    """科学计量: 热点排名 + 语种分布 + 前沿识别"""
    s = kwm.get_state(year)

    # 热点排名 (按论文数)
    ranked = [(kwm.topic_names[t], float(s.vec[t][0]), float(s.vec[t][1]),
               float(s.vec[t][2]), float(s.vec[t][3]))
              for t in kwm.topics if s.vec[t][0] > 0]
    ranked.sort(key=lambda x: x[1], reverse=True)
    hotspots_data = [
        {"topic": r[0], "heat": r[1], "growth": round(r[2], 4),
         "centrality": round(r[3], 2), "connections": int(r[4])}
        for r in ranked[:top_k]
    ]

    # 前沿 (增速最快)
    emerging = sorted(ranked, key=lambda x: x[2], reverse=True)[:5]
    emerging_data = [
        {"topic": r[0], "growth": round(r[2], 4)}
        for r in emerging if r[2] > 0
    ]

    # 年度趋势 (最近10年)
    by_year = kwm.data["by_year"]
    trend = []
    for y in range(max(2015, kwm.year_range[0]), kwm.year_range[1] + 1):
        papers = by_year.get(y, [])
        trend.append({"year": y, "count": len(papers)})

    return {
        "year": year,
        "hotspots": hotspots_data,
        "emerging_topics": emerging_data,
        "trend": trend,
        "total_papers": kwm.data["total"],
    }


# ============ 文献分布 ============

@app.get("/api/literature")
def literature(year: int = Query(0)):
    """文献分布: 各分类论文数 + 最近文献"""
    by_cat = kwm.data["by_category"]
    by_year = kwm.data["by_year"]
    all_papers = kwm.data["all"]

    cat_list = []
    for cat in kwm.topics:
        papers = by_cat.get(cat, [])
        total = len(papers)
        max_cite = max((p["citations"] for p in papers), default=0)
        avg_cite = sum(p["citations"] for p in papers) / max(1, total)
        cat_list.append({
            "id": cat,
            "name": kwm.topic_names[cat],
            "total": total,
            "avg_cites": round(avg_cite, 1),
            "max_cites": max_cite,
        })
    cat_list.sort(key=lambda x: x["total"], reverse=True)

    # 最近文献
    recent = sorted(all_papers, key=lambda p: p["year"], reverse=True)[:20]
    recent_data = [
        {"title": p["title"][:60], "year": p["year"],
         "citations": p["citations"], "journal": p["journal"][:30]}
        for p in recent
    ]

    # 年度分布
    yr_stats = []
    for y in range(2010, 2027):
        papers = by_year.get(y, [])
        if papers:
            yr_stats.append({
                "year": y,
                "count": len(papers),
                "cites": sum(p["citations"] for p in papers),
            })

    return {
        "total": kwm.data["total"],
        "categories": cat_list,
        "recent": recent_data,
        "yearly": yr_stats,
    }


# ============ 知识图谱 ============

_KG_DATA: dict | None = None

@app.get("/api/knowledge-graph")
def knowledge_graph():
    """知识图谱实体与关系 (从真实文献提取)"""
    global _KG_DATA
    if _KG_DATA is not None:
        return _KG_DATA
    kg_path = Path(__file__).parent / "kg_data.json"
    if kg_path.exists():
        with open(kg_path, "r", encoding="utf-8") as f:
            _KG_DATA = json.load(f)
        return _KG_DATA
    return {"statistics": {"entities": 0, "relations": 0},
            "entity_types": [], "relation_types": [],
            "top_entities": [], "entities": [], "relations": []}


@app.get("/api/knowledge-graph/entity")
def graph_entity(name: str = Query(""), type: str = Query("")):
    """查询单个实体的关联网络"""
    kg = knowledge_graph()
    if not isinstance(kg, dict):
        return kg
    # 查找实体
    target = None
    for e in kg.get("entities", []):
        if (not name or name.lower() in e["name"].lower()) and \
           (not type or type == e["type"]):
            target = e
            break
    if not target:
        return {"entity": None, "relations": []}

    # 找出关联关系
    rels = [r for r in kg.get("relations", [])
            if r["source"] == target["id"] or r["target"] == target["id"]]
    # 找出关联实体
    neighbor_ids = set()
    for r in rels:
        neighbor_ids.add(r["source"])
        neighbor_ids.add(r["target"])
    neighbors = [e for e in kg.get("entities", []) if e["id"] in neighbor_ids and e["id"] != target["id"]]

    return {"entity": target, "relations": rels[:50], "neighbors": neighbors[:30]}


# ============ 报告中心 ============

_REPORT_CACHE: list[dict] | None = None

@app.get("/api/reports")
def list_reports():
    """已生成的闭环决策报告"""
    global _REPORT_CACHE
    if _REPORT_CACHE is not None:
        return {"reports": _REPORT_CACHE, "total": len(_REPORT_CACHE)}

    reports = []
    for user in ["teacher", "student", "librarian", "manager"]:
        decisions = ctrl.run(t0=2020, T=2024, goal="前沿识别", user=user, M=4, L=3, B=6)
        for d in decisions:
            topic_list = ", ".join(kwm.topic_names.get(t, t) for t in d["plan"].emphasis)
            reports.append({
                "id": f"{user}-{d['year']}",
                "title": f"{d['year']}年 {user} 知识服务决策报告",
                "type": {"teacher": "教师课题", "student": "学生选题",
                         "librarian": "学科周报", "manager": "科研管理"}.get(user, user),
                "date": f"{d['year']}-07-13",
                "status": "已完成",
                "size": "2.4KB",
                "summary": f"推荐: {topic_list}  (评分 {d['score']:.1f})",
                "user": user,
            })
    reports.sort(key=lambda r: r["date"], reverse=True)
    _REPORT_CACHE = reports
    return {"reports": reports, "total": len(reports)}
