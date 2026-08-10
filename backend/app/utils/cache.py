"""缓存工具 — Redis 封装（P3 修复）

缓存统一走 Redis（水平扩展友好），无 Redis 时 fallback 到「有界 + TTL」的内存缓存，
避免原实现中 _cache 无上限增长导致的内存泄漏（P3/P9）。
"""
import json
import time
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class _MemoryBackend:
    """有界 TTL 内存缓存：maxsize 控制容量上限，TTL 控制条目过期。

    用于 Redis 不可用时的 fallback，保证即使长期运行也不会无限膨胀。
    """

    def __init__(self, maxsize: int = 1000, default_ttl: int = 3600):
        self._maxsize = maxsize
        self._ttl = default_ttl
        self._store: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expire_at)
        self._order: list = []  # FIFO 写入顺序，用于超额淘汰

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if item is None:
            return None
        value, expire_at = item
        if expire_at is not None and time.time() > expire_at:
            self._store.pop(key, None)
            self._safe_remove_order(key)
            return None
        return value

    def set(self, key: str, value: Any, expire: int) -> None:
        ttl = expire or self._ttl
        self._store[key] = (value, time.time() + ttl)
        self._order.append(key)
        while len(self._store) > self._maxsize:
            old = self._order.pop(0)
            self._store.pop(old, None)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._safe_remove_order(key)

    def _safe_remove_order(self, key: str) -> None:
        if key in self._order:
            try:
                self._order.remove(key)
            except ValueError:
                pass


class Cache:
    """缓存工具类 — 优先 Redis，无 Redis 时使用有界内存"""

    def __init__(self):
        self._redis = None
        self._memory = _MemoryBackend()

    async def _get_redis(self):
        """懒加载 Redis 连接"""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                from app.core.config import settings
                self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
                await self._redis.ping()
                logger.info("Redis 已连接")
            except Exception as e:
                logger.warning(f"Redis 连接失败，使用内存缓存: {e}")
                self._redis = False
        return self._redis if self._redis is not False else None

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        r = await self._get_redis()
        if r:
            try:
                value = await r.get(key)
                return json.loads(value) if value else None
            except Exception:
                return None
        return self._memory.get(key)

    async def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存"""
        r = await self._get_redis()
        if r:
            try:
                await r.set(key, json.dumps(value, default=str), ex=expire)
                return True
            except Exception:
                pass
        self._memory.set(key, value, expire)
        return True

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        r = await self._get_redis()
        if r:
            try:
                await r.delete(key)
                return True
            except Exception:
                pass
        self._memory.delete(key)
        return True


# 全局实例
cache = Cache()
