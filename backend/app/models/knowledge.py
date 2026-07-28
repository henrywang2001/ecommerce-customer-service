"""知识库表模型"""
from sqlalchemy import Column, BigInteger, String, Integer, Boolean, DateTime, Text, DECIMAL
from datetime import datetime
from app.core.database import Base


class Knowledge(Base):
    __tablename__ = "knowledge"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="知识ID")
    category = Column(String(50), nullable=False, comment="知识分类")
    question = Column(Text, nullable=False, comment="问题")
    answer = Column(Text, nullable=False, comment="答案")
    keywords = Column(String(500), nullable=True, comment="关键词")
    vector_id = Column(String(100), nullable=True, comment="向量数据库ID")
    embedding_model = Column(String(50), default="text-embedding-v1", comment="向量化模型")
    hit_count = Column(Integer, default=0, comment="命中次数")
    satisfaction_rate = Column(DECIMAL(5, 2), nullable=True, comment="满意度")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
