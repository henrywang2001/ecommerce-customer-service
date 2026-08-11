"""：并发安全 + 分页裁剪 + LLM 韧性回落。

- asyncio.gather 并发 send_message：无 KeyError、历史条数一致；
- get_history(page=-1, page_size=9999) 被裁剪（page→1, page_size→100）；
- post_with_resilience 强制抛错 → generate 返回回落文本、generate_json 返回 None。
"""
import asyncio

import pytest

from app.services.chat_service import chat_service
from app.services import llm_service as _llm_mod


def test_concurrent_send_no_keyerror_and_consistent(patch_embedding, patch_llm, patch_intent_llm):
    """并发发送：无 KeyError，历史 user+assistant 条数 = 2*N 且一致。"""
    sid = "s_tc7_concurrent"
    # 预建会话（Redis/cache 内存后端在测试中被强制，进程内一致）
    asyncio.run(chat_service.session_manager.prepare(sid, None))

    n = 10

    async def run_all():
        tasks = [
            chat_service.send_message(sid, f"消息{i}", None)
            for i in range(n)
        ]
        return await asyncio.gather(*tasks)

    results = asyncio.run(run_all())
    assert len(results) == n
    for r in results:
        assert r["response"]

    hist = asyncio.run(chat_service.get_history(sid))
    # 每条用户消息产生 1 user + 1 assistant = 2 条
    assert hist["total"] == 2 * n
    assert len(hist["items"]) == min(2 * n, 100)


def test_get_history_page_clamped(patch_embedding, patch_llm, patch_intent_llm):
    """get_history 分页参数防御性裁剪：负页/超大页被夹到合法范围。"""
    sid = "s_tc7_clamp"
    asyncio.run(chat_service.session_manager.prepare(sid, None))
    asyncio.run(chat_service.send_message(sid, "你好", None))

    hist = asyncio.run(chat_service.get_history(sid, page=-1, page_size=9999))
    assert hist["page"] == 1
    assert hist["page_size"] == 100
    assert hist["total"] == 2


def test_llm_resilience_fallback(monkeypatch):
    """post_with_resilience 强制抛错 → generate 回落文本；generate_json 返回 None。"""

    async def boom(*args, **kwargs):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(_llm_mod, "post_with_resilience", boom)

    out = asyncio.run(_llm_mod.llm_service.generate("你好"))
    assert "抱歉" in out  # 韧性回落文本

    j = asyncio.run(_llm_mod.llm_service.generate_json("你好"))
    assert j is None
