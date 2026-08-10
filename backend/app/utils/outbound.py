"""上游调用弹性层（P4）：并发信号量 + 指数退避重试 + 轻量熔断。

- Semaphore：限制对第三方 LLM/Embedding 的并发，避免突发流量打满对方配额/速率限制。
- tenacity 重试：仅对 429 / 5xx / 传输错误重试（4xx 如 401/400 不重试）。
- 熔断器：连续失败达到阈值后短暂熔断，期间快速失败，给上游恢复窗口。
"""
from typing import Optional
import asyncio
import time
import logging

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


# 并发配额（P4）
llm_semaphore = asyncio.Semaphore(settings.UPSTREAM_LLM_MAX_CONCURRENCY)
embedding_semaphore = asyncio.Semaphore(settings.UPSTREAM_EMBEDDING_MAX_CONCURRENCY)


class CircuitBreakerOpen(Exception):
    """熔断器开启，快速失败。"""


class CircuitBreaker:
    """极简熔断器：连续失败达阈值后熔断 cooldown 秒，期间直接抛 CircuitBreakerOpen。"""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    async def call(self, coro_fn):
        async with self._lock:
            if self._opened_at is not None:
                if time.time() - self._opened_at < self.cooldown_seconds:
                    raise CircuitBreakerOpen("circuit breaker open")
                self._opened_at = None
                self._failures = 0
        try:
            result = await coro_fn()
            async with self._lock:
                self._failures = 0
                self._opened_at = None
            return result
        except Exception:
            async with self._lock:
                self._failures += 1
                if self._failures >= self.failure_threshold:
                    self._opened_at = time.time()
            raise


llm_breaker = CircuitBreaker(
    failure_threshold=settings.UPSTREAM_LLM_CB_FAILURES,
    cooldown_seconds=settings.UPSTREAM_LLM_CB_COOLDOWN,
)
embedding_breaker = CircuitBreaker(
    failure_threshold=settings.UPSTREAM_EMBEDDING_CB_FAILURES,
    cooldown_seconds=settings.UPSTREAM_EMBEDDING_CB_COOLDOWN,
)


def _is_retryable(exc: BaseException) -> bool:
    """仅对网络错误与 429/5xx 重试；401/400 等 4xx 不重试。"""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code if exc.response is not None else 0
        return code == 429 or code >= 500
    return False


@retry(
    stop=stop_after_attempt(settings.UPSTREAM_MAX_RETRIES + 1),
    wait=wait_exponential(
        multiplier=settings.UPSTREAM_RETRY_BASE_DELAY,
        max=settings.UPSTREAM_RETRY_MAX_DELAY,
    ),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
async def _raw_post(client: httpx.AsyncClient, url: str, **kwargs):
    return await client.post(url, **kwargs)


async def post_with_resilience(client, url, semaphore, breaker, **kwargs):
    """带 并发信号量 + 熔断 + 指数退避重试 的上游 POST（P4）。"""
    async with semaphore:
        return await breaker.call(lambda: _raw_post(client, url, **kwargs))


async def stream_post(client, url, semaphore, breaker, **kwargs):
    """带 并发信号量 + 熔断 的上游流式 POST（P6）；熔断仅包裹连接建立阶段。

    注意：长连接流不做 tenacity 整体重试（已半发送无法重放），连接建立失败会
    抛异常由调用方捕获并优雅降级。
    """
    async with semaphore:
        cm = await breaker.call(lambda: client.stream("POST", url, **kwargs))
        async with cm as response:
            if response.status_code >= 400:
                await response.aread()
                raise httpx.HTTPStatusError(
                    f"upstream status {response.status_code}",
                    request=response.request,
                    response=response,
                )
            async for line in response.aiter_lines():
                yield line
