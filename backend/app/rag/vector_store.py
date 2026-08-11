"""RAG 模块 — 向量存储（ChromaDB）"""
import logging
from typing import List, Dict, Any, Optional

from app.rag.chroma_client import collection_has_docs, invalidate_collection_cache

logger = logging.getLogger(__name__)


class VectorStore:
    """向量存储封装 — ChromaDB"""

    async def _get_collection(self):
        """获取或创建 ChromaDB collection（ 修复：复用全局客户端单例，避免同目录多客户端锁竞争）"""
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
            # ：文档增减后使「是否非空」缓存失效
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
        """向量相似度检索 — 计分收口

        集中处理：零向量 / 降级检测、Chroma 查询、distance → [0,1] 归一化。
        rag_service 只需合并「向量结果 + 关键词结果」，不再直接依赖 chromadb 内部字段。

        返回形态与 rag_service 内置库结果对齐：{"id", "category", "question", "answer", "score"}
        """
        # ── 零向量 / 降级处理：embedding 不可用时（全 0 向量）直接跳过向量检索，
        # 避免用无意义向量污染结果，调用方回退到关键词检索。置于最前，连 Chroma 客户端都不创建。
        if not query_embedding or all(v == 0.0 for v in query_embedding):
            return []

        collection = await self._get_collection()
        # ：用带缓存的「是否非空」判断替代每次检索都执行的 collection.count
        if collection is None or not await collection_has_docs(collection):
            return []
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )
            if not results["ids"] or not results["ids"][0]:
                return []

            # 1) 收集原始字段与 distance，暂存后统一归一化
            raw_items: List[Dict[str, Any]] = []
            distances: List[float] = []
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = (
                    results["distances"][0][i]
                    if results.get("distances")
                    else 0.1 * i
                )
                raw_items.append({
                    "id": doc_id,
                    "category": metadata.get("category", ""),
                    "question": metadata.get("question", ""),
                    "answer": (
                        results["documents"][0][i]
                        if results["documents"]
                        else ""
                    ),
                })
                distances.append(distance)

            # 2) 对本次查询返回的 Chroma 结果集做 min-max 归一化到 [0,1]
            # （最近→1.0，最远→0.0），使其与内置库关键词分数（0.3~1.0）同量纲，
            # 合并排序时向量命中能合理上浮。
            # 不用 1/(1+distance)：本数据所有距离都在 ~万级，该式会把所有向量分数
            # 压成 ~1e-5 且几乎无差异，等于没修。
            dmin = min(distances)
            dmax = max(distances)
            span = dmax - dmin
            for item, distance in zip(raw_items, distances):
                item["score"] = 1.0 if span == 0 else 1.0 - (distance - dmin) / span
            return raw_items
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
            # ：文档增减后使「是否非空」缓存失效
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
