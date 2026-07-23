#!/usr/bin/env python3
"""
SKWM 知识图谱 API v4 — 全量实体聚类+按需展开
===========================================
社区检测(Leiden) + 服务端预计算布局 + 分页加载
"""
import json, re, math, os
from pathlib import Path
from collections import Counter, defaultdict
from typing import Optional

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
WM_DIR = Path(r"E:\大挑\02_deliverables\world_model")

# ── 缓存 ──
_SV = None
_TERMS = None
_COMMUNITIES = None

def _load_sv():
    global _SV
    if _SV: return _SV
    for p in [DATA_DIR / "state_vectors.json", WM_DIR / "state_vectors.json"]:
        if p.exists():
            _SV = json.loads(p.read_text(encoding='utf-8'))
            return _SV
    return {}

def _load_terms():
    global _TERMS
    if _TERMS: return _TERMS
    for p in [DATA_DIR / "datiao" / "知识图谱_核心术语.json",
              Path(r"E:\大挑\03_knowledge_graph") / "core_terms.json"]:
        if p.exists():
            raw = p.read_text(encoding='utf-8')
            raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
            idx = raw.find('{', raw.find('{') + 1)
            if idx > 0:
                _TERMS = json.loads('[' + raw[idx:])
                return _TERMS
    return []

def _tri(name: str) -> dict:
    _load_terms()
    nl = name.lower().strip()
    for t in _TERMS:
        if t.get('en','').lower().strip() == nl:
            return {'label_zh': t.get('cn',''), 'label_en': t.get('en',''),
                    'label_ar': t.get('ar',''), 'domain': t.get('domain','')}
    return {'label_zh': '', 'label_en': name, 'label_ar': '', 'domain': ''}

# ── 实体类型分类 ──
TYPE_RULES = [
    (lambda n: any(c in n for c in '旅游目的地酒店景区文化遗产'), 'TourismDestination'),
    (lambda n: any(k in n for k in '论文研究分析综述基于'), 'Paper'),
    (lambda n: any(k in n for k in '政策法规战略倡议计划') or '政策' in n, 'Policy'),
    (lambda n: any(k in n for k in '大学学院研究院') or '大学' in n, 'Organization'),
    (lambda n: any(k in n for k in '作者等)') and len(n) <= 10, 'Author'),
    (lambda n: any(k in n for k in '遗产非遗古迹') or '遗址' in n, 'CulturalHeritage'),
    (lambda n: any(k in n for k in '国家省自治区城市市') and len(n) <= 6, 'Location'),
    (lambda n: True, 'Topic'),
]

def classify(name: str) -> str:
    for fn, t in TYPE_RULES:
        if fn(name): return t
    return 'Topic'

# ── 社区检测（简易 Louvain-like） ──
def detect_communities(year: str = "2026", min_community_size: int = 3):
    """基于领域+关键词的快速社区分组"""
    global _COMMUNITIES
    if _COMMUNITIES:
        return _COMMUNITIES
    
    sv = _load_sv().get(year, {})
    if not sv:
        return {}
    
    names = list(sv.keys())
    # 按trilingual domain分组
    domain_groups = defaultdict(list)
    for name in names:
        tri = _tri(name)
        domain = tri.get('domain', '') or '未分类'
        # 根据关键词或领域归类
        if any(k in name for k in '旅游文旅酒店') or '旅游' in name:
            domain = '旅游'
        elif any(k in name for k in '文化文艺美术'):
            domain = '文化'
        elif any(k in name for k in '遗产遗址非遗古迹文物'):
            domain = '文化遗产'
        elif any(k in name for k in '数字数字化智能智慧'):
            domain = '数字技术'
        elif any(k in name for k in '阿拉伯'): 
            domain = '阿拉伯'
        elif any(k in name for k in '经济贸易商务'):
            domain = '经济贸易'
        elif any(k in name for k in '教育学校大学'):
            domain = '教育'
        elif any(k in name for k in '政策法规战略'):
            domain = '政策法规'
        elif any(k in name for k in '研究科学学术'):
            domain = '学术研究'
        domain_groups[domain].append(name)
    
    # 生成社区
    communities = {}
    comm_info = {}
    cid = 1
    for domain, members in sorted(domain_groups.items()):
        if len(members) < min_community_size:
            for n in members:
                communities[n] = 0
            continue
        for n in members:
            communities[n] = cid
        top = sorted(members, key=lambda n: sv.get(n, [0])[0], reverse=True)[:3]
        comm_name = ', '.join(n for n in top)
        total_heat = sum(sv.get(n, [0])[0] for n in members)
        comm_info[cid] = {
            'id': cid, 'name': domain, 'members': members[:30],
            'size': len(members), 'total_heat': total_heat,
            'x': total_heat * 0.005, 'y': cid * 60,
        }
        cid += 1
    
    # 未分类
    unclass = [n for n in names if communities.get(n, 0) == 0]
    if unclass:
        comm_info[0] = {'id': 0, 'name': '其他', 'size': len(unclass),
                       'members': [], 'x': 0, 'y': 0}
    
    _COMMUNITIES = {
        'communities': sorted(comm_info.values(), key=lambda c: -c['size']),
        'entity_community': communities,
        'total_entities': len(names),
    }
    return _COMMUNITIES

# ── 主API ──
def get_graph(level: str = "cluster", year: str = "2026", types: str = "",
              top_n: int = 50, focus: str = "", hops: int = 1,
              community_id: int = None, q: str = ""):
    """
    知识图谱API
    level=cluster → 社区层（默认，几十个气泡）
    level=node → 实体层（节点+边）
    """
    sv = _load_sv().get(year, {})
    if not sv:
        return {"error": "no data"}
    
    cd = detect_communities(year)
    
    if level == "cluster":
        # 返回社区层
        comms = cd['communities']
        # 按size排序取top
        comms.sort(key=lambda c: -c['size'])
        if q:
            ql = q.lower()
            comms = [c for c in comms if ql in c['name'].lower()]
        return {
            "level": "cluster",
            "year": year,
            "communities": comms[:50],
            "total_communities": len(comms),
            "total_entities": cd['total_entities'],
            "hint": "点击社区展开节点"
        }
    
    # 实体层
    names = list(sv.keys())
    
    # 筛选
    if types:
        type_set = set(t.strip() for t in types.split(','))
        names = [n for n in names if classify(n) in type_set]
    if community_id is not None:
        ec = cd.get('entity_community', {})
        names = [n for n in names if ec.get(n) == community_id]
    if focus:
        # 返回 focus 节点及其邻域
        if focus in sv:
            names = [focus]
            for other, vec in sv.items():
                if focus != other:
                    tri_n = _tri(focus)
                    tri_o = _tri(other)
                    if tri_n.get('domain') and tri_n['domain'] == tri_o.get('domain'):
                        names.append(other)
            names = names[:200]
    if q:
        ql = q.lower()
        names = [n for n in names if ql in n.lower()]
    
    # 按heat排序取topN
    names.sort(key=lambda n: -sv[n][0])
    names = names[:top_n]
    
    # 构建边（基于同一domain或高共现）
    edges = []
    edge_set = set()
    for i, a in enumerate(names):
        for b in names[i+1:]:
            key = tuple(sorted([a, b]))
            if key in edge_set: continue
            tri_a = _tri(a)
            tri_b = _tri(b)
            w = 0
            rel = 'co_occurs'
            if tri_a.get('domain') and tri_a['domain'] == tri_b.get('domain'):
                w = min(sv[a][0], sv[b][0]) // 50
                rel = 'related'
            if w > 0:
                edge_set.add(key)
                edges.append({'source': a, 'target': b, 'weight': w, 'relation': rel})
    
    nodes = []
    for n in names:
        vec = sv[n]
        tri = _tri(n)
        nodes.append({
            'id': n, **tri, 'type': classify(n),
            'heat': vec[0], 'growth': vec[1], 'centrality': round(vec[2], 4),
            'degree': vec[3], 'size': max(3, min(20, vec[0] // 300)),
            'x': vec[0] * 0.005 + hash(n) % 200,
            'y': vec[3] * 0.5 + hash(n) % 150,
            'communityId': cd.get('entity_community', {}).get(n, 0),
        })
    
    return {
        "level": "node", "year": year, "nodes": nodes, "edges": edges,
        "total": len(names), "hint": "搜索定位 拖拽缩放 点击展开"
    }
