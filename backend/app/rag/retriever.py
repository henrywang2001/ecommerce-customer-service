"""RAG 模块 — 检索器"""
from typing import List, Dict, Any, Optional
import logging
from app.services.embedding_service import embedding_service
from app.rag.vector_store import vector_store

logger = logging.getLogger(__name__)


class Retriever:
    """RAG 检索器"""

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        use_keywords: bool = True,
    ) -> List[Dict[str, Any]]:
        """检索相关文档 — 混合策略（向量 + 关键词）"""
        results = []

        # 1. 向量检索
        try:
            query_embedding = await embedding_service.encode_single(query)
            vector_results = await vector_store.search(query_embedding, top_k)
            results.extend(vector_results)
        except Exception as e:
            logger.warning(f"向量检索失败: {e}")

        # 2. 关键词检索（如果 ChromaDB 为空，使用内置知识库）
        if not results:
            from app.services.rag_service import rag_service
            kw_results = rag_service._keyword_search(query, top_k)
            results = [{"score": r.pop("score", 0), "document": r.get("answer", ""), "metadata": {"category": r.get("category", ""), "question": r.get("question", "")}} for r in kw_results]

        # 3. 去重和排序
        seen = set()
        unique = []
        for r in results:
            key = r.get("document", "")[:100]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        unique.sort(key=lambda x: x.get("score", 0), reverse=True)
        return unique[:top_k]


# 全局单例
retriever = Retriever()
