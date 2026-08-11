"""客服 Agent — 基于 ReAct 架构（集成 Langfuse 追踪）"""
from typing import Dict, Any, Optional, List
import logging
from app.agents.base_agent import BaseAgent
from app.services.observe_service import observe

logger = logging.getLogger(__name__)


class CustomerServiceAgent(BaseAgent):
    """电商客服 Agent — 整合意图识别、情感分析和工具调用"""

    def __init__(self, session_id: str, user_id: Optional[int] = None):
        super().__init__(session_id, user_id)
        self._init_tools()

    def _init_tools(self):
        """初始化工具集 — 扫描工具注册表自动注册（EX-2）。

        新增工具只需在 app/agents/tools 下用 ``@tool`` 注册，无需改动此处；
        注册表为单一事实来源（见 app/agents/tools/registry.py）。
        """
        from app.agents.tools import registry as _reg
        # 触发所有工具模块的类定义（@tool 注册发生在 import 时）
        from app.agents.tools import (  # noqa: F401
            search_knowledge, query_order, query_product,
            refund_tool, transfer_human, create_ticket,
        )
        for cls in _reg.get_all_tool_classes():
            meta = getattr(cls, "_tool_meta", None)
            name = meta.name if meta is not None else getattr(cls, "name", cls.__name__)
            self.register_tool(name, cls())

    async def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定工具 — Langfuse tool 追踪"""
        tool = self.get_tool(tool_name)
        if tool is None:
            return {"success": False, "response": f"未找到工具: {tool_name}"}

        # ── F1: requires_auth 强制执行 ──
        # 需要登录的工具（如 query_order）在未携带已认证 user_id 时直接拦截，
        # 避免匿名用户获取订单等敏感数据。user_id 来自令牌（生产）或登录态（demo），不可伪造。
        if getattr(tool, "requires_auth", False) and not self.user_id:
            return {
                "success": False,
                "response": "🔒 该操作需要登录后查看，请先登录您的账号。",
                "requires_auth": True,
            }

        # ── Langfuse: agent tool 执行追踪 ──
        with observe.tool(
            name=f"agent-tool-{tool_name}",
            input=params,
        ) as tool_span:
            try:
                result = await tool.execute(params)
                if tool_span is not None:
                    tool_span.update(
                        output={
                            "success": result.get("success", False),
                            "response": str(result.get("response", ""))[:200],
                        }
                    )
                return result
            except Exception as e:
                logger.error(f"工具执行失败 [{tool_name}]: {e}")
                if tool_span is not None:
                    tool_span.update(
                        output={},
                        status_message=str(e),
                        level="ERROR",
                    )
                return {"success": False, "response": f"工具执行失败: {str(e)}"}

    async def dispatch_intent(
        self,
        intent_code: str,
        content: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """注册表驱动的意图路由：intent_code → 注册表 → execute(params)（EX-2）。

        ``chat_service`` 仍保留其 ``_TOOL_MAP``（解析到同一批工具名）以兼容既有路由；
        本方法提供「意图编码直达工具」的注册表单一路径，新增意图只需在对应工具的
        ``@tool(triggers=[...])`` 中声明触发词即可，无需改动调度代码。
        """
        from app.agents.tools import registry as _reg

        tool_name = _reg.get_tool_name_for_intent(intent_code)
        if tool_name is None:
            return {
                "success": False,
                "response": f"未找到意图 [{intent_code}] 对应的工具",
            }
        params: Dict[str, Any] = {
            "user_message": content,
            "user_id": user_id if user_id is not None else self.user_id,
            "session_id": session_id if session_id is not None else self.session_id,
        }
        return await self.execute_tool(tool_name, params)
