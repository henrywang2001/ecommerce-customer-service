"""TC-2: 鉴权安全原语 — 锁死 JWT 安全语义（P0 安全红线）

覆盖：编解码往返、过期→None、错误密钥→None、sub 非数字→None、缺令牌且 REQUIRE_AUTH→401。
防止「可伪造令牌 / 密钥误配 / 类型崩溃」三类高危回归。
"""
import pytest
from datetime import timedelta

from app.core import security
from app.core.config import settings


@pytest.fixture
def fixed_secret(monkeypatch):
    """固定 SECRET_KEY，避免运行时随机化导致旧令牌失效、测试不稳定。"""
    monkeypatch.setattr(
        settings, "SECRET_KEY", "test-secret-key-for-unit-tests-1234567890"
    )


class _FakeRequest:
    """最小 Request-like 对象，仅提供 request.state.user。"""

    def __init__(self, user=None):
        class _State:
            pass

        self.state = _State()
        self.state.user = user


def test_token_roundtrip(fixed_secret):
    token = security.create_access_token({"sub": "1", "user_id": 1})
    payload = security.decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "1"


def test_expired_token_returns_none(fixed_secret):
    token = security.create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-1))
    assert security.decode_access_token(token) is None


def test_wrong_key_returns_none(fixed_secret, monkeypatch):
    token = security.create_access_token({"sub": "1"})
    monkeypatch.setattr(
        settings, "SECRET_KEY", "a-different-secret-key-0987654321"
    )
    assert security.decode_access_token(token) is None


def test_current_user_id_non_numeric_sub_returns_none(fixed_secret, monkeypatch):
    # sub 非数字（如 "abc"）时 current_user_id 必须返回 None，不得抛 TypeError
    monkeypatch.setattr(settings, "REQUIRE_AUTH", False)
    token = security.create_access_token({"sub": "abc"})
    payload = security.decode_access_token(token)
    assert security.current_user_id(_FakeRequest(payload)) is None


def test_get_current_user_raises_without_token_when_required(fixed_secret, monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True)
    with pytest.raises(Exception):
        security.get_current_user(_FakeRequest(None))
