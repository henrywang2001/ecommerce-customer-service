"""创建工单工具"""
from typing import Dict, Any
import random
import time
import logging

logger = logging.getLogger(__name__)


class CreateTicketTool:
    """创建客服工单"""

    def __init__(self):
        self.name = "create_ticket"
        self.description = "创建客服工单，记录用户问题和反馈"
        self.requires_auth = True

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id", "")
        user_id = params.get("user_id")
        ticket_type = params.get("type", "consult")
        title = params.get("title", "用户咨询")
        content = params.get("content", "")

        try:
            ticket_no = f"TKT{int(time.time())}{random.randint(100, 999)}"
            type_name = {
                "complaint": "投诉建议", "refund": "退款申请",
                "consult": "业务咨询", "suggestion": "意见反馈", "other": "其他",
            }.get(ticket_type, "其他")

            return {
                "success": True,
                "response": (
                    f"✅ 工单已创建\n\n"
                    f"工单编号：{ticket_no}\n"
                    f"问题类型：{type_name}\n"
                    f"我们的工作人员将在 24 小时内处理\n\n"
                    f"处理结果会通过短信/站内消息通知您。"
                ),
                "ticket_no": ticket_no,
            }
        except Exception as e:
            logger.error(f"创建工单失败: {e}")
            return {"success": False, "response": "工单创建失败，请稍后重试。"}

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["complaint", "refund", "consult", "suggestion"],
                        "description": "工单类型",
                    },
                    "title": {"type": "string", "description": "工单标题"},
                    "content": {"type": "string", "description": "工单内容"},
                },
                "required": ["type", "content"],
            },
        }
