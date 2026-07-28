"""知识库 API 路由"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from app.services.rag_service import rag_service

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索关键词")
    top_k: int = Field(5, ge=1, le=20, description="返回数量")
    category: Optional[str] = Field(None, description="知识库分类")


class AddDocumentRequest(BaseModel):
    question: str = Field(..., description="问题")
    answer: str = Field(..., description="答案")
    category: str = Field("", description="分类")
    keywords: str = Field("", description="关键词")


@router.post("/search")
async def search_knowledge(req: SearchRequest):
    """搜索知识库"""
    results = await rag_service.search(req.query, req.top_k)
    return {"query": req.query, "results": results, "total": len(results)}


@router.post("/add")
async def add_document(req: AddDocumentRequest):
    """添加知识文档"""
    vector_id = await rag_service.add_document(
        question=req.question,
        answer=req.answer,
        category=req.category,
        keywords=req.keywords,
    )
    return {"success": True, "vector_id": vector_id, "message": "文档添加成功"}


@router.get("/categories")
async def list_categories():
    """获取知识库分类列表"""
    # Mock 分类数据
    categories = ["退换货政策", "配送服务", "支付问题", "会员权益", "促销活动", "售后政策", "订单修改", "发票问题"]
    return {"categories": categories}
