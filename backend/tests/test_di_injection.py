"""CQ-4 构造函数依赖注入（DI）可测试性验证。

证明核心服务可通过构造函数注入 fake 依赖，而无需对全局单例做重型 monkeypatch：
- RAGService(cache=fake_cache, embedding=fake_embedding)：验证缓存读写走注入的 fake；
- LLMService(client=fake_client)：验证生成调用走注入的 fake client，离线返回桩文本。
"""
import asyncio

from app.services.rag_service import RAGService
from app.services.llm_service import LLMService


class FakeCache:
    """记录 get/set 调用的内存 fake 缓存，接口对齐 app.utils.cache.Cache。"""

    def __init__(self):
        self._store = {}
        self.get_calls = []
        self.set_calls = []

    async def get(self, key):
        self.get_calls.append(key)
        return self._store.get(key)

    async def set(self, key, value, expire=3600):
        self.set_calls.append((key, value, expire))
        self._store[key] = value
        return True


class FakeEmbedding:
    """返回零向量的 fake embedding，使 chroma 检索被跳过（离线、无联网）。"""

    def __init__(self):
        self.calls = []

    async def encode_single(self, text):
        self.calls.append(text)
        return [0.0] * 8


class FakeClient:
    """fake httpx 客户端，提供 .post 返回桩文本，验证 LLMService 走注入 client。"""

    def __init__(self):
        self.calls = []

    async def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append((url, json))
        return FakeResponse()


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "（注入桩）你好，我是客服小e"}}]}


def test_rag_service_cache_injection():
    fake_cache = FakeCache()
    fake_emb = FakeEmbedding()
    svc = RAGService(cache=fake_cache, embedding=fake_emb)

    # 注入生效：实例持有注入的 fake 依赖而非全局单例
    assert svc.cache is fake_cache
    assert svc.embedding is fake_emb

    r1 = asyncio.run(svc.search("退款多久到账", top_k=5))
    r2 = asyncio.run(svc.search("退款多久到账", top_k=5))

    # 两次检索均先查缓存（命中则跳过计算）
    assert len(fake_cache.get_calls) >= 2
    # 结果缓存键（rag:res:）仅写入一次：第一次检索写入，第二次命中直接返回
    res_sets = [k for k, _, _ in fake_cache.set_calls if k.startswith("rag:res:")]
    assert len(res_sets) == 1
    # 两次结果一致（第二次来自缓存）
    assert r1 == r2
    # 内置关键词检索命中退款知识
    assert any("退款" in (item.get("answer") or "") for item in r1)


def test_llm_service_client_injection():
    fake = FakeClient()
    svc = LLMService(client=fake)

    out = asyncio.run(svc.generate("你好"))

    assert out == "（注入桩）你好，我是客服小e"
    assert fake.calls  # 生成确实走了注入的 client（而非真实联网）
