"""TC-3：流式 stream_message 契约验证。

用 CQ-4 风格注入 FakeSessionManager（不依赖真实 Redis），并用 conftest 的
patch_intent_*/patch_embedding 让意图确定性；LLM 流式路径额外 monkeypatch chat_stream
避免真实联网。验证：
- async for 收集的输出含 ≥1 个 token 事件，且以 type=done 结束（含 intent/sentiment/quick_replies）；
- transfer 分支 done.need_transfer == True；
- 工具异常时产出 type=error 事件（不抛出，SSE 正常结束）。
"""
import asyncio
import json

import pytest

from app.services.chat_service import ChatService
from app.services import llm_service as _llm_mod


def _parse_sse(chunk: str) -> dict:
    """解析 SSE 行 `data: {...}` 为 dict。"""
    assert chunk.startswith("data: "), f"非预期 SSE 行: {chunk!r}"
    return json.loads(chunk[len("data: "):].strip())


class FakeAgent:
    """可控的假 Agent：默认成功返回桩文本；raise_on 中的工具执行时抛异常。"""

    def __init__(self, raise_on=None):
        self.raise_on = set(raise_on or [])

    async def execute_tool(self, tool_name: str, params: dict):
        if tool_name in self.raise_on:
            raise RuntimeError(f"tool {tool_name} failed on purpose")
        return {"success": True, "response": f"[FAKE]{tool_name}", "results": []}


class FakeSessionManager:
    """CQ-4 风格注入的假 SessionManager：会话状态留在内存 dict，不碰 Redis。"""

    def __init__(self, agent=None):
        self._agent = agent if agent is not None else FakeAgent()
        self.store: dict = {}
        self.meta: dict = {}
        self.transferred = set()

    async def prepare(self, session_id, user_id):
        self.meta.setdefault(session_id, {"user_id": user_id, "status": "active"})
        return self._agent

    async def get_session(self, session_id):
        return self.meta.get(session_id)

    async def commit(self, session_id, user_msg, assistant_msg):
        self.store.setdefault(session_id, []).append(user_msg)
        self.store.setdefault(session_id, []).append(assistant_msg)

    async def get_conversation(self, session_id):
        return self.store.get(session_id, [])

    async def mark_transferred(self, session_id):
        self.transferred.add(session_id)

    async def mark_satisfaction(self, session_id, score):
        pass

    async def delete(self, session_id):
        existed = session_id in self.store or session_id in self.meta
        self.store.pop(session_id, None)
        self.meta.pop(session_id, None)
        return existed

    async def list_all(self, user_id=None):
        return {"sessions": [], "total": 0}


def _collect(svc, session_id, content, user_id=None, preferred_intent=None):
    events = []

    async def run():
        async for chunk in svc.stream_message(
            session_id, content, user_id, preferred_intent=preferred_intent
        ):
            events.append(chunk)

    asyncio.run(run())
    return [_parse_sse(c) for c in events]


def test_stream_llm_yields_tokens_and_done(patch_embedding, patch_intent_llm, monkeypatch):
    """LLM 流式路径：≥1 token + 末尾 done（含 intent/sentiment/quick_replies）。"""

    async def fake_stream(messages, temperature=None):
        for piece in ["你好", "，我是客服小e，", "很高兴为您服务～"]:
            yield piece

    monkeypatch.setattr(_llm_mod.llm_service, "chat_stream", fake_stream)

    sm = FakeSessionManager()
    svc = ChatService(session_manager=sm)
    parsed = _collect(svc, "s_llm", "你好", None)

    token_events = [p for p in parsed if p["type"] == "token"]
    assert len(token_events) >= 1
    joined = "".join(t["content"] for t in token_events)
    assert "客服小e" in joined

    done = [p for p in parsed if p["type"] == "done"]
    assert len(done) == 1
    d = done[0]
    for key in ("intent", "sentiment", "quick_replies"):
        assert key in d, f"done 事件缺少 {key}"
    assert d["need_transfer"] is False
    assert d["intent"]["intent_code"] == "fallback"


def test_stream_transfer_need_transfer(patch_embedding, patch_intent_transfer):
    """transfer 分支：done.need_transfer == True，且已标记转人工。"""
    sm = FakeSessionManager()
    svc = ChatService(session_manager=sm)
    parsed = _collect(svc, "s_transfer", "转人工", None)

    done = [p for p in parsed if p["type"] == "done"]
    assert len(done) == 1
    assert done[0]["need_transfer"] is True
    assert "s_transfer" in sm.transferred


def test_stream_tool_exception_yields_error(patch_embedding, patch_intent_order):
    """tool 分支工具异常：产出 type=error 事件（不抛出，SSE 正常结束）。"""
    sm = FakeSessionManager(agent=FakeAgent(raise_on={"query_order"}))
    svc = ChatService(session_manager=sm)
    parsed = _collect(svc, "s_err", "查订单 ORDER20260401001", 1)

    errors = [p for p in parsed if p["type"] == "error"]
    assert len(errors) >= 1
    assert "query_order" in errors[0]["message"]
