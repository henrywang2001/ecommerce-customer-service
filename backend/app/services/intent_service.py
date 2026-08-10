"""意图识别服务（集成 Langfuse 追踪）"""
from typing import List, Optional, Dict, Any
import json
import re
import logging
from app.schemas.intent import IntentResult, Entity
from app.services.llm_service import llm_service
from app.services.observe_service import observe
from app.core.config import settings

logger = logging.getLogger(__name__)

# 预定义意图配置
INTENT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "product_inquiry": {
        "name": "商品咨询",
        "keywords": ["商品", "产品", "多少钱", "价格", "怎么样", "好不好", "推荐", "有货"],
        "handler": "tool",
        "priority": 5,
    },
    "ticket_create": {
        "name": "提交工单",
        "keywords": ["工单", "提交工单", "开个工单", "建工单", "创建工单", "问题反馈"],
        "handler": "tool",
        "priority": 7,
    },
    "order_query": {
        "name": "订单查询",
        "keywords": ["订单", "查订单", "什么时候到", "发货没", "物流", "快递", "到哪了"],
        "handler": "tool",
        "priority": 8,
    },
    "refund_request": {
        "name": "退款退货",
        "keywords": ["退款", "退货", "取消订单", "不想要了", "退钱", "换货"],
        "handler": "tool",
        "priority": 10,
    },
    "complaint": {
        "name": "投诉",
        "keywords": ["投诉", "差评", "太差了", "骗子", "态度差", "举报"],
        "handler": "transfer",
        "priority": 10,
    },
    "human_agent": {
        "name": "转人工",
        "keywords": ["人工", "客服", "真人", "转人工", "人工服务", "找人工"],
        "handler": "transfer",
        "priority": 10,
    },
    "payment_issue": {
        "name": "支付问题",
        "keywords": ["支付", "付款", "扣款", "支付失败", "微信支付", "支付宝"],
        "handler": "rag",
        "priority": 6,
    },
    "shipping_info": {
        "name": "配送查询",
        "keywords": ["配送", "送货", "多久到", "配送时间", "包邮"],
        "handler": "rag",
        "priority": 6,
    },
    "promotion": {
        "name": "促销活动",
        "keywords": ["优惠", "活动", "打折", "满减", "优惠券", "折扣", "促销"],
        "handler": "rag",
        "priority": 5,
    },
    "greeting": {
        "name": "问候",
        "keywords": ["你好", "您好", "hi", "hello", "在吗", "嗨"],
        "handler": "llm",
        "priority": 1,
    },
    "fallback": {
        "name": "其他",
        "keywords": [],
        "handler": "llm",
        "priority": 0,
    },
}


class IntentService:
    """意图识别服务"""

    def __init__(self):
        pass

    async def recognize(self, text: str, user_id: Optional[int] = None) -> IntentResult:
        """识别用户意图 — 多策略融合"""
        logger.info(f"意图识别: {text[:50]}...")

        # 1. 关键词匹配
        keyword_result = self._keyword_match(text)

        # 2. LLM 深度理解（P2 优化：关键词高置信命中则跳过 LLM，意图分类调用减半）
        if keyword_result is not None and keyword_result.confidence >= settings.INTENT_THRESHOLD:
            logger.info("关键词高置信命中，跳过 LLM 意图分类")
            llm_result = None
        else:
            llm_result = await self._llm_understand(text)

        # 3. 多策略融合：取最高置信度*优先级
        final = self._fuse_intents(keyword_result, llm_result)

        # 4. 实体抽取
        entities = self._extract_entities(text, final.intent_code)

        logger.info(f"意图识别结果: {final.intent_code} (置信度: {final.confidence})")
        return IntentResult(
            intent_code=final.intent_code,
            intent_name=final.intent_name,
            confidence=final.confidence,
            entities=entities,
            handler_type=final.handler_type,
            priority=final.priority,
        )

    def _keyword_match(self, text: str) -> Optional[IntentResult]:
        """关键词匹配"""
        text_lower = text.lower()
        best_match = None
        best_priority = 0

        for code, config in INTENT_CONFIGS.items():
            for kw in config["keywords"]:
                if kw.lower() in text_lower:
                    if config["priority"] > best_priority:
                        best_priority = config["priority"]
                        best_match = IntentResult(
                            intent_code=code,
                            intent_name=config.get("name", code),
                            confidence=0.7,
                            entities=[],
                            handler_type=config["handler"],
                            priority=config["priority"],
                        )
                    break  # 已匹配此意图，跳到下一个

        return best_match

    async def _semantic_match(self, text: str) -> Optional[IntentResult]:
        """基于向量相似的语义匹配（预留）"""
        # 可以用 embedding 做语义相似度匹配
        return None

    async def _llm_understand(self, text: str) -> Optional[IntentResult]:
        """LLM 深度意图理解 — Langfuse generation 追踪"""
        prompt = f"""分析以下用户消息的意图，从下列意图中选一个最匹配的：
可选意图: product_inquiry(商品咨询), order_query(订单查询), refund_request(退款退货),
complaint(投诉), human_agent(转人工), payment_issue(支付问题),
shipping_info(配送查询), promotion(促销活动), greeting(问候), fallback(其他)

用户消息: {text}

请返回JSON: {{"intent_code": "xxx", "confidence": 0.0-1.0, "reason": "简短理由"}}"""

        # ── Langfuse: 意图分类 generation 追踪 ──
        with observe.generation(
            name="intent-classify",
            model=llm_service.model,
            input=text,
            model_parameters={"temperature": 0.1, "task": "intent_classification"},
        ) as gen:
            result = await llm_service.generate_json(prompt)
            if result:
                code = result.get("intent_code", "fallback")
                config = INTENT_CONFIGS.get(code, INTENT_CONFIGS["fallback"])
                intent = IntentResult(
                    intent_code=code,
                    intent_name=config.get("name", code),
                    confidence=float(result.get("confidence", 0.6)),
                    entities=[],
                    handler_type=config["handler"],
                    priority=config["priority"],
                )
                if gen is not None:
                    gen.update(output={
                        "intent_code": code,
                        "confidence": intent.confidence,
                        "reason": result.get("reason", ""),
                    })
                return intent
            return None

    def _fuse_intents(self, *intents) -> IntentResult:
        """多策略融合：取置信度*优先级最高的"""
        valid = [i for i in intents if i is not None]
        if not valid:
            return IntentResult(
                intent_code="fallback",
                intent_name="其他",
                confidence=0.5,
                entities=[],
                handler_type="llm",
                priority=0,
            )

        # 综合评分 = 置信度 * (1 + 优先级/10)
        best = max(valid, key=lambda x: x.confidence * (1 + x.priority / 10))
        return best

    def _extract_entities(self, text: str, intent_code: str) -> List[Entity]:
        """实体抽取"""
        entities: List[Entity] = []

        # 订单号
        for match in re.finditer(r'ORDER[\w]{8,20}', text, re.IGNORECASE):
            entities.append(Entity(
                type="order_no", value=match.group(),
                start=match.start(), end=match.end(),
            ))

        # 手机号
        for match in re.finditer(r'1[3-9]\d{9}', text):
            entities.append(Entity(
                type="phone", value=match.group(),
                start=match.start(), end=match.end(),
            ))

        # 金额
        for match in re.finditer(r'(\d+\.?\d*)\s*元', text):
            entities.append(Entity(
                type="amount", value=match.group(1),
                start=match.start(), end=match.end(),
            ))

        # SKU / 商品编号
        for match in re.finditer(r'SKU[-\s]?[\w]+', text, re.IGNORECASE):
            entities.append(Entity(
                type="sku", value=match.group(),
                start=match.start(), end=match.end(),
            ))

        return entities


# 全局单例
intent_service = IntentService()
