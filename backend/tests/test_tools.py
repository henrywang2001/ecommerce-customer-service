""" — 工具层测试（ 注册表 + 各工具行为）。

覆盖：
- 注册表收录全部 6 个工具、requires_auth 元数据正确；
- 需要登录的工具在 user_id=None 时被拦截（ 鉴权）；
- 各工具 execute 返回结构正确、退款分支正确、transfer_human 的 “or” 逻辑稳固；
- 异常兜底：工具内部抛错时返回 {"success": False, ...} 而非崩溃；
- 注册表驱动的意图路由 dispatch_intent（intent_code → 注册表 → execute）。

全程离线：query_order/query_product/refund/transfer_human/create_ticket 读本地 Mock 数据；
search_knowledge 通过 monkeypatch rag_service.search 注入桩，不触网。
"""
import pytest

from app.agents.customer_agent import CustomerServiceAgent
from app.agents.tools import registry as tool_registry
from app.agents.tools.search_knowledge import SearchKnowledgeTool
from app.agents.tools.search_knowledge import rag_service as sk_rag
from app.agents.tools.query_order import QueryOrderTool
from app.agents.tools.query_product import QueryProductTool
from app.agents.tools.refund_tool import RefundTool
from app.agents.tools.transfer_human import TransferHumanTool
from app.agents.tools.create_ticket import CreateTicketTool
from app.agents.tools import create_ticket as ct_module


EXPECTED_TOOLS = {
    "search_knowledge", "query_order", "query_product",
    "refund", "transfer_human", "create_ticket",
}


@pytest.fixture
def agent():
    return CustomerServiceAgent(session_id="tc5", user_id=123)


@pytest.fixture
def anon_agent():
    return CustomerServiceAgent(session_id="tc5", user_id=None)


# ───────────────────────── 注册表 ─────────────────────────

def test_registry_contains_all_six_tools():
    assert EXPECTED_TOOLS == set(tool_registry.get_registered_tool_names())


def test_tool_requires_auth_metadata():
    assert QueryOrderTool().requires_auth is True
    assert RefundTool().requires_auth is True
    assert CreateTicketTool().requires_auth is True
    assert SearchKnowledgeTool().requires_auth is False
    assert QueryProductTool().requires_auth is False
    assert TransferHumanTool().requires_auth is False


# ──────────────────── requires_auth 拦截────────────────────

async def test_requires_auth_blocks_when_user_id_none(anon_agent):
    # 即使 params 带了 user_id，agent.user_id 为 None 也必须拦截
    res = await anon_agent.execute_tool(
        "query_order", {"user_message": "查订单 ORDER20260315001", "user_id": 123}
    )
    assert res["success"] is False
    assert res.get("requires_auth") is True


async def test_requires_auth_allows_when_authed(agent):
    res = await agent.execute_tool(
        "query_order", {"user_message": "查订单 ORDER20260315001", "user_id": 123}
    )
    assert res["success"] is True
    assert res["order"]["order_no"] == "ORDER20260315001"


async def test_create_ticket_requires_auth_blocks_anon(anon_agent):
    res = await anon_agent.execute_tool(
        "create_ticket",
        {"session_id": "s", "user_id": 123, "type": "consult", "title": "x", "content": "c"},
    )
    assert res["success"] is False
    assert res.get("requires_auth") is True


async def test_no_auth_tools_not_blocked_when_anon(anon_agent):
    # search_knowledge / query_product / transfer_human 不需要登录，匿名可用
    r1 = await anon_agent.execute_tool("transfer_human", {"session_id": "s", "reason": "用户主动请求"})
    assert r1["success"] is True
    r2 = await anon_agent.execute_tool("query_product", {"user_message": "iPhone手机"})
    assert r2["success"] is True


# ───────────────────── 各工具 execute ─────────────────────

async def test_query_order_execute_and_not_found():
    tool = QueryOrderTool()
    res = await tool.execute({"user_message": "查订单 ORDER20260315001", "user_id": 123})
    assert res["success"] is True
    assert res["order"]["order_no"] == "ORDER20260315001"

    res2 = await tool.execute({"user_message": "查订单 ORDERNOPE0001", "user_id": 123})
    assert res2["success"] is False
    assert "未找到订单号" in res2["response"]


async def test_query_product_execute():
    tool = QueryProductTool()
    res = await tool.execute({"user_message": "我想买iPhone手机", "user_id": 123})
    assert res["success"] is True
    assert len(res["products"]) > 0

    # 无关键词 → 成功但商品列表为空
    res2 = await tool.execute({"user_message": "   ", "user_id": 123})
    assert res2["success"] is True
    assert res2["products"] == []


async def test_search_knowledge_execute(monkeypatch):
    async def fake_search(q, top_k=3):
        return [{
            "id": "kb_009", "category": "支付问题", "question": "退款多久到账",
            "answer": "1-3 个工作日原路退回", "score": 0.95,
        }]

    monkeypatch.setattr(sk_rag, "search", fake_search)
    res = await SearchKnowledgeTool().execute({"user_message": "退款多久到账", "top_k": 3})
    assert res["success"] is True
    assert res["source"] == "knowledge_base"
    assert res["results"][0]["answer"]


# ───────────────────── 退款分支（显式要求）─────────────────────

async def test_refund_branches():
    tool = RefundTool()
    # 取消
    r = await tool.execute({"user_message": "帮我取消订单 ORDER20260315001", "user_id": 123})
    assert r["success"] is True and r.get("action") == "cancel_order"
    # 退货
    r = await tool.execute({"user_message": "我要退货 ORDER20260315001", "user_id": 123})
    assert r["success"] is True and r.get("action") == "return_goods"
    # 退款进度（无订单号 → 退款信息）
    r = await tool.execute({"user_message": "退款进度", "user_id": 123})
    assert r["success"] is True and "退款信息" in r["response"]
    # 退款政策咨询（“退换规则咨询”不含 取消/退货/退款 等关键词 → 走咨询分支）
    r = await tool.execute({"user_message": "退换规则咨询", "user_id": 123})
    assert r["success"] is True and "退款政策" in r["response"]


# ─────────── transfer_human “or” 逻辑稳固（显式要求）───────────

async def test_transfer_human_or_logic():
    tool = TransferHumanTool()
    # 精确匹配投诉
    r1 = await tool.execute({"session_id": "s", "user_id": 123, "reason": "投诉"})
    assert r1["success"] is True
    assert "优先转接专业投诉处理专员" in r1["response"]
    # 投诉包含于 reason（or 逻辑：reason != "投诉" 但 "投诉" in reason）
    r2 = await tool.execute({"session_id": "s", "user_id": 123, "reason": "商品质量投诉"})
    assert "投诉处理专员" in r2["response"]
    # 用户主动请求
    r3 = await tool.execute({"session_id": "s", "user_id": 123, "reason": "用户主动请求"})
    assert "已为您转接人工客服" in r3["response"]
    assert "投诉处理专员" not in r3["response"]
    # 技术问题 → 兜底分支（非投诉）
    r4 = await tool.execute({"session_id": "s", "user_id": 123, "reason": "技术问题"})
    assert "正在为您转接人工客服" in r4["response"]


async def test_transfer_human_return_fields():
    r = await TransferHumanTool().execute(
        {"session_id": "s", "user_id": 123, "reason": "用户主动请求"}
    )
    assert r["success"] is True
    assert r["transfer_id"].startswith("TRF")
    assert 1 <= r["queue_position"] <= 3
    assert r["estimated_wait_time"] == r["queue_position"] * 3


def test_transfer_human_is_complaint_helper():
    assert TransferHumanTool._is_complaint("投诉") is True
    assert TransferHumanTool._is_complaint("用户投诉了") is True
    assert TransferHumanTool._is_complaint("用户主动请求") is False
    assert TransferHumanTool._is_complaint("技术问题") is False
    assert TransferHumanTool._is_complaint("") is False
    assert TransferHumanTool._is_complaint(None) is False


# ───────────────────── 创建工单 ─────────────────────

async def test_create_ticket_execute():
    tool = CreateTicketTool()
    res = await tool.execute({
        "session_id": "s", "user_id": 123, "type": "complaint",
        "title": "商品破损", "content": "收到时外壳碎裂",
    })
    assert res["success"] is True
    assert res["ticket_no"].startswith("TKT")


# ───────────────────── 异常兜底（显式要求）─────────────────────

async def test_exception_fallback_search_knowledge(monkeypatch):
    async def raise_search(q, top_k=3):
        raise RuntimeError("search down")

    monkeypatch.setattr(sk_rag, "search", raise_search)
    res = await SearchKnowledgeTool().execute({"user_message": "x", "top_k": 3})
    assert res["success"] is False
    assert "检索服务暂时不可用" in res["response"]


async def test_exception_fallback_query_order(monkeypatch):
    tool = QueryOrderTool()
    monkeypatch.setattr(tool, "_extract_order_no", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    res = await tool.execute({"user_message": "查订单 ORDER20260315001", "user_id": 123})
    assert res["success"] is False


async def test_exception_fallback_query_product(monkeypatch):
    tool = QueryProductTool()
    monkeypatch.setattr(tool, "_search_products", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    res = await tool.execute({"user_message": "iPhone", "user_id": 123})
    assert res["success"] is False


async def test_exception_fallback_refund(monkeypatch):
    tool = RefundTool()
    monkeypatch.setattr(tool, "_extract_order_no", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    # “取消” 分支内部会调用 _extract_order_no，触发兜底
    res = await tool.execute({"user_message": "我要取消订单 ORDER20260315001", "user_id": 123})
    assert res["success"] is False


async def test_exception_fallback_transfer_human(monkeypatch):
    tool = TransferHumanTool()
    monkeypatch.setattr(tool, "_is_complaint", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    res = await tool.execute({"session_id": "s", "user_id": 123, "reason": "用户主动请求"})
    assert res["success"] is False
    assert "转接人工客服失败" in res["response"]


async def test_exception_fallback_create_ticket(monkeypatch):
    tool = CreateTicketTool()
    monkeypatch.setattr(
        ct_module.random,
        "randint",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    res = await tool.execute({"session_id": "s", "user_id": 123, "type": "consult", "title": "x", "content": "c"})
    assert res["success"] is False


# ───────────────────── 返回字段正确性 ─────────────────────

async def test_each_tool_returns_expected_fields(agent, monkeypatch):
    # 搜索（注入桩）
    async def fake_search(q, top_k=3):
        return [{"id": "k", "category": "c", "question": "q", "answer": "a", "score": 0.9}]

    monkeypatch.setattr(sk_rag, "search", fake_search)

    cases = {
        "search_knowledge": ({"user_message": "x", "top_k": 3}, ["results", "source"]),
        "query_order": ({"user_message": "查订单 ORDER20260315001", "user_id": 123}, ["order"]),
        "query_product": ({"user_message": "iPhone手机"}, ["products"]),
        "refund": ({"user_message": "退款进度", "user_id": 123}, []),
        "transfer_human": ({"session_id": "s", "user_id": 123, "reason": "用户主动请求"}, ["transfer_id"]),
        "create_ticket": ({"session_id": "s", "user_id": 123, "type": "consult", "title": "x", "content": "c"}, ["ticket_no"]),
    }
    for name, (params, extra_keys) in cases.items():
        res = await agent.execute_tool(name, params)
        assert res["success"] is True, f"{name} 应成功: {res}"
        assert "response" in res and isinstance(res["response"], str)
        for k in extra_keys:
            assert k in res, f"{name} 缺少字段 {k}"


# ───────────────────── 注册表驱动意图路由 ─────────────────────

async def test_dispatch_intent_routes_to_registry(agent):
    # intent_code(order_query) → 注册表 → query_order.execute
    res = await agent.dispatch_intent("order_query", "查订单 ORDER20260315001", user_id=123)
    assert res["success"] is True
    assert res["order"]["order_no"] == "ORDER20260315001"

    # 未知意图 → 注册表无对应工具
    res2 = await agent.dispatch_intent("no_such_intent", "hello")
    assert res2["success"] is False
