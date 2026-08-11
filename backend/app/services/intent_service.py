"""意图识别服务（集成 Langfuse 追踪）

EX-1 声明式意图配置
--------------------
- ``IntentSpec`` 为单一来源（single source of truth），集中每个意图的
  keywords / handler / priority / prompt_label / synonyms；
- ``INTENT_CONFIGS``、``_INTENT_SYNONYMS`` 以及 LLM 提示词全部由 ``INTENT_SPECS``
  自动派生。新增（或调整）一个意图 = 往 ``INTENT_SPECS`` 追加一条 ``IntentSpec``，
  **零识别逻辑改动**。

公共 API 约束：``recognize()`` 的签名与返回结构保持不变，chat_service.py 等调用方无需改动。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import re
import logging

from app.schemas.intent import IntentResult, Entity
from app.services.llm_service import llm_service as _default_llm_service
from app.services.observe_service import observe
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class IntentSpec:
    """意图声明式规格 —— 唯一需要维护的意图配置。

    新增/调整意图只改这里，识别逻辑（关键词匹配、LLM 提示词渲染、同义词归一）
    全部基于本规格自动派生，无需改动任何代码。
    """

    code: str
    name: str                       # IntentResult.intent_name 使用的中文名
    keywords: List[str]             # 关键词匹配词表
    handler: str                    # 处理类型: rag / tool / transfer / llm
    priority: int                   # 优先级（用于多策略融合）
    prompt_label: str               # LLM 提示词中展示的标签，如 "退款退货"
    synonyms: List[str] = field(default_factory=list)  # 近义/口语化意图码 → 本意图


# ── 单一来源：声明式意图配置 ───────────────────────────────────────────────
# 新增意图 = 在此追加一条 IntentSpec，识别逻辑零改动。
INTENT_SPECS: List[IntentSpec] = [
    IntentSpec(
        code="product_inquiry", name="商品咨询", handler="tool", priority=5,
        prompt_label="商品咨询",
        keywords=["商品", "产品", "多少钱", "价格", "怎么样", "好不好", "推荐", "有货"],
        synonyms=["商品咨询", "商品查询", "产品咨询", "产品查询"],
    ),
    IntentSpec(
        code="ticket_create", name="提交工单", handler="tool", priority=7,
        prompt_label="提交工单",
        keywords=["工单", "提交工单", "开个工单", "建工单", "创建工单", "问题反馈"],
        synonyms=[],
    ),
    IntentSpec(
        code="order_query", name="订单查询", handler="tool", priority=8,
        prompt_label="订单查询",
        keywords=["订单", "查订单", "什么时候到", "发货没", "物流", "快递", "到哪了"],
        synonyms=["查订单", "订单查询", "我的订单"],
    ),
    IntentSpec(
        code="refund_request", name="退款退货", handler="tool", priority=10,
        prompt_label="退款退货",
        keywords=["退款", "退货", "取消订单", "不想要了", "退钱", "换货"],
        synonyms=["取消订单", "退单", "退货退款"],
    ),
    IntentSpec(
        code="complaint", name="投诉", handler="transfer", priority=10,
        prompt_label="投诉",
        keywords=["投诉", "差评", "太差了", "骗子", "态度差", "举报"],
        synonyms=["投诉建议", "举报", "差评"],
    ),
    IntentSpec(
        code="human_agent", name="转人工", handler="transfer", priority=10,
        prompt_label="转人工",
        keywords=["人工", "客服", "真人", "转人工", "人工服务", "找人工"],
        synonyms=["人工客服", "找人工", "转人工", "真人"],
    ),
    IntentSpec(
        code="payment_issue", name="支付问题", handler="rag", priority=6,
        prompt_label="支付问题",
        keywords=["支付", "付款", "扣款", "支付失败", "微信支付", "支付宝"],
        synonyms=["支付问题", "付款问题", "扣款"],
    ),
    IntentSpec(
        code="shipping_info", name="配送查询", handler="rag", priority=6,
        prompt_label="配送查询",
        keywords=["配送", "送货", "多久到", "配送时间", "包邮"],
        synonyms=["物流查询", "物流", "查物流", "快递查询", "配送查询", "配送"],
    ),
    IntentSpec(
        code="promotion", name="促销活动", handler="rag", priority=5,
        prompt_label="促销活动",
        keywords=["优惠", "活动", "打折", "满减", "优惠券", "折扣", "促销"],
        synonyms=["促销活动", "优惠活动", "打折"],
    ),
    IntentSpec(
        code="greeting", name="问候", handler="llm", priority=1,
        prompt_label="问候",
        keywords=["你好", "您好", "hi", "hello", "在吗", "嗨"],
        synonyms=["打招呼", "问候", "你好"],
    ),
    IntentSpec(
        code="fallback", name="其他", handler="llm", priority=0,
        prompt_label="其他",
        keywords=[],
        synonyms=[],
    ),
]


# 由单一来源派生的查表表（保留对外名字 INTENT_CONFIGS，值为 IntentSpec）
INTENT_CONFIGS: Dict[str, IntentSpec] = {s.code: s for s in INTENT_SPECS}

# 由单一来源派生的同义词表（B8 修复：口语化/近义意图码 → 标准码）
_INTENT_SYNONYMS: Dict[str, str] = {
    syn: s.code for s in INTENT_SPECS for syn in s.synonyms
}


def _render_intent_prompt(text: str) -> str:
    """由 INTENT_SPECS 单一来源渲染 LLM 意图分类提示词。

    新增意图后此提示词自动包含新意图，无需改动任何代码。
    """
    intent_lines = ", ".join(f"{s.code}({s.prompt_label})" for s in INTENT_SPECS)
    return f"""分析以下用户消息的意图，从下列意图中选一个最匹配的：
可选意图: {intent_lines}

用户消息: {text}

请返回JSON: {{"intent_code": "xxx", "confidence": 0.0-1.0, "reason": "简短理由"}}"""


class IntentService:
    """意图识别服务"""

    def __init__(self, llm_service=None):
        # 默认复用全局 LLM 服务；测试可注入 fake LLM 服务。
        self.llm_service = llm_service if llm_service is not None else _default_llm_service

    async def recognize(self, text: str, user_id: Optional[int] = None, preferred_intent: Optional[str] = None) -> IntentResult:
        """识别用户意图 — 多策略融合

        F12 修复：若调用方已预识别意图（如 Agent 路由携带 intent_code）且意图码合法，
        直接采用预识别结果（高置信），跳过 LLM，既省一次调用也保证前后链路意图一致；
        否则走原有的「关键词 + LLM」多策略融合。

        B13 修复（更完善）：text 可能为 None（调用方未传 / 异常负载 / 上游解析失败）。
        原报告仅建议在日志切片处加 `or ""`，但运行时实测真正崩溃点在
        `_keyword_match` 内部的 `text.lower()`（text 为 None 时抛 AttributeError）。
        故在此统一将 text 归一为字符串；None/空串直接短路返回 fallback 意图，
        既杜绝崩溃，也避免对空文本发起无意义的 LLM 调用。
        """
        # B13：归一化为字符串，杜绝下游 text.lower() 在 None 上抛 AttributeError
        safe_text = text if isinstance(text, str) else ""
        logger.info(f"意图识别: {safe_text[:50]}...")  # 日志切片安全（双保险）

        # F12：预识别意图优先（仅当意图码在已知配置内，不依赖 text）
        if preferred_intent and preferred_intent in INTENT_CONFIGS:
            config = INTENT_CONFIGS[preferred_intent]
            return IntentResult(
                intent_code=preferred_intent,
                intent_name=config.name,
                confidence=0.95,
                entities=[],
                handler_type=config.handler,
                priority=config.priority,
            )

        # B13：空文本（None 已归一为 "" 或用户传入空白串）直接兜底，
        # 避免对空文本调用 LLM 造成浪费与潜在异常。
        if not safe_text.strip():
            cfg = INTENT_CONFIGS["fallback"]
            logger.info("输入文本为空，直接返回 fallback 意图")
            return IntentResult(
                intent_code="fallback",
                intent_name=cfg.name,
                confidence=0.0,
                entities=[],
                handler_type=cfg.handler,
                priority=cfg.priority,
            )

        text = safe_text
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
            for kw in config.keywords:
                if kw.lower() in text_lower:
                    if config.priority > best_priority:
                        best_priority = config.priority
                        best_match = IntentResult(
                            intent_code=code,
                            intent_name=config.name,
                            confidence=0.7,
                            entities=[],
                            handler_type=config.handler,
                            priority=config.priority,
                        )
                    break  # 已匹配此意图，跳到下一个

        return best_match

    def _normalize_intent_code(self, code: str, text: str) -> Optional[str]:
        """B8 修复：将 LLM 返回的（可能不在配置表中的）意图码归一为已知标准码。

        原实现用 ``INTENT_CONFIGS.get(code, fallback)``，未知码整体当作 fallback
        （handler_type="llm"、priority=0），在 _fuse_intents 中几乎必输给关键词匹配，
        导致「LLM 已识别的意图」被丢弃，用户问题被错误走通用 LLM。

        归一策略：
        1) 已是标准码 → 直接采用；
        2) 命中同义词表（近义/口语化表述）→ 映射到标准码；
        3) 模糊包含标准码或意图名 → 映射；
        4) 仍未知 → 回退到关键词匹配结果（保留意图信号），
           若关键词也无结果则交给上层 fallback，而非强制 LLM fallback。
        """
        if not code:
            return None
        if code in INTENT_CONFIGS:
            return code
        # 2) 同义词/近义码映射（精确 / 互相包含）
        for key, val in _INTENT_SYNONYMS.items():
            if key == code or key in code or code in key:
                return val
        # 3) 模糊：是否包含已知意图码或意图名
        cl = code.lower()
        for known in INTENT_CONFIGS:
            if known in cl or cl in known:
                return known
        for known, cfg in INTENT_CONFIGS.items():
            name = cfg.name
            if name and name in code:
                return known
        # 4) 仍未知 → 退回关键词匹配，避免使用错误意图
        kw = self._keyword_match(text)
        if kw is not None:
            return kw.intent_code
        return None

    async def _llm_understand(self, text: str) -> Optional[IntentResult]:
        """LLM 深度意图理解 — Langfuse generation 追踪"""
        # EX-1：提示词由 INTENT_SPECS 单一来源渲染，新增意图自动纳入候选
        prompt = _render_intent_prompt(text)

        # ── Langfuse: 意图分类 generation 追踪 ──
        with observe.generation(
            name="intent-classify",
            model=self.llm_service.model,
            input=text,
            model_parameters={"temperature": 0.1, "task": "intent_classification"},
        ) as gen:
            result = await self.llm_service.generate_json(prompt, max_tokens=256)
            if result:
                raw_code = result.get("intent_code", "fallback")
                code = self._normalize_intent_code(raw_code, text)
                if code is None:
                    # 未知码且无法归一 → 不强制 LLM fallback，交给上层（关键词/默认）处理
                    return None
                config = INTENT_CONFIGS[code]
                intent = IntentResult(
                    intent_code=code,
                    intent_name=config.name,
                    confidence=float(result.get("confidence", 0.6)),
                    entities=[],
                    handler_type=config.handler,
                    priority=config.priority,
                )
                if gen is not None:
                    gen.update(output={
                        "intent_code": code,
                        "raw_intent_code": raw_code,
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
