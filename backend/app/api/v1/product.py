"""商品服务 API 路由"""
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

MOCK_PRODUCTS = [
    {"id": 1, "sku": "SKU-IPHONE15PM-256", "name": "Apple iPhone 15 Pro Max 256GB 钛金属色",
     "category": "手机", "brand": "Apple", "price": 9999.00, "original_price": 10999.00,
     "stock": 50, "sales_count": 12580, "is_active": True},
    {"id": 2, "sku": "SKU-DYSON-HD15", "name": "戴森（Dyson）HD15 新一代吹风机",
     "category": "家电", "brand": "戴森", "price": 2999.00, "original_price": 3299.00,
     "stock": 120, "sales_count": 8950, "is_active": True},
    {"id": 3, "sku": "SKU-NIKE-AJ1-001", "name": "Nike Air Jordan 1 Retro High OG 男款篮球鞋",
     "category": "运动鞋", "brand": "Nike", "price": 1499.00, "original_price": 1499.00,
     "stock": 35, "sales_count": 5680, "is_active": True},
    {"id": 4, "sku": "SKU-MACBOOK-M3-014", "name": "Apple MacBook Pro 14英寸 M3 Pro芯片",
     "category": "电脑", "brand": "Apple", "price": 16999.00, "original_price": 18999.00,
     "stock": 25, "sales_count": 3200, "is_active": True},
    {"id": 5, "sku": "SKU-HW-P60PRO-256", "name": "华为 P60 Pro 超聚光XMAGE影像",
     "category": "手机", "brand": "华为", "price": 5988.00, "original_price": 6988.00,
     "stock": 80, "sales_count": 9800, "is_active": True},
]


@router.get("/list")
async def list_products(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取商品列表"""
    products = MOCK_PRODUCTS
    if category:
        products = [p for p in products if category in p["category"]]
    if keyword:
        kw = keyword.lower()
        products = [p for p in products if kw in p["name"].lower() or kw in p["brand"].lower()]
    total = len(products)
    start = (page - 1) * page_size
    end = start + page_size
    return {"products": products[start:end], "total": total, "page": page, "page_size": page_size}


@router.get("/detail/{sku}")
async def product_detail(sku: str):
    """获取商品详情"""
    for product in MOCK_PRODUCTS:
        if product["sku"].upper() == sku.upper():
            return {"success": True, "product": product}
    return {"success": False, "message": f"未找到商品: {sku}"}
