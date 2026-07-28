"""退款退货工具"""
from typing import Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


class RefundTool:
    """退款退货处理工具"""

    def __init__(self):
        self.name = "refund"
        self.description = "处理退款退货申请、取消订单、查询退款进度"
        self.requires_auth = True

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        user_message = params.get("user_message", "")
        user_id = params.get("user_id")
        logger.info(f"退款处理: {user_message[:50]}")

        try:
            if any(w in user_message for w in ["取消", "撤单", "不要了"]):
                return await self._handle_cancel_order(user_message, user_id)
            elif any(w in user_message for w in ["退货", "退回"]):
                return await self._handle_return_goods(user_message, user_id)
            elif any(w in user_message for w in ["退款", "退钱", "返款", "进度"]):
                return await self._handle_refund(user_message, user_id)
            else:
                return await self._handle_refund_consult()
        except Exception as e:
            logger.error(f"退款处理失败: {e}")
            return {"success": False, "response": "服务处理失败，请稍后重试或联系人工客服。"}

    async def _handle_cancel_order(self, message: str, user_id: Optional[int]) -> Dict[str, Any]:
        order_no = self._extract_order_no(message)
        if order_no:
            return {
                "success": True,
                "response": (
                    f"✅ 已为您提交取消订单 {order_no} 的申请\n\n"
                    f"订单取消后：\n"
                    f"• 支付金额将在 1-3 个工作日内原路退回\n"
                    f"• 如已发货，需等待快递退回后再处理退款\n\n"
                    f"如有疑问，请联系人工客服。"
                ),
                "action": "cancel_order",
                "order_no": order_no,
            }
        return {
            "success": True,
            "response": (
                "请提供您要取消的订单号，格式如：\n"
                "• 取消订单 ORDER20260315001\n\n"
                "或者我帮您查询最近的待发货订单？"
            ),
        }

    async def _handle_return_goods(self, message: str, user_id: Optional[int]) -> Dict[str, Any]:
        order_no = self._extract_order_no(message) or "ORDER20260315001"
        return {
            "success": True,
            "response": (
                f"📦 退货申请已受理（订单 {order_no}）\n\n"
                f"退货流程：\n"
                f"1. 请在 7 天内将商品寄回（保持完好）\n"
                f"2. 寄回地址：广东省深圳市龙华区xxx仓库\n"
                f"   （退货码：R{order_no[5:]}）\n"
                f"3. 我们收到商品后 1-3 个工作日退款\n\n"
                f"📌 退货说明：\n"
                f"• 7 天无理由退货（商品不影响二次销售）\n"
                f"• 质量问题我们承担运费\n"
                f"• 退换货可选择上门取件或自行寄回\n\n"
                f"需要帮您申请上门取件服务吗？"
            ),
            "action": "return_goods",
            "order_no": order_no,
        }

    async def _handle_refund(self, message: str, user_id: Optional[int]) -> Dict[str, Any]:
        return {
            "success": True,
            "response": (
                "💰 您的退款信息：\n\n"
                "【退款中】\n"
                "• 订单 ORDER20260228003\n"
                "• 退款金额：¥299.00\n"
                "• 退款方式：原路退回（支付宝）\n"
                "• 预计到账：1-3 个工作日\n\n"
                "【已完成】\n"
                "• 订单 ORDER20260115008\n"
                "• 退款金额：¥59.00\n"
                "• 到账时间：2026-01-18\n\n"
                "如需了解更多，请提供订单号。"
            ),
        }

    async def _handle_refund_consult(self) -> Dict[str, Any]:
        return {
            "success": True,
            "response": (
                "📋 退款政策说明：\n\n"
                "【退款时效】\n"
                "• 取消订单：1-3 个工作日原路退回\n"
                "• 退货退款：收到商品后 1-3 个工作日\n"
                "• 退款至原支付账户\n\n"
                "【特殊情况】\n"
                "• 节假日顺延至下一个工作日\n"
                "• 银行转账可能延迟 1-2 天\n"
                "• 超时请联系客服处理\n\n"
                "您想了解哪方面的退款问题？"
            ),
        }

    def _extract_order_no(self, text: str) -> Optional[str]:
        match = re.search(r'ORDER[\w]{8,20}', text, re.IGNORECASE)
        return match.group(0) if match else None

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["cancel", "return", "refund", "query"],
                        "description": "操作类型",
                    },
                    "order_no": {"type": "string", "description": "订单号"},
                    "reason": {"type": "string", "description": "退款/退货原因"},
                },
                "required": ["action"],
            },
        }
