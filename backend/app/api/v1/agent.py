"""Agent API 路由"""
from fastapi import APIRouter, Request

from app.core.security import current_user_id
from app.schemas.agent import AgentProcessRequest, AgentProcessResponse
from app.services.chat_service import chat_service

router = APIRouter()


@router.post("/process", response_model=AgentProcessResponse)
async def process_message(req: AgentProcessRequest, request: Request = None):
    """Agent 处理用户消息"""
    uid = current_user_id(request) if request is not None else None
    result = await chat_service.send_message(
        session_id=req.session_id,
        content=req.user_message,
        user_id=uid if uid is not None else req.user_id,
        preferred_intent=req.intent_code,
    )
    return AgentProcessResponse(
        response=result["response"],
        intent_code=result["intent"]["intent_code"],
        intent_name=result["intent"]["intent_name"],
        confidence=result["intent"]["confidence"],
        sentiment=result["sentiment"],
        sentiment_score=result["sentiment_score"],
        need_transfer=result.get("need_transfer", False),
    )
