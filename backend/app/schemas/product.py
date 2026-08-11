"""商品相关 Pydantic Schemas（ 修复：对齐真实返回结构，提供契约校验）"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ProductResponse(BaseModel):
    id: Optional[str] = None
    sku: str
    name: str
    category: Optional[str] = None
    brand: Optional[str] = None
    price: float
    original_price: Optional[float] = None
    stock: int
    rating: Optional[float] = None
    sales: Optional[int] = None
    tags: Optional[List[str]] = None


class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    total: int
    page: int
    page_size: int


class ProductDetailResponse(BaseModel):
    success: bool
    product: Optional[ProductResponse] = None
    message: Optional[str] = None
