"""订单模型"""
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Enum as SQLEnum, DECIMAL, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="订单ID")
    order_no = Column(String(32), unique=True, nullable=False, comment="订单号")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    status = Column(
        SQLEnum("pending", "paid", "shipped", "delivered", "completed", "cancelled", "refunded"),
        default="pending",
        comment="订单状态",
    )
    total_amount = Column(DECIMAL(10, 2), nullable=False, comment="订单总金额")
    pay_amount = Column(DECIMAL(10, 2), nullable=True, comment="实付金额")
    shipping_address = Column(JSON, nullable=True, comment="收货地址")
    receiver_name = Column(String(50), nullable=True, comment="收货人")
    receiver_phone = Column(String(20), nullable=True, comment="联系电话")
    tracking_no = Column(String(50), nullable=True, comment="物流单号")
    remark = Column(Text, nullable=True, comment="订单备注")
    paid_at = Column(DateTime, nullable=True, comment="支付时间")
    shipped_at = Column(DateTime, nullable=True, comment="发货时间")
    delivered_at = Column(DateTime, nullable=True, comment="收货时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    user = relationship("User", back_populates="orders")
