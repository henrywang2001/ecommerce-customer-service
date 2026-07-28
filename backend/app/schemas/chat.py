"""对话相关 Pydantic Schemas"""
from pydantic import BaseModel, Field, AliasChoices
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SenderType(str, Enum):
    USER = "user"
    BOT = "bot"
    AGENT = "agent"


# ==================== 请求模型 ====================

class SendMessageRequest(BaseModel):
    session_id: str = Field(..., validation_alias=AliasChoices("session_id", "sessionId"), description="会话ID")
    content: str = Field(..., min_length=1, max_length=2000, description="消息内容")
    user_id: Optional[int] = Field(None, validation_alias=AliasChoices("user_id", "userId"), description="用户ID")
    content_type: str = Field("text", validation_alias=AliasChoices("content_type", "contentType"), description="内容类型")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class CreateSessionRequest(BaseModel):
    user_id: Optional[int] = Field(None, description="用户ID")
    channel: str = Field("web", description="渠道来源")
    initial_message: Optional[str] = Field(None, description="初始消息")


class RateSessionRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    score: int = Field(..., ge=1, le=5, description="评分 1-5")
    comment: Optional[str] = Field(None, description="评价内容")


class TransferRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    reason: Optional[str] = Field("用户主动请求", description="转接原因")


# ==================== 响应模型 ====================

class IntentInfo(BaseModel):
    intent_code: str
    intent_name: str
    confidence: float
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    handler_type: str
    priority: int = 0


class SendMessageResponse(BaseModel):
    response: str = Field(..., description="回复内容")
    intent: IntentInfo = Field(..., description="意图信息")
    sentiment: SentimentType = Field(..., description="情感类型")
    sentiment_score: float = Field(..., description="情感得分")
    quick_replies: List[str] = Field(default_factory=list, description="快捷回复")
    need_transfer: bool = Field(False, description="是否需要转人工")


class SessionInfo(BaseModel):
    session_id: str
    user_id: Optional[int] = None
    status: str
    started_at: datetime
    message_count: int = 0
    bot_name: str = "智能客服小e"


class CreateSessionResponse(BaseModel):
    session: SessionInfo
    welcome_message: str = "您好！我是智能客服小e，很高兴为您服务～请问有什么可以帮到您的？"
    quick_replies: List[str] = Field(default_factory=list)


class MessageItem(BaseModel):
    id: int
    session_id: str
    sender_type: SenderType
    content: str
    content_type: str = "text"
    intent: Optional[IntentInfo] = None
    sentiment: Optional[SentimentType] = None
    sentiment_score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    messages: List[MessageItem]
    total: int
    page: int
    page_size: int


class RateSessionResponse(BaseModel):
    success: bool
    message: str = "感谢您的评价！"
