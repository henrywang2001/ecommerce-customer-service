"""LLM 服务 - 使用 DeepSeek API（集成 Langfuse 追踪）"""
from typing import List, Dict, Optional
import httpx
import json
import logging
from app.core.config import settings
from app.services.observe_service import observe

logger = logging.getLogger(__name__)


class LLMService:
    """大语言模型服务 — DeepSeek"""

    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.api_base = settings.LLM_API_BASE.rstrip("/")
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """生成文本（单轮）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        temp = temperature or self.temperature
        max_tok = max_tokens or self.max_tokens
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temp,
            "max_tokens": max_tok,
        }

        # ── Langfuse 追踪 ──
        with observe.generation(
            name="llm-generate",
            model=self.model,
            input=prompt,
            model_parameters={
                "temperature": temp,
                "max_tokens": max_tok,
                "api_base": self.api_base,
            },
        ) as gen:
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    result = data["choices"][0]["message"]["content"]

                    # 尝试记录 token 用量（DeepSeek 可能不返回）
                    usage = data.get("usage", {})
                    usage_details = {}
                    if usage:
                        usage_details = {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                        }

                    if gen is not None:
                        gen.update(output=result, usage_details=usage_details)
                    return result
            except Exception as e:
                logger.error(f"LLM 生成失败: {e}")
                if gen is not None:
                    gen.update(
                        output="",
                        status_message=str(e),
                        level="ERROR",
                    )
                return "抱歉，AI 服务暂时不可用，请稍后重试。"

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> str:
        """多轮对话"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        temp = temperature or self.temperature
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": self.max_tokens,
        }

        # ── Langfuse 追踪 ──
        with observe.generation(
            name="llm-chat",
            model=self.model,
            input={"messages": messages},
            model_parameters={
                "temperature": temp,
                "max_tokens": self.max_tokens,
                "api_base": self.api_base,
            },
        ) as gen:
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    result = data["choices"][0]["message"]["content"]

                    usage = data.get("usage", {})
                    usage_details = {}
                    if usage:
                        usage_details = {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                        }

                    if gen is not None:
                        gen.update(output=result, usage_details=usage_details)
                    return result
            except Exception as e:
                logger.error(f"LLM 对话失败: {e}")
                if gen is not None:
                    gen.update(
                        output="",
                        status_message=str(e),
                        level="ERROR",
                    )
                return "抱歉，AI 服务暂时不可用，请稍后重试。"

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.1,
    ) -> Optional[dict]:
        """生成 JSON 结构化输出"""
        response = await self.generate(
            prompt + "\n请仅返回JSON格式，不要包含任何其他内容。",
            temperature=temperature,
        )
        try:
            # 尝试提取 JSON
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"JSON 解析失败: {e}, 原始输出: {response[:200]}")
            return None


# 全局单例
llm_service = LLMService()
