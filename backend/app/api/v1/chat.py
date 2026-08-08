"""对话 API 路由"""
from fastapi import APIRouter, HTTPException
from app.schemas.chat import (
    SendMessageRequest, SendMessageResponse,
    CreateSessionRequest, CreateSessionResponse,
    MessageListResponse, MessageItem,
    SessionListResponse,
    RateSessionRequest, RateSessionResponse,
    TransferRequest,
)
from app.services.chat_service import chat_service

router = APIRouter()


@router.post("/session", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest = None):
    """创建新会话"""
    if req is None:
        req = CreateSessionRequest()
    result = await chat_service.create_session(
        user_id=req.user_id,
        channel=req.channel,
        initial_message=req.initial_message,
    )
    return CreateSessionResponse(**result)


@router.post("/send", response_model=SendMessageResponse)
async def send_message(req: SendMessageRequest):
    """发送消息"""
    result = await chat_service.send_message(
        session_id=req.session_id,
        content=req.content,
        user_id=req.user_id,
        content_type=req.content_type,
    )
    return SendMessageResponse(**result)


@router.get("/history", response_model=MessageListResponse)
async def get_history(session_id: str, page: int = 1, page_size: int = 20):
    """获取对话历史"""
    result = await chat_service.get_history(session_id, page, page_size)
    return MessageListResponse(**result)


@router.post("/transfer")
async def transfer_to_human(req: TransferRequest):
    """转人工客服"""
    result = await chat_service.transfer_to_human(req.session_id, req.reason)
    return result


@router.post("/rate", response_model=RateSessionResponse)
async def rate_session(req: RateSessionRequest):
    """评价会话"""
    result = await chat_service.rate_session(req.session_id, req.score, req.comment)
    return RateSessionResponse(**result)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    """获取会话列表"""
    result = await chat_service.list_sessions()
    return SessionListResponse(**result)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话（含内存中的会话元数据、对话记录、Agent 实例）"""
    deleted = await chat_service.delete_session(session_id)
    return {"success": deleted, "deleted_id": session_id}
