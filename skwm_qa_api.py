#!/usr/bin/env python3
"""
SKWM 问答系统 API — GraphRAG + DeepSeek 检索增强生成
===================================================
1. 检索层：知识图谱实体 + 文献片段 + 术语表
2. 生成层：DeepSeek 生成带引用的回答
3. 诚实性：无数据时不编造
"""
import os, json, re, hashlib, time
from pathlib import Path
from typing import List, Dict, Optional

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
WM_DIR = Path(r"E:\大挑\02_deliverables\world_model")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY", "")

# ── 缓存 ──
_SV = None
_B1 = None

def _load_sv():
    global _SV
    if _SV: return _SV
    for p in [DATA_DIR / "state_vectors.json", WM_DIR / "state_vectors.json"]:
        if p.exists():
            _SV = json.loads(p.read_text(encoding='utf-8'))
            return _SV
    return {}

def _load_b1():
    global _B1
    if _B1: return _B1
    b1_path = DATA_DIR / "B1_文献主表.json"
    if b1_path.exists():
        raw = b1_path.read_text(encoding='utf-8')
        raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
        idx = raw.find('{', raw.find('{') + 1)
        if idx > 0:
            _B1 = json.loads('[' + raw[idx:])
            return _B1
    return []

def _search_entities(q: str, top_k: int = 10) -> list:
    """搜索知识图谱实体"""
    _load_sv()
    sv = _SV.get('2026', {})
    ql = q.lower()
    results = []
    for name, vec in sv.items():
        if ql in name.lower():
            results.append({'name': name, 'heat': vec[0], 'type': 'entity'})
    results.sort(key=lambda x: -x['heat'])
    return results[:top_k]

def _search_papers(q: str, top_k: int = 5) -> list:
    """搜索文献"""
    _load_b1()
    if not _B1: return []
    ql = q.lower()
    results = []
    for p in _B1:
        title = p.get('title', '')
        kw = p.get('keywords', '')
        kw_str = ' '.join(kw) if isinstance(kw, list) else (kw or '')
        if ql in title.lower() or ql in kw_str.lower():
            results.append({
                'title': title, 'year': p.get('year', ''),
                'authors': (p.get('authors', '') or '')[:50],
                'doi': p.get('doi', ''),
            })
    results.sort(key=lambda x: -int(x.get('year') or 0))
    return results[:top_k]


def ask(question: str, lang: str = "zh", history: list = None) -> dict:
    """
    问答主入口
    返回 { answer, sources, confidence, has_evidence }
    """
    # 1. 检索
    entities = _search_entities(question, 8)
    papers = _search_papers(question, 5)
    
    has_evidence = bool(entities) or bool(papers)
    
    if not has_evidence:
        return {
            "answer": "关于您的问题，知识图谱和文献库中暂无相关数据。请尝试更换关键词或联系馆员补充数据源。" if lang == "zh" else "No relevant data found. Please try different keywords.",
            "sources": [],
            "confidence": 0.0,
            "has_evidence": False,
        }
    
    # 2. 构建上下文
    ctx_parts = []
    if entities:
        ctx_parts.append("=== 知识图谱相关实体 ===")
        for e in entities[:5]:
            ctx_parts.append(f"- {e['name']} (热度: {e['heat']})")
    
    if papers:
        ctx_parts.append("\n=== 相关文献 ===")
        for p in papers[:3]:
            ctx_parts.append(f"- 《{p['title']}》({p.get('year','')})")
    
    context = "\n".join(ctx_parts)
    
    # 3. 调用 DeepSeek
    answer_text = _call_deepseek(question, context, lang)
    
    # 4. 构建来源
    sources = []
    for e in entities[:5]:
        sources.append({"type": "知识图谱", "title": e['name'], "confidence": min(e['heat']/10000, 0.99)})
    for p in papers[:3]:
        sources.append({"type": "文献", "title": p['title'], "year": p.get('year',''), "id": p.get('doi','')})
    
    confidence = min(0.5 + len(entities)*0.05 + len(papers)*0.08, 0.95)
    
    return {
        "answer": answer_text,
        "sources": sources,
        "confidence": round(confidence, 2),
        "has_evidence": True,
    }


def _call_deepseek(question: str, context: str, lang: str) -> str:
    """调用 DeepSeek API"""
    if not DEEPSEEK_KEY:
        return _fallback_answer(question, context, lang)
    
    try:
        import requests
        sys_prompt = "你是一个中阿文旅研究领域的知识图谱问答助手。基于提供的上下文回答用户问题。" if lang == "zh" else "You are a QA assistant for China-Arab cultural tourism research."
        
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"上下文：\n{context}\n\n问题：{question}\n\n请基于以上信息回答。如果没有足够信息，请如实说明。"}
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=30,
        )
        data = resp.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return _fallback_answer(question, context, lang)


def _fallback_answer(question: str, context: str, lang: str) -> str:
    """DeepSeek不可用时的兜底"""
    entities = [line for line in context.split('\n') if line.startswith('- ') and '热度' in line]
    papers = [line for line in context.split('\n') if line.startswith('- 《')]
    
    if not entities and not papers:
        return "暂无相关数据。"
    
    answer = f"关于「{question}」的查询结果：\n\n"
    if entities:
        answer += "**相关研究主题：**\n" + "\n".join(entities[:5]) + "\n\n"
    if papers:
        answer += "**相关文献：**\n" + "\n".join(papers[:3]) + "\n\n"
    answer += "（DeepSeek 深度分析暂不可用，以上为知识图谱检索结果。）"
    return answer
