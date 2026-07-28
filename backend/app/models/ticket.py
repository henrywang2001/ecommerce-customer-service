"""工单模型"""
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="工单ID")
    ticket_no = Column(String(32), unique=True, nullable=False, comment="工单号")
    session_id = Column(BigInteger, nullable=True, comment="关联会话ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    type = Column(
        SQLEnum("complaint", "refund", "consult", "suggestion", "other"),
        nullable=False,
        comment="工单类型",
    )
    title = Column(String(200), nullable=False, comment="工单标题")
    content = Column(Text, nullable=False, comment="工单内容")
    status = Column(
        SQLEnum("pending", "processing", "resolved", "closed"),
        default="pending",
        comment="处理状态",
    )
    priority = Column(
        SQLEnum("low", "normal", "high", "urgent"),
        default="normal",
        comment="优先级",
    )
    assigned_to = Column(BigInteger, nullable=True, comment="处理人")
    resolution = Column(Text, nullable=True, comment="处理结果")
    resolved_at = Column(DateTime, nullable=True, comment="解决时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    user = relationship("User", back_populates="tickets")
