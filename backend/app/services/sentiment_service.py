"""情感分析服务（集成 Langfuse 追踪）"""
from typing import Tuple, Dict
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SentimentService:
    """情感分析服务 — 基于词典+规则"""

    NEGATIVE_WORDS = {
        "非常差": -1.0, "很差": -0.9, "差": -0.8,
        "不满意": -0.7, "失望": -0.7, "生气": -0.9,
        "愤怒": -1.0, "投诉": -0.8, "骗子": -1.0,
        "太差": -0.9, "糟糕": -0.8, "后悔": -0.6,
        "垃圾": -1.0, "烂": -0.9, "坑": -0.7,
        "恶心": -0.9, "无语": -0.6, "气死": -1.0,
        "坑爹": -0.9, "差劲": -0.8, "糊弄": -0.7,
        "忽悠": -0.7, "骗人": -0.9, "假货": -0.9,
        "坏的": -0.6, "坏了": -0.7, "有问题": -0.5,
    }

    POSITIVE_WORDS = {
        "很好": 0.9, "非常好": 1.0, "棒": 0.8,
        "满意": 0.7, "喜欢": 0.8, "感谢": 0.6,
        "谢谢": 0.5, "好评": 0.8, "推荐": 0.7,
        "划算": 0.6, "便宜": 0.5, "漂亮": 0.7,
        "太棒": 1.0, "超赞": 0.9, "完美": 0.9,
        "不错": 0.6, "好用": 0.7, "方便": 0.6,
        "给力": 0.7, "赞": 0.8, "爱了": 0.8,
        "超值": 0.8, "nb": 0.7, "nice": 0.7,
    }

    NEGATION_WORDS = {"不", "没", "无", "非", "别", "勿"}

    async def analyze(self, text: str) -> Tuple[SentimentType, float]:
        """分析文本情感，返回类型和得分"""
        lexicon_score = self._lexicon_analysis(text)
        rule_score = self._rule_analysis(text)
        final_score = lexicon_score * 0.7 + rule_score * 0.3
        # 限制范围
        final_score = max(-1.0, min(1.0, final_score))
        sentiment_type = self._score_to_type(final_score)
        logger.debug(f"情感分析: score={final_score:.2f}, type={sentiment_type}")
        return sentiment_type, final_score

    def _lexicon_analysis(self, text: str) -> float:
        """词典匹配分析"""
        total_score = 0.0
        word_count = 0
        all_words = {**self.NEGATIVE_WORDS, **self.POSITIVE_WORDS}

        for word, score in all_words.items():
            if word in text:
                if self._is_negated(text, word):
                    total_score += score * -0.5  # 否定反转
                else:
                    total_score += score
                word_count += 1

        if word_count == 0:
            return 0.0
        return total_score / word_count

    def _is_negated(self, text: str, word: str) -> bool:
        """检查情感词是否被否定词修饰"""
        for neg in self.NEGATION_WORDS:
            if neg in text:
                idx = text.find(neg)
                w_idx = text.find(word)
                if 0 < w_idx - idx < 5:
                    return True
        return False

    def _rule_analysis(self, text: str) -> float:
        """规则辅助分析"""
        score = 0.0
        # 重复标点/字符可能表示强烈情绪
        if re.findall(r'([!！?？])\1{2,}', text):
            score += 0.15
        # 全大写（英文）可能表示强调
        if re.search(r'[A-Z]{4,}', text):
            score += 0.15
        # 感叹号数量
        exclaim_count = text.count("!") + text.count("！")
        score += exclaim_count * 0.05
        # 问号+感叹号混合（强烈不满）
        if re.search(r'[?？]+[!！]+|[!！]+[?？]+', text):
            score += 0.2
        return min(0.5, score)  # 规则分不超过 0.5

    def _score_to_type(self, score: float) -> SentimentType:
        """得分转类型"""
        if score <= -0.3:
            return SentimentType.NEGATIVE
        elif score >= 0.3:
            return SentimentType.POSITIVE
        return SentimentType.NEUTRAL

    def get_response_strategy(self, sentiment: SentimentType, score: float) -> Dict:
        """获取基于情感的回复策略"""
        strategies = {
            SentimentType.NEGATIVE: {
                "tone": "empathetic",
                "prefix": "很抱歉给您带来不愉快的体验，",
                "action": "建议转人工服务",
                "emoji": "😔",
            },
            SentimentType.NEUTRAL: {
                "tone": "professional",
                "prefix": "您好，",
                "action": "正常服务流程",
                "emoji": "🤖",
            },
            SentimentType.POSITIVE: {
                "tone": "friendly",
                "prefix": "很高兴为您服务，",
                "action": "主动推荐关联服务",
                "emoji": "😊",
            },
        }
        return strategies.get(sentiment, strategies[SentimentType.NEUTRAL])


# 全局单例
sentiment_service = SentimentService()
