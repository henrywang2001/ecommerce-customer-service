"""会话模型"""
from sqlalchemy import (
    Column, BigInteger, String, Integer, DateTime, ForeignKey, Enum as SQLEnum, SmallInteger
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="会话ID")
    session_id = Column(String(64), unique=True, nullable=False, comment="会话唯一标识")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    agent_id = Column(BigInteger, nullable=True, comment="分配的Agent ID")
    status = Column(
        SQLEnum("active", "waiting", "transferred", "closed"),
        default="active",
        comment="会话状态",
    )
    channel = Column(String(20), default="web", comment="来源渠道")
    started_at = Column(DateTime, default=datetime.utcnow, comment="开始时间")
    ended_at = Column(DateTime, nullable=True, comment="结束时间")
    last_message_at = Column(DateTime, nullable=True, comment="最后消息时间")
    message_count = Column(Integer, default=0, comment="消息数量")
    satisfaction_score = Column(SmallInteger, nullable=True, comment="满意度评分")

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session")
