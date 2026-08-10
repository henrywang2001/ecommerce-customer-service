"""后端回归测试公共 fixture。

目标：在不依赖外部 Key（LLM/Embedding/Langfuse）的前提下验证核心链路。
- patch_embedding：embedding 返回零向量（命中既有「零向量跳过 Chroma」逻辑，走内置关键词）。
- patch_llm：LLM 返回测试桩文本，避免真实联网超时。
- patch_intent_*：用确定性意图替换 intent_service.recognize，使路由可预测。
"""
import asyncio

import pytest

from app.core.config import settings
from app.services import embedding_service
from app.services import intent_service
from app.services import llm_service
from app.schemas.intent import IntentResult


def _make_intent(code: str, handler_type: str, confidence: float = 0.9) -> IntentResult:
    return IntentResult(
        intent_code=code,
        intent_name=code,
        confidence=confidence,
        entities=[],
        handler_type=handler_type,
        priority=5,
    )


@pytest.fixture
def patch_embedding(monkeypatch):
    """避免测试时真实调用 DashScope（无 Key 会网络超时）。返回零向量。"""
    dim = settings.EMBEDDING_DIMENSION

    async def fake_encode_single(text):
        return [0.0] * dim

    monkeypatch.setattr(embedding_service.embedding_service, "encode_single", fake_encode_single)
    yield


@pytest.fixture
def patch_llm(monkeypatch):
    """LLM 返回测试桩，避免真实联网。"""

    async def fake_chat(messages, temperature=None):
        return "（测试桩）AI 回复"

    async def fake_generate(prompt, temperature=None, max_tokens=None):
        return "（测试桩）生成文本"

    monkeypatch.setattr(llm_service.llm_service, "chat", fake_chat)
    monkeypatch.setattr(llm_service.llm_service, "generate", fake_generate)
    yield


def _patch_intent(monkeypatch, code: str, handler_type: str):
    async def fake(text, user_id=None, preferred_intent=None):
        return _make_intent(code, handler_type)

    monkeypatch.setattr(intent_service.intent_service, "recognize", fake)


@pytest.fixture
def patch_intent_order(monkeypatch):
    _patch_intent(monkeypatch, "order_query", "tool")
    yield


@pytest.fixture
def patch_intent_refund(monkeypatch):
    _patch_intent(monkeypatch, "refund_request", "tool")
    yield


@pytest.fixture
def patch_intent_product(monkeypatch):
    _patch_intent(monkeypatch, "product_inquiry", "tool")
    yield


@pytest.fixture
def patch_intent_transfer(monkeypatch):
    _patch_intent(monkeypatch, "human_agent", "transfer")
    yield


@pytest.fixture
def patch_intent_ticket(monkeypatch):
    _patch_intent(monkeypatch, "ticket_create", "tool")
    yield


@pytest.fixture
def patch_intent_llm(monkeypatch):
    _patch_intent(monkeypatch, "fallback", "llm")
    yield
