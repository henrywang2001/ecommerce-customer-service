"""用户模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    # 使用 Integer 而非 BigInteger：SQLite 仅对 INTEGER PRIMARY KEY 自动自增，
    # 便于本地/CI 用 SQLite 验证用户落库（MySQL 下 INT 同样满足用户量级的 ID 空间）。
    id = Column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    username = Column(String(50), unique=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, nullable=True, comment="邮箱")
    phone = Column(String(20), unique=True, nullable=True, comment="手机号")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    user_type = Column(
        SQLEnum("customer", "agent", "admin"),
        default="customer",
        comment="用户类型",
    )
    avatar_url = Column(String(500), nullable=True, comment="头像URL")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    sessions = relationship("Session", back_populates="user")
    orders = relationship("Order", back_populates="user")
    tickets = relationship("Ticket", back_populates="user")
