"""CQ-6 — 运行期参数收口验证：会话/连接池/关键词权重集中到 config，且 chat_service 不再硬编码。"""
from app.core.config import settings
import app.services.chat_service as chat_service


def test_cq6_session_config_defaults():
    assert settings.SESSION_MAX_COUNT == 200
    assert settings.SESSION_TTL == 86400
    assert settings.HISTORY_TURNS == 6


def test_cq6_db_pool_config_defaults():
    assert settings.DB_POOL_SIZE == 20
    assert settings.DB_MAX_OVERFLOW == 10


def test_cq6_keyword_weights_defaults():
    assert settings.INTENT_KEYWORD_WEIGHTS == {
        "explicit": 0.4,
        "token": 0.8,
        "category": 0.5,
    }


def test_chat_service_no_hardcoded_session_constants():
    # 会话容量/TTL/历史轮数已收口至 config，模块级硬编码常量应移除
    assert not hasattr(chat_service, "MAX_SESSIONS")
    assert not hasattr(chat_service, "SESSION_TTL_SECONDS")
