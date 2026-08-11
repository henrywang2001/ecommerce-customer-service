"""商品服务 API 路由（/ 修复：单一数据源 + 声明 response_model 对齐契约）"""
from fastapi import APIRouter, Query
from typing import Optional

from app.data.mock_data import PRODUCTS
from app.schemas.product import ProductListResponse, ProductDetailResponse, ProductResponse

router = APIRouter()


@router.get("/list", response_model=ProductListResponse)
async def list_products(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取商品列表（数据来自统一 Mock 来源 app.data.mock_data.PRODUCTS）"""
    products = PRODUCTS
    if category:
        products = [p for p in products if category in p["category"]]
    if keyword:
        kw = keyword.lower()
        products = [p for p in products if kw in p["name"].lower() or kw in p["brand"].lower()]
    total = len(products)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = [ProductResponse(**p) for p in products[start:end]]
    return ProductListResponse(
        products=page_items, total=total, page=page, page_size=page_size
    )


@router.get("/detail/{sku}", response_model=ProductDetailResponse)
async def product_detail(sku: str):
    """获取商品详情"""
    for product in PRODUCTS:
        if product["sku"].upper() == sku.upper():
            return ProductDetailResponse(success=True, product=ProductResponse(**product))
    return ProductDetailResponse(success=False, message=f"未找到商品: {sku}")
