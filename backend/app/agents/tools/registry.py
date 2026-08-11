"""工具注册表— 单一工具来源 + 意图触发映射。

目标：把「有哪些工具、各自触发哪些意图、是否需要登录」收敛到一处，
使新增工具 = 1 个类 + 1 行 ``@tool`` 装饰器，无需改动 ``CustomerServiceAgent._init_tools``
或 ``chat_service`` 的调度逻辑。

- ``@tool`` 装饰器在类定义时把工具注册进 ``TOOL_REGISTRY``，并把 ``triggers``（意图编码）
  映射进 ``INTENT_TRIGGER_MAP``；``_init_tools`` 只需扫描注册表即可完成注册。
- ``BaseTool`` 是工具抽象基类，约束 ``execute`` 接口，并统一承载
  ``name`` / ``description`` / ``requires_auth`` / ``triggers`` 元数据。
- 注册表支持「意图编码 → 工具」的直接路由（``get_tool_name_for_intent``），
  供 ``CustomerServiceAgent.dispatch_intent`` 使用；``chat_service`` 仍保留其 ``_TOOL_MAP``
  （解析到同一批工具名），二者保持一致的单一事实来源。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type


class BaseTool(ABC):
    """工具抽象基类。

    子类通过 ``@tool(...)`` 声明元数据；``__init__`` 中调用 ``super.__init__``
    即从装饰器元数据拉取 ``name`` / ``requires_auth`` / ``description`` / ``triggers``，
    无需在子类里重复赋值（单一事实来源，杜绝 类元数据漂移）。
    """

    name: str = ""
    description: str = ""
    requires_auth: bool = False
    triggers: List[str] = []

    def __init__(self):
        meta = getattr(type(self), "_tool_meta", None)
        if meta is not None:
            if not self.name:
                self.name = meta.name
            self.requires_auth = meta.requires_auth
            self.triggers = list(meta.triggers or [])
            if not self.description:
                self.description = meta.description or ""

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具，返回统一结构 ``{"success": bool, "response": str, ...}``。"""
        raise NotImplementedError

    def get_schema(self) -> Dict[str, Any]:
        """返回工具的函数调用 schema（供模型选择工具用）。可被子类覆盖。"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }


class _ToolMeta:
    """装饰器写入类的元数据载体。"""

    __slots__ = ("name", "triggers", "requires_auth", "description")

    def __init__(self, name: str, triggers: List[str], requires_auth: bool, description: str):
        self.name = name
        self.triggers = triggers
        self.requires_auth = requires_auth
        self.description = description


# name -> 工具类
TOOL_REGISTRY: Dict[str, Type[BaseTool]] = {}
# intent_code -> 工具名（注册表驱动的意图路由）
INTENT_TRIGGER_MAP: Dict[str, str] = {}


def tool(
    name: str,
    triggers: Optional[List[str]] = None,
    requires_auth: bool = False,
    description: str = "",
):
    """工具注册装饰器。

    用法::

        @tool("query_order", triggers=["order_query"], requires_auth=True,
              description="查询用户订单状态、物流信息、收货地址等")
        class QueryOrderTool(BaseTool):
            ...
    """

    def deco(cls: Type[BaseTool]) -> Type[BaseTool]:
        cls._tool_meta = _ToolMeta(
            name=name,
            triggers=list(triggers or []),
            requires_auth=requires_auth,
            description=description,
        )
        TOOL_REGISTRY[name] = cls
        for t in (triggers or []):
            INTENT_TRIGGER_MAP[t] = name
        return cls

    return deco


def get_all_tool_classes() -> List[Type[BaseTool]]:
    """返回全部已注册工具类（供 ``_init_tools`` 扫描）。"""
    return list(TOOL_REGISTRY.values())


def get_tool_class(name: str) -> Optional[Type[BaseTool]]:
    """按工具名取注册类。"""
    return TOOL_REGISTRY.get(name)


def get_tool_name_for_intent(intent_code: str) -> Optional[str]:
    """意图编码 → 工具名（注册表驱动的意图路由）。"""
    return INTENT_TRIGGER_MAP.get(intent_code)


def get_registered_tool_names() -> List[str]:
    """已注册工具名列表（调试 / 自测用）。"""
    return list(TOOL_REGISTRY.keys())
