"""NLU 模块 — 意图分类器（基于 LLM 的版本）"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class IntentClassifier:
    """意图分类器 — 使用 LLM 进行意图分类"""

    INTENT_LABELS = [
        "product_inquiry", "order_query", "refund_request",
        "complaint", "human_agent", "payment_issue",
        "shipping_info", "promotion", "greeting", "fallback",
    ]

    def __init__(self, model_type: str = "llm"):
        self.model_type = model_type

    async def classify(self, text: str) -> Dict[str, Any]:
        """分类文本意图"""
        from app.services.llm_service import llm_service

        prompt = f"""分析用户消息的意图，从下列标签中选一个最匹配的：
标签: {", ".join(self.INTENT_LABELS)}

用户消息: {text}

返回JSON: {{"intent": "标签名", "confidence": 0.0-1.0, "reason": "简短理由"}}"""

        result = await llm_service.generate_json(prompt)
        if result:
            return result
        return {"intent": "fallback", "confidence": 0.3, "reason": "无法识别"}
