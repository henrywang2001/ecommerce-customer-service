"""RAG 检索增强生成服务（集成 Langfuse 追踪）"""
from typing import List, Dict, Any, Optional
import asyncio
import json
import logging
import re
import hashlib
from app.services.embedding_service import embedding_service
from app.services.llm_service import llm_service
from app.services.observe_service import observe
from app.rag.vector_store import vector_store
from app.rag.chroma_client import collection_has_docs, invalidate_collection_cache
from app.utils.cache import cache

logger = logging.getLogger(__name__)

# 知识库写操作异步锁（防御并发修改全局 BUILT_IN_KNOWLEDGE）
_kb_lock = asyncio.Lock()

# ── PF-1：KB 版本号命名空间（主动失效）──
# 知识库发生写操作（add/delete_document）时自增版本号，使检索/embedding 缓存键随版本变化，
# 旧版本缓存键自然 orphan（不再命中），下次检索必走实时计算，根治「快但旧」。
# 单 worker 模型下用进程内计数器即可（MN-6 约束：A1 落地前 Docker 维持单副本）。
KB_VERSION = 0


def _bump_kb_version() -> int:
    """知识库写操作后调用：自增版本号，返回新版本。"""
    global KB_VERSION
    KB_VERSION += 1
    return KB_VERSION


def get_kb_version() -> int:
    """测试 / 可观测用：读取当前版本号。"""
    return KB_VERSION


def _normalize_query(q: str) -> str:
    """PF-5：查询归一化（lower + 去全部空白 + 去标点），使同义问法命中同一缓存键。

    空白对 RAG 检索缓存无语义价值（中文本无空白；英文合并亦可提升命中率），
    故直接去除而非仅压缩；标点同样去除。注意：仅用于缓存键，embedding 仍用原始 query。
    """
    q = (q or "").lower()
    q = re.sub(r"\s+", "", q)
    q = re.sub(r"[^\w\u4e00-\u9fff]", "", q)
    return q


def _filters_key(filters: Optional[Dict]) -> str:
    """PF-5：filters 稳定序列化（按 key 排序），避免 dict 顺序差异导致缓存未命中。"""
    if not filters:
        return ""
    return json.dumps(filters, sort_keys=True, ensure_ascii=False)


def _make_res_key(query: str, top_k: int, filters: Optional[Dict]) -> str:
    return f"rag:res:{KB_VERSION}:{_normalize_query(query)}:{top_k}:{_filters_key(filters)}"


def _make_emb_key(query: str) -> str:
    return f"rag:emb:{KB_VERSION}:{_normalize_query(query)}"

# 内置知识库内容（Mock 数据，实际项目中使用 ChromaDB）
BUILT_IN_KNOWLEDGE: List[Dict[str, Any]] = [
    {
        "id": "kb_001",
        "category": "退换货政策",
        "question": "商品可以退换吗？",
        "answer": "7天内可无理由退换货，15天内可申请质量问题退换货。退换货时请保持商品完好、配件齐全。",
        "keywords": "退换货 退货 换货 退款",
    },
    {
        "id": "kb_002",
        "category": "配送服务",
        "question": "配送时间是多久？",
        "answer": "普通商品2-5个工作日送达；偏远地区可能延长1-3天；大型商品需预约配送时间。",
        "keywords": "配送 快递 物流 送货 到货时间",
    },
    {
        "id": "kb_003",
        "category": "支付问题",
        "question": "支持哪些支付方式？",
        "answer": "支持支付宝、微信支付、银行卡支付、货到付款（部分地区）。信用支付可使用花呗、京东白条等。",
        "keywords": "支付 付款 微信 支付宝 银行卡",
    },
    {
        "id": "kb_004",
        "category": "会员权益",
        "question": "会员有什么优惠？",
        "answer": "会员可享受积分返利、专属折扣、生日礼包、优先发货等权益。会员等级越高，权益越丰富。",
        "keywords": "会员 积分 折扣 优惠 权益 VIP",
    },
    {
        "id": "kb_005",
        "category": "促销活动",
        "question": "近期有什么优惠活动？",
        "answer": "当前正在进行以下活动：1. 新用户首单满100减20；2. 夏季大促全品类8折起；3. 会员日双倍积分。",
        "keywords": "活动 优惠 促销 打折 满减",
    },
    {
        "id": "kb_006",
        "category": "售后政策",
        "question": "保修期是多久？",
        "answer": "电器类产品保修1年，家具类产品保修3年，服饰类商品支持7天无理由退换（不影响二次销售）。",
        "keywords": "保修 质保 维修 售后",
    },
    {
        "id": "kb_007",
        "category": "订单修改",
        "question": "下单后可以修改地址吗？",
        "answer": "未发货的订单可以在订单详情中修改收货地址。已发货的订单如需修改，请联系客服协助处理。",
        "keywords": "修改地址 改地址 修改订单 换地址",
    },
    {
        "id": "kb_008",
        "category": "发票问题",
        "question": "如何开具发票？",
        "answer": "下单时可在结算页面选择开具发票，支持电子发票和纸质发票。已完成的订单可在订单详情中补开发票。",
        "keywords": "发票 开票 电子发票 纸质发票",
    },
    {
        "id": "kb_009",
        "category": "支付问题",
        "question": "退款多久到账？",
        "answer": "退款审核通过后将在1-3个工作日内原路退回：支付宝/微信支付通常1-3个工作日到账，银行卡支付3-7个工作日。可在「我的订单」中查看退款进度。",
        "keywords": "退款 到账 退款时间 退款进度 原路退回",
    },
    {
        "id": "kb_010",
        "category": "退换货政策",
        "question": "退换货运费由谁承担？",
        "answer": "7天无理由退换货（非质量问题）的运费由买家承担；因商品质量问题产生的退换货运费由商家承担。建议下单前查看商品页面的运费说明。",
        "keywords": "退货运费 换货运费 运费 谁承担 运费险",
    },
    {
        "id": "kb_011",
        "category": "配送服务",
        "question": "下单后多久发货？",
        "answer": "现货商品一般在付款后24-48小时内发货；预售/定制商品以商品页标注的发货时间为准。发货后可通过物流单号跟踪配送进度。",
        "keywords": "发货 发货时间 多久发货 预售 发货时效",
    },
    {
        "id": "kb_012",
        "category": "促销活动",
        "question": "优惠券怎么使用？",
        "answer": "结算页面选择可用优惠券即可抵扣金额；注意每张优惠券的有效期与使用门槛（如满减门槛），优惠券通常不可叠加使用。可在「我的优惠券」查看可用券。",
        "keywords": "优惠券 满减 抵扣 怎么用 使用规则 叠加",
    },
    {
        "id": "kb_013",
        "category": "售后政策",
        "question": "客服服务时间是什么时候？",
        "answer": "在线智能客服7×24小时为您服务；人工客服服务时间为每日9:00-22:00。非人工服务时段您可留言，人工上线后会优先回复。",
        "keywords": "客服时间 服务时间 人工客服 在线时间 上班时间",
    },
]


class RAGService:
    """检索增强生成服务 — ChromaDB + 千问 Embedding"""

    async def _get_chroma(self):
        """懒加载 ChromaDB 客户端（P7 修复：复用全局单例，避免同目录多客户端锁竞争）"""
        from app.rag.chroma_client import get_chroma_client
        return get_chroma_client()

    def _make_vector_id(self, text: str) -> str:
        """生成跨进程稳定的向量 ID（B3 修复）

        原实现用内置 hash()，受 PYTHONHASHSEED 影响，重启后同一文档 ID 不同，
        导致重复写入 / 删除失效。改用 sha256 摘要，结果跨进程、跨重启稳定。
        """
        return f"vec_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> str:
        """检索相关文档并格式化为上下文字符串"""
        results = await self.search(query, top_k, filters)
        return self._format_context(results)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """检索相关文档 — Langfuse retriever 追踪
        关键修复：无论 Chroma 是否非空，始终将「内置知识库关键词检索」结果与
        Chroma 向量检索结果合并去重后返回，避免 Chroma 一旦写入就挤掉内置知识。
        """
        from app.core.config import settings
        logger.info(f"RAG 检索: {query[:50]}...")

        # ── Langfuse: retriever 追踪 ──
        with observe.retriever(
            name="rag-search",
            input={"query": query, "top_k": top_k, "filters": filters},
        ) as ret:
            # ── PF-1/PF-5: 结果缓存（命中则跳过 embedding + 检索，仅做缓存命中追踪后返回）──
            # 键含 KB 版本号（写操作自增）+ 归一化查询 + 稳定 filters，天然支持主动失效
            res_key = _make_res_key(query, top_k, filters)
            cached = await cache.get(res_key)
            if cached:
                if ret is not None:
                    ret.update(
                        output={
                            "result_count": len(cached),
                            "top_scores": [r["score"] for r in cached[:3]],
                            "source": "cache",
                        },
                    )
                logger.info(f"RAG 检索命中结果缓存: {query[:50]}...")
                return cached

            chroma_results: List[Dict[str, Any]] = []
            chroma = await self._get_chroma()
            # 检测零向量：embedding 不可用时（返回全 0 向量）不再做向量检索，避免污染结果
            if chroma is not None:
                # ── PF-1/PF-5: embedding 缓存（命中则跳过远程 embedding 调用）──
                # 键含 KB 版本号 + 归一化查询；知识库变更后旧版本 embedding 键自动 orphan
                emb_key = _make_emb_key(query)
                query_embedding = await cache.get(emb_key)
                if query_embedding is None:
                    query_embedding = await embedding_service.encode_single(query)
                    await cache.set(emb_key, query_embedding, expire=3600)
                is_zero = all(v == 0.0 for v in query_embedding)
            else:
                is_zero = False
            if chroma is not None and not is_zero:
                try:
                    collection = chroma.get_or_create_collection(
                        name=settings.CHROMA_COLLECTION,
                    )
                    # P10：用带缓存的「是否非空」判断替代每次检索都执行的 collection.count()
                    if await collection_has_docs(collection):
                        chroma_raw = collection.query(
                            query_embeddings=[query_embedding],
                            n_results=top_k,
                        )
                        if chroma_raw["ids"] and chroma_raw["ids"][0]:
                            # 1) 先收集每条结果的原始 distance（distance 缺失时回退 0.1*i），
                            #    连同文档字段一起暂存，稍后统一做归一化。
                            raw_items: List[Dict[str, Any]] = []
                            distances: List[float] = []
                            for i, doc_id in enumerate(chroma_raw["ids"][0]):
                                metadata = (
                                    chroma_raw["metadatas"][0][i]
                                    if chroma_raw["metadatas"]
                                    else {}
                                )
                                distance = (
                                    chroma_raw["distances"][0][i]
                                    if chroma_raw.get("distances")
                                    else 0.1 * i
                                )
                                raw_items.append({
                                    "id": doc_id,
                                    "category": metadata.get("category", ""),
                                    "question": metadata.get("question", ""),
                                    "answer": (
                                        chroma_raw["documents"][0][i]
                                        if chroma_raw["documents"]
                                        else ""
                                    ),
                                })
                                distances.append(distance)

                            # 2) 对本次查询返回的 Chroma 结果集做 min-max 归一化到 [0,1]
                            #    （最近→1.0，最远→0.0），使其与内置库关键词分数（0.3~1.0）
                            #    同量纲，合并排序时向量命中能合理上浮。
                            #    说明：不用 1/(1+distance) —— 本数据所有距离都在 ~2万级，
                            #    该式会把所有向量分数压成 ~4e-5 且几乎无差异，等于没修。
                            dmin = min(distances)
                            dmax = max(distances)
                            span = dmax - dmin
                            for item, distance in zip(raw_items, distances):
                                item["score"] = (
                                    1.0 if span == 0 else 1.0 - (distance - dmin) / span
                                )
                                chroma_results.append(item)
                except Exception as e:
                    logger.warning(f"ChromaDB 查询失败: {e}")

            # 始终基于内置知识库做关键词检索，保证内置知识任何情况下可检索
            builtin_results = self._keyword_search(query, top_k, filters)

            # 合并去重（按 id 取高分），按分数降序截取 top_k
            merged = self._merge_search_results(chroma_results, builtin_results, top_k)

            if ret is not None:
                source = "chromadb+built-in" if chroma_results else "built-in-keyword"
                ret.update(
                    output={
                        "result_count": len(merged),
                        "top_scores": [r["score"] for r in merged[:3]],
                        "source": source,
                    },
                    metadata={"embedding_model": settings.EMBEDDING_MODEL} if chroma_results else {},
                )
            # ── P5: 写入结果缓存 ──
            await cache.set(res_key, merged, expire=600)
            return merged

    def _merge_search_results(
        self,
        chroma_results: List[Dict[str, Any]],
        builtin_results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """合并 Chroma 与内置库结果，按 id 去重（保留分数更高者），降序截取 top_k。"""
        by_id: Dict[str, Dict[str, Any]] = {}
        for r in list(chroma_results) + list(builtin_results):
            existing = by_id.get(r["id"])
            if existing is None or r["score"] > existing["score"]:
                by_id[r["id"]] = r
        merged = sorted(by_id.values(), key=lambda x: x["score"], reverse=True)
        return merged[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        """中文友好的轻量分词（B6 修复）

        英文/数字按词切分；中文按「单字 + 相邻二字 bigram」展开，
        使整句中文也能与知识库问题/关键词逐字、逐段匹配，解决原空白切分
        导致中文整句成一个 token、几乎不得分的问题。
        """
        text = (text or "").lower()
        tokens: List[str] = []
        for w in re.findall(r"[a-z0-9]+", text):
            tokens.append(w)
        for seg in re.findall(r"[\u4e00-\u9fff]+", text):
            for ch in seg:
                tokens.append(ch)
            for i in range(len(seg) - 1):
                tokens.append(seg[i:i + 2])
        return tokens

    def _keyword_search(self, query: str, top_k: int, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """基于关键词的内置知识库检索（B6 修复：中文逐字/bigram 召回）"""
        query_lower = query.lower()
        scored = []
        q_token_set = set(self._tokenize(query_lower))
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
                item = kb.copy()
                item["score"] = min(score, 1.0)
                scored.append(item)
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _format_context(self, results: List[Dict]) -> str:
        """格式化检索结果为上下文字符串"""
        if not results:
            return ""
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"【文档 {i}】相似度: {r.get('score', 0):.2f}\n"
                f"分类: {r.get('category', '')}\n"
                f"问题: {r.get('question', '')}\n"
                f"答案: {r.get('answer', '')}"
            )
        return "\n\n".join(parts)

    async def generate(self, query: str, context: str) -> str:
        """基于检索结果生成回答 — Langfuse generation 追踪"""
        if not context:
            return await llm_service.generate(f"请简洁回答用户问题：{query}")

        prompt = (
            f"基于以下知识库内容回答用户问题。如果知识库中没有相关信息，"
            f"请直接告知用户并建议咨询人工客服。\n\n"
            f"知识库内容：\n{context}\n\n"
            f"用户问题：{query}\n\n"
            f"要求：直接回答，简洁专业。如果信息充分则不要提及'根据知识库'等字眼。"
        )

        # ── Langfuse: rag-generation 追踪 ──
        with observe.generation(
            name="rag-generate",
            model=llm_service.model,
            input={"query": query, "context_length": len(context)},
            model_parameters={
                "temperature": llm_service.temperature,
                "max_tokens": llm_service.max_tokens,
            },
        ) as gen:
            result = await llm_service.generate(prompt)
            if gen is not None:
                gen.update(output=result)
            return result

    async def generate_stream(self, query: str, context: str):
        """基于检索结果流式生成（P6）。"""
        if not context:
            async for piece in llm_service.generate_stream(f"请简洁回答用户问题：{query}"):
                yield piece
            return

        prompt = (
            f"基于以下知识库内容回答用户问题。如果知识库中没有相关信息，"
            f"请直接告知用户并建议咨询人工客服。\n\n"
            f"知识库内容：\n{context}\n\n"
            f"用户问题：{query}\n\n"
            f"要求：直接回答，简洁专业。如果信息充分则不要提及'根据知识库'等字眼。"
        )
        async for piece in llm_service.generate_stream(prompt):
            yield piece

    async def add_document(self, question: str, answer: str, category: str = "", keywords: str = "") -> str:
        """添加文档到向量数据库"""
        text = f"问题: {question}\n答案: {answer}"
        vector_id = self._make_vector_id(text)

        chroma = await self._get_chroma()
        if chroma is not None:
            try:
                from app.core.config import settings
                collection = chroma.get_or_create_collection(name=settings.CHROMA_COLLECTION)
                embedding = await embedding_service.encode_single(text)
                collection.add(
                    ids=[vector_id],
                    embeddings=[embedding],
                    documents=[answer],
                    metadatas=[{
                        "category": category,
                        "question": question,
                        "keywords": keywords,
                    }],
                )
                logger.info(f"文档已添加到 ChromaDB: {vector_id}")
            except Exception as e:
                logger.warning(f"ChromaDB 写入失败: {e}")
            finally:
                # P10：文档增减后使「是否非空」缓存失效
                invalidate_collection_cache()
                # PF-1：知识库写操作自增版本号，使检索/embedding 缓存键主动失效（根治「快但旧」）
                _bump_kb_version()

        # 同时加到内置库（加锁保证写操作并发安全）
        async with _kb_lock:
            BUILT_IN_KNOWLEDGE.append({
                "id": vector_id,
                "category": category,
                "question": question,
                "answer": answer,
                "keywords": keywords,
            })

        return vector_id

    async def delete_document(self, knowledge_id: str) -> bool:
        """删除知识文档（Chroma + 内置库）。

        先确认 id 是否真实存在，避免对「不存在的 id」误报『已删除』：
        - 内置库命中 → 删除并返回 True
        - 仅存在于 Chroma → 删除并返回 True
        - 两处均不存在 → 返回 False（上层据此返回 success:false / 未找到）
        """
        global BUILT_IN_KNOWLEDGE
        # 1) 内置库是否存在（加锁读取）
        async with _kb_lock:
            in_builtin = any(k.get("id") == knowledge_id for k in BUILT_IN_KNOWLEDGE)
        # 2) Chroma 是否存在（内置库未命中时才查，避免无谓调用）
        in_chroma = False
        if not in_builtin:
            try:
                existing = await vector_store.get(ids=[knowledge_id])
                in_chroma = bool(existing)
            except Exception:
                in_chroma = False
        if not (in_builtin or in_chroma):
            return False
        # 3) 执行删除
        try:
            await vector_store.delete([knowledge_id])
        except Exception:
            pass
        finally:
            # P10：文档增减后使「是否非空」缓存失效
            invalidate_collection_cache()
            # PF-1：知识库写操作自增版本号，使检索/embedding 缓存键主动失效（根治「快但旧」）
            _bump_kb_version()
        async with _kb_lock:
            BUILT_IN_KNOWLEDGE = [k for k in BUILT_IN_KNOWLEDGE if k.get("id") != knowledge_id]
        return True


# 全局单例
rag_service = RAGService()
