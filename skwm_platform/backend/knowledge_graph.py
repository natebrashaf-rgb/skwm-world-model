"""
知识图谱增强模块 — 在 SKWM 现有 relation_query 基础上提供完整图谱服务
支持 Neo4j 图数据库查询（如果可用）
"""
import logging
from typing import Optional, List, Dict

logger = logging.getLogger("skwm.kg")


class KnowledgeGraph:
    """知识图谱查询引擎（基于 SKWM 的 DataLayer + Neo4j）"""

    def __init__(self, data, neo4j_client=None):
        self.data = data
        self.neo4j = neo4j_client

    def overview(self) -> dict:
        """图谱全景（面向前端）"""
        hot = self.data.get_hot_topics(self._latest(), 8)
        
        result = {
            "total_entities": sum(s.get("n_nodes", 0) for s in self.data.snapshots.values()),
            "total_relations": sum(s.get("n_edges", 0) for s in self.data.snapshots.values()),
            "year_range": self.data.year_range,
            "hot_topics": hot,
            "emerging_topics": self.data.get_emerging(self._latest(), 5),
        }
        
        # 如果有 Neo4j，添加图数据库统计
        if self.neo4j and self.neo4j.connected:
            try:
                neo4j_stats = self.neo4j.stats()
                result["neo4j"] = {
                    "connected": True,
                    "node_count": sum(n.get("count", 0) for n in neo4j_stats.get("nodes", [])),
                    "edge_count": sum(e.get("count", 0) for e in neo4j_stats.get("edges", [])),
                }
            except Exception as e:
                result["neo4j"] = {"connected": False, "error": str(e)}
        
        return result

    def query(self, entity: str) -> dict:
        """实体关系查询（优先 Neo4j，降级到 SKWM）"""
        # 尝试 Neo4j 查询
        if self.neo4j and self.neo4j.connected:
            try:
                results = self.neo4j.search(entity, limit=10)
                if results:
                    neighbors = self.neo4j.get_neighbors(results[0].get("id", ""), depth=1)
                    return {
                        "entity": entity,
                        "source": "neo4j",
                        "found": True,
                        "neighbors": neighbors.get("nodes", [])[:10],
                        "edges": neighbors.get("edges", [])[:20],
                    }
            except Exception as e:
                logger.warning(f"Neo4j 查询失败，降级到 SKWM: {e}")
        
        # 降级到 SKWM
        from skwm_aligned_v4 import SKWMController, DeepSeekClient
        ds = DeepSeekClient()
        ctrl = SKWMController(self.data, ds)
        y = self._latest()
        return ctrl.kg.relation_query(entity, y)

    def search(self, keyword: str) -> List[dict]:
        """模糊搜索实体（优先 Neo4j，降级到 SKWM）"""
        # 尝试 Neo4j 搜索
        if self.neo4j and self.neo4j.connected:
            try:
                results = self.neo4j.search(keyword, limit=20)
                if results:
                    return [
                        {
                            "name": r.get("name", ""),
                            "heat": r.get("heat", 0),
                            "growth": 0,
                            "centrality": 0,
                            "connections": 0,
                            "year": r.get("year", 0),
                            "labels": r.get("labels", []),
                        }
                        for r in results
                    ]
            except Exception as e:
                logger.warning(f"Neo4j 搜索失败，降级到 SKWM: {e}")
        
        # 降级到 SKWM
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

    def get_neighbors(self, entity: str, depth: int = 1) -> dict:
        """获取实体邻居（Neo4j）"""
        if self.neo4j and self.neo4j.connected:
            try:
                search_results = self.neo4j.search(entity, limit=1)
                if search_results:
                    node_id = search_results[0].get("id", "")
                    return self.neo4j.get_neighbors(node_id, depth)
            except Exception as e:
                logger.warning(f"Neo4j 邻居查询失败: {e}")
        
        return {"nodes": [], "edges": [], "error": "Neo4j 不可用"}

    def get_hot_topics(self, year: int = None, top_k: int = 10) -> List[dict]:
        """获取热点主题（Neo4j）"""
        y = year or self._latest()
        
        if self.neo4j and self.neo4j.connected:
            try:
                return self.neo4j.get_hot_topics(y, top_k)
            except Exception as e:
                logger.warning(f"Neo4j 热点查询失败: {e}")
        
        return self.data.get_hot_topics(y, top_k)

    def get_collaboration_network(self, author: str, limit: int = 10) -> List[dict]:
        """获取作者合作网络（Neo4j）"""
        if self.neo4j and self.neo4j.connected:
            try:
                return self.neo4j.get_collaboration_network(author, limit)
            except Exception as e:
                logger.warning(f"Neo4j 合作网络查询失败: {e}")
        
        return []

    def get_co_occur_keywords(self, keyword: str, limit: int = 10) -> List[dict]:
        """获取共现关键词（Neo4j）"""
        if self.neo4j and self.neo4j.connected:
            try:
                return self.neo4j.get_co_occur_keywords(keyword, limit)
            except Exception as e:
                logger.warning(f"Neo4j 共现查询失败: {e}")
        
        return []

    def _latest(self) -> int:
        return max(self.data.year_range) if self.data.year_range else 2026
