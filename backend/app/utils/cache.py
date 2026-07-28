"""缓存工具 — Redis 封装"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 简化的内存缓存（无 Redis 时 fallback）
_cache: dict = {}


class Cache:
    """缓存工具类 — 优先 Redis，无 Redis 时使用内存"""

    def __init__(self):
        self._redis = None

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
        return _cache.get(key)

    async def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存"""
        r = await self._get_redis()
        if r:
            try:
                await r.set(key, json.dumps(value, default=str), ex=expire)
                return True
            except Exception:
                pass
        _cache[key] = value
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
        _cache.pop(key, None)
        return True


# 全局实例
cache = Cache()
