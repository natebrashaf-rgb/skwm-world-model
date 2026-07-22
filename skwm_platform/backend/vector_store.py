"""
向量库模块 — 基于 ChromaDB 的知识检索
作为 SKWM 的补充，不修改已有代码
"""
import os, logging
from typing import List, Dict, Optional

logger = logging.getLogger("skwm.vector_store")

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False


class VectorStore:
    """向量检索层 — 为 SKWM 提供语义搜索能力"""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.collection = None
        self._mock_store: List[Dict] = []

        if HAS_CHROMA:
            try:
                os.makedirs(persist_dir, exist_ok=True)
                client = chromadb.PersistentClient(
                    path=persist_dir, settings=Settings(anonymized_telemetry=False)
                )
                self.collection = client.get_or_create_collection(
                    name="skwm_kb", metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"  ✅ ChromaDB 向量库已连接")
            except Exception as e:
                logger.warning(f"  ChromaDB 初始化失败: {e}")
        else:
            logger.info("  ℹ️ 使用模拟向量库")

    def count(self) -> int:
        if self.collection:
            return self.collection.count()
        return len(self._mock_store)

    def add(self, documents: List[Dict]):
        if self.collection:
            ids = [d["id"] for d in documents]
            texts = [d["text"] for d in documents]
            metas = [d.get("metadata", {}) for d in documents]
            self.collection.add(documents=texts, ids=ids, metadatas=metas)
        else:
            self._mock_store.extend(documents)
        logger.info(f"  ✅ 向量库新增 {len(documents)} 条 (共 {self.count()})")

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if self.collection:
            results = self.collection.query(
                query_texts=[query], n_results=min(top_k, self.count() or 1)
            )
            hits = []
            for i in range(len(results["ids"][0])):
                hits.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": round(1 - results["distances"][0][i], 3) if results["distances"] else 0,
                })
            return hits
        # 模拟检索
        hits = []
        for doc in self._mock_store:
            score = sum(1 for word in query.lower().split() if word in doc.get("text", "").lower())
            if score > 0:
                hits.append({**doc, "score": score / max(len(query.split()), 1)})
        hits.sort(key=lambda x: -x.get("score", 0))
        return hits[:top_k]

    def load_skwm_data(self, data):
        """从 SKWM 的 DataLayer 加载数据到向量库"""
        docs = []
        # 从状态向量提取热点实体
        if not hasattr(data, 'state_vectors'):
            return
        for year, entities in data.state_vectors.items():
            if not isinstance(entities, dict):
                continue
            for name, vec in list(entities.items())[:100]:
                if not isinstance(vec, (list, tuple)) or len(vec) < 4:
                    continue
                docs.append({
                    "id": f"sv_{year}_{name}",
                    "text": f"{name} 在 {year} 年的知识热度为 {vec[0]}，增长 {vec[1]}，中心度 {vec[2]}，关联 {vec[3]} 个实体",
                    "metadata": {"year": year, "entity": name, "source": "state_vectors"},
                })
        if docs:
            self.add(docs)
