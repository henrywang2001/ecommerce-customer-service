"""商品查询工具（F5 修复：商品数据统一从 app.data.mock_data 读取，杜绝双源漂移）"""
from typing import Dict, Any, List
import logging

from app.data.mock_data import PRODUCTS

logger = logging.getLogger(__name__)

# Mock 商品数据（单一来源，见 app/data/mock_data.py）
MOCK_PRODUCTS = PRODUCTS

CATEGORY_KEYWORDS = [
    "手机", "电脑", "平板", "耳机", "音箱", "相机",
    "衣服", "鞋子", "包包", "化妆品", "护肤品",
    "家电", "家具", "玩具", "图书", "食品",
    "iPhone", "Nike", "Adidas", "Apple", "戴森",
    "小米", "华为", "三星", "索尼", "飞利浦",
]


class QueryProductTool:
    """商品查询工具"""

    def __init__(self):
        self.name = "query_product"
        self.description = "搜索商品信息、查询库存、价格和促销活动"
        self.requires_auth = False

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        user_message = params.get("user_message", "")
        try:
            keywords = self._extract_keywords(user_message)
            if not keywords:
                return {
                    "success": True,
                    "response": "请告诉我您想查询什么商品？比如「iPhone手机」或「运动鞋」。",
                    "products": [],
                }
            products = self._search_products(keywords)
            return {
                "success": True,
                "response": self._format_product_list(products, keywords),
                "products": products,
            }
        except Exception as e:
            logger.error(f"商品查询失败: {e}")
            return {"success": False, "response": "商品查询服务暂时不可用。"}

    def _extract_keywords(self, text: str) -> List[str]:
        found = []
        text_lower = text.lower()
        for cat in CATEGORY_KEYWORDS:
            if cat.lower() in text_lower:
                found.append(cat)
        if not found:
            import re
            words = re.findall(r'[一-龥]{2,}|[\w]{3,}', text)
            found = words[:2]
        return found

    def _search_products(self, keywords: List[str]) -> List[Dict]:
        scored = []
        for product in MOCK_PRODUCTS:
            product_text = f"{product['name']} {product['brand']} {product['category']}".lower()
            score = sum(1.0 for kw in keywords if kw.lower() in product_text)
            if kw_lower := keywords[0].lower():
                if kw_lower in product["brand"].lower():
                    score += 0.5
            if score > 0:
                item = product.copy()
                item["match_score"] = score
                scored.append(item)
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored[:5]

    def _format_product_list(self, products: List[Dict], keywords: List[str]) -> str:
        if not products:
            return f'抱歉，暂未找到与"{" ".join(keywords)}"相关的商品。'
        lines = [f"🔍 为您找到 {len(products)} 件相关商品：\n\n"]
        for i, p in enumerate(products, 1):
            if p["original_price"] > p["price"]:
                discount = int((1 - p["price"] / p["original_price"]) * 100)
                price_str = f"¥{p['price']:,.2f} ~~¥{p['original_price']:,.2f}~~ ({discount}% OFF)"
            else:
                price_str = f"¥{p['price']:,.2f}"
            stock_status = "✅有货" if p["stock"] > 10 else ("⚠️库存紧张" if p["stock"] > 0 else "❌缺货")
            lines.append(
                f"{i}. **{p['name']}**\n"
                f" 💰 {price_str} | ⭐{p['rating']} | 🛒已售{p['sales']}\n"
                f" {stock_status} | {p['brand']} | {p['category']}\n\n"
            )
        lines.append('回复「商品 [编号]」查看详情，如：商品 P001')
        return "".join(lines)

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {"type": "string", "description": "商品关键词"},
                    "category": {"type": "string", "description": "商品分类"},
                },
                "required": ["keywords"],
            },
        }
