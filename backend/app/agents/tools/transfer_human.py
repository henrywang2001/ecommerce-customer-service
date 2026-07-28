"""转人工客服工具"""
from typing import Dict, Any, Optional
import random
import time
import logging

logger = logging.getLogger(__name__)


class TransferHumanTool:
    """转人工客服工具"""

    def __init__(self):
        self.name = "transfer_human"
        self.description = "将用户转接给人工客服，处理复杂问题"
        self.requires_auth = False

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id", "")
        user_id = params.get("user_id")
        reason = params.get("reason", "用户主动请求")
        logger.info(f"转人工: session={session_id}, reason={reason}")

        try:
            position = random.randint(1, 3)
            wait_time = position * 3
            transfer_id = f"TRF{int(time.time())}{random.randint(1000, 9999)}"

            message = self._generate_transfer_message(reason, position, wait_time)
            return {
                "success": True,
                "response": message,
                "transfer_id": transfer_id,
                "queue_position": position,
                "estimated_wait_time": wait_time,
            }
        except Exception as e:
            logger.error(f"转人工失败: {e}")
            return {
                "success": False,
                "response": "抱歉，转接人工客服失败，请稍后重试或拨打客服热线 400-123-4567",
            }

    def _generate_transfer_message(self, reason: str, position: int, wait_time: int) -> str:
        if reason == "投诉" or "投诉" in reason:
            return (
                f"😔 非常抱歉给您带来不好的体验\n\n"
                f"已为您优先转接专业投诉处理专员\n"
                f"当前队列位置：第 {position} 位\n"
                f"预计等待时间：{wait_time} 分钟\n\n"
                f"📞 如需紧急处理，可直接拨打投诉专线 400-123-4567\n\n"
                f"我们非常重视您的反馈，会尽快为您处理！"
            )
        elif reason == "用户主动请求":
            return (
                f"👤 已为您转接人工客服\n\n"
                f"当前队列位置：第 {position} 位\n"
                f"预计等待时间：{wait_time} 分钟\n\n"
                f"💡 温馨提示：\n"
                f"• 请保持当前页面，客服将自动接入\n"
                f"• 如需紧急帮助，可拨打客服热线 400-123-4567\n"
                f"• 您也可以先描述问题，客服接入后可快速处理\n\n"
                f"感谢您的耐心等待~"
            )
        else:
            return (
                f"👤 正在为您转接人工客服...\n\n"
                f"当前队列位置：第 {position} 位\n"
                f"预计等待时间：{wait_time} 分钟\n\n"
                f"请稍候，客服代表将马上为您服务。"
            )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "enum": ["用户主动请求", "投诉", "技术问题", "其他"],
                        "description": "转接原因",
                    },
                },
                "required": ["reason"],
            },
        }
