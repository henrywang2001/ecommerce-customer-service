"""TC-1: HTTP 路由层 + 鉴权/限流中间件（P0 安全红线）

覆盖：
- REQUIRE_AUTH=True 且无令牌 → 401
- 合法 JWT → 通过鉴权（非 401）
- DEBUG=False 时 /docs → 401（文档不泄露）
- 限流触发 → 429

依赖 conftest._isolate_external_env 已强制 cache→内存、observe→no-op，
故本测试不依赖本机 Redis / Langfuse。
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import security
from app.core.config import settings
from app.utils.rate_limiter import rate_limiter


@pytest.fixture
def fixed_secret(monkeypatch):
    monkeypatch.setattr(
        settings, "SECRET_KEY", "test-secret-key-for-unit-tests-1234567890"
    )


@pytest.fixture
def client():
    return TestClient(app)


def test_no_token_returns_401(client, monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True)
    resp = client.get("/api/v1/chat/sessions")
    assert resp.status_code == 401


def test_valid_token_passes_auth(client, monkeypatch, fixed_secret):
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True)
    token = security.create_access_token({"sub": "1"})
    resp = client.get(
        "/api/v1/chat/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 中间件接受合法令牌即不应返回 401（端点内部逻辑由其他测试覆盖）
    assert resp.status_code != 401


def test_docs_blocked_when_debug_false(client, monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "REQUIRE_AUTH", False)
    resp = client.get("/docs")
    assert resp.status_code == 401


def test_ratelimit_returns_429(client, monkeypatch):
    # 关闭鉴权避免 401 干扰；强制限流器拒绝以验证 429 分支
    monkeypatch.setattr(settings, "REQUIRE_AUTH", False)

    async def _deny(*args, **kwargs):
        return False

    monkeypatch.setattr(rate_limiter, "is_allowed", _deny)
    resp = client.get("/api/v1/chat/sessions")
    assert resp.status_code == 429
