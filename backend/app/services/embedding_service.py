"""Embedding 服务 - 使用千问 text-embedding-v1"""
from typing import List
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量嵌入服务 — 千问 DashScope"""

    def __init__(self):
        self.api_key = settings.EMBEDDING_API_KEY
        self.model = settings.EMBEDDING_MODEL
        self.api_base = settings.EMBEDDING_API_BASE.rstrip("/")

    async def encode(self, texts: List[str]) -> List[List[float]]:
        """将文本列表转换为向量列表"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # DashScope compatible-mode API 使用 OpenAI 格式
        payload = {
            "model": self.model,
            "input": texts,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_base}/embeddings",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                # 按 index 排序返回
                embeddings = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in embeddings]
        except Exception as e:
            logger.error(f"Embedding 生成失败: {e}")
            # 返回零向量作为 fallback
            return [[0.0] * settings.EMBEDDING_DIMENSION for _ in texts]

    async def encode_single(self, text: str) -> List[float]:
        """将单个文本转换为向量"""
        results = await self.encode([text])
        return results[0] if results else [0.0] * settings.EMBEDDING_DIMENSION


# 全局单例
embedding_service = EmbeddingService()
