"""槽位填充"""
from typing import Dict, Any, Optional


class SlotFilling:
    """槽位填充器 — 根据意图类型收集必要信息"""

    INTENT_SLOTS = {
        "order_query": ["order_no"],
        "refund_request": ["order_no", "reason"],
        "product_inquiry": ["product_name", "category"],
        "complaint": ["order_no", "complaint_type"],
    }

    def __init__(self):
        self.slots: Dict[str, Any] = {}

    def get_required_slots(self, intent_code: str) -> list:
        """获取意图所需的槽位列表"""
        return self.INTENT_SLOTS.get(intent_code, [])

    def fill_slot(self, key: str, value: Any) -> None:
        """填充单个槽位"""
        self.slots[key] = value

    def get_missing_slots(self, intent_code: str, entities: list) -> list:
        """检查缺失的槽位"""
        required = self.get_required_slots(intent_code)
        # 从实体中自动填充
        entity_types = {e["type"]: e["value"] for e in entities} if entities else {}

        missing = []
        for slot in required:
            if slot not in self.slots and slot not in entity_types:
                missing.append(slot)
        return missing

    def is_complete(self, intent_code: str, entities: list = None) -> bool:
        """检查槽位是否完整"""
        return len(self.get_missing_slots(intent_code, entities or [])) == 0
