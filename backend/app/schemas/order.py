"""订单相关 Pydantic Schemas（ 修复：对齐真实返回结构，提供契约校验）

原 OrderResponse 要求 id(int)/created_at(datetime) 等字段，与 Mock 数据及路由实际
返回结构不一致，导致「有 schema 无契约」的脆弱状态。这里改为贴合实际返回（订单号
为主键、时间字符串、富字段）的模型，路由层据此声明 response_model，使契约真实生效。
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class OrderResponse(BaseModel):
    order_no: str
    product_name: Optional[str] = None
    quantity: Optional[int] = None
    pay_amount: Optional[float] = None
    status: Optional[str] = None
    status_text: Optional[str] = None
    tracking_no: Optional[str] = None
    express_company: Optional[str] = None
    receiver_name: Optional[str] = None
    receiver_phone: Optional[str] = None
    shipping_address: Optional[str] = None
    created_at: Optional[str] = None
    shipped_at: Optional[str] = None
    estimated_delivery: Optional[str] = None


class OrderListResponse(BaseModel):
    orders: List[OrderResponse]
    total: int


class OrderDetailResponse(BaseModel):
    success: bool
    order: Optional[OrderResponse] = None
    message: Optional[str] = None
