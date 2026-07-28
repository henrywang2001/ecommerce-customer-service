"""Agent API 路由"""
from fastapi import APIRouter
from app.schemas.agent import AgentProcessRequest, AgentProcessResponse

router = APIRouter()


@router.post("/process", response_model=AgentProcessResponse)
async def process_message(req: AgentProcessRequest):
    """Agent 处理用户消息"""
    from app.services.chat_service import chat_service
    result = await chat_service.send_message(
        session_id=req.session_id,
        content=req.user_message,
        user_id=req.user_id,
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
