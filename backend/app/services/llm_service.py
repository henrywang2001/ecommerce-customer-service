"""LLM 服务 - 使用 DeepSeek API（集成 Langfuse 追踪）"""
from typing import List, Dict, Optional
import httpx
import json
import logging
from app.core.config import settings
from app.services.observe_service import observe
from app.utils.http_client import get_http_client
from app.utils.outbound import (
    post_with_resilience, stream_post,
    llm_semaphore, llm_breaker,
)

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
                client = get_http_client()
                response = await post_with_resilience(
                    client,
                    f"{self.api_base}/chat/completions",
                    semaphore=llm_semaphore,
                    breaker=llm_breaker,
                    headers=headers,
                    json=payload,
                    timeout=120.0,
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
                client = get_http_client()
                response = await post_with_resilience(
                    client,
                    f"{self.api_base}/chat/completions",
                    semaphore=llm_semaphore,
                    breaker=llm_breaker,
                    headers=headers,
                    json=payload,
                    timeout=120.0,
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
        max_tokens: Optional[int] = None,
    ) -> Optional[dict]:
        """生成 JSON 结构化输出（P14：意图分类等短输出可传较小 max_tokens 降本提速）"""
        response = await self.generate(
            prompt + "\n请仅返回JSON格式，不要包含任何其他内容。",
            temperature=temperature,
            max_tokens=max_tokens,
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

    async def _stream_post(self, messages: List[Dict[str, str]], temperature: Optional[float] = None):
        """内部：以 stream=True 调用 LLM，逐 token 产出（P6）。"""
        temp = temperature or self.temperature
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        client = get_http_client()
        async for line in stream_post(
            client,
            f"{self.api_base}/chat/completions",
            semaphore=llm_semaphore,
            breaker=llm_breaker,
            headers=headers,
            json=payload,
            timeout=120.0,
        ):
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                continue
            delta = obj.get("choices", [{}])[0].get("delta", {})
            piece = delta.get("content")
            if piece:
                yield piece

    async def chat_stream(self, messages: List[Dict[str, str]], temperature: Optional[float] = None):
        """多轮对话流式输出（P6）。"""
        async for piece in self._stream_post(messages, temperature):
            yield piece

    async def generate_stream(self, prompt: str, temperature: Optional[float] = None):
        """单轮生成流式输出（P6）。"""
        async for piece in self._stream_post([{"role": "user", "content": prompt}], temperature):
            yield piece


# 全局单例
llm_service = LLMService()
