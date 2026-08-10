"""Embedding 服务 - 使用千问 text-embedding-v1（集成 Langfuse 追踪）"""
from typing import List
import httpx
import logging
from app.core.config import settings
from app.services.observe_service import observe
from app.utils.http_client import get_http_client
from app.utils.outbound import post_with_resilience, embedding_semaphore, embedding_breaker

logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量嵌入服务 — 千问 DashScope"""

    def __init__(self):
        self.api_key = settings.EMBEDDING_API_KEY
        self.model = settings.EMBEDDING_MODEL
        self.api_base = settings.EMBEDDING_API_BASE.rstrip("/")

    async def encode(self, texts: List[str]) -> List[List[float]]:
        """将文本列表转换为向量列表 — Langfuse embedding 追踪"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # DashScope compatible-mode API 使用 OpenAI 格式
        payload = {
            "model": self.model,
            "input": texts,
        }

        # ── Langfuse: embedding 追踪 ──
        with observe.embedding(
            name="text-embedding",
            model=self.model,
            input={"texts": texts, "count": len(texts)},
        ) as emb:
            try:
                client = get_http_client()
                response = await post_with_resilience(
                    client,
                    f"{self.api_base}/embeddings",
                    semaphore=embedding_semaphore,
                    breaker=embedding_breaker,
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                # 按 index 排序返回
                embeddings = sorted(data["data"], key=lambda x: x["index"])
                result = [item["embedding"] for item in embeddings]

                if emb is not None:
                    usage = data.get("usage", {})
                    emb.update(
                        output={
                            "count": len(result),
                            "dimension": len(result[0]) if result else 0,
                        },
                        usage_details={
                            "total_tokens": usage.get("total_tokens", 0),
                        },
                    )
                return result
            except Exception as e:
                logger.error(f"Embedding 生成失败: {e}")
                if emb is not None:
                    emb.update(
                        output={},
                        status_message=str(e),
                        level="ERROR",
                    )
                # 返回零向量作为 fallback
                return [[0.0] * settings.EMBEDDING_DIMENSION for _ in texts]

    async def encode_single(self, text: str) -> List[float]:
        """将单个文本转换为向量"""
        results = await self.encode([text])
        return results[0] if results else [0.0] * settings.EMBEDDING_DIMENSION


# 全局单例
embedding_service = EmbeddingService()
