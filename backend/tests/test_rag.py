"""知识库检索回归测试：关键词命中 + 向量分数归一化 + 分类过滤。"""
import asyncio

from app.services.rag_service import rag_service


def test_knowledge_search_by_keyword(patch_embedding):
    """零向量跳过 Chroma，走内置关键词，应能命中 kb_009（退款多久到账）。"""
    results = asyncio.run(rag_service.search("退款多久到账", top_k=5))
    ids = [r["id"] for r in results]
    assert "kb_009" in ids


def test_scores_in_unit_interval(patch_embedding):
    """L9 修复：所有结果 score 必须落在 [0,1]（向量已归一化）。"""
    results = asyncio.run(rag_service.search("退款多久到账", top_k=5))
    assert results, "应有检索结果"
    for r in results:
        assert 0.0 <= r["score"] <= 1.0


def test_category_filter(patch_embedding):
    """ 修复：category 过滤透传，返回结果分类应一致。"""
    results = asyncio.run(rag_service.search("退款", top_k=5, filters={"category": "退换货政策"}))
    for r in results:
        assert r["category"] == "退换货政策"
