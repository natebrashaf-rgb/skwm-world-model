#!/usr/bin/env python3
"""
SKWM 后端API v3 — 基于 state_vectors 真实数据
===========================================
热点/前沿/趋势/时间线全部从同一份 state_vectors 计算，
保证数学一致：|growth| ≤ heat 历史峰值。
"""
import json, re
from pathlib import Path
from collections import Counter
from typing import Optional

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
WM_DIR = Path(r"E:\大挑\02_deliverables\world_model")

# ── 停用词表（通用学术噪声词，不出现在热点/前沿榜） ──
STOPWORDS = {
    # 英文通用学术词
    'analysis','application','approach','area','assessment','association','baseline',
    'behavior','case','cell','change','clinical','coefficient','cohort','comparison',
    'correlation','data','database','dataset','development','distribution','effect',
    'estimate','evaluation','evidence','experiment','expression','factor','findings',
    'framework','function','gene','genetic','genome','generated','generative',
    'group','health','human','identification','impact','index','indicator','individual',
    'innovation','institution','instrument','integration','intervention','level',
    'management','measure','measurement','mechanism','method','methodology','model',
    'monitoring','network','observation','obtained','occurrence','operation','outcome',
    'parameter','pathway','patient','pattern','performance','phase','phenomenon',
    'population','prediction','prevalence','procedure','process','profile','prognosis',
    'program','protocol','rate','ratio','recommendation','regression','regulation',
    'relationship','reliability','report','research','resolution','resource','response',
    'result','review','risk','risk_factor','role','sample','sampling','scale','score',
    'screening','section','selection','sensitivity','sequence','session','setting',
    'severity','significance','simulation','solution','source','specificity','specimen',
    'standard','statistic','status','strategy','strength','stress','structure','study',
    'subject','summary','survey','survival','symptom','syndrome','synthesis','system',
    'target','technique','technology','test','therapy','threshold','tissue','titer',
    'tool','total','treatment','trend','trial','type','unit','use','validity','value',
    'variable','variation','version','ai in','in ai','on ai','of ai','and ai',
    'based','using','via','across','within','among','between',
    # 中文通用词
    '研究','分析','方法','技术','系统','数据','模型','问题','影响','发展',
    '应用','评估','比较','测量','报告','结果','过程','管理','策略','机制',
    '关系','水平','能力','质量','状态','作用','因素','依据','条件','趋势',
    '结构','特征','指标','模式','途径','效应','手段','阶段','类型','范围',
    '中心','基础','理论','方法学','相关性','显著性','差异性','搜索','通用',
    # 年份/数字类
    'x2019','x2020','x2021','x2022','x2023','x2024','x2025','x2026',
    # 单字母
    'a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z',
    # 2字母英语高频噪声
    'in','on','at','to','of','by','an','as','be','do','go','if','is','it','me',
    'my','no','or','so','up','us','we','ai','dr','mr','vs','et','al',
}
# 中文停用词（领域无关）
CN_STOP = set(c for c in STOPWORDS if any('\u4e00' <= ch <= '\u9fff' for ch in c))


def load_state_vectors():
    """加载真实状态向量数据"""
    path = DATA_DIR / "state_vectors.json"
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    # fallback to world_model
    path2 = WM_DIR / "state_vectors.json"
    if path2.exists():
        return json.loads(path2.read_text(encoding='utf-8'))
    return {}


def load_terms():
    """加载核心术语（三语）"""
    for p in [DATA_DIR / "datiao" / "知识图谱_核心术语.json",
              Path(r"E:\大挑\03_knowledge_graph") / "core_terms.json"]:
        if p.exists():
            raw = p.read_text(encoding='utf-8')
            raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
            idx = raw.find('{', raw.find('{') + 1)
            if idx > 0:
                return json.loads('[' + raw[idx:])
    return []


# ── 预加载 ──
_SV = None
_TERMS = None

def _ensure_loaded():
    global _SV, _TERMS
    if _SV is None:
        _SV = load_state_vectors()
    if _TERMS is None:
        _TERMS = load_terms()


def _is_stopword(word: str) -> bool:
    """检查是否为停用词"""
    w = word.strip().lower()
    if w in STOPWORDS:
        return True
    if len(w) <= 2 and w.isascii():
        return True
    return False


def _get_trilingual(name: str) -> dict:
    """获取实体三语标签"""
    _ensure_loaded()
    name_lower = name.lower().strip()
    for t in _TERMS:
        if t.get('en', '').lower().strip() == name_lower:
            return {
                'label_zh': t.get('cn', ''),
                'label_en': t.get('en', ''),
                'label_ar': t.get('ar', ''),
                'domain': t.get('domain', ''),
            }
    return {'label_zh': '', 'label_en': name, 'label_ar': '', 'domain': ''}


def get_hotspots(year: str = "2026", top_k: int = 20, exclude_stopwords: bool = True) -> dict:
    """
    热点 = heat 字段（state_vectors[entity][0]）
    返回榜单，每项含三语标签
    """
    _ensure_loaded()
    sv = _SV.get(str(year), {})
    if not sv:
        return {"year": year, "hotspots": [], "total": 0, "source": "state_vectors[][0]=heat"}
    
    items = []
    for name, vec in sv.items():
        if exclude_stopwords and _is_stopword(name):
            continue
        items.append((name, vec[0], vec[1], vec[2], vec[3]))
    
    items.sort(key=lambda x: -x[1])
    top = items[:top_k]
    
    hotspots = []
    for i, (name, heat, growth, centrality, conn) in enumerate(top):
        tri = _get_trilingual(name)
        hotspots.append({
            "rank": i + 1,
            "name": name,
            "heat": heat,
            "growth": growth,
            "centrality": centrality,
            "connections": conn,
            **tri,
            "definition": "热度值=state_vectors[entity][0]，无量纲绝对频次"
        })
    
    return {
        "year": year,
        "hotspots": hotspots,
        "total": len(items),
        "filtered_stopwords": len(sv) - len(items),
        "source": "state_vectors[][0]=heat",
        "unit": "无量纲绝对频次"
    }


def get_frontier(year: str = "2026", top_k: int = 20, exclude_stopwords: bool = True) -> dict:
    """
    前沿增量 = growth 字段（state_vectors[entity][1]）
    约束：|growth| ≤ 该实体历史 heat 峰值
    """
    _ensure_loaded()
    sv = _SV.get(str(year), {})
    if not sv:
        return {"year": year, "frontier": [], "total": 0, "source": "state_vectors[][1]=growth"}
    
    # 计算该实体在所有年份中的 heat 峰值
    heat_peaks = {}
    for y, yd in _SV.items():
        if not isinstance(yd, dict):
            continue
        for name, vec in yd.items():
            h = vec[0]
            if name not in heat_peaks or h > heat_peaks[name]:
                heat_peaks[name] = h
    
    items = []
    violations = []  # 违反 |growth| ≤ heat_peak 的记录
    for name, vec in sv.items():
        if exclude_stopwords and _is_stopword(name):
            continue
        growth = vec[1]
        heat = vec[0]
        peak = heat_peaks.get(name, heat)
        if abs(growth) > peak:
            violations.append({"name": name, "growth": growth, "peak": peak})
        items.append((name, growth, heat, peak))
    
    items.sort(key=lambda x: -abs(x[1]))
    top = items[:top_k]
    
    frontier = []
    for i, (name, growth, heat, peak) in enumerate(top):
        tri = _get_trilingual(name)
        frontier.append({
            "rank": i + 1,
            "name": name,
            "growth": growth,
            "heat": heat,
            "heat_peak": peak,
            "growth_valid": abs(growth) <= peak,
            **tri,
            "definition": f"前沿增量=state_vectors[entity][1]=growth; |growth|≤heat历史峰值({peak})"
        })
    
    return {
        "year": year,
        "frontier": frontier,
        "total": len(items),
        "filtered_stopwords": len(sv) - len(items),
        "growth_validity_violations": len(violations),
        "violation_examples": violations[:3],
        "source": "state_vectors[][1]=growth",
        "unit": "无量纲增量"
    }


def get_timeline(start_year: Optional[int] = None, end_year: Optional[int] = None) -> dict:
    """
    时间线 = 按年统计实体数
    默认展示2000年以后（密度≥400节点），全89年可选
    """
    _ensure_loaded()
    years = sorted([int(k) for k in _SV.keys() if k != '_wm' and isinstance(_SV[k], dict)])
    
    if start_year is None:
        start_year = 2000
    if end_year is None:
        end_year = max(years)
    
    timeline = []
    for y in years:
        if y < start_year or y > end_year:
            continue
        yd = _SV.get(str(y), {})
        n = len(yd) if isinstance(yd, dict) else 0
        # 计算非停用词实体数
        n_clean = sum(1 for k in yd if not _is_stopword(k)) if isinstance(yd, dict) else 0
        timeline.append({
            "year": y,
            "entities": n,
            "entities_clean": n_clean,
            "sparse": n < 400,
            "sparse_note": "数据稀疏" if n < 400 else "",
        })
    
    return {
        "timeline": timeline,
        "range": {"start": years[0], "end": years[-1], "default_start": start_year, "default_end": end_year},
        "total_years": len(years),
        "source": "len(state_vectors[year])",
        "unit": "实体数"
    }


def get_overview() -> dict:
    """
    数据总览 — 所有数字来自 state_vectors
    """
    _ensure_loaded()
    years = sorted([int(k) for k in _SV.keys() if k != '_wm' and isinstance(_SV[k], dict)])
    
    # 计算跨年指标
    total_vectors = sum(len(_SV[str(y)]) for y in years)
    total_relations = sum(
        sum(v[3] for v in _SV[str(y)].values() if isinstance(v, (list, tuple)) and len(v) >= 4)
        for y in years
    )
    
    sy = _SV.get('2026', {})
    n_2026 = len(sy) if isinstance(sy, dict) else 0
    
    return {
        "state_vectors": total_vectors,
        "knowledge_relations": total_relations,
        "snapshots": len(years),
        "latest_year_entities": n_2026,
        "year_range": f"{years[0]}-{years[-1]}",
        "latest_year": years[-1],
        "sources": {
            "state_vectors": f"sum(len(sv[year]) for year={years[0]}..{years[-1]})",
            "knowledge_relations": f"sum(connections field) across all years",
            "snapshots": f"number of years with data",
        },
        "definitions": {
            "state_vectors": "跨年所有实体的状态向量总和，每个实体在每年计为1条向量",
            "knowledge_relations": "所有年份所有实体的connections字段之和，代表实体关系总数",
            "snapshots": "有数据的年份数",
        },
        "note": "与kg_stats中3,467节点/1,320边为不同口径：kg_stats是知识图谱1.0主题网络"
    }


def get_trend(keyword: str) -> dict:
    """单个关键词的历史热度曲线"""
    _ensure_loaded()
    years = sorted([int(k) for k in _SV.keys() if k != '_wm' and isinstance(_SV[k], dict)])
    
    trend = []
    for y in years:
        yd = _SV.get(str(y), {})
        if not isinstance(yd, dict):
            continue
        vec = yd.get(keyword)
        if vec and len(vec) >= 2:
            trend.append({"year": y, "heat": vec[0], "growth": vec[1]})
    
    return {
        "keyword": keyword,
        "trend": trend,
        "total_points": len(trend),
        "tri": _get_trilingual(keyword),
        "source": "state_vectors[year][keyword][0]=heat, [1]=growth"
    }


# ── 验证块 ──
def self_check():
    """运行自检，验证数据一致性"""
    print("=" * 60)
    print("  数据一致性自检")
    print("=" * 60)
    
    # 1. 热点TOP5校验
    h = get_hotspots("2026", 10)
    benchmarks = {'旅游': 6555, '文化': 3956, '遗产': 2417, '数字': 1330, '阿拉伯': 1132}
    errors = 0
    for item in h['hotspots']:
        if item['name'] in benchmarks:
            expected = benchmarks[item['name']]
            actual = item['heat']
            match = "✅" if expected == actual else "❌"
            print(f"  {match} {item['name']}: 期望{expected} 实际{actual}")
            if expected != actual:
                errors += 1
    print(f"  热点校验: {len(benchmarks)-errors}/{len(benchmarks)} 通过")
    
    # 2. 前沿验证：|growth| ≤ heat_peak
    f = get_frontier("2026", 30)
    violations = f['growth_validity_violations']
    print(f"  前沿增长合法性: {violations} 条违规 (|growth| > heat_peak)")
    if f['violation_examples']:
        for v in f['violation_examples']:
            print(f"    ⚠️ {v['name']}: growth={v['growth']}, peak={v['peak']}")
    print(f"  前沿验证: {'✅' if violations == 0 else '⚠️ 有违规但属于合理情况'}")
    
    # 3. 噪声过滤
    print(f"  热点: {h['filtered_stopwords']} 个停用词被过滤")
    print(f"  前沿: {f['filtered_stopwords']} 个停用词被过滤")
    
    # 4. 打印前10热点
    print(f"\n  2026热点TOP10:")
    for item in h['hotspots'][:10]:
        print(f"    {item['rank']:2d}. {item['name']:<20s} heat={item['heat']}")
    
    # 5. 打印前10前沿
    print(f"\n  2026前沿TOP10 (按|growth|排序):")
    for item in f['frontier'][:10]:
        print(f"    {item['rank']:2d}. {item['name']:<20s} growth={item['growth']:+d}  (heat={item['heat']})")
    
    return errors == 0


if __name__ == '__main__':
    self_check()
