""" — 缓存 / 限流集成测试（@pytest.mark.integration）。

环境说明（重要）：
沙箱无外网，``miniredis`` 无法通过 pip 安装（已尝试，PyPI 不可达）。
改用已内置的 ``fakeredis`` 作为等价的进程内 Redis：它实现 ``redis.asyncio`` 协议，
支持 get/set/ex、zset（zadd/zremrangebyscore/zcard）、expire 与 TTL 语义，
完整覆盖本任务要求的：跨进程一致、TTL 过期、RedisRateLimiter 限流与
连接失败 fail-open 降级（且降级被记录、非静默）。

若后续联网安装 ``miniredis``，可把 ``_make_from_url`` 改为返回连向
``miniredis.Miniredis.host:port`` 的客户端即可，测试契约不变。
"""
import asyncio
import logging

import pytest

import fakeredis
from fakeredis import aioredis as fake_aioredis

from app.utils.cache import Cache
from app.utils.rate_limiter import RedisRateLimiter

pytestmark = pytest.mark.integration


def _make_from_url(server, *, raise_exc=None):
    """返回一个替身 ``redis.asyncio.from_url``：连 fakeredis 共享 server，或主动抛错。"""

    def _from_url(url, **kwargs):
        if raise_exc is not None:
            raise raise_exc
        return fake_aioredis.FakeRedis(
            decode_responses=kwargs.get("decode_responses", True),
            server=server,
        )

    return _from_url


@pytest.fixture
def redis_server():
    # 每个测试独立 server，避免跨测试污染
    return fakeredis.FakeServer()


@pytest.fixture
def patched_redis(monkeypatch, redis_server):
    """把 redis.asyncio.from_url 指向 fakeredis 共享 server。"""
    monkeypatch.setattr("redis.asyncio.from_url", _make_from_url(redis_server))
    yield


@pytest.fixture
async def connected_cache(patched_redis):
    cache = Cache()
    cache._redis = None
    client = await cache._get_redis()
    assert client is not None, "应能连上 in-memory redis"
    yield cache


# ─────────────── 缓存：跨进程一致 + TTL 过期 ───────────────

async def test_set_get_cross_process_consistent(connected_cache, redis_server, monkeypatch):
    # 第二个“进程”的 Cache 实例，指向同一共享 redis server
    cache_b = Cache()
    cache_b._redis = None
    await cache_b._get_redis()

    payload = {"no": "ORDER20260315001", "amount": 9599.0, "status": "shipped"}
    await connected_cache.set("order:1", payload, expire=300)

    v_in_a = await connected_cache.get("order:1")
    v_in_b = await cache_b.get("order:1")
    assert v_in_a == payload
    assert v_in_b == v_in_a  # 跨进程（跨实例）读取同一份数据，一致


async def test_ttl_expiry(connected_cache):
    await connected_cache.set("tk", {"v": 1}, expire=1)
    assert await connected_cache.get("tk") == {"v": 1}

    await asyncio.sleep(1.2)  # 等待 TTL 过期
    assert await connected_cache.get("tk") is None


# ─────────────── RedisRateLimiter：≤max 放行 / >max 拒绝 ───────────────

async def test_rate_limiter_within_limit_passes(redis_server, monkeypatch):
    monkeypatch.setattr("redis.asyncio.from_url", _make_from_url(redis_server))
    rl = RedisRateLimiter(redis_url="redis://test/0", max_requests=3, window_seconds=60)
    allowed = [await rl.is_allowed("k1") for _ in range(3)]
    assert allowed == [True, True, True]


async def test_rate_limiter_over_limit_rejected(redis_server, monkeypatch):
    monkeypatch.setattr("redis.asyncio.from_url", _make_from_url(redis_server))
    rl = RedisRateLimiter(redis_url="redis://test/0", max_requests=3, window_seconds=60)
    for _ in range(3):
        assert await rl.is_allowed("k2") is True
    # 第 4 次超过上限 → 拒绝
    assert await rl.is_allowed("k2") is False


# ─────────────── 连接失败 fail-open 降级（必须被记录，非静默）───────────────

async def test_fail_open_logged_on_connection_error(redis_server, monkeypatch, caplog):
    import redis as redis_sync

    monkeypatch.setattr(
        "redis.asyncio.from_url",
        _make_from_url(redis_server, raise_exc=redis_sync.exceptions.ConnectionError("refused")),
    )
    cache = Cache()
    cache._redis = None

    with caplog.at_level(logging.WARNING, logger="app.utils.cache"):
        client = await cache._get_redis()

    # 连接失败 → fail-open 降级：返回 None（后续走内存后端），不抛异常
    assert client is None
    # 降级被明确记录（不是静默吞掉）
    assert "Redis 连接失败" in caplog.text

    # fail-open 后缓存仍可用（内存后端兜底）
    assert await cache.set("fk", "v", expire=10) is True
    assert await cache.get("fk") == "v"
