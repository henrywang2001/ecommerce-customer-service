"""订单查询工具"""
from typing import Dict, Any, List, Optional
import re
import logging

logger = logging.getLogger(__name__)

# Mock 订单数据
MOCK_ORDERS: Dict[str, Dict] = {
    "ORDER20260315001": {
        "order_no": "ORDER20260315001",
        "product_name": "Apple iPhone 15 Pro Max 256GB",
        "quantity": 1,
        "pay_amount": 9599.00,
        "status": "shipped",
        "status_text": "已发货",
        "tracking_no": "SF1234567890",
        "express_company": "顺丰速运",
        "receiver_name": "张先生",
        "receiver_phone": "138****6789",
        "shipping_address": "北京市朝阳区建国路88号",
        "created_at": "2026-03-15 10:30:00",
        "shipped_at": "2026-03-16 14:20:00",
        "estimated_delivery": "2026-03-18",
    },
    "ORDER20260401001": {
        "order_no": "ORDER20260401001",
        "product_name": "戴森吹风机 HD15",
        "quantity": 1,
        "pay_amount": 2699.00,
        "status": "paid",
        "status_text": "已支付，待发货",
        "tracking_no": None,
        "express_company": None,
        "receiver_name": "李女士",
        "receiver_phone": "139****1234",
        "shipping_address": "上海市浦东新区世纪大道1000号",
        "created_at": "2026-04-01 16:00:00",
        "shipped_at": None,
        "estimated_delivery": None,
    },
    "ORDER20260310005": {
        "order_no": "ORDER20260310005",
        "product_name": "Nike Air Jordan 1 Retro High OG",
        "quantity": 1,
        "pay_amount": 1499.00,
        "status": "delivered",
        "status_text": "已收货",
        "tracking_no": "YT9876543210",
        "express_company": "圆通速递",
        "receiver_name": "王先生",
        "receiver_phone": "136****5678",
        "shipping_address": "广州市天河区体育西路100号",
        "created_at": "2026-03-10 09:00:00",
        "shipped_at": "2026-03-11 08:00:00",
        "estimated_delivery": "2026-03-14",
    },
}


class QueryOrderTool:
    """订单查询工具"""

    def __init__(self):
        self.name = "query_order"
        self.description = "查询用户订单状态、物流信息、收货地址等"
        self.requires_auth = True

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        user_message = params.get("user_message", "")
        user_id = params.get("user_id")
        logger.info(f"订单查询: user_id={user_id}, message={user_message[:50]}")

        try:
            order_no = self._extract_order_no(user_message)
            if order_no:
                return await self._query_by_order_no(order_no, user_id)
            return await self._query_user_orders(user_id)
        except Exception as e:
            logger.error(f"订单查询失败: {e}")
            return {"success": False, "response": "查询服务暂时不可用，请稍后重试。"}

    def _extract_order_no(self, text: str) -> Optional[str]:
        patterns = [
            r'ORDER[\w]{8,20}',
            r'DD[\d]{10,}',
            r'订单号[：:]?\s*([A-Za-z0-9]{10,20})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0) if match.lastindex is None else match.group(1)
        # 如果文本中有 ORDER 开头的字符串
        match = re.search(r'(ORDER[\d]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    async def _query_by_order_no(self, order_no: str, user_id: Optional[int]) -> Dict[str, Any]:
        order = MOCK_ORDERS.get(order_no.upper())
        if not order:
            return {
                "success": False,
                "response": f"未找到订单号 {order_no}，请确认订单号是否正确。",
            }
        return {"success": True, "response": self._format_order_detail(order), "order": order}

    async def _query_user_orders(self, user_id: Optional[int]) -> Dict[str, Any]:
        mock_list = [
            {"order_no": "ORDER20260401001", "product_name": "戴森吹风机 HD15", "pay_amount": 2699.00, "status": "paid", "status_text": "待发货", "created_at": "2026-04-01"},
            {"order_no": "ORDER20260315001", "product_name": "Apple iPhone 15 Pro Max", "pay_amount": 9599.00, "status": "shipped", "status_text": "已发货", "created_at": "2026-03-15"},
            {"order_no": "ORDER20260310005", "product_name": "Nike Air Jordan 1", "pay_amount": 1499.00, "status": "delivered", "status_text": "已收货", "created_at": "2026-03-10"},
        ]
        return {"success": True, "response": self._format_order_list(mock_list), "orders": mock_list}

    def _format_order_detail(self, order: Dict) -> str:
        status_emoji = {"pending": "⏳", "paid": "💳", "shipped": "🚚", "delivered": "✅", "completed": "🎉", "cancelled": "❌", "refunded": "💰"}
        emoji = status_emoji.get(order.get("status", ""), "📦")
        lines = [
            f"📦 订单详情\n",
            f"━━━━━━━━━━━━━━━━━━━━\n",
            f"订单号：{order['order_no']}\n",
            f"商品：{order['product_name']} × {order['quantity']}\n",
            f"实付金额：¥{order['pay_amount']:,.2f}\n",
            f"订单状态：{emoji} {order['status_text']}\n",
        ]
        if order.get("tracking_no"):
            lines.append(f"快递公司：{order['express_company']}\n")
            lines.append(f"运单号：{order['tracking_no']}\n")
            lines.append(f"预计送达：{order['estimated_delivery']}\n")
        lines.extend([
            f"━━━━━━━━━━━━━━━━━━━━\n",
            f"📍 收货信息\n",
            f"{order['receiver_name']} {order['receiver_phone']}\n",
            f"{order['shipping_address']}\n",
            f"下单时间：{order['created_at']}\n",
        ])
        return "".join(lines)

    def _format_order_list(self, orders: List[Dict]) -> str:
        if not orders:
            return "您还没有订单记录。"
        lines = ["📋 您的近期订单：\n\n"]
        status_emoji = {"pending": "⏳", "paid": "💳", "shipped": "🚚", "delivered": "✅", "completed": "🎉"}
        for i, o in enumerate(orders, 1):
            emoji = status_emoji.get(o.get("status", ""), "📦")
            lines.append(f"{i}. {emoji} {o['order_no']}\n   {o['product_name']} — ¥{o['pay_amount']:,.2f} {o['status_text']}\n\n")
        lines.append('回复「查订单 [订单号]」查看详情')
        return "".join(lines)

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {"order_no": {"type": "string", "description": "订单号（可选，不提供返回列表）"}},
                "required": [],
            },
        }
