"""MN-1b（阈值区间校验）+ MN-7a（生产密钥强制）配置层回归测试。"""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_intent_threshold_out_of_range_raises():
    """MN-1b：INTENT_THRESHOLD 必须在 (0, 1]，越界启动即失败。"""
    with pytest.raises(ValidationError):
        Settings(INTENT_THRESHOLD=2.0)
    with pytest.raises(ValidationError):
        Settings(INTENT_THRESHOLD=0.0)


def test_rag_top_k_positive():
    with pytest.raises(ValidationError):
        Settings(RAG_TOP_K=0)


def test_llm_temperature_range():
    with pytest.raises(ValidationError):
        Settings(LLM_TEMPERATURE=5.0)


def test_other_positive_params():
    with pytest.raises(ValidationError):
        Settings(RATE_LIMIT_HEAVY_MAX_REQUESTS=0)
    with pytest.raises(ValidationError):
        Settings(EMBEDDING_DIMENSION=0)


def test_valid_config_ok():
    s = Settings(INTENT_THRESHOLD=0.6, RAG_TOP_K=5, LLM_TEMPERATURE=0.7)
    assert s.INTENT_THRESHOLD == 0.6
    assert s.RAG_TOP_K == 5


def test_prod_requires_keys():
    """MN-7a：生产环境(DEBUG=False)缺失 LLM/EMBEDDING 密钥或 SECRET_KEY 占位即启动失败。"""
    with pytest.raises(ValidationError):
        Settings(
            DEBUG=False,
            LLM_API_KEY="",
            EMBEDDING_API_KEY="",
            SECRET_KEY="ecommerce-cs-secret-key-change-in-production",
        )


def test_prod_with_real_keys_ok():
    s = Settings(
        DEBUG=False,
        LLM_API_KEY="sk-x",
        EMBEDDING_API_KEY="sk-y",
        SECRET_KEY="real-random-secret-key-1234567890abcdef",
    )
    assert s.DEBUG is False


def test_dev_placeholder_secret_allowed():
    """开发环境(DEBUG=True)允许占位密钥（由 B2 运行时随机化），不强制。"""
    s = Settings(DEBUG=True, SECRET_KEY="ecommerce-cs-secret-key-change-in-production")
    assert s.DEBUG is True
