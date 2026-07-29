"""可观测性服务 — Langfuse 追踪封装

提供 LLM 调用、RAG 检索、Agent 工具执行等环节的全链路追踪能力。
基于 Langfuse Python SDK v4，通过 context manager 和手动 span 两种方式埋点。

使用方式:
    from app.services.observe_service import observe

    # Context manager 方式（推荐）
    with observe.span("my-operation", input_data) as span:
        result = do_work()
        span.update(output=result)

    # Generation 追踪
    with observe.generation("llm-call", model="deepseek-v4-flash", input=prompt) as gen:
        response = await llm.generate(prompt)
        gen.update(output=response)
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

from langfuse import Langfuse

from app.core.config import settings

logger = logging.getLogger(__name__)


class ObserveService:
    """Langfuse 可观测服务 — 单例"""

    _client: Optional[Langfuse] = None
    _ready: bool = False

    def __init__(self):
        self._init_client()

    def _init_client(self) -> None:
        """初始化 Langfuse 客户端"""
        if not settings.LANGFUSE_TRACING_ENABLED:
            logger.info("Langfuse 追踪已禁用")
            return

        if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
            logger.warning(
                "Langfuse 未配置 API Key，追踪已跳过。"
                "请在 .env 中设置 LANGFUSE_PUBLIC_KEY 和 LANGFUSE_SECRET_KEY"
            )
            return

        try:
            self._client = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                base_url=settings.LANGFUSE_BASE_URL,
                environment=settings.LANGFUSE_ENVIRONMENT,
                release=settings.LANGFUSE_RELEASE,
                sample_rate=settings.LANGFUSE_SAMPLE_RATE,
                flush_interval=5.0,
            )
            self._ready = True
            logger.info(
                "Langfuse 已连接: %s (env=%s)",
                settings.LANGFUSE_BASE_URL,
                settings.LANGFUSE_ENVIRONMENT,
            )
        except Exception as e:
            logger.error("Langfuse 初始化失败: %s", e)
            self._ready = False

    @property
    def client(self) -> Optional[Langfuse]:
        return self._client

    @property
    def enabled(self) -> bool:
        return self._ready and self._client is not None

    def flush(self) -> None:
        """强制刷新，将缓冲区中的追踪数据发送到 Langfuse 服务端"""
        if self._client:
            try:
                self._client.flush()
            except Exception as e:
                logger.warning("Langfuse flush 失败: %s", e)

    # ── Context Manager API ──────────────────────────────────────

    @contextmanager
    def span(
        self,
        name: str,
        input: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """创建一个 span 类型的观测节点

        用于追踪非 LLM 的业务逻辑片段: 意图识别、情感分析、工具调用等。
        """
        if not self.enabled:
            yield None
            return

        with self._client.start_as_current_observation(
            name=name,
            as_type="span",
            input=input,
            metadata=metadata,
        ) as span_ctx:
            yield span_ctx

    @contextmanager
    def generation(
        self,
        name: str,
        model: str,
        input: Any = None,
        model_parameters: Optional[Dict[str, Any]] = None,
    ):
        """创建一个 generation 类型的观测节点

        用于追踪 LLM 调用 (DeepSeek chat/completions)。

        Args:
            name: 本次调用的逻辑名称
            model: 模型标识 (如 deepseek-v4-flash)
            input: 模型输入 (messages 或 prompt)
            model_parameters: 模型参数 (temperature, max_tokens 等)
        """
        if not self.enabled:
            yield None
            return

        with self._client.start_as_current_observation(
            name=name,
            as_type="generation",
            model=model,
            input=input,
            model_parameters=model_parameters,
        ) as gen_ctx:
            yield gen_ctx

    @contextmanager
    def tool(
        self,
        name: str,
        input: Any = None,
    ):
        """创建一个 tool 类型的观测节点

        用于追踪 Agent 工具调用: 订单查询、退款处理、转人工等。
        """
        if not self.enabled:
            yield None
            return

        with self._client.start_as_current_observation(
            name=name,
            as_type="tool",
            input=input,
        ) as tool_ctx:
            yield tool_ctx

    @contextmanager
    def retriever(
        self,
        name: str,
        input: Any = None,
    ):
        """创建一个 retriever 类型的观测节点

        用于追踪 RAG 检索过程: ChromaDB 向量检索 / 关键词匹配。
        """
        if not self.enabled:
            yield None
            return

        with self._client.start_as_current_observation(
            name=name,
            as_type="retriever",
            input=input,
        ) as ret_ctx:
            yield ret_ctx

    @contextmanager
    def agent(
        self,
        name: str,
        input: Any = None,
    ):
        """创建一个 agent 类型的观测节点

        用于追踪 Agent 决策/执行过程 (CustomerServiceAgent.process)。
        """
        if not self.enabled:
            yield None
            return

        with self._client.start_as_current_observation(
            name=name,
            as_type="agent",
            input=input,
        ) as agent_ctx:
            yield agent_ctx

    @contextmanager
    def embedding(
        self,
        name: str,
        model: str,
        input: Any = None,
    ):
        """创建一个 embedding 类型的观测节点

        用于追踪向量嵌入调用: 千问 text-embedding-v1。
        """
        if not self.enabled:
            yield None
            return

        with self._client.start_as_current_observation(
            name=name,
            as_type="embedding",
            model=model,
            input=input,
        ) as emb_ctx:
            yield emb_ctx

    # ── 手动 API（用于异步场景需要显式控制的场合）───────────────

    def start_span(self, name: str, input: Any = None) -> Any:
        """手动创建 span（需显式调用 .end()）"""
        if not self.enabled:
            return _NoopSpan()
        return self._client.start_observation(
            name=name, as_type="span", input=input
        )

    def start_generation(
        self,
        name: str,
        model: str,
        input: Any = None,
        model_parameters: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """手动创建 generation（需显式调用 .end()）"""
        if not self.enabled:
            return _NoopSpan()
        return self._client.start_observation(
            name=name,
            as_type="generation",
            model=model,
            input=input,
            model_parameters=model_parameters,
        )


class _NoopSpan:
    """空 Span — 当 Langfuse 未启用时返回，所有操作均为 no-op"""

    def update(self, **kwargs: Any) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args: Any) -> None:
        pass


# 全局单例
observe = ObserveService()
