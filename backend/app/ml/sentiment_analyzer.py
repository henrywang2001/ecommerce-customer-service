"""ML 模块 — 情感分析器"""
from app.services.sentiment_service import SentimentService, SentimentType, sentiment_service

# 重导出以保持模块结构清晰
__all__ = ["SentimentService", "SentimentType", "sentiment_service"]
