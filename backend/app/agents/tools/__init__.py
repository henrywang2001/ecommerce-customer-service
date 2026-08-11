"""工具包 — 导入所有工具模块以触发 ``@tool`` 注册。

导入本包即完成全部工具注册，``CustomerServiceAgent._init_tools`` 只需扫描注册表。
新增工具：在本目录新增一个文件并用 ``@tool`` 装饰，然后在此处补一行导入即可。
"""
from app.agents.tools import (  # noqa: F401
    search_knowledge,
    query_order,
    query_product,
    refund_tool,
    transfer_human,
    create_ticket,
)

from app.agents.tools.registry import (
    BaseTool,
    tool,
    TOOL_REGISTRY,
    INTENT_TRIGGER_MAP,
    get_all_tool_classes,
    get_tool_class,
    get_tool_name_for_intent,
    get_registered_tool_names,
)

__all__ = [
    "BaseTool",
    "tool",
    "TOOL_REGISTRY",
    "INTENT_TRIGGER_MAP",
    "get_all_tool_classes",
    "get_tool_class",
    "get_tool_name_for_intent",
    "get_registered_tool_names",
]
