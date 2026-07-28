"""Agent 基类"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类

    提供 Agent 的基础能力：
    - 会话管理
    - 工具注册
    - 状态追踪
    - 历史记录
    """

    def __init__(self, session_id: str, user_id: Optional[int] = None):
        self.session_id = session_id
        self.user_id = user_id
        self.agent_id = str(uuid.uuid4())
        self.state: Dict[str, Any] = {}
        self.tools: Dict[str, Any] = {}
        self.conversation_history: List[Dict[str, str]] = []
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

    def add_to_history(self, role: str, content: str) -> None:
        """添加对话历史"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    def get_history(self, last_n: Optional[int] = None) -> List[Dict]:
        """获取对话历史"""
        if last_n is None:
            return self.conversation_history
        return self.conversation_history[-last_n:]

    def clear_history(self) -> None:
        """清空对话历史"""
        self.conversation_history = []
        logger.info(f"Agent {self.agent_id} 清空对话历史")

    @abstractmethod
    async def process(self, input_text: str) -> str:
        """处理输入（子类必须实现）"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "state": self.state,
            "tools": list(self.tools.keys()),
            "history_count": len(self.conversation_history),
            "created_at": self.created_at,
        }
