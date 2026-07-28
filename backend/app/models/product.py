"""商品模型"""
from sqlalchemy import Column, BigInteger, String, Integer, Boolean, DateTime, DECIMAL, JSON, Text
from datetime import datetime
from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="商品ID")
    sku = Column(String(50), unique=True, nullable=False, comment="商品SKU")
    name = Column(String(200), nullable=False, comment="商品名称")
    category = Column(String(50), nullable=False, comment="商品分类")
    brand = Column(String(50), nullable=True, comment="品牌")
    price = Column(DECIMAL(10, 2), nullable=False, comment="售价")
    original_price = Column(DECIMAL(10, 2), nullable=True, comment="原价")
    stock = Column(Integer, default=0, comment="库存")
    sales_count = Column(Integer, default=0, comment="销量")
    description = Column(Text, nullable=True, comment="商品描述")
    specifications = Column(JSON, nullable=True, comment="规格参数")
    images = Column(JSON, nullable=True, comment="图片列表")
    is_active = Column(Boolean, default=True, comment="是否上架")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
