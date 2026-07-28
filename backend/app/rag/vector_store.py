"""RAG 模块 — 向量存储（ChromaDB）"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class VectorStore:
    """向量存储封装 — ChromaDB"""

    def __init__(self):
        self._client = None

    async def _get_collection(self):
        """获取或创建 ChromaDB collection"""
        if self._client is None:
            try:
                import chromadb
                from app.core.config import settings
                self._client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
                logger.info(f"ChromaDB 客户端已初始化: {settings.CHROMA_PERSIST_DIR}")
            except ImportError:
                logger.warning("chromadb 未安装")
                return None
        try:
            from app.core.config import settings
            return self._client.get_or_create_collection(name=settings.CHROMA_COLLECTION)
        except Exception as e:
            logger.error(f"获取 collection 失败: {e}")
            return None

    async def add(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict]] = None,
    ) -> bool:
        """批量添加文档到向量存储"""
        collection = await self._get_collection()
        if collection is None:
            return False
        try:
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            return True
        except Exception as e:
            logger.error(f"向量存储添加失败: {e}")
            return False

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """向量相似度检索"""
        collection = await self._get_collection()
        if collection is None or collection.count() == 0:
            return []
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )
            output = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    output.append({
                        "id": doc_id,
                        "score": 1.0 - (results["distances"][0][i] if results.get("distances") else 0.1 * i),
                        "document": results["documents"][0][i] if results["documents"] else "",
                        "metadata": metadata,
                    })
            return output
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []

    async def delete(self, ids: List[str]) -> bool:
        """删除向量"""
        collection = await self._get_collection()
        if collection is None:
            return False
        try:
            collection.delete(ids=ids)
            return True
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False


# 全局单例
vector_store = VectorStore()
