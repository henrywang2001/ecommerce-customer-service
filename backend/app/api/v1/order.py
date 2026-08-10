"""订单服务 API 路由（F3/F5 修复：单一数据源 + 声明 response_model 对齐契约）"""
from fastapi import APIRouter, Query
from typing import Optional

from app.data.mock_data import ORDERS
from app.schemas.order import OrderListResponse, OrderDetailResponse, OrderResponse

router = APIRouter()


@router.get("/list", response_model=OrderListResponse)
async def list_orders(user_id: Optional[int] = Query(None), status: Optional[str] = Query(None)):
    """获取订单列表（数据来自统一 Mock 来源 app.data.mock_data.ORDERS）"""
    orders = list(ORDERS.values())
    if status:
        orders = [o for o in orders if o["status"] == status]
    return OrderListResponse(orders=[OrderResponse(**o) for o in orders], total=len(orders))


@router.get("/detail/{order_no}", response_model=OrderDetailResponse)
async def order_detail(order_no: str):
    """获取订单详情"""
    order = ORDERS.get(order_no.upper())
    if order:
        return OrderDetailResponse(success=True, order=OrderResponse(**order))
    return OrderDetailResponse(success=False, message=f"未找到订单: {order_no}")
