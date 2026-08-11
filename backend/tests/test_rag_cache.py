"""（KB 版本号命名空间主动失效）+ （查询/ filters 键归一化）单测。

不依赖 Chroma / Embedding / Redis：纯函数级验证缓存键构造逻辑，
确保「知识库写操作后旧缓存键主动失效」「同义问法命中同一键」。
"""
import pytest

from app.services.rag_service import (
    _normalize_query,
    _filters_key,
    _make_res_key,
    _make_emb_key,
    _bump_kb_version,
    get_kb_version,
)


def test_normalize_query_collapses_whitespace_and_strips_punctuation():
    """：lower + 去除全部空白 + 去标点，使『退款 多久到账？』==『退款多久到账』。"""
    assert _normalize_query("退款  多久到账？") == "退款多久到账"
    assert _normalize_query("  Refund NOW! ") == "refundnow"


def test_res_key_equivalent_for_synonymous_queries():
    """同义问法（空白/标点差异）应映射到同一结果缓存键，提升命中率。"""
    a = _make_res_key("退款 多久到账？", 5, None)
    b = _make_res_key("退款多久到账", 5, None)
    assert a == b
    assert "退款多久到账" in a  # 归一化后的查询应出现在键中


def test_filters_key_order_independent():
    """：filters 按 key 排序序列化，dict 顺序差异不应导致缓存未命中。"""
    a = _make_res_key("x", 5, {"category": "支付问题", "b": 1})
    b = _make_res_key("x", 5, {"b": 1, "category": "支付问题"})
    assert a == b


def test_version_bump_invalidates_old_res_key():
    """：知识库写操作后版本自增，旧版本结果缓存键不再被使用（主动失效）。"""
    before = _make_res_key("退款多久到账", 5, None)
    v_before = get_kb_version()
    _bump_kb_version()
    after = _make_res_key("退款多久到账", 5, None)
    assert get_kb_version() == v_before + 1
    assert before != after
    # 旧键含旧版本号、新键含新版本号
    assert f":{v_before}:" in before
    assert f":{v_before + 1}:" in after


def test_version_bump_invalidates_old_emb_key():
    """：embedding 缓存键同样随版本变化而 orphan。"""
    before = _make_emb_key("退款多久到账")
    _bump_kb_version()
    after = _make_emb_key("退款多久到账")
    assert before != after


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("退款", "退款"),
        ("How to RETURN?", "howtoreturn"),
        ("  \t\n  你好 世界  ", "你好世界"),
    ],
)
def test_normalize_query_parametrized(raw, expected):
    assert _normalize_query(raw) == expected
