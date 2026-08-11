"""（计分收口到 VectorStore.search）+ （关键词倒排 / 加权索引）验证。

不依赖真实 Chroma / Embedding / Redis：
- 通过 monkeypatch 注入 fake collection / fake VectorStore，验证计分已收口到
  VectorStore.search（零向量降级、distance→[0,1] 归一化、返回形态），且 rag_service.search
  只做向量 + 关键词合并，不再直接碰 chromadb 内部字段。
- 验证启动时已构建 resident 倒排索引、_keyword_search 查索引与原逐文档扫描算法
  输出完全一致、以及文档增删后索引随之重建。
"""
import asyncio
from typing import List, Dict, Any

import pytest

import app.services.rag_service as rag_service_mod
from app.rag import vector_store as vector_store_mod
from app.services.rag_service import (
    RAGService,
    rag_service,
    BUILT_IN_KNOWLEDGE,
    _KEYWORD_INDEX,
    _tokenize,
    _build_keyword_index,
)


# ───────────────────────── ：VectorStore.search 计分收口 ─────────────────────────

class FakeCollection:
    """模拟 Chroma collection.query，返回可预测 distance 以验证归一化。"""

    def query(self, query_embeddings, n_results):
        return {
            "ids": [["d1", "d2", "d3"]],
            "distances": [[1.0, 5.0, 9.0]],
            "documents": [["a1", "a2", "a3"]],
            "metadatas": [[
                {"category": "c1", "question": "q1"},
                {"category": "c2", "question": "q2"},
                {"category": "c3", "question": "q3"},
            ]],
        }


async def _fake_get_collection():
    return FakeCollection()


async def _async_true(*_a, **_k):
    return True


async def _no_chroma():
    return None


def test_vectorstore_zero_vector_returns_empty_and_skips_chroma(monkeypatch):
    """：零向量 / 降级检测应短路返回 []，且不创建 Chroma 客户端。"""
    called = {"n": 0}

    async def _spy_get_collection():
        called["n"] += 1
        return None

    monkeypatch.setattr(vector_store_mod.vector_store, "_get_collection", _spy_get_collection)
    result = asyncio.run(vector_store_mod.vector_store.search([0.0, 0.0, 0.0], 5))
    assert result == []
    assert called["n"] == 0  # 零向量未触发任何 Chroma 访问


def test_vectorstore_none_embedding_returns_empty(monkeypatch):
    """：embedding 为 None 时同样降级返回 []。"""
    result = asyncio.run(vector_store_mod.vector_store.search(None, 5))
    assert result == []


def test_vectorstore_minmax_normalization(monkeypatch):
    """：distance 经 min-max 归一化到 [0,1]（最近→1.0，最远→0.0），形态与内置库对齐。"""
    monkeypatch.setattr(vector_store_mod.vector_store, "_get_collection", _fake_get_collection)
    monkeypatch.setattr(vector_store_mod, "collection_has_docs", _async_true)

    results = asyncio.run(vector_store_mod.vector_store.search([0.1, 0.2, 0.3], 5))
    assert [r["score"] for r in results] == [1.0, 0.5, 0.0]
    for r in results:
        assert set(r.keys()) == {"id", "category", "question", "answer", "score"}
        assert 0.0 <= r["score"] <= 1.0


def test_vectorstore_normalization_span_zero(monkeypatch):
    """：单条结果（span=0）归一化为 1.0，不出现 NaN。"""

    class OneDocCollection:
        def query(self, query_embeddings, n_results):
            return {
                "ids": [["x1"]],
                "distances": [[3.3]],
                "documents": [["ax"]],
                "metadatas": [[{"category": "c", "question": "q"}]],
            }

    async def _one():
        return OneDocCollection()

    monkeypatch.setattr(vector_store_mod.vector_store, "_get_collection", _one)
    monkeypatch.setattr(vector_store_mod, "collection_has_docs", _async_true)
    results = asyncio.run(vector_store_mod.vector_store.search([0.5], 5))
    assert len(results) == 1
    assert results[0]["score"] == 1.0


class _MemCache:
    def __init__(self):
        self._s: Dict[str, Any] = {}

    async def get(self, k):
        return self._s.get(k)

    async def set(self, k, v, expire=3600):
        self._s[k] = v
        return True


class _IdentityEmb:
    async def encode_single(self, text):
        # 非全零，确保走向量检索路径（本测试 vector_store 为 fake，不依赖真实 embedding）
        return [0.1, 0.2, 0.3]


class FakeVectorStore:
    """返回已归一化分数的向量结果，验证 rag_service 仅做合并、不再碰 chroma。"""

    def __init__(self, items: List[Dict[str, Any]]):
        self.items = items
        self.calls = 0

    async def search(self, query_embedding, top_k=5):
        self.calls += 1
        return [dict(it) for it in self.items[:top_k]]


def test_rag_service_merges_vector_and_keyword(patch_embedding):
    """：rag_service.search 仅合并 VectorStore 结果 + 关键词结果，分数在 [0,1]。"""
    fake_vs = FakeVectorStore([
        {"id": "vec_abc", "category": "支付问题", "question": "退款多久到账",
         "answer": "退款说明", "score": 0.9},
    ])
    svc = RAGService(cache=_MemCache(), embedding=_IdentityEmb(), vector_store=fake_vs)
    results = asyncio.run(svc.search("退款多久到账", top_k=5))
    ids = [r["id"] for r in results]
    assert "vec_abc" in ids        # 向量结果被合并
    assert "kb_009" in ids         # 关键词结果被合并
    for r in results:
        assert 0.0 <= r["score"] <= 1.0
    assert fake_vs.calls == 1      # 仅调用一次 VectorStore.search，rag_service 不再直接查 chroma


# ───────────────────────── ：关键词倒排索引 ─────────────────────────

def test_keyword_index_built_at_import():
    """：启动时已构建 resident 倒排索引，覆盖全部内置文档。"""
    assert len(rag_service_mod._KEYWORD_INDEX["docs"]) == len(BUILT_IN_KNOWLEDGE) == 13
    assert rag_service_mod._KEYWORD_INDEX["token_index"]  # 非空


def test_build_keyword_index_dedupes_repeated_tokens():
    """：_build_keyword_index 对问题内重复词去重，避免多次命中计数。"""
    kb = [{"id": "k1", "category": "测试", "question": "物流流",
           "answer": "a", "keywords": "物流"}]
    idx = _build_keyword_index(kb)
    # '流' 在问题中出现两次，倒排仅记录一次文档下标
    assert idx["token_index"]["流"] == [0]
    # 关键词预存
    assert idx["docs"][0]["keywords_list"] == ["物流"]


def _brute_keyword_search(query, top_k, filters=None):
    """旧实现复刻，用于验证 索引路径与逐文档扫描等价。"""
    query_lower = query.lower()
    scored = []
    q_token_set = set(_tokenize(query_lower))
    for kb in BUILT_IN_KNOWLEDGE:
        if filters and filters.get("category") and kb["category"] != filters["category"]:
            continue
        score = 0.0
        q_text = kb["question"].lower()
        kw_text = kb["keywords"].lower()
        cat_text = kb["category"].lower()
        for kw in kw_text.split():
            if kw and kw in query_lower:
                score += 0.4
        if q_token_set:
            hit = sum(1 for t in q_token_set if t and t in q_text)
            score += 0.8 * (hit / len(q_token_set))
        if cat_text and cat_text in query_lower:
            score += 0.5
        if score > 0:
            item = dict(kb)
            item["score"] = min(score, 1.0)
            scored.append(item)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


@pytest.mark.parametrize("query,filters", [
    ("退款多久到账", None),
    ("退款", {"category": "退换货政策"}),
    ("会员有什么优惠", None),
    ("发票", None),
    ("优惠券怎么使用", None),
    ("如何开具发票", {"category": "发票问题"}),
    ("", None),
])
def test_keyword_search_equivalent_to_bruteforce(query, filters):
    """：索引路径与原逐文档扫描算法输出完全一致（id 顺序 + score）。"""
    got = rag_service._keyword_search(query, 5, filters)
    exp = _brute_keyword_search(query, 5, filters)
    assert [r["id"] for r in got] == [r["id"] for r in exp]
    for g, e in zip(got, exp):
        assert g["id"] == e["id"]
        assert abs(g["score"] - e["score"]) < 1e-9


def test_keyword_search_scores_in_unit_interval():
    """：索引路径返回的分数必须落在 [0,1]。"""
    results = rag_service._keyword_search("退款多久到账", 5, None)
    assert results
    for r in results:
        assert 0.0 <= r["score"] <= 1.0


@pytest.fixture
def preserve_kb():
    """快照并恢复全局 BUILT_IN_KNOWLEDGE / _KEYWORD_INDEX，避免污染其他测试。"""
    snapshot = list(rag_service_mod.BUILT_IN_KNOWLEDGE)
    yield
    rag_service_mod.BUILT_IN_KNOWLEDGE = list(snapshot)
    rag_service_mod._KEYWORD_INDEX = _build_keyword_index(rag_service_mod.BUILT_IN_KNOWLEDGE)


def test_keyword_index_rebuild_on_add_delete(patch_embedding, monkeypatch, preserve_kb):
    """：文档增删后倒排索引随之更新（新文档可被召回，删除后不再召回）。"""
    monkeypatch.setattr(rag_service, "_get_chroma", _no_chroma)

    before = len(rag_service_mod._KEYWORD_INDEX["docs"])
    new_id = asyncio.run(rag_service.add_document(
        question="会员积分怎么兑换",
        answer="积分可在会员中心兑换礼品",
        category="会员权益",
        keywords="积分 兑换",
    ))
    assert len(rag_service_mod._KEYWORD_INDEX["docs"]) == before + 1
    hits = rag_service._keyword_search("会员积分怎么兑换", 5, None)
    assert any(h["id"] == new_id for h in hits)

    ok = asyncio.run(rag_service.delete_document(new_id))
    assert ok is True
    assert len(rag_service_mod._KEYWORD_INDEX["docs"]) == before
    hits2 = rag_service._keyword_search("会员积分怎么兑换", 5, None)
    assert all(h["id"] != new_id for h in hits2)
