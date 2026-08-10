"""RAG 模块 — 向量存储（ChromaDB）"""
import logging
from typing import List, Dict, Any, Optional

from app.rag.chroma_client import collection_has_docs, invalidate_collection_cache

logger = logging.getLogger(__name__)


class VectorStore:
    """向量存储封装 — ChromaDB"""

    async def _get_collection(self):
        """获取或创建 ChromaDB collection（P7 修复：复用全局客户端单例，避免同目录多客户端锁竞争）"""
        from app.rag.chroma_client import get_chroma_client
        client = get_chroma_client()
        if client is None:
            return None
        try:
            from app.core.config import settings
            return client.get_or_create_collection(name=settings.CHROMA_COLLECTION)
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
            # P10：文档增减后使「是否非空」缓存失效
            invalidate_collection_cache()
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
        # P10：用带缓存的「是否非空」判断替代每次检索都执行的 collection.count()
        if collection is None or not await collection_has_docs(collection):
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
            # P10：文档增减后使「是否非空」缓存失效
            invalidate_collection_cache()
            return True
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False

    async def get(self, ids: List[str]) -> List[str]:
        """返回实际存在的 id 列表（用于删除前确认存在性，避免误报）"""
        collection = await self._get_collection()
        if collection is None:
            return []
        try:
            res = collection.get(ids=ids)
            return (res.get("ids") or []) if res else []
        except Exception as e:
            logger.error(f"向量获取失败: {e}")
            return []


# 全局单例
vector_store = VectorStore()
