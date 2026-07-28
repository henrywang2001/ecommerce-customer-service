"""实体抽取"""
import re
from typing import List, Dict, Any


class EntityExtractor:
    """实体抽取器"""

    ENTITY_PATTERNS = {
        "order_no": r'ORDER[\w]{8,20}',
        "phone": r'1[3-9]\d{9}',
        "amount": r'(\d+\.?\d*)\s*元',
        "sku": r'SKU[-\s]?[\w]+',
        "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        "url": r'https?://[^\s]+',
        "date": r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
    }

    def extract(self, text: str) -> List[Dict[str, Any]]:
        """从文本中抽取所有实体"""
        entities = []
        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(0) if match.lastindex is None else match.group(1)
                entities.append({
                    "type": entity_type,
                    "value": value,
                    "start": match.start(),
                    "end": match.end(),
                })
        return entities
