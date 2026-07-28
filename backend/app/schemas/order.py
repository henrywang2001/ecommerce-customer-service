"""订单相关 Pydantic Schemas"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class OrderResponse(BaseModel):
    id: int
    order_no: str
    user_id: int
    status: str
    total_amount: float
    pay_amount: Optional[float] = None
    shipping_address: Optional[Dict[str, Any]] = None
    receiver_name: Optional[str] = None
    receiver_phone: Optional[str] = None
    tracking_no: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    orders: List[OrderResponse]
    total: int
