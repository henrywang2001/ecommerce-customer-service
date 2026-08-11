"""限流器

修复要点：
1. 内存泄漏：原实现用 defaultdict(list)，键（client_ip）永不删除，空列表残留导致
   内存随不同 IP 数无限增长。现改用普通 dict + 窗口清空即删除键，内存有界。
2. 多进程/水平扩展：新增 RedisRateLimiter（有序集合滑动窗口），多实例共享同一窗口，
   限流在多进程下真正生效。create_rate_limiter 在启动时探测 Redis 连通性，
   可达则用 Redis 后端，否则回退内存模式（单进程）。
"""
import time
import asyncio
import logging
import threading
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MAX_REQUESTS: int = 60
DEFAULT_WINDOW_SECONDS: int = 60


class InMemoryRateLimiter:
    """单进程滑动窗口限流器（修复内存泄漏）"""

    def __init__(self, max_requests: int = DEFAULT_MAX_REQUESTS, window_seconds: int = DEFAULT_WINDOW_SECONDS, max_keys: int = 10000):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._windows: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def _evict_overflow(self) -> None:
        """键数量超过上限时，淘汰最早活动窗口的键，保证内存有界。"""
        while len(self._windows) > self.max_keys:
            oldest_key = min(
                self._windows.keys(),
                key=lambda k: (self._windows[k][0] if self._windows[k] else float("inf"), k),
            )
            self._windows.pop(oldest_key, None)

    async def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            window = self._windows.get(key)
            if window is None:
                window = []
                self._windows[key] = window
            # 清除过期记录
            while window and window[0] < cutoff:
                window.pop(0)
            # 窗口已空：删除键（修复内存泄漏），并放行
            if not window:
                self._windows.pop(key, None)
                window = []
                self._windows[key] = window
            if len(window) >= self.max_requests:
                return False
            window.append(now)
            self._evict_overflow()
            return True


class RedisRateLimiter:
    """多进程滑动窗口限流器（基于 Redis 有序集合，支持水平扩展）"""

    def __init__(self, redis_url: str, max_requests: int = DEFAULT_MAX_REQUESTS, window_seconds: int = DEFAULT_WINDOW_SECONDS):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._url = redis_url
        self._pool = None

    def _get_client(self):
        import redis.asyncio as redis
        if self._pool is None:
            self._pool = redis.from_url(self._url, decode_responses=True)
        return self._pool

    async def is_allowed(self, key: str) -> bool:
        try:
            import uuid as _uuid
            r = self._get_client()
            now = time.time()
            cutoff = now - self.window_seconds
            # 清理窗口外的旧记录
            await r.zremrangebyscore(key, 0, cutoff)
            count = await r.zcard(key)
            if count >= self.max_requests:
                return False
            # 以时间戳为 score、唯一 member 写入本次请求（避免同毫秒 member 冲突）
            await r.zadd(key, {f"{now}:{_uuid.uuid4().hex}": now})
            await r.expire(key, self.window_seconds)
            return True
        except Exception as e:
            # Redis 异常时降级为放行，避免雪崩；生产环境应配合监控告警
            logger.warning(f"Redis 限流失败，降级放行: {e}")
            return True


def create_rate_limiter(max_requests: int = None, window_seconds: int = None, backend: str = None):
    """根据 Redis 可用性选择后端：可达用 Redis（多进程安全），否则内存模式。

    backend 可强制指定后端：
      - "memory"：跳过 Redis 探测，直接使用内存模式（测试 / 单进程明确场景）；
      - "redis" ：强制探测 Redis（探测失败仍回退内存）；
      - None ：自动探测（默认行为，保持向后兼容）。
    max_requests / window_seconds 可覆盖默认（用于昂贵接口更严格的限流，）。
    """
    mr = max_requests if max_requests is not None else DEFAULT_MAX_REQUESTS
    ws = window_seconds if window_seconds is not None else DEFAULT_WINDOW_SECONDS
    # 强制内存模式：不探测 Redis
    if backend == "memory":
        logger.info("限流器强制使用内存后端（配置/测试指定）")
        return InMemoryRateLimiter(max_requests=mr, window_seconds=ws)
    # 自动探测或强制 Redis：探测成功用 Redis，失败回退内存
    redis_ok = False
    if backend != "memory":
        try:
            from app.core.config import settings
            url = settings.REDIS_URL
            import redis
            client = redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
            client.ping()
            redis_ok = True
        except Exception as e:
            logger.warning(f"Redis 不可用，限流器回退内存模式（单进程）: {e}")
    if redis_ok:
        logger.info("限流器使用 Redis 后端（支持多进程/水平扩展）")
        return RedisRateLimiter(url, max_requests=mr, window_seconds=ws)
    return InMemoryRateLimiter(max_requests=mr, window_seconds=ws)


# 全局实例（启动时探测后端）
rate_limiter = create_rate_limiter()
# 昂贵接口专用限流：/send 等 LLM 重路径单分钟上限更低
from app.core.config import settings as _settings
heavy_rate_limiter = create_rate_limiter(max_requests=_settings.RATE_LIMIT_HEAVY_MAX_REQUESTS, window_seconds=60)
