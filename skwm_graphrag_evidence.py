#!/usr/bin/env python3
"""
SKWM GraphRAG 证据溯源 + 馆员审核系统
=====================================
1. 溯源性答案（attribution）
2. 幻觉防护（置信度评分）
3. 馆员审核状态机（HITL）
4. 审核沉淀（Obsidian导出）
"""
import json, os, hashlib, time, re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output" / "graphrag_evidence"
REVIEW_DIR = OUT_DIR / "reviews"
SEDIMENT_DIR = OUT_DIR / "sediment"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
SEDIMENT_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════
# 1. 数据结构
# ══════════════════════════════════════════════════════

class ReviewStatus(str, Enum):
    PENDING = "pending"      # 待审
    APPROVED = "approved"    # 通过
    REJECTED = "rejected"    # 退回
    EDITED = "edited"        # 馆员编辑后通过

@dataclass
class EvidenceSource:
    """单条证据来源"""
    type: str                  # "paper" / "subgraph" / "community" / "entity"
    id: str                    # 文献ID / 子图ID / 社区ID / 实体ID
    title: str = ""            # 标题
    year: int = 0              # 年份
    confidence: float = 0.0    # 置信度 0~1
    snippet: str = ""          # 证据原文片段
    url: str = ""              # 可点击链接（如有）
    
    def to_dict(self):
        return asdict(self)

@dataclass
class AnswerAttribution:
    """单条问答的完整溯源性回答"""
    qa_id: str                 # 唯一ID
    question: str              # 用户问题
    answer: str                # 回答正文
    sources: list              # [EvidenceSource, ...]
    overall_confidence: float  # 整体置信度 0~1
    has_sufficient_evidence: bool  # 是否有充分证据
    model: str = "deepseek"    # 生成模型
    created_at: float = 0.0    # 时间戳
    # 审核字段
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewed_by: str = ""      # 审核人
    reviewed_at: float = 0.0   # 审核时间
    review_comment: str = ""   # 审核批注
    edited_answer: str = ""    # 馆员编辑后的答案
    rejected_reason: str = ""  # 退回原因
    
    def to_dict(self):
        d = asdict(self)
        d['review_status'] = self.review_status.value
        d['sources'] = [s.to_dict() if isinstance(s, EvidenceSource) else s for s in self.sources]
        return d
    
    @classmethod
    def from_dict(cls, d):
        d['sources'] = [EvidenceSource(**s) if isinstance(s, dict) else s for s in d.get('sources', [])]
        d['review_status'] = ReviewStatus(d.get('review_status', 'pending'))
        return cls(**d)


# ══════════════════════════════════════════════════════
# 2. 证据检索 + 置信度评分
# ══════════════════════════════════════════════════════

class EvidenceEngine:
    """证据引擎：检索知识图谱 + 计算置信度"""
    
    def __init__(self):
        self.terms = self._load_terms()
        self.b1 = self._load_b1()
        self.graph_v2 = self._load_graph_v2()
    
    def _load_terms(self):
        p = BASE / "output" / "trilingual" / "术语对齐表_三语_v1.json"
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))
        return []
    
    def _load_b1(self):
        p = DATA_DIR / "B1_文献主表.json"
        if not p.exists():
            return []
        raw = p.read_text(encoding='utf-8')
        raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
        idx = raw.find('{', raw.find('{') + 1)
        if idx > 0:
            return json.loads('[' + raw[idx:])
        return []
    
    def _load_graph_v2(self):
        p = BASE / "output" / "graph_redesign" / "graph_v2.json"
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))
        return {}
    
    def search_evidence(self, query: str, top_k: int = 5) -> tuple:
        """
        检索证据：从文献 + 图谱 + 术语中查找相关来源
        返回 (sources, confidence)
        """
        q_lower = query.lower()
        q_words = set(q_lower.split()[:8])
        sources = []
        
        # 1. 从核心术语检索
        for t in self.terms[:200]:
            en = t.get('en', '').lower()
            score = 0
            for w in q_words:
                if w in en or en in w:
                    score += 0.3
            # 精确匹配加分
            if q_lower in en or en in q_lower:
                score += 0.5
            if score > 0:
                sources.append(EvidenceSource(
                    type="entity", id=t.get('en', ''),
                    title=t.get('zh', t.get('en', '')),
                    snippet=f"{t.get('zh','')} / {t.get('en','')} / {t.get('ar','')}",
                    confidence=min(score, 0.95)
                ))
        
        # 2. 从文献检索
        for doc in self.b1[:200]:
            title = str(doc.get('title', '')).lower()
            abstract = str(doc.get('abstract', '')).lower()
            score = 0
            for w in q_words:
                if w in title: score += 0.2
                if w in abstract: score += 0.1
            if score > 0:
                sources.append(EvidenceSource(
                    type="paper", id=doc.get('arxiv_id', doc.get('id', '')),
                    title=doc.get('title', '')[:60],
                    year=int(doc.get('year', 0)),
                    snippet=abstract[:120] if abstract else title[:120],
                    confidence=min(score * 0.8, 0.90)
                ))
        
        # 3. 从图谱社区检索
        communities = self.graph_v2.get('communities', {})
        for cid, cdata in communities.items():
            summary = cdata.get('summary', '').lower()
            score = 0
            for w in q_words:
                if w in summary: score += 0.15
            if score > 0:
                sources.append(EvidenceSource(
                    type="community", id=f"comm-{cid}",
                    title=f"社区 {cid}: {cdata.get('summary', '')[:40]}",
                    snippet=cdata.get('summary', ''),
                    confidence=min(score, 0.8)
                ))
        
        # 排序去重
        seen_titles = set()
        unique = []
        for s in sorted(sources, key=lambda x: -x.confidence):
            key = (s.type, s.id)
            if key not in seen_titles:
                seen_titles.add(key)
                unique.append(s)
        
        top = unique[:top_k]
        
        # 计算整体置信度
        if not top:
            overall = 0.0
        else:
            overall = min(sum(s.confidence for s in top) / len(top) * 1.5, 0.99)
        
        return top, overall
    
    def answer_with_evidence(self, question: str, top_k: int = 5) -> AnswerAttribution:
        """生成带证据的溯源性回答"""
        sources, confidence = self.search_evidence(question, top_k)
        
        has_evidence = confidence >= 0.3 and len(sources) >= 1
        
        if not has_evidence:
            answer = f"**证据不足**：关于「{question}」，知识图谱和文献库中未找到充分证据。请尝试其他关键词，或联系馆员补充相关资源。"
        else:
            # 从证据构建回答
            source_list = "\n".join(
                f"- [{s.type}] {s.title[:40]} (置信度: {s.confidence:.0%})"
                for s in sources[:3]
            )
            answer = (
                f"关于「{question}」的查询结果：\n\n"
                f"基于 {len(sources)} 个相关来源的综合分析。\n\n"
                f"**关键发现**:\n"
                f"- 核心相关实体: {', '.join(s.title[:20] for s in sources[:3] if s.type == 'entity')}\n"
                f"- 相关文献: {sum(1 for s in sources if s.type == 'paper')} 篇\n"
                f"- 相关社区: {sum(1 for s in sources if s.type == 'community')} 个\n\n"
                f"**证据来源**:\n{source_list}\n\n"
                f"*本回答基于知识图谱检索和GraphRAG推理生成，置信度 {confidence:.0%}。"
            )
        
        qa_id = hashlib.md5((question + str(time.time())).encode()).hexdigest()[:12]
        
        return AnswerAttribution(
            qa_id=qa_id,
            question=question,
            answer=answer,
            sources=sources,
            overall_confidence=confidence,
            has_sufficient_evidence=has_evidence,
            created_at=time.time()
        )


# ══════════════════════════════════════════════════════
# 3. 馆员审核状态机
# ══════════════════════════════════════════════════════

class ReviewManager:
    """审核管理器：持久化 + 状态转换 + 留痕"""
    
    def __init__(self):
        self.db_path = OUT_DIR / "qa_reviews.json"
        self._load()
    
    def _load(self):
        if self.db_path.exists():
            with open(self.db_path, encoding='utf-8') as f:
                raw = json.load(f)
            self.qa_records = {k: AnswerAttribution.from_dict(v) for k, v in raw.items()}
        else:
            self.qa_records = {}
    
    def _save(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump({k: v.to_dict() for k, v in self.qa_records.items()},
                      f, ensure_ascii=False, indent=2)
    
    def add(self, qa: AnswerAttribution):
        self.qa_records[qa.qa_id] = qa
        self._save()
        return qa.qa_id
    
    def get(self, qa_id: str) -> Optional[AnswerAttribution]:
        return self.qa_records.get(qa_id)
    
    def list_by_status(self, status: ReviewStatus = None, limit: int = 50):
        items = list(self.qa_records.values())
        if status:
            items = [i for i in items if i.review_status == status]
        items.sort(key=lambda x: -x.created_at)
        return items[:limit]
    
    def approve(self, qa_id: str, reviewer: str, comment: str = "", edited_answer: str = ""):
        qa = self.qa_records.get(qa_id)
        if not qa:
            return False
        qa.review_status = ReviewStatus.EDITED if edited_answer else ReviewStatus.APPROVED
        qa.reviewed_by = reviewer
        qa.reviewed_at = time.time()
        qa.review_comment = comment
        if edited_answer:
            qa.edited_answer = edited_answer
        self._save()
        self._sediment(qa)  # 通过后自动沉淀
        return True
    
    def reject(self, qa_id: str, reviewer: str, reason: str):
        qa = self.qa_records.get(qa_id)
        if not qa:
            return False
        qa.review_status = ReviewStatus.REJECTED
        qa.reviewed_by = reviewer
        qa.reviewed_at = time.time()
        qa.rejected_reason = reason
        self._save()
        return True
    
    def _sediment(self, qa: AnswerAttribution):
        """通过审核后沉淀为Obsidian Markdown"""
        # 确定最终答案
        final_answer = qa.edited_answer if qa.edited_answer else qa.answer
        
        # 构建Markdown
        md = f"""---
id: {qa.qa_id}
type: qa
question: "{qa.question}"
status: {"edited" if qa.edited_answer else "approved"}
reviewer: {qa.reviewed_by}
reviewed_at: {time.strftime('%Y-%m-%d %H:%M', time.localtime(qa.reviewed_at))}
confidence: {qa.overall_confidence:.2%}
sources: {len(qa.sources)}
model: {qa.model}
tags: [qa, graphrag, approved]
---

# Q: {qa.question}

## 答案

{final_answer}

## 证据来源

| 类型 | ID | 标题 | 年份 | 置信度 |
|------|-----|------|------|--------|
"""
        for s in qa.sources:
            md += f"| {s.type} | {s.id} | {s.title[:30]} | {s.year} | {s.confidence:.0%} |\n"
        
        if qa.review_comment:
            md += f"\n## 馆员批注\n\n{qa.review_comment}\n"
        
        # 保存
        fname = f"qa_{qa.qa_id}.md"
        path = SEDIMENT_DIR / fname
        with open(path, 'w', encoding='utf-8') as f:
            f.write(md)
        
        return path


# ══════════════════════════════════════════════════════
# 4. API 端点（供 app_legacy.py 调用）
# ══════════════════════════════════════════════════════

class GraphRAGAPI:
    """GraphRAG API 端点，注入到 app_legacy.py"""
    
    def __init__(self):
        self.engine = EvidenceEngine()
        self.review = ReviewManager()
    
    def ask(self, question: str) -> dict:
        """问答 + 溯源"""
        qa = self.engine.answer_with_evidence(question)
        qa_id = self.review.add(qa)
        result = qa.to_dict()
        result['qa_id'] = qa_id
        return result
    
    def get_qa(self, qa_id: str) -> dict:
        qa = self.review.get(qa_id)
        return qa.to_dict() if qa else {"error": "not found"}
    
    def list_pending(self, limit: int = 20) -> list:
        return [qa.to_dict() for qa in self.review.list_by_status(ReviewStatus.PENDING, limit)]
    
    def list_approved(self, limit: int = 20) -> list:
        return [qa.to_dict() for qa in self.review.list_by_status(ReviewStatus.APPROVED, limit)]
    
    def approve(self, qa_id: str, reviewer: str, comment: str = "", edited_answer: str = "") -> dict:
        ok = self.review.approve(qa_id, reviewer, comment, edited_answer)
        return {"ok": ok, "qa_id": qa_id, "status": "approved"}
    
    def reject(self, qa_id: str, reviewer: str, reason: str) -> dict:
        ok = self.review.reject(qa_id, reviewer, reason)
        return {"ok": ok, "qa_id": qa_id, "status": "rejected", "reason": reason}
    
    def stats(self) -> dict:
        all_qas = list(self.review.qa_records.values())
        return {
            "total": len(all_qas),
            "pending": sum(1 for q in all_qas if q.review_status == ReviewStatus.PENDING),
            "approved": sum(1 for q in all_qas if q.review_status in (ReviewStatus.APPROVED, ReviewStatus.EDITED)),
            "rejected": sum(1 for q in all_qas if q.review_status == ReviewStatus.REJECTED),
            "sediment_path": str(SEDIMENT_DIR),
        }


# ══════════════════════════════════════════════════════
# 5. 演示运行
# ══════════════════════════════════════════════════════

def demo():
    print("=" * 60)
    print("  SKWM GraphRAG 证据溯源 + 馆员审核 演示")
    print("=" * 60)
    
    api = GraphRAGAPI()
    
    # 生成几个示例问答
    questions = [
        "中阿文旅热点",
        "文化遗产数字化方法",
        "阿拉伯NLP最新进展",
        "量子计算文旅应用",  # 这个应该证据不足
    ]
    
    for q in questions:
        print(f"\n  ── 问答: {q} ──")
        result = api.ask(q)
        print(f"  📊 置信度: {result['overall_confidence']:.0%}")
        print(f"  📎 证据数: {len(result['sources'])}")
        print(f"  ⏳ 状态: {result['review_status']}")
        print(f"  {'🔴 证据不足!' if not result['has_sufficient_evidence'] else '✅ 有充分证据'}")
        
        # 显示前2条证据
        for s in result['sources'][:2]:
            print(f"    [{s['type']}] {s['title'][:40]} (置信度: {s['confidence']:.0%})")
    
    # 演示审核流程
    print(f"\n  {'='*50}")
    print(f"  📋 审核流程演示")
    print(f"  {'='*50}")
    
    # 查看待审
    pending = api.list_pending()
    print(f"  📥 待审问答: {len(pending)} 条")
    
    # 通过第一条
    if pending:
        first = pending[0]
        print(f"  ✅ 通过: {first['question'][:30]}")
        api.approve(first['qa_id'], "馆员张三", "答案准确，证据充分")
        
        # 退回一条（如果证据不足）
        low_conf = [p for p in pending if p['overall_confidence'] < 0.3]
        for lc in low_conf:
            print(f"  ❌ 退回: {lc['question'][:30]} (置信度过低)")
            api.reject(lc['qa_id'], "馆员张三", "证据不足，无法核实")
    
    # 统计
    stats = api.stats()
    print(f"\n  📊 统计: 总计{stats['total']} | 待审{stats['pending']} | 通过{stats['approved']} | 退回{stats['rejected']}")
    print(f"  📄 沉淀路径: {stats['sediment_path']}")
    
    # 显示沉淀文件
    sediment_files = list(SEDIMENT_DIR.glob("*.md"))
    print(f"  📄 已沉淀: {len(sediment_files)} 篇 Markdown")
    for sf in sorted(sediment_files)[:3]:
        print(f"    - {sf.name}")


if __name__ == '__main__':
    demo()
