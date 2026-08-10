"""订单查询工具（F5 修复：订单数据统一从 app.data.mock_data 读取，杜绝双源漂移）"""
from typing import Dict, Any, List, Optional
import re
import logging

from app.data.mock_data import ORDERS

logger = logging.getLogger(__name__)

# Mock 订单数据（单一来源，见 app/data/mock_data.py）
MOCK_ORDERS = ORDERS


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
        # F5：直接由单一数据源 ORDERS 派生，不再维护一份独立写死的列表
        mock_list = [
            {
                "order_no": o["order_no"],
                "product_name": o["product_name"],
                "pay_amount": o["pay_amount"],
                "status": o["status"],
                "status_text": o["status_text"],
                "created_at": o["created_at"],
            }
            for o in ORDERS.values()
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
