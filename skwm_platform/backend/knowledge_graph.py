"""
知识图谱增强模块 — 在 SKWM 现有 relation_query 基础上提供完整图谱服务
"""
import logging
from typing import Optional, List, Dict

logger = logging.getLogger("skwm.kg")


class KnowledgeGraph:
    """知识图谱查询引擎（基于 SKWM 的 DataLayer）"""

    def __init__(self, data):
        self.data = data

    def overview(self) -> dict:
        """图谱全景（面向前端）"""
        hot = self.data.get_hot_topics(self._latest(), 8)
        return {
            "total_entities": sum(s.get("n_nodes", 0) for s in self.data.snapshots.values()),
            "total_relations": sum(s.get("n_edges", 0) for s in self.data.snapshots.values()),
            "year_range": self.data.year_range,
            "hot_topics": hot,
            "emerging_topics": self.data.get_emerging(self._latest(), 5),
        }

    def query(self, entity: str) -> dict:
        """实体关系查询（利用 SKWM 的 relation_query）"""
        from skwm_aligned_v4 import SKWMController, DeepSeekClient
        ds = DeepSeekClient()
        ctrl = SKWMController(self.data, ds)
        y = self._latest()
        return ctrl.kg.relation_query(entity, y)

    def search(self, keyword: str) -> List[dict]:
        """模糊搜索实体"""
        results = []
        for year in sorted(self.data.state_vectors.keys(), key=int, reverse=True)[:1]:
            ents = self.data.state_vectors.get(year, {})
            for name, vec in ents.items():
                if keyword.lower() in name.lower():
                    results.append({
                        "name": name,
                        "heat": vec[0], "growth": vec[1],
                        "centrality": vec[2], "connections": vec[3],
                        "year": year,
                    })
        return results[:20]

    def _latest(self) -> int:
        return max(self.data.year_range) if self.data.year_range else 2026
