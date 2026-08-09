#!/usr/bin/env python3
"""
Neo4j 图数据库客户端 — 中阿文旅知识图谱

对接: SKWM DataLayer + 知识图谱数据
功能: 连接管理 / 数据导入 / 图查询 / Cypher 执行
"""
import os
import json
import csv
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("skwm.neo4j")


try:
    from neo4j import GraphDatabase, Driver, Session
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j 驱动未安装。运行: pip install neo4j")


@dataclass
class Neo4jConfig:
    """Neo4j 连接配置"""
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"
    
    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        """从环境变量或 .env 文件加载配置"""
        # 尝试加载 .env 文件
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())
        
        return cls(
            uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            user=os.environ.get("NEO4J_USER", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", "password"),
            database=os.environ.get("NEO4J_DATABASE", "neo4j"),
        )


class Neo4jClient:
    """
    Neo4j 图数据库客户端
    
    功能:
    - 连接管理 (connect/close)
    - 数据导入 (import_from_skwm / import_from_csv)
    - 图查询 (execute_cypher / search / get_neighbors)
    - 统计 (stats / constraints)
    """
    
    def __init__(self, config: Optional[Neo4jConfig] = None):
        if not NEO4J_AVAILABLE:
            raise RuntimeError("neo4j 驱动未安装。运行: pip install neo4j")
        
        self.config = config or Neo4jConfig.from_env()
        self.driver: Optional[Driver] = None
        self.connected = False
    
    def connect(self) -> bool:
        """连接到 Neo4j"""
        try:
            self.driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
            )
            self.driver.verify_connectivity()
            self.connected = True
            logger.info(f"✅ Neo4j 连接成功: {self.config.uri}")
            return True
        except Exception as e:
            logger.error(f"❌ Neo4j 连接失败: {e}")
            self.connected = False
            return False
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            self.connected = False
    
    def _session(self) -> "Session":
        """获取会话"""
        if not self.connected:
            self.connect()
        return self.driver.session(database=self.config.database)
    
    def execute_cypher(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        执行 Cypher 查询
        返回: [{key: value, ...}, ...]
        """
        with self._session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
    
    def write_cypher(self, query: str, params: Optional[Dict] = None) -> int:
        """
        执行写入 Cypher
        返回: 受影响的记录数
        """
        with self._session() as session:
            result = session.run(query, params or {})
            summary = result.consume()
            return summary.counters.properties_set
    
    # ═══════════════════════════════════════════════════════════════
    # 约束与索引
    # ═══════════════════════════════════════════════════════════════
    
    def create_constraints(self):
        """创建唯一性约束"""
        constraints = [
            "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT country_id IF NOT EXISTS FOR (c:Country) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT org_id IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE",
        ]
        for c in constraints:
            try:
                self.execute_cypher(c)
            except Exception as e:
                logger.warning(f"约束创建失败: {e}")
        logger.info("✅ 约束创建完成")
    
    def create_indexes(self):
        """创建全文索引"""
        indexes = [
            "CREATE INDEX paper_title IF NOT EXISTS FOR (p:Paper) ON (p.title)",
            "CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name)",
            "CREATE INDEX author_name IF NOT EXISTS FOR (a:Author) ON (a.name)",
        ]
        for idx in indexes:
            try:
                self.execute_cypher(idx)
            except Exception as e:
                logger.warning(f"索引创建失败: {e}")
        logger.info("✅ 索引创建完成")
    
    # ═══════════════════════════════════════════════════════════════
    # 数据导入
    # ═══════════════════════════════════════════════════════════════
    
    def import_from_skwm(self, data_layer, verbose: bool = True) -> Dict[str, int]:
        """
        从 SKWM DataLayer 导入数据到 Neo4j
        
        导入:
        - 时间切片中的节点 (Topic/Entity)
        - 时间切片中的边 (CO_OCCUR)
        - 合作边 (COLLABORATION)
        - 状态向量 (属性)
        """
        stats = {"nodes": 0, "edges": 0, "errors": 0}
        
        if verbose:
            print("📦 开始导入 SKWM 数据到 Neo4j...")
        
        self.create_constraints()
        
        # 1. 导入节点 (从时间切片)
        if verbose:
            print("  📝 导入节点...")
        
        for year, snapshot in data_layer.snapshots.items():
            if not year.isdigit():
                continue
            
            nodes = snapshot.get("nodes", [])
            for name in nodes:
                try:
                    # 获取状态向量
                    state_vec = data_layer.state_vectors.get(year, {}).get(name, [0, 0, 0, 0])
                    
                    query = """
                    MERGE (t:Topic {id: $id})
                    SET t.name = $name,
                        t.year = $year,
                        t.heat = $heat,
                        t.growth = $growth,
                        t.centrality = $centrality,
                        t.connections = $connections
                    """
                    self.write_cypher(query, {
                        "id": f"{name}_{year}",
                        "name": name,
                        "year": int(year),
                        "heat": float(state_vec[0]) if len(state_vec) > 0 else 0,
                        "growth": float(state_vec[1]) if len(state_vec) > 1 else 0,
                        "centrality": float(state_vec[2]) if len(state_vec) > 2 else 0,
                        "connections": int(state_vec[3]) if len(state_vec) > 3 else 0,
                    })
                    stats["nodes"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    if verbose:
                        print(f"    ⚠️ 节点导入失败 {name}: {e}")
        
        if verbose:
            print(f"  ✅ 节点导入: {stats['nodes']}个")
        
        # 2. 导入边 (从时间切片)
        if verbose:
            print("  📝 导入共现边...")
        
        for year, snapshot in data_layer.snapshots.items():
            if not year.isdigit():
                continue
            
            edges = snapshot.get("edges", [])
            for edge in edges:
                try:
                    src = edge.get("u", "") or edge.get("source", "")
                    tgt = edge.get("v", "") or edge.get("target", "")
                    weight = edge.get("w", 1)
                    
                    if not src or not tgt:
                        continue
                    
                    query = """
                    MATCH (a:Topic {id: $src_id})
                    MATCH (b:Topic {id: $tgt_id})
                    MERGE (a)-[r:CO_OCCUR {year: $year}]->(b)
                    SET r.weight = $weight
                    """
                    self.write_cypher(query, {
                        "src_id": f"{src}_{year}",
                        "tgt_id": f"{tgt}_{year}",
                        "year": int(year),
                        "weight": float(weight),
                    })
                    stats["edges"] += 1
                except Exception as e:
                    stats["errors"] += 1
        
        if verbose:
            print(f"  ✅ 共现边导入: {stats['edges']}条")
        
        # 3. 导入合作边
        if verbose:
            print("  📝 导入合作边...")
        
        collab_count = 0
        for edge in data_layer.collab_edges:
            try:
                query = """
                MERGE (a:Author {id: $src})
                SET a.name = $src
                MERGE (b:Author {id: $tgt})
                SET b.name = $tgt
                MERGE (a)-[r:COLLABORATES_WITH]->(b)
                SET r.weight = $weight
                """
                self.write_cypher(query, {
                    "src": edge["source"],
                    "tgt": edge["target"],
                    "weight": float(edge.get("weight", 1)),
                })
                collab_count += 1
            except Exception as e:
                stats["errors"] += 1
        
        stats["edges"] += collab_count
        if verbose:
            print(f"  ✅ 合作边导入: {collab_count}条")
        
        if verbose:
            print(f"\n🎉 导入完成: {stats['nodes']}节点, {stats['edges']}边, {stats['errors']}错误")
        
        return stats
    
    def import_from_csv(self, csv_path: str, node_type: str, 
                        mapping: Dict[str, str]) -> int:
        """
        从 CSV 导入节点
        
        Args:
            csv_path: CSV 文件路径
            node_type: 节点类型 (Paper/Topic/Author/...)
            mapping: 列名 → 属性名 映射
        
        Returns:
            导入的记录数
        """
        count = 0
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    props = {}
                    for csv_col, neo4j_prop in mapping.items():
                        if csv_col in row:
                            props[neo4j_prop] = row[csv_col]
                    
                    if "id" not in props:
                        props["id"] = f"{node_type}_{count}"
                    
                    set_clause = ", ".join([f"n.{k} = ${k}" for k in props.keys()])
                    query = f"""
                    MERGE (n:{node_type} {{id: $id}})
                    SET {set_clause}
                    """
                    self.write_cypher(query, props)
                    count += 1
                except Exception as e:
                    logger.warning(f"CSV 行导入失败: {e}")
        
        logger.info(f"✅ CSV 导入完成: {count}条 {node_type}")
        return count
    
    # ═══════════════════════════════════════════════════════════════
    # 图查询
    # ═══════════════════════════════════════════════════════════════
    
    def stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        query = """
        MATCH (n)
        WITH labels(n) AS labels, count(n) AS cnt
        RETURN collect({labels: labels, count: cnt}) AS nodes
        """
        nodes = self.execute_cypher(query)
        
        query = """
        MATCH ()-[r]->()
        WITH type(r) AS type, count(r) AS cnt
        RETURN collect({type: type, count: cnt}) AS edges
        """
        edges = self.execute_cypher(query)
        
        return {
            "nodes": nodes[0]["nodes"] if nodes else [],
            "edges": edges[0]["edges"] if edges else [],
            "connected": self.connected,
            "database": self.config.database,
        }
    
    def search(self, keyword: str, limit: int = 20) -> List[Dict]:
        """模糊搜索节点"""
        query = """
        MATCH (n)
        WHERE n.name CONTAINS $keyword OR n.title CONTAINS $keyword
        RETURN labels(n) AS labels, n.id AS id, n.name AS name, 
               n.heat AS heat, n.year AS year
        LIMIT $limit
        """
        return self.execute_cypher(query, {"keyword": keyword, "limit": limit})
    
    def get_neighbors(self, node_id: str, depth: int = 1) -> Dict:
        """获取节点的邻居 (修复: start保留字 + 变长路径不可参数化)"""
        d = max(1, min(int(depth), 3))  # 限制深度 1-3
        query = f"""
        MATCH path = (n {{id: $id}})-[*1..{d}]-(neighbor)
        RETURN path
        LIMIT 50
        """
        results = self.execute_cypher(query, {"id": node_id})

        nodes = {}  # id -> node dict (dict不可哈希, 用id去重)
        edges = []

        for r in results:
            path = r.get("path")
            if path and isinstance(path, list):
                # record.data() 把 Path 序列化为交替列表: [node, rel, node, rel, ...]
                for i, item in enumerate(path):
                    if i % 2 == 0 and isinstance(item, dict):
                        nid = item.get("id", "")
                        if nid:
                            nodes[nid] = item
                    elif i % 2 == 1 and isinstance(item, str):
                        # 关系: 前一个元素是起点, 后一个元素是终点
                        if i - 1 >= 0 and i + 1 < len(path) \
                           and isinstance(path[i-1], dict) and isinstance(path[i+1], dict):
                            edges.append({
                                "source": path[i-1].get("id", ""),
                                "target": path[i+1].get("id", ""),
                                "type": item,
                            })

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "center": node_id,
        }
    
    def get_hot_topics(self, year: int, top_k: int = 10) -> List[Dict]:
        """获取某年热点主题"""
        query = """
        MATCH (t:Topic {year: $year})
        RETURN t.name AS name, t.heat AS heat, t.growth AS growth,
               t.centrality AS centrality
        ORDER BY t.heat DESC
        LIMIT $top_k
        """
        return self.execute_cypher(query, {"year": year, "top_k": top_k})
    
    def get_collaboration_network(self, author_name: str, limit: int = 10) -> List[Dict]:
        """获取作者合作网络"""
        query = """
        MATCH (a1:Author)-[:AUTHORED]-(p:Paper)-[:AUTHORED]-(a2:Author)
        WHERE a1.name = $name AND a1 <> a2
        RETURN a2.name AS collaborator, count(p) AS weight
        ORDER BY weight DESC
        LIMIT $limit
        """
        return self.execute_cypher(query, {"name": author_name, "limit": limit})
    
    def get_co_occur_keywords(self, keyword: str, limit: int = 10) -> List[Dict]:
        """获取共现关键词"""
        query = """
        MATCH (k:Topic)-[r:CO_OCCURS_WITH]-(other:Topic)
        WHERE k.name = $keyword
        RETURN other.name AS keyword, count(r) AS weight
        ORDER BY weight DESC
        LIMIT $limit
        """
        return self.execute_cypher(query, {"keyword": keyword, "limit": limit})
    
    def clear_all(self):
        """清空数据库（危险操作）"""
        self.execute_cypher("MATCH (n) DETACH DELETE n")
        logger.warning("⚠️ 数据库已清空")


# ═══════════════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════════════

def create_neo4j_client() -> Optional[Neo4jClient]:
    """创建 Neo4j 客户端（如果可用）"""
    if not NEO4J_AVAILABLE:
        return None
    
    config = Neo4jConfig.from_env()
    client = Neo4jClient(config)
    
    if client.connect():
        return client
    return None


# ═══════════════════════════════════════════════════════════════════
# 命令行工具
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    print("🔌 Neo4j 客户端测试")
    print("=" * 50)
    
    if not NEO4J_AVAILABLE:
        print("❌ neo4j 驱动未安装")
        print("运行: pip install neo4j")
        sys.exit(1)
    
    config = Neo4jConfig.from_env()
    print(f"配置: uri={config.uri}, user={config.user}")
    
    client = Neo4jClient(config)
    
    if not client.connect():
        print("❌ 连接失败，请检查 Neo4j 是否运行")
        sys.exit(1)
    
    print("\n📊 图统计:")
    stats = client.stats()
    print(f"  节点: {stats['nodes']}")
    print(f"  边: {stats['edges']}")
    
    print("\n🔍 测试搜索 '旅游':")
    results = client.search("旅游", limit=5)
    for r in results:
        print(f"  {r}")
    
    client.close()
    print("\n✅ 完成")
