"""Agent 相关 Pydantic Schemas"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class AgentProcessRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    user_message: str = Field(..., description="用户消息")
    user_id: Optional[int] = Field(None, description="用户ID")
    intent_code: Optional[str] = Field(None, description="预识别意图")


class AgentProcessResponse(BaseModel):
    response: str = Field(..., description="Agent 回复")
    intent_code: Optional[str] = None
    intent_name: Optional[str] = None
    confidence: Optional[float] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    tool_used: Optional[str] = None
    need_transfer: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolInfo(BaseModel):
    name: str
    description: str
    requires_auth: bool = False


class AgentInfoResponse(BaseModel):
    agent_id: str
    session_id: str
    tools: List[ToolInfo]
    state: Dict[str, Any]
    history_count: int
