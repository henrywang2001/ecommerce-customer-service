""" 意图识别服务测试。

验证意图识别核心链路（ 声明式配置落地后）：
- 关键词匹配：`退款` → refund_request（confidence≈0.7）
- preferred_intent 直通车：直接采用、不调用 LLM
- recognize(None) / recognize("") → fallback 兜底
- `退款多久到账 ORDER...` 抽取 order_no 实体

测试手法（对应 要求）：通过构造函数注入 fake LLM（mock 其 ``generate_json``）
使测试离线、不联网；**绝不整体替换 ``recognize``**，始终调用真实 ``IntentService.recognize``。
"""
import asyncio

import pytest

from app.services.intent_service import IntentService
from app.schemas.intent import IntentResult


class FakeLLM:
    """fake LLM 服务，对齐 LLMService.generate_json / .model 接口。

    - 不真实联网；
    - 记录 ``generate_json`` 调用次数，用于断言「preferred_intent 直通车不触发 LLM」。
    """

    def __init__(self, json_payload=None):
        self.model = "fake-model"
        self.json_calls = 0
        self.json_payload = json_payload or {
            "intent_code": "refund_request",
            "confidence": 0.8,
            "reason": "fake-llm",
        }

    async def generate_json(self, prompt, temperature=0.1, max_tokens=None):
        self.json_calls += 1
        return self.json_payload


def test_keyword_refund_maps_to_refund_request():
    """关键词 `退款` 应命中 refund_request，置信度≈0.7，且跳过 LLM。"""
    fake = FakeLLM()
    svc = IntentService(llm_service=fake)

    result = asyncio.run(svc.recognize("退款"))

    assert isinstance(result, IntentResult)
    assert result.intent_code == "refund_request"
    # 关键词命中置信度固定 0.7（>= INTENT_THRESHOLD=0.6），故 LLM 被跳过
    assert result.confidence == pytest.approx(0.7)
    assert result.handler_type == "tool"
    assert fake.json_calls == 0


def test_preferred_intent_skips_llm():
    """preferred_intent 直通车：直接采用预识别意图，全程不调用 LLM。"""
    fake = FakeLLM()
    svc = IntentService(llm_service=fake)

    result = asyncio.run(
        svc.recognize("这段文本不含任何关键词因此本应走LLM", preferred_intent="refund_request")
    )

    assert result.intent_code == "refund_request"
    assert result.confidence == pytest.approx(0.95)
    assert result.handler_type == "tool"
    # 直通车在 LLM 之前短路返回，generate_json 不应被调用
    assert fake.json_calls == 0


def test_recognize_none_returns_fallback():
    """recognize(None) 应归一为空串并兜底返回 fallback，且不调用 LLM。"""
    fake = FakeLLM()
    svc = IntentService(llm_service=fake)

    result = asyncio.run(svc.recognize(None))

    assert result.intent_code == "fallback"
    assert result.confidence == 0.0
    assert result.handler_type == "llm"
    assert fake.json_calls == 0


def test_recognize_empty_returns_fallback():
    """recognize("") 应兜底返回 fallback，且不调用 LLM。"""
    fake = FakeLLM()
    svc = IntentService(llm_service=fake)

    result = asyncio.run(svc.recognize(""))

    assert result.intent_code == "fallback"
    assert result.confidence == 0.0
    assert result.handler_type == "llm"
    assert fake.json_calls == 0


def test_refund_query_extracts_order_no():
    """`退款多久到账 ORDER...` 应识别为 refund_request 并抽取 order_no 实体。

    底层 llm_service.generate_json 被 mock（fake），但 recognize 真实方法完整执行，
    未被整体替换。
    """
    fake = FakeLLM(json_payload={
        "intent_code": "refund_request",
        "confidence": 0.8,
        "reason": "退款相关",
    })
    svc = IntentService(llm_service=fake)

    text = "退款多久到账 ORDER20240812ABC12345"
    result = asyncio.run(svc.recognize(text))

    assert result.intent_code == "refund_request"
    order_entities = [e for e in result.entities if e.type == "order_no"]
    assert order_entities, "应当抽取到 order_no 实体"
    assert order_entities[0].value == "ORDER20240812ABC12345"


def test_llm_generate_json_mock_drives_result():
    """验证注入的 fake generate_json 确实被真实 recognize 消费（mock 生效）。

    文本无高置信关键词 → 触发 LLM 路径 → 结果应由 fake 的 json_payload 决定。
    """
    fake = FakeLLM(json_payload={
        "intent_code": "order_query",
        "confidence": 0.85,
        "reason": "咨询订单",
    })
    svc = IntentService(llm_service=fake)

    # “帮我看看” 不含任何意图关键词，必然走到 LLM
    result = asyncio.run(svc.recognize("帮我看看"))

    assert fake.json_calls == 1
    assert result.intent_code == "order_query"
    assert result.confidence == pytest.approx(0.85)
