"""Agent 基类"""
from abc import ABC
from typing import Any, Dict, Optional
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类

    提供 Agent 的基础能力：
    - 工具注册
    - 状态追踪
    - 会话上下文由外部 SessionManager 持有，Agent 本身保持无状态

    说明：原实现中的「会话历史管理」与抽象方法属于冗余伪抽象，
    实际编排逻辑在 chat_service 中完成，无外部调用方。
    此处已移除死代码，使 Agent 明确为「工具容器 + 无状态执行器」。
    """

    def __init__(self, session_id: str, user_id: Optional[int] = None):
        self.session_id = session_id
        self.user_id = user_id
        self.agent_id = str(uuid.uuid4())
        self.state: Dict[str, Any] = {}
        self.tools: Dict[str, Any] = {}
        self.created_at = datetime.now().isoformat()
        logger.info(f"Agent {self.agent_id} 初始化，会话: {session_id}")

    def register_tool(self, name: str, tool: Any) -> None:
        """注册工具"""
        self.tools[name] = tool
        logger.debug(f"工具已注册: {name}")

    def get_tool(self, name: str) -> Optional[Any]:
        """获取工具"""
        return self.tools.get(name)

    def update_state(self, key: str, value: Any) -> None:
        """更新状态"""
        self.state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """获取状态"""
        return self.state.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "state": self.state,
            "tools": list(self.tools.keys()),
            "created_at": self.created_at,
        }
