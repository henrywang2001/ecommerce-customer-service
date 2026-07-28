"""消息模型"""
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, DateTime, ForeignKey,
    Enum as SQLEnum, DECIMAL, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="消息ID")
    session_id = Column(BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, comment="会话ID")
    sender_type = Column(
        SQLEnum("user", "bot", "agent"),
        nullable=False,
        comment="发送者类型",
    )
    sender_id = Column(BigInteger, nullable=True, comment="发送者ID")
    content = Column(Text, nullable=False, comment="消息内容")
    content_type = Column(
        SQLEnum("text", "image", "voice", "file", "quick_reply"),
        default="text",
        comment="内容类型",
    )
    intent_id = Column(BigInteger, ForeignKey("intents.id", ondelete="SET NULL"), nullable=True, comment="识别的意图ID")
    intent_confidence = Column(DECIMAL(5, 4), nullable=True, comment="意图置信度")
    sentiment = Column(
        SQLEnum("positive", "neutral", "negative"),
        nullable=True,
        comment="情感倾向",
    )
    sentiment_score = Column(DECIMAL(3, 2), nullable=True, comment="情感得分")
    is_human_transfer = Column(Boolean, default=False, comment="是否转人工")
    is_generated = Column(Boolean, default=False, comment="是否AI生成")
    metadata = Column(JSON, nullable=True, comment="元数据")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    session = relationship("Session", back_populates="messages")
    intent = relationship("Intent", back_populates="messages")
