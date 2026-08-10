"""统一的 Mock 数据来源（F5 修复：订单/商品收敛单一数据源）

原实现中，订单/商品数据在「路由层（order.py / product.py）」与「对话工具层
（query_order.py / query_product.py）」各维护一套，字段命名与取值互相独立，
任何一端修正都不会同步到另一端，必然逐步漂移。

本模块作为唯一权威来源（single source of truth），路由与工具均从这里读取，
从源头消除数据漂移。记录采用对话工具所需的「富字段」结构（product_name /
status_text / rating / sales / tags 等），路由层据此对外暴露，契约保持一致。
"""
from typing import Dict, List, Any

# ===== 订单（以订单号为主键）=====
ORDERS: Dict[str, Dict[str, Any]] = {
    "ORDER20260315001": {
        "order_no": "ORDER20260315001",
        "product_name": "Apple iPhone 15 Pro Max 256GB",
        "quantity": 1,
        "pay_amount": 9599.00,
        "status": "shipped",
        "status_text": "已发货",
        "tracking_no": "SF1234567890",
        "express_company": "顺丰速运",
        "receiver_name": "张先生",
        "receiver_phone": "138****6789",
        "shipping_address": "北京市朝阳区建国路88号",
        "created_at": "2026-03-15 10:30:00",
        "shipped_at": "2026-03-16 14:20:00",
        "estimated_delivery": "2026-03-18",
    },
    "ORDER20260401001": {
        "order_no": "ORDER20260401001",
        "product_name": "戴森吹风机 HD15",
        "quantity": 1,
        "pay_amount": 2699.00,
        "status": "paid",
        "status_text": "已支付，待发货",
        "tracking_no": None,
        "express_company": None,
        "receiver_name": "李女士",
        "receiver_phone": "139****1234",
        "shipping_address": "上海市浦东新区世纪大道1000号",
        "created_at": "2026-04-01 16:00:00",
        "shipped_at": None,
        "estimated_delivery": None,
    },
    "ORDER20260310005": {
        "order_no": "ORDER20260310005",
        "product_name": "Nike Air Jordan 1 Retro High OG",
        "quantity": 1,
        "pay_amount": 1499.00,
        "status": "delivered",
        "status_text": "已收货",
        "tracking_no": "YT9876543210",
        "express_company": "圆通速递",
        "receiver_name": "王先生",
        "receiver_phone": "136****5678",
        "shipping_address": "广州市天河区体育西路100号",
        "created_at": "2026-03-10 09:00:00",
        "shipped_at": "2026-03-11 08:00:00",
        "estimated_delivery": "2026-03-14",
    },
}

# ===== 商品 =====
PRODUCTS: List[Dict[str, Any]] = [
    {
        "id": "P001", "sku": "SKU-IPHONE15PM-256",
        "name": "Apple iPhone 15 Pro Max 256GB 钛金属色",
        "category": "手机", "brand": "Apple",
        "price": 9999.00, "original_price": 10999.00,
        "stock": 50, "rating": 4.9, "sales": 12580,
        "tags": ["旗舰", "5G", "钛金属"],
    },
    {
        "id": "P002", "sku": "SKU-DYSON-HD15",
        "name": "戴森（Dyson）HD15 新一代吹风机",
        "category": "家电", "brand": "戴森",
        "price": 2999.00, "original_price": 3299.00,
        "stock": 120, "rating": 4.8, "sales": 8950,
        "tags": ["高速吹风", "护发"],
    },
    {
        "id": "P003", "sku": "SKU-NIKE-AJ1-001",
        "name": "Nike Air Jordan 1 Retro High OG 男款篮球鞋",
        "category": "运动鞋", "brand": "Nike",
        "price": 1499.00, "original_price": 1499.00,
        "stock": 35, "rating": 4.7, "sales": 5680,
        "tags": ["AJ1", "经典", "OG"],
    },
    {
        "id": "P004", "sku": "SKU-MACBOOK-M3-014",
        "name": "Apple MacBook Pro 14英寸 M3 Pro芯片 18+512GB",
        "category": "电脑", "brand": "Apple",
        "price": 16999.00, "original_price": 18999.00,
        "stock": 25, "rating": 4.9, "sales": 3200,
        "tags": ["M3 Pro", "专业级", "轻薄"],
    },
    {
        "id": "P005", "sku": "SKU-HW-P60PRO-256",
        "name": "华为 P60 Pro 超聚光XMAGE影像 玄武镀膜",
        "category": "手机", "brand": "华为",
        "price": 5988.00, "original_price": 6988.00,
        "stock": 80, "rating": 4.8, "sales": 9800,
        "tags": ["XMAGE", "双向卫星消息"],
    },
]
