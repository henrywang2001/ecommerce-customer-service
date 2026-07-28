"""意图识别 API 路由"""
from fastapi import APIRouter
from app.schemas.intent import IntentRecognizeRequest, IntentRecognizeResponse
from app.services.intent_service import intent_service

router = APIRouter()


@router.post("/recognize", response_model=IntentRecognizeResponse)
async def recognize_intent(req: IntentRecognizeRequest):
    """识别文本意图"""
    result = await intent_service.recognize(req.text, req.user_id)
    return IntentRecognizeResponse(
        intent=result,
        entities=result.entities,
    )
