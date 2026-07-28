"""商品相关 Pydantic Schemas"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    category: str
    brand: Optional[str] = None
    price: float
    original_price: Optional[float] = None
    stock: int
    sales_count: int
    description: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    images: Optional[List[str]] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    total: int
