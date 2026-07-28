"""订单服务 API 路由"""
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

# Mock 订单数据
MOCK_ORDERS = [
    {"id": 1, "order_no": "ORDER20260401001", "user_id": 1, "status": "paid",
     "total_amount": 2999.00, "pay_amount": 2699.00,
     "receiver_name": "李女士", "receiver_phone": "139****1234",
     "tracking_no": None, "created_at": "2026-04-01T16:00:00"},
    {"id": 2, "order_no": "ORDER20260315001", "user_id": 1, "status": "shipped",
     "total_amount": 9999.00, "pay_amount": 9599.00,
     "receiver_name": "张先生", "receiver_phone": "138****6789",
     "tracking_no": "SF1234567890", "created_at": "2026-03-15T10:30:00",
     "shipped_at": "2026-03-16T14:20:00"},
    {"id": 3, "order_no": "ORDER20260310005", "user_id": 1, "status": "delivered",
     "total_amount": 1499.00, "pay_amount": 1499.00,
     "receiver_name": "王先生", "receiver_phone": "136****5678",
     "tracking_no": "YT9876543210", "created_at": "2026-03-10T09:00:00"},
]


@router.get("/list")
async def list_orders(user_id: Optional[int] = Query(None), status: Optional[str] = Query(None)):
    """获取订单列表"""
    orders = MOCK_ORDERS
    if user_id:
        orders = [o for o in orders if o["user_id"] == user_id]
    if status:
        orders = [o for o in orders if o["status"] == status]
    return {"orders": orders, "total": len(orders)}


@router.get("/detail/{order_no}")
async def order_detail(order_no: str):
    """获取订单详情"""
    for order in MOCK_ORDERS:
        if order["order_no"].upper() == order_no.upper():
            return {"success": True, "order": order}
    return {"success": False, "message": f"未找到订单: {order_no}"}
