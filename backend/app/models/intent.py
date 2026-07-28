"""意图模型"""
from sqlalchemy import Column, BigInteger, String, Integer, Boolean, DateTime, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Intent(Base):
    __tablename__ = "intents"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="意图ID")
    intent_name = Column(String(100), nullable=False, comment="意图名称")
    intent_code = Column(String(50), unique=True, nullable=False, comment="意图编码")
    description = Column(String(255), nullable=True, comment="意图描述")
    handler_type = Column(
        SQLEnum("rag", "tool", "transfer", "llm", "fallback"),
        nullable=False,
        comment="处理类型",
    )
    handler_config = Column(JSON, nullable=True, comment="处理配置")
    sample_utterances = Column(Text, nullable=True, comment="示例语料")
    priority = Column(Integer, default=0, comment="优先级")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    messages = relationship("Message", back_populates="intent")
