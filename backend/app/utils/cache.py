"""缓存工具 — Redis 封装（ 修复）

缓存统一走 Redis（水平扩展友好），无 Redis 时 fallback 到「有界 + TTL」的内存缓存，
避免原实现中 _cache 无上限增长导致的内存泄漏（/）。
"""
import json
import time
import logging
import threading
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
        # ：_redis 三态——
        # None = 尚未探测
        # client = 已连接（redis.asyncio client）
        # dict = 退避中 {"next_retry": float, "failures": int}
        # （兼容测试中将 _redis 置为 False 直接走内存后端的用法）
        self._redis = None
        self._memory = _MemoryBackend()
        self._hits = 0
        self._misses = 0
        self._stats_lock = threading.Lock()
        self._backoff_base = 2.0       # 退避基数（秒），指数增长
        self._max_backoff = 30.0       # 退避上限（秒）

    async def _get_redis(self):
        """懒加载 Redis 连接，带「退避重试」而非永久降级。

        - None → 首次探测
        - dict → 处于退避窗口内，直接降级内存（fail-open，不阻断请求）
        - client→ 已连接
        - False → 测试/强制内存模式（兼容 conftest 置 _redis=False 的用法）
        任何失败都 fail-open（返回 None → 走内存），并 LOG 失败；达到退避时间后
        才会再次尝试重连，避免 Redis 抖动时高频重试打满日志/连接。
        """
        if self._redis is None:
            return await self._connect_redis()
        if isinstance(self._redis, dict):
            if time.time() < self._redis["next_retry"]:
                return None
            return await self._connect_redis()
        return self._redis

    async def _connect_redis(self):
        """尝试连接 Redis；失败则记录退避窗口并返回 None（fail-open）。"""
        try:
            import redis.asyncio as redis
            from app.core.config import settings
            client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await client.ping()
            self._redis = client
            logger.info("Redis 已连接")
            return client
        except Exception as e:
            failures = (self._redis["failures"] + 1) if isinstance(self._redis, dict) else 1
            delay = min(self._backoff_base ** failures, self._max_backoff)
            self._redis = {"next_retry": time.time() + delay, "failures": failures}
            logger.warning("Redis 连接失败（第 %d 次，%.1fs 后退避重试）: %s", failures, delay, e)
            return None

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存；记录命中/未命中（供 /stats 与监控使用）。"""
        r = await self._get_redis()
        if r:
            try:
                value = await r.get(key)
                if value is not None:
                    self._record_hit()
                    return json.loads(value)
            except Exception:
                # Redis 读取异常：记为未命中并回退内存（fail-open）
                pass
        v = self._memory.get(key)
        if v is not None:
            self._record_hit()
        else:
            self._record_miss()
        return v

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

    def _record_hit(self) -> None:
        with self._stats_lock:
            self._hits += 1

    def _record_miss(self) -> None:
        with self._stats_lock:
            self._misses += 1

    def stats(self) -> Dict[str, Any]:
        """返回缓存命中统计（hits / misses / hit_rate）。"""
        with self._stats_lock:
            hits, misses = self._hits, self._misses
        total = hits + misses
        return {
            "hits": hits,
            "misses": misses,
            "hit_rate": (hits / total) if total else 0.0,
        }


# 全局实例
cache = Cache()
