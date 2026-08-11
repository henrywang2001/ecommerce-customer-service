"""对话服务回归测试：ReAct 工具接线 + 会话生命周期。

用确定性意图替换意图识别，并 mock embedding/llm，避免依赖外部 Key。
"""
import asyncio

from app.services.chat_service import chat_service


def test_order_query_returns_real_order(patch_embedding, patch_intent_order):
    """：order_query 委派 QueryOrderTool，返回真实订单（含戴森，非 iPhone）。

    ：query_order 需要登录（requires_auth），须携带已认证 user_id。
    """
    res = asyncio.run(chat_service.send_message("s_order", "查订单 ORDER20260401001", 1))
    assert res["intent"]["intent_code"] == "order_query"
    assert "戴森" in res["response"]
    assert "iPhone" not in res["response"]


def test_refund_tool_no_fake_order(patch_embedding, patch_intent_refund):
    """ + 前轮修复：refund_request 走 RefundTool，不再硬编码 iPhone。"""
    res = asyncio.run(chat_service.send_message("s_refund", "我要申请退款", None))
    assert res["intent"]["intent_code"] == "refund_request"
    assert "iPhone" not in res["response"]


def test_product_inquiry_wires_query_product(patch_embedding, patch_intent_product):
    """：product_inquiry 改为 tool handler，委派 QueryProductTool。"""
    res = asyncio.run(chat_service.send_message("s_product", "我想买戴森吹风机", None))
    assert res["intent"]["intent_code"] == "product_inquiry"
    assert len(res["response"]) > 0


def test_transfer_wires_tool(patch_embedding, patch_intent_transfer):
    """：transfer 分支委派 TransferHumanTool，need_transfer 保持。"""
    res = asyncio.run(chat_service.send_message("s_transfer", "转人工", None))
    assert res["need_transfer"] is True
    assert "人工" in res["response"]


def test_ticket_create_wires_tool(patch_embedding, patch_intent_ticket):
    """：新增 ticket_create 意图，委派 CreateTicketTool。

    ：create_ticket 需要登录（requires_auth），须携带已认证 user_id。
    """
    res = asyncio.run(chat_service.send_message("s_ticket", "我要提交工单反馈问题", 1))
    assert res["intent"]["intent_code"] == "ticket_create"
    assert "工单" in res["response"]


def test_history_and_delete_idempotent(patch_embedding, patch_llm, patch_intent_llm):
    """建会话→发消息→历史→删除；DELETE 删除不存在 id 严格幂等返回 True。"""
    sess = asyncio.run(chat_service.create_session(user_id=None))
    sid = sess["session"]["session_id"]
    asyncio.run(chat_service.send_message(sid, "你好", None))

    hist = asyncio.run(chat_service.get_history(sid))
    assert hist["total"] == 2  # user + assistant

    assert asyncio.run(chat_service.delete_session(sid)) is True
    # ：删除不存在的 id 幂等，但返回 False 表示"该会话此前并不存在"
    assert asyncio.run(chat_service.delete_session("nonexistent_id_x")) is False


def test_send_message_structure(patch_embedding, patch_llm, patch_intent_llm):
    """send_message 返回结构兼容前端契约。"""
    res = asyncio.run(chat_service.send_message("s_struct", "你好", None))
    for key in ("response", "intent", "sentiment", "sentiment_score", "quick_replies", "need_transfer"):
        assert key in res
