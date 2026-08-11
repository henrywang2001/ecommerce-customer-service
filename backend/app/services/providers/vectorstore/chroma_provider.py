"""Chroma 向量库具体实现（EX-3）。

委派给现有 ``app.rag.vector_store.vector_store`` 单例，复用其全部 Chroma 逻辑
（含 P7 单客户端锁竞争修复、P10 非空缓存、合并去重等），不重复实现，
也不触碰 AR-5 正在改动的 ``VectorStore.search`` 计分逻辑——保持单一事实来源。

follow-up: Milvus 等其它后端实现 ``VectorStoreProvider`` 即可热插拔。
"""
from typing import Any, Dict, List, Optional

from app.services.providers.base import VectorStoreProvider
from app.rag.vector_store import vector_store


class ChromaVectorStoreProvider(VectorStoreProvider):
    """Chroma 向量库提供方 — 包装现有 Chroma 单例。"""

    async def add(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict]] = None,
    ) -> bool:
        return await vector_store.add(ids, documents, embeddings, metadatas)

    async def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        return await vector_store.search(query_embedding, top_k)

    async def delete(self, ids: List[str]) -> bool:
        return await vector_store.delete(ids)

    async def get(self, ids: List[str]) -> List[str]:
        return await vector_store.get(ids)
