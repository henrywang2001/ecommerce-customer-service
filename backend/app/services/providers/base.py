"""Provider 抽象层— LLM / Embedding / VectorStore 的 ABC 与配置驱动选择。

设计目标：把「用哪家厂商的 LLM / Embedding / 向量库」从业务逻辑中解耦。
- 业务层（chat_service / rag_service / agent）只依赖本文件的 ABC 接口；
- 具体厂商实现（DeepSeek / DashScope / Chroma ...）通过 config 选择；
- 新增厂商 = 新增一个 ABC 子类 + 在对应 ``get_*_provider`` 工厂里加一个分支。

当前交付（受任务范围约束，其余厂商列为 follow-up）：
- ABC：``LLMProvider`` / ``EmbeddingProvider`` / ``VectorStoreProvider``
- 每种类型一个具体实现（与现有单例对齐）：
  - LLM → ``LLMService``（DeepSeek，兼容 OpenAI Chat Completions 协议）
  - Embedding → ``EmbeddingService``（DashScope / 千问 text-embedding）
  - VectorStore → ``ChromaVectorStoreProvider``（委派给现有 rag.vector_store 单例）
- 配置驱动选择：``settings.LLM_PROVIDER`` / ``EMBEDDING_PROVIDER`` / ``VECTORSTORE_PROVIDER``

follow-up（仅占位、未实现，避免本次改动过大）：
  OpenAI / Claude 的 LLM 实现，Qwen 之外的 Embedding 实现，Milvus 向量库实现。
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """LLM 提供方抽象：统一 单轮 / 多轮 / JSON / 流式 接口。"""

    @abstractmethod
    async def generate(self, prompt: str, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str: ...

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> str: ...

    @abstractmethod
    async def generate_json(self, prompt: str, temperature: float = 0.1, max_tokens: Optional[int] = None) -> Optional[dict]: ...

    @abstractmethod
    async def chat_stream(self, messages: List[Dict[str, str]], temperature: Optional[float] = None): ...

    @abstractmethod
    async def generate_stream(self, prompt: str, temperature: Optional[float] = None): ...


class EmbeddingProvider(ABC):
    """Embedding 提供方抽象。"""

    @abstractmethod
    async def encode(self, texts: List[str]) -> List[List[float]]: ...

    @abstractmethod
    async def encode_single(self, text: str) -> List[float]: ...


class VectorStoreProvider(ABC):
    """向量存储提供方抽象（Chroma / Milvus ...）。"""

    @abstractmethod
    async def add(self, ids: List[str], documents: List[str], embeddings: Optional[List[List[float]]] = None, metadatas: Optional[List[Dict]] = None) -> bool: ...

    @abstractmethod
    async def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def delete(self, ids: List[str]) -> bool: ...

    @abstractmethod
    async def get(self, ids: List[str]) -> List[str]: ...


def get_llm_provider() -> LLMProvider:
    """根据 ``settings.LLM_PROVIDER`` 选择 LLM 实现（配置驱动）。

    follow-up: "openai" / "claude" 等分支。当前仅有 deepseek 具体实现
    （即现有 ``LLMService``，DeepSeek 兼容 OpenAI Chat Completions 协议）。
    """
    name = (settings.LLM_PROVIDER or "deepseek").lower()
    if name == "deepseek":
        from app.services.llm_service import LLMService

        return LLMService()
    # elif name == "openai": return OpenAILLMProvider
    # elif name == "claude": return ClaudeLLMProvider
    logger.warning("未知 LLM_PROVIDER=%s，回退 deepseek", name)
    from app.services.llm_service import LLMService

    return LLMService()


def get_embedding_provider() -> EmbeddingProvider:
    """根据 ``settings.EMBEDDING_PROVIDER`` 选择 Embedding 实现（配置驱动）。

    follow-up: Qwen 之外的多模型 / 其它 Embedding 厂商分支。当前仅有 dashscope（千问）。
    """
    name = (settings.EMBEDDING_PROVIDER or "dashscope").lower()
    if name == "dashscope":
        from app.services.embedding_service import EmbeddingService

        return EmbeddingService()
    # elif name == "openai": return OpenAIEmbeddingProvider
    logger.warning("未知 EMBEDDING_PROVIDER=%s，回退 dashscope", name)
    from app.services.embedding_service import EmbeddingService

    return EmbeddingService()


def get_vector_store() -> VectorStoreProvider:
    """根据 ``settings.VECTORSTORE_PROVIDER`` 选择向量库实现（配置驱动）。

    follow-up: "milvus" 等分支。当前仅有 chroma 具体实现（委派现有单例）。
    """
    name = (settings.VECTORSTORE_PROVIDER or "chroma").lower()
    if name == "chroma":
        from app.services.providers.vectorstore import ChromaVectorStoreProvider

        return ChromaVectorStoreProvider()
    # elif name == "milvus": return MilvusVectorStoreProvider
    logger.warning("未知 VECTORSTORE_PROVIDER=%s，回退 chroma", name)
    from app.services.providers.vectorstore import ChromaVectorStoreProvider

    return ChromaVectorStoreProvider()
