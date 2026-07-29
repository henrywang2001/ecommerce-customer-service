"""RAG 检索增强生成服务（集成 Langfuse 追踪）"""
from typing import List, Dict, Any, Optional
import logging
from app.services.embedding_service import embedding_service
from app.services.llm_service import llm_service
from app.services.observe_service import observe

logger = logging.getLogger(__name__)

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
]


class RAGService:
    """检索增强生成服务 — ChromaDB + 千问 Embedding"""

    def __init__(self):
        self._chroma_client = None

    async def _get_chroma(self):
        """懒加载 ChromaDB 客户端"""
        if self._chroma_client is None:
            try:
                import chromadb
                from app.core.config import settings
                self._chroma_client = chromadb.PersistentClient(
                    path=settings.CHROMA_PERSIST_DIR,
                )
                logger.info(f"ChromaDB 已连接: {settings.CHROMA_PERSIST_DIR}")
            except ImportError:
                logger.warning("chromadb 未安装，使用内置知识库作为 fallback")
            except Exception as e:
                logger.warning(f"ChromaDB 连接失败: {e}，使用内置知识库")
        return self._chroma_client

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
        """检索相关文档 — Langfuse retriever 追踪"""
        logger.info(f"RAG 检索: {query[:50]}...")

        # ── Langfuse: retriever 追踪 ──
        with observe.retriever(
            name="rag-search",
            input={"query": query, "top_k": top_k, "filters": filters},
        ) as ret:
            chroma = await self._get_chroma()
            if chroma is not None:
                try:
                    from app.core.config import settings
                    collection = chroma.get_or_create_collection(
                        name=settings.CHROMA_COLLECTION,
                    )
                    if collection.count() > 0:
                        query_embedding = await embedding_service.encode_single(query)
                        chroma_results = collection.query(
                            query_embeddings=[query_embedding],
                            n_results=top_k,
                        )
                        results = []
                        if chroma_results["ids"] and chroma_results["ids"][0]:
                            for i, doc_id in enumerate(chroma_results["ids"][0]):
                                metadata = chroma_results["metadatas"][0][i] if chroma_results["metadatas"] else {}
                                score = 1.0 - (chroma_results["distances"][0][i] if chroma_results.get("distances") else 0.1 * i)
                                results.append({
                                    "score": score,
                                    "category": metadata.get("category", ""),
                                    "question": metadata.get("question", ""),
                                    "answer": chroma_results["documents"][0][i] if chroma_results["documents"] else "",
                                })

                            if ret is not None:
                                ret.update(
                                    output={
                                        "result_count": len(results),
                                        "top_scores": [r["score"] for r in results[:3]],
                                        "source": "chromadb",
                                    },
                                    metadata={"embedding_model": settings.EMBEDDING_MODEL},
                                )
                            return results
                except Exception as e:
                    logger.warning(f"ChromaDB 查询失败: {e}")

            # Fallback: 使用内置知识库做关键词匹配
            results = self._keyword_search(query, top_k)
            if ret is not None:
                ret.update(
                    output={
                        "result_count": len(results),
                        "top_scores": [r["score"] for r in results[:3]],
                        "source": "built-in-keyword",
                    }
                )
            return results

    def _keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """基于关键词的内置知识库检索"""
        query_lower = query.lower()
        scored = []
        for kb in BUILT_IN_KNOWLEDGE:
            score = 0.0
            for word in query_lower.split():
                if word in kb["question"]:
                    score += 0.8
            for kw in kb["keywords"].split():
                if kw in query_lower:
                    score += 0.3
            if any(w in kb["category"] for w in query_lower.split()):
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

    async def add_document(self, question: str, answer: str, category: str = "", keywords: str = "") -> str:
        """添加文档到向量数据库"""
        text = f"问题: {question}\n答案: {answer}"
        vector_id = f"vec_{hash(text) & 0xFFFFFFFF:08x}"

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

        # 同时加到内置库
        BUILT_IN_KNOWLEDGE.append({
            "id": vector_id,
            "category": category,
            "question": question,
            "answer": answer,
            "keywords": keywords,
        })

        return vector_id


# 全局单例
rag_service = RAGService()
