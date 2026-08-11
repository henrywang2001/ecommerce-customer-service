"""知识库检索工具"""
from typing import Dict, Any, List
import logging
from app.services.rag_service import rag_service
from app.agents.tools.registry import BaseTool, tool

logger = logging.getLogger(__name__)


@tool("search_knowledge", triggers=[], requires_auth=False,
      description="从知识库中检索商品信息、平台政策、常见问题等")
class SearchKnowledgeTool(BaseTool):
    """从知识库检索相关信息"""

    def __init__(self):
        super().__init__()

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        user_message = params.get("user_message", "")
        top_k = params.get("top_k", 3)
        logger.info(f"知识库检索: {user_message[:50]}...")

        try:
            results = await rag_service.search(user_message, top_k)
            if not results:
                return {
                    "success": False,
                    "response": "抱歉，知识库中没有找到相关信息，建议咨询人工客服。",
                    "results": [],
                    "source": "knowledge_base",
                }

            response = self._format_response(results, user_message)
            return {
                "success": True,
                "response": response,
                "results": results,
                "source": "knowledge_base",
            }
        except Exception as e:
            logger.error(f"知识库检索失败: {e}")
            return {
                "success": False,
                "response": "检索服务暂时不可用，请稍后重试。",
                "results": [],
                "source": "knowledge_base",
            }

    def _format_response(self, results: List[Dict], query: str) -> str:
        if not results:
            return "抱歉，未找到相关信息。"

        best = results[0]
        parts = []
        if best.get("score", 0) >= 0.8:
            parts.append(f"根据您的疑问，我找到以下信息：\n\n📖 {best['answer']}\n\n")
        elif best.get("score", 0) >= 0.5:
            parts.append(f"您可能想了解的是：\n\n{best['answer']}\n\n")
        else:
            parts.append(f"{best['answer']}\n\n")

        if len(results) > 1:
            parts.append("💡 您可能还想了解：")
            for r in results[1:3]:
                parts.append(f"\n • {r['question']}")

        parts.append(f"\n\n📂 来源：{best.get('category', '知识库')}")
        return "".join(parts)

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "category": {"type": "string", "description": "知识库分类（可选）"},
                    "top_k": {"type": "integer", "description": "返回结果数量", "default": 3},
                },
                "required": ["query"],
            },
        }
