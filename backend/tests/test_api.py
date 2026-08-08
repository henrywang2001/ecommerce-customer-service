"""HTTP 层冒烟测试：健康检查与根路由（REQUIRE_AUTH 默认关闭时放行）。"""
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


def test_root_no_auth_by_default():
    """H2：REQUIRE_AUTH 默认 False，根路径无需令牌即可访问。"""
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "version" in r.json()
