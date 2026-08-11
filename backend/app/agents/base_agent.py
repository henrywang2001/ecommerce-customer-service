"""Agent 基类（：无状态执行器）"""
from abc import ABC
from typing import Any, Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类 — 纯执行器，不持有任何会话可变状态。

    职责：
    - 工具注册与执行（工具本身亦为无状态，会话上下文由外部 SessionManager/Redis 持有）。
    - 仅保存构造期注入的不可变标识（session_id / user_id / agent_id / tools / created_at），
      不缓存对话历史、不维护 per-session 可变字典。

    多副本正确性：每次请求经 `SessionManager.prepare` 按会话元数据重建本实例，
    对话上下文从 Redis 加载，因此副本间不会因本地状态而漂移（见 chat_service ）。
    """

    def __init__(self, session_id: str, user_id: Optional[int] = None):
        self.session_id = session_id
        self.user_id = user_id
        self.agent_id = str(uuid.uuid4())
        self.tools: Dict[str, Any] = {}
        self.created_at = __import__("datetime").datetime.now().isoformat()
        logger.info(f"Agent {self.agent_id} 初始化，会话: {session_id}")

    def register_tool(self, name: str, tool: Any) -> None:
        """注册工具"""
        self.tools[name] = tool
        logger.debug(f"工具已注册: {name}")

    def get_tool(self, name: str) -> Optional[Any]:
        """获取工具"""
        return self.tools.get(name)
