"""AR-3 / MN-2 / MN-3 / MN-4 / PF-4 相关测试：持久化、探针、指标、请求 ID。

依赖 conftest._isolate_external_env 已强制 cache→内存、observe→no-op。
DB 层是否「真读写」由 test_db_layer_persists_and_reads 用临时 SQLite 引擎证明
（非 no-op）；内存兜底路径由 test_memory_fallback_* 覆盖。
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.services import user_service
from app.core.database import Base
from app.schemas.user import UserCreateRequest


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ───────────────────────── AR-3：DB 层真实读写（非 no-op） ─────────────────────────
def test_db_layer_persists_and_reads(tmp_path):
    # 用临时文件型 SQLite 替换 user_service 引擎，验证 DB 层真实读写（非内存 no-op）
    db_file = tmp_path / "test_users.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 注册全部模型表（message.py 的 metadata 保留字问题已修复，可正常导入）
    import app.models  # noqa: F401

    async def _create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    user_service._db_runner.run(_create_tables())
    user_service._install_test_db(engine, factory)

    try:
        req = UserCreateRequest(
            username="dbuser", password="Db@12345", email="db@example.com", phone="13900000009"
        )
        user = user_service.create_user(req)
        assert user.id is not None
        assert user.username == "dbuser"
        assert user.user_type == "customer"

        # 经 DB 重新读取（登录 + 按 id 查询）
        again = user_service.authenticate("dbuser", "Db@12345")
        assert again is not None and again.id == user.id
        by_id = user_service.get_by_id(user.id)
        assert by_id is not None and by_id.username == "dbuser"

        # 密码应为哈希（非明文）
        async def _pw():
            async with factory() as s:
                from app.models.user import User as U
                res = await s.execute(select(U).where(U.id == user.id))
                return res.scalar_one().password_hash

        ph = user_service._db_runner.run(_pw())
        assert ph != "Db@12345"
        assert ph.startswith("$pbkdf2")

        # 重复用户名 / 邮箱冲突
        with pytest.raises(ValueError):
            user_service.create_user(UserCreateRequest(username="dbuser", password="Db@12345"))
        with pytest.raises(ValueError):
            user_service.create_user(
                UserCreateRequest(username="dbuser2", password="Db@12345", email="db@example.com")
            )
    finally:
        # 恢复默认 MySQL 引擎，避免污染其它测试
        user_service._db_runner.shutdown_engine()
        user_service._db_initialized = False
        user_service._seeded_db = False
        user_service._mark_db_unreachable(False)
        try:
            user_service._db_runner.run(engine.dispose())
        except Exception:
            pass
        if db_file.exists():
            try:
                os.unlink(db_file)
            except OSError:
                pass


# ───────────────────────── AR-3：内存兜底路径（DB 不可达时不阻断请求） ─────────────────────────
def test_memory_fallback_register_and_login(monkeypatch):
    # 强制走内存兜底，验证 DB 不可达时功能仍可用
    monkeypatch.setattr(user_service, "_db_is_enabled", lambda: False)

    user = user_service.create_user(
        UserCreateRequest(username="memuser", password="Mem@123", email="mem@example.com")
    )
    assert user.username == "memuser"

    auth = user_service.authenticate("memuser", "Mem@123")
    assert auth is not None and auth.username == "memuser"
    assert user_service.authenticate("memuser", "wrongpass") is None

    with pytest.raises(ValueError):
        user_service.create_user(UserCreateRequest(username="memuser", password="Mem@123"))


# ───────────────────────── MN-2：存活 / 就绪探针 ─────────────────────────
def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_readyz_structure(client):
    r = client.get("/readyz")
    # 本环境 Redis 未运行 / 未配置 Key -> 通常 503；但结构与字段必须正确
    assert r.status_code in (200, 503)
    data = r.json()
    assert data["status"] in ("ready", "not_ready")
    assert "dependencies" in data
    for key in ("redis", "chroma", "llm_api_key", "embedding_api_key"):
        assert key in data["dependencies"]


# ───────────────────────── MN-3：指标 / 状态 ─────────────────────────
def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_stats_endpoint(client):
    r = client.get("/stats")
    assert r.status_code == 200
    data = r.json()
    assert "request_count" in data
    assert "cache" in data
    assert "hit_rate" in data["cache"]


# ───────────────────────── MN-4：请求 ID ─────────────────────────
def test_request_id_header_present(client):
    r = client.get("/healthz")
    assert "X-Request-ID" in r.headers
    assert len(r.headers["X-Request-ID"]) > 0


def test_request_id_honors_header(client):
    r = client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"
