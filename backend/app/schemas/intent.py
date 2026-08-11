"""意图相关 Pydantic Schemas"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Entity(BaseModel):
    type: str
    value: str
    start: int = 0
    end: int = 0


class IntentResult(BaseModel):
    intent_code: str
    intent_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    entities: List[Entity] = Field(default_factory=list)
    handler_type: str = "llm"
    priority: int = 0


class IntentRecognizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="待识别的文本")
    user_id: Optional[int] = Field(None, description="用户ID")


class IntentRecognizeResponse(BaseModel):
    """意图识别响应。

    修复：移除与 ``intent.entities`` 语义重复的顶层 ``entities`` 字段，
    避免冗余契约与「前端取错层级」的不一致风险（意图实体统一从 ``intent.entities`` 读取）。
    """
    intent: IntentResult


class IntentCreateRequest(BaseModel):
    intent_name: str = Field(..., description="意图名称")
    intent_code: str = Field(..., description="意图编码")
    description: Optional[str] = None
    handler_type: str = Field("llm", description="处理类型: rag/tool/transfer/llm/fallback")
    handler_config: Optional[Dict[str, Any]] = None
    sample_utterances: Optional[str] = None
    priority: int = 0


class IntentUpdateRequest(BaseModel):
    intent_name: Optional[str] = None
    description: Optional[str] = None
    handler_type: Optional[str] = None
    handler_config: Optional[Dict[str, Any]] = None
    sample_utterances: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
