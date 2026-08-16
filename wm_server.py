"""wm_server.py — 世界模型算法服务 (FastAPI) v2
==============================================
修复 (v2, 对应 Notion §6.2):
  1. API 明确返回 rssm_loaded、模型版本、checkpoint哈希、数据版本和 rollout 模式
  2. RSSM 加载失败时不标记为 RSSM 预测
  3. 修复重复路由
  4. 服务输出附证据、置信度和降级说明
  5. 区分静态热点、普通趋势和 RSSM 预测
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from real_data_layer import RealKnowledgeWorldModel
from skwm_closed_loop import (
    SKWMClosedLoopController, ProposalPolicy, RevisionPolicy
)
import json
import hashlib
from pathlib import Path

app = FastAPI(title="SKWM World Model Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

kwm = RealKnowledgeWorldModel()
proposal = ProposalPolicy()
revision = RevisionPolicy()
ctrl = SKWMClosedLoopController(kwm, proposal, revision)

_rssm_loaded = False
_rssm_adapter = None
_rssm_model_version = None
_rssm_ckpt_hash = None
_rssm_error = None
_rssm_model_path = Path(__file__).parent / "model_rssm.pt"

if _rssm_model_path.exists():
    try:
        from skwm_world_model import WorldModel, SKWMWorldModelAdapter
        import torch
        _rssm_model = WorldModel.load(str(_rssm_model_path))
        _rssm_adapter = SKWMWorldModelAdapter(_rssm_model)
        kwm.rollout = lambda o, c, h: _rssm_adapter.rollout(o, c, h)
        _rssm_loaded = True
        _rssm_model_version = "v2"
        with open(_rssm_model_path, "rb") as _f:
            _rssm_ckpt_hash = hashlib.md5(_f.read()).hexdigest()[:12]
        print(f"  RSSM 内核已加载 ({_rssm_model_path.name})")
    except Exception as e:
        _rssm_loaded = False
        _rssm_error = str(e)
        print(f"  RSSM 加载失败: {e}")
else:
    _rssm_error = "model_rssm.pt 不存在"


def _get_prediction_mode() -> str:
    if _rssm_loaded:
        return "rssm"
    return "static_baseline"


def _get_model_info() -> dict:
    return {
        "rssm_loaded": _rssm_loaded,
        "model_version": _rssm_model_version,
        "checkpoint_hash": _rssm_ckpt_hash,
        "data_version": f"papers={kwm.data['total']}, years={list(kwm.year_range)}",
        "rollout_mode": _get_prediction_mode(),
        "error": _rssm_error,
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "algorithm": "propose→simulate→revise",
        "data_source": f"真实文献 {kwm.data['total']} 篇",
        "year_range": list(kwm.year_range),
        "model_info": _get_model_info(),
    }


@app.get("/api/model-info")
def model_info():
    return _get_model_info()


@app.get("/api/closed-loop")
def closed_loop(
    user: str = Query("teacher", description="服务对象 (teacher/research_team/librarian)"),
    M: int = Query(4, description="束宽(提议数)"),
    L: int = Query(3, description="视野(预测年数)"),
    B: int = Query(6, description="推理预算(rollout次数)"),
    t0: int = Query(2020, description="起始年"),
    T: int = Query(2024, description="结束年"),
):
    decisions = ctrl.run(t0=t0, T=T, goal="前沿识别", user=user, M=M, L=L, B=B)

    prediction_mode = _get_prediction_mode()
    confidence = 0.7 if _rssm_loaded else 0.3
    degradation_note = None if _rssm_loaded else "RSSM 未加载，使用静态基线预测"

    return {
        "user": user,
        "goal": "前沿识别",
        "algorithm": "propose→simulate→revise",
        "data_source": f"真实文献 {kwm.data['total']} 篇",
        "config": {"M": M, "L": L, "B": B, "t0": t0, "T": T},
        "prediction_mode": prediction_mode,
        "confidence": confidence,
        "degradation_note": degradation_note,
        "decisions": [
            {"year": d["year"],
             "note": d["plan"].note,
             "score": round(d["score"], 2),
             "topics": list(d["plan"].emphasis.keys())}
            for d in decisions
        ],
        "model_info": _get_model_info(),
    }


@app.get("/api/closed-loop/evaluate")
def evaluate(
    user: str = Query("teacher"),
    eval_years: str = Query("2018,2019,2020"),
):
    from skwm_closed_loop import ClosedLoopEvaluator
    ev = ClosedLoopEvaluator(kwm)
    years = [int(y) for y in eval_years.split(",")]
    hr = ev.hit_rate(ctrl, eval_years=years, user=user, L=4, M=5, B=8, k=10)
    return {
        "user": user,
        "eval_years": years,
        "hit_rate": round(hr, 4),
        "data_source": f"真实文献 {kwm.data['total']} 篇",
        "prediction_mode": _get_prediction_mode(),
        "model_info": _get_model_info(),
    }


@app.get("/api/overview")
def overview():
    return {
        "total_papers": kwm.data["total"],
        "year_range": list(kwm.year_range),
        "categories": len(kwm.topics),
        "topic_names": {t: kwm.topic_names[t] for t in kwm.topics},
        "model_info": _get_model_info(),
    }


@app.get("/api/state")
def get_state(year: int = Query(2024)):
    s = kwm.get_state(year)
    return {
        "year": year,
        "type": "static_observation",
        "hot": [{"topic": kwm.topic_names[t], "heat": float(s.vec[t][0]),
                 "growth": float(s.vec[t][1]), "centrality": float(s.vec[t][2]),
                 "connections": float(s.vec[t][3])}
                for t in kwm.topics if s.vec[t][0] > 0],
        "note": "静态观测，非预测",
    }


@app.get("/api/dashboard")
def dashboard():
    by_cat = kwm.data["by_category"]
    by_year = kwm.data["by_year"]

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


@app.get("/api/hotspots")
def hotspots(year: int = Query(2024), top_k: int = Query(10)):
    s = kwm.get_state(year)

    ranked = [(kwm.topic_names[t], float(s.vec[t][0]), float(s.vec[t][1]),
               float(s.vec[t][2]), float(s.vec[t][3]))
              for t in kwm.topics if s.vec[t][0] > 0]
    ranked.sort(key=lambda x: x[1], reverse=True)
    hotspots_data = [
        {"topic": r[0], "heat": r[1], "growth": round(r[2], 4),
         "centrality": round(r[3], 2), "connections": int(r[4])}
        for r in ranked[:top_k]
    ]

    emerging = sorted(ranked, key=lambda x: x[2], reverse=True)[:5]
    emerging_data = [
        {"topic": r[0], "growth": round(r[2], 4)}
        for r in emerging if r[2] > 0
    ]

    by_year = kwm.data["by_year"]
    trend = []
    for y in range(max(2015, kwm.year_range[0]), kwm.year_range[1] + 1):
        papers = by_year.get(y, [])
        trend.append({"year": y, "count": len(papers)})

    return {
        "year": year,
        "type": "static_observation",
        "hotspots": hotspots_data,
        "emerging_topics": emerging_data,
        "trend": trend,
        "total_papers": kwm.data["total"],
        "note": "基于历史数据的静态热点和增速排序，非预测结果",
    }


@app.get("/api/predict")
def predict(
    year: int = Query(2024),
    horizon: int = Query(3),
    top_k: int = Query(10),
):
    s = kwm.get_state(year)

    if _rssm_loaded:
        import numpy as np
        from skwm_world_model import WMConfig
        import torch

        topics = list(s.vec.keys())
        N = len(topics)
        x0_np = np.array([s.vec[t] for t in topics])
        x0 = torch.tensor(x0_np, dtype=torch.float32)
        a_future = torch.zeros(N, horizon, _rssm_adapter.wm.c.a_dim)

        all_preds = []
        B = 5
        for _ in range(B):
            with torch.no_grad():
                pred = _rssm_adapter.wm.imagine(x0, a_future)
            all_preds.append(pred.numpy())

        stacked = np.stack(all_preds, axis=0)
        mean_pred = stacked.mean(axis=0)
        std_pred = stacked.std(axis=0)

        predictions = []
        for i, topic in enumerate(topics):
            heat_pred = float(np.expm1(mean_pred[i, -1, 0]))
            heat_std = float(std_pred[i, -1, 0])
            predictions.append({
                "topic": kwm.topic_names.get(topic, topic),
                "current_heat": float(s.vec[topic][0]),
                "predicted_heat": max(0, heat_pred),
                "uncertainty": heat_std,
                "confidence": max(0.1, min(0.9, 0.7 - heat_std * 0.3)),
            })

        predictions.sort(key=lambda x: -x["predicted_heat"])

        return {
            "year": year,
            "horizon": horizon,
            "type": "rssm_prediction",
            "predictions": predictions[:top_k],
            "confidence": 0.7,
            "n_rollouts": B,
            "evidence": f"RSSM {B}次 rollout 平均",
            "model_info": _get_model_info(),
        }
    else:
        ranked = sorted(
            [(kwm.topic_names[t], float(s.vec[t][0])) for t in s.vec if s.vec[t][0] > 0],
            key=lambda x: -x[1]
        )
        return {
            "year": year,
            "horizon": horizon,
            "type": "static_baseline",
            "predictions": [
                {"topic": name, "current_heat": heat, "predicted_heat": heat,
                 "uncertainty": None, "confidence": 0.3}
                for name, heat in ranked[:top_k]
            ],
            "confidence": 0.3,
            "degradation_note": "RSSM 未加载，返回静态基线（当前热度排序）",
            "evidence": "无预测模型，仅历史热度排序",
            "model_info": _get_model_info(),
        }


@app.get("/api/literature")
def literature(year: int = Query(0)):
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

    recent = sorted(all_papers, key=lambda p: p["year"], reverse=True)[:20]
    recent_data = [
        {"title": p["title"][:60], "year": p["year"],
         "citations": p["citations"], "journal": p["journal"][:30]}
        for p in recent
    ]

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


_KG_DATA: dict | None = None

@app.get("/api/knowledge-graph")
def knowledge_graph():
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
    kg = knowledge_graph()
    if not isinstance(kg, dict):
        return kg
    target = None
    for e in kg.get("entities", []):
        if (not name or name.lower() in e["name"].lower()) and \
           (not type or type == e["type"]):
            target = e
            break
    if not target:
        return {"entity": None, "relations": []}

    rels = [r for r in kg.get("relations", [])
            if r["source"] == target["id"] or r["target"] == target["id"]]
    neighbor_ids = set()
    for r in rels:
        neighbor_ids.add(r["source"])
        neighbor_ids.add(r["target"])
    neighbors = [e for e in kg.get("entities", []) if e["id"] in neighbor_ids and e["id"] != target["id"]]

    return {"entity": target, "relations": rels[:50], "neighbors": neighbors[:30]}


_REPORT_CACHE: list[dict] | None = None

@app.get("/api/reports")
def list_reports():
    global _REPORT_CACHE
    if _REPORT_CACHE is not None:
        return {"reports": _REPORT_CACHE, "total": len(_REPORT_CACHE)}

    reports = []
    for user in ["teacher", "research_team", "librarian"]:
        decisions = ctrl.run(t0=2020, T=2024, goal="前沿识别", user=user, M=4, L=3, B=6)
        for d in decisions:
            topic_list = ", ".join(kwm.topic_names.get(t, t) for t in d["plan"].emphasis)
            reports.append({
                "id": f"{user}-{d['year']}",
                "title": f"{d['year']}年 {user} 知识服务决策报告",
                "type": {"teacher": "教师课题", "research_team": "科研团队",
                         "librarian": "学科周报"}.get(user, user),
                "date": f"{d['year']}-07-13",
                "status": "已完成",
                "size": "2.4KB",
                "summary": f"推荐: {topic_list}  (评分 {d['score']:.1f})",
                "user": user,
                "prediction_mode": _get_prediction_mode(),
            })
    reports.sort(key=lambda r: r["date"], reverse=True)
    _REPORT_CACHE = reports
    return {"reports": reports, "total": len(reports)}
