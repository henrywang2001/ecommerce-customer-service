"""HTTP 层冒烟测试：健康检查与根路由（"/" 与 "/health" 为永远公开路由）。"""
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


def test_root_is_always_public():
    """：根路径为永远公开路由，无需令牌即可访问（不受 REQUIRE_AUTH 影响）。"""
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "version" in r.json()
