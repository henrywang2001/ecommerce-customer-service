"""对话 API 路由"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Body, Query
from fastapi.responses import StreamingResponse
import json
import logging

from app.core.security import current_user_id
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
logger = logging.getLogger(__name__)


def _resolve_user_id(request: Request, fallback: Optional[int]) -> Optional[int]:
    """鉴权用户优先（令牌不可伪造）；demo 模式回退到前端传入值。"""
    uid = current_user_id(request)
    return uid if uid is not None else fallback


@router.post("/session", response_model=CreateSessionResponse)
async def create_session(
    req: CreateSessionRequest = Body(default_factory=CreateSessionRequest),
    request: Request = None,
):
    """创建新会话。

    F10 修复：原先把 Pydantic 请求体参数默认设为 ``None``（反模式），使本应可校验的
    body 变成「可缺省」，绕过参数校验且语义含糊。改为 ``Body(default_factory=...)``，
    既保留「可不传 body」的向后兼容（前端发送 ``{}`` 仍可用），又让必填字段可被正常校验。
    """
    result = await chat_service.create_session(
        user_id=_resolve_user_id(request, req.user_id),
        channel=req.channel,
        initial_message=req.initial_message,
    )
    return CreateSessionResponse(**result)


@router.post("/send", response_model=SendMessageResponse)
async def send_message(req: SendMessageRequest, request: Request = None):
    """发送消息"""
    result = await chat_service.send_message(
        session_id=req.session_id,
        content=req.content,
        user_id=_resolve_user_id(request, req.user_id),
        content_type=req.content_type,
    )
    return SendMessageResponse(**result)


@router.post("/send_stream")
async def send_message_stream(req: SendMessageRequest, request: Request = None):
    """流式发送消息（SSE，P6）：逐 token 推送，首字延迟大幅降低。"""
    uid = _resolve_user_id(request, req.user_id)

    async def event_gen():
        try:
            async for chunk in chat_service.stream_message(
                session_id=req.session_id,
                content=req.content,
                user_id=uid,
                content_type=req.content_type,
            ):
                yield chunk
        except Exception as e:
            logger.error(f"流式回复失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': '抱歉，服务暂时不可用，请稍后重试。'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/history", response_model=MessageListResponse)
async def get_history(
    session_id: str,
    page: int = Query(1, ge=1, le=1000, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数，范围 1~100"),
):
    """获取对话历史（B10 修复：为分页参数加边界约束，避免非法 page/page_size 产生异常切片）"""
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
async def list_sessions(request: Request = None):
    """获取会话列表（F4：按当前登录用户隔离；demo 模式返回全部）"""
    uid = current_user_id(request) if request is not None else None
    result = await chat_service.list_sessions(user_id=uid)
    return SessionListResponse(**result)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话（含内存中的会话元数据、对话记录、Agent 实例）"""
    deleted = await chat_service.delete_session(session_id)
    return {"success": deleted, "deleted_id": session_id}
