"""客服 Agent — 基于 ReAct 架构"""
from typing import Dict, Any, Optional, List
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CustomerServiceAgent(BaseAgent):
    """电商客服 Agent — 整合意图识别、情感分析和工具调用"""

    def __init__(self, session_id: str, user_id: Optional[int] = None):
        super().__init__(session_id, user_id)
        self._init_tools()

    def _init_tools(self):
        """初始化工具集"""
        from app.agents.tools.search_knowledge import SearchKnowledgeTool
        from app.agents.tools.query_order import QueryOrderTool
        from app.agents.tools.query_product import QueryProductTool
        from app.agents.tools.refund_tool import RefundTool
        from app.agents.tools.transfer_human import TransferHumanTool
        from app.agents.tools.create_ticket import CreateTicketTool

        self.register_tool("search_knowledge", SearchKnowledgeTool())
        self.register_tool("query_order", QueryOrderTool())
        self.register_tool("query_product", QueryProductTool())
        self.register_tool("refund", RefundTool())
        self.register_tool("transfer_human", TransferHumanTool())
        self.register_tool("create_ticket", CreateTicketTool())

    async def process(self, input_text: str) -> str:
        """处理用户输入（基础 ReAct 循环）"""
        self.add_to_history("user", input_text)

        # 注意：完整的 ReAct 循环在 chat_service 中实现
        # 这里提供一个简化的单轮处理入口
        return f"Agent {self.agent_id} 已收到消息: {input_text[:50]}..."

    async def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定工具"""
        tool = self.get_tool(tool_name)
        if tool is None:
            return {"success": False, "response": f"未找到工具: {tool_name}"}
        try:
            result = await tool.execute(params)
            return result
        except Exception as e:
            logger.error(f"工具执行失败 [{tool_name}]: {e}")
            return {"success": False, "response": f"工具执行失败: {str(e)}"}
