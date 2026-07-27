"""
GraphRAG 问答模块 — 多路召回（规则+向量+图谱）+ LLM 生成
"""
import os, re, logging
from typing import Dict, Optional

logger = logging.getLogger("skwm.graphrag")


class GraphRAG:
    """GraphRAG 流水线，对接 SKWM 现有数据层"""

    def __init__(self, data, vector_store, knowledge_graph, service_rules):
        self.data = data
        self.vs = vector_store
        self.kg = knowledge_graph
        self.svc = service_rules

    def answer(self, question: str, user: str = "teacher") -> Dict:
        """三路召回 + 生成"""
        y = self._latest()

        # 1. 规则匹配（P 层）
        rule_result = self._match_rules(question)
        rule_triggered = rule_result is not None

        # 2. 向量检索
        vector_hits = self.vs.search(question, top_k=3)

        # 3. 图谱遍历
        graph_hit = None
        for ent_name in self.data.get_entities(y):
            if any(kw in question for kw in [ent_name, ent_name[:2]]):
                graph_hit = ent_name
                break

        # 4. 回答
        if rule_triggered:
            answer = rule_result
            confidence = 0.95
            sources = ["规则引擎 (P)"]
        else:
            ctx = self._build_context(question, vector_hits, graph_hit)
            answer = self._call_llm(question, ctx, user)
            confidence = 0.4 if not vector_hits else 0.7
            sources = [h.get("text", "")[:60] for h in vector_hits[:2]]
            if graph_hit:
                sources.append(f"图谱: {graph_hit}")

        return {
            "question": question,
            "rule_triggered": rule_triggered,
            "confidence": confidence,
            "answer": answer,
            "sources": sources,
            "vector_hits": len(vector_hits),
            "graph_entity": graph_hit or "",
        }

    def _match_rules(self, question: str) -> Optional[str]:
        patterns = {
            "热点|趋势|前沿": "**热点分析**\n" + self._hotspot_text(),
            "关系|关联|联系|图谱": "**关系查询**\n请在知识图谱页面(/knowledge-graph)输入实体名查看关联。",
            "预测|未来|趋势": "**趋势预测**\n基于时间序列，SKWM 预计知识网络持续增长。",
            "推荐|建议|帮助": "**智能推荐**\n请先在系统设置中选择您的用户角色（教师/学生/馆员/管理）。",
        }
        for pattern, response in patterns.items():
            if re.search(pattern, question):
                return response
        return None

    def _hotspot_text(self) -> str:
        y = self._latest()
        hot = self.data.get_hot_topics(y, 5)
        return "\n".join([f"- {t['name']} (热度 {t['heat']})" for t in hot])

    def _build_context(self, question: str, vector_hits: list, graph_hit: Optional[str]) -> str:
        parts = ["## 相关知识"]
        for i, h in enumerate(vector_hits[:3]):
            parts.append(f"[{i+1}] {h.get('text', '')[:200]}")
        if graph_hit:
            rels = self.kg.query(graph_hit)
            neighbors = [n.get("entity", n.get("target", "")) for n in rels.get("neighbors", [])[:5]]
            if neighbors:
                parts.append(f"\n## 关联实体\n{graph_hit} → {', '.join(neighbors)}")
        return "\n\n".join(parts)

    def _call_llm(self, question: str, ctx: str, user: str) -> str:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return self._fallback(question, ctx)
        import httpx
        try:
            resp = httpx.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    "messages": [
                        {"role": "system", "content": f"你是 SKWM 智能助手，用户角色：{user}"},
                        {"role": "user", "content": f"问题：{question}\n\n{ctx}"},
                    ],
                    "temperature": 0.3, "max_tokens": 1024,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            pass
        return self._fallback(question, ctx)

    def _fallback(self, question: str, ctx: str = "") -> str:
        return (
            f"**SKWM 智能回答**\n\n"
            f"关于「{question}」，当前 LLM 暂不可用。\n\n"
            f"1. 查看知识图谱获取实体关系\n"
            f"2. 设置 DEEPSEEK_API_KEY 获取精准回答\n\n"
            f"*规则引擎模式*"
        )

    def _latest(self) -> int:
        return max(self.data.year_range) if self.data.year_range else 2026
