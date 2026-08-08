"""对话服务 - 整合意图识别、情感分析、RAG、Agent（集成 Langfuse 追踪）"""
from typing import Dict, Any, Optional, List
import uuid
import datetime
import logging
from app.services.intent_service import intent_service
from app.services.sentiment_service import sentiment_service, SentimentType
from app.services.rag_service import rag_service
from app.services.llm_service import llm_service
from app.services.observe_service import observe
from app.agents.customer_agent import CustomerServiceAgent

logger = logging.getLogger(__name__)

# 内存中的会话存储（生产环境应使用 Redis）
_sessions: Dict[str, Dict[str, Any]] = {}
_conversations: Dict[str, List[Dict[str, Any]]] = {}
_agents: Dict[str, CustomerServiceAgent] = {}

# 会话生命周期治理（M1）：容量上限 + 空闲 TTL 惰性淘汰
MAX_SESSIONS: int = 200
SESSION_TTL_SECONDS: int = 86400  # 24 小时


class ChatService:
    """对话服务"""

    async def create_session(
        self,
        user_id: Optional[int] = None,
        channel: str = "web",
        initial_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建新会话"""
        self._purge_expired()

        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        session_info = {
            "session_id": session_id,
            "user_id": user_id,
            "status": "active",
            "started_at": datetime.datetime.now(datetime.timezone.utc),
            "last_message_at": datetime.datetime.now(datetime.timezone.utc),
            "message_count": 0,
            "bot_name": "智能客服小e",
        }
        _sessions[session_id] = session_info
        _conversations[session_id] = []

        # 创建 Agent 实例
        agent = CustomerServiceAgent(session_id, user_id)
        _agents[session_id] = agent

        self._evict_lru()
        logger.info(f"会话已创建: {session_id}")

        # 欢迎消息
        welcome = "您好！我是智能客服小e，很高兴为您服务～请问有什么可以帮到您的？"
        quick_replies = ["查订单", "商品咨询", "退款退货", "促销活动", "转人工"]

        if initial_message:
            result = await self.send_message(session_id, initial_message, user_id)
            return {
                "session": session_info,
                "welcome_message": welcome,
                "quick_replies": quick_replies,
                "initial_response": result,
            }

        return {
            "session": session_info,
            "welcome_message": welcome,
            "quick_replies": quick_replies,
        }

    async def send_message(
        self,
        session_id: str,
        content: str,
        user_id: Optional[int] = None,
        content_type: str = "text",
    ) -> Dict[str, Any]:
        """处理用户消息并返回回复 — 全链路 Langfuse 追踪"""
        logger.info(f"处理消息: session={session_id}, content={content[:50]}...")

        # 确保会话存在
        if session_id not in _conversations:
            _conversations[session_id] = []
        if session_id not in _agents:
            _agents[session_id] = CustomerServiceAgent(session_id, user_id)

        agent = _agents[session_id]

        # 惰性淘汰过期会话（M1）
        self._purge_expired()

        # ── Langfuse: 创建根 Trace ──
        with observe.span(
            name="chat-send-message",
            input={
                "session_id": session_id,
                "user_id": user_id,
                "content": content,
                "content_type": content_type,
            },
            metadata={
                "channel": "web",
                "session_message_count": len(_conversations.get(session_id, [])),
            },
        ) as root_span:

            # 1. 意图识别
            with observe.span(
                name="intent-recognition",
                input={"text": content},
            ) as intent_span:
                intent_result = await intent_service.recognize(content, user_id)
                if intent_span is not None:
                    intent_span.update(
                        output={
                            "intent_code": intent_result.intent_code,
                            "intent_name": intent_result.intent_name,
                            "confidence": intent_result.confidence,
                            "handler_type": intent_result.handler_type,
                        }
                    )

            # 2. 情感分析
            with observe.span(
                name="sentiment-analysis",
                input={"text": content},
            ) as sent_span:
                sent_type, sent_score = await sentiment_service.analyze(content)
                if sent_span is not None:
                    sent_span.update(
                        output={
                            "sentiment": sent_type.value,
                            "score": round(sent_score, 2),
                        }
                    )

            # 3. 根据意图类型处理
            response_text = ""
            quick_replies: List[str] = []
            need_transfer = False

            if intent_result.handler_type == "transfer":
                # 转人工（委派 TransferHumanTool）
                with observe.span(name="handle-transfer") as t_span:
                    reason = "投诉" if intent_result.intent_code == "complaint" else "用户主动请求"
                    response_text = await self._handle_transfer(session_id, content, intent_result, user_id, reason)
                    need_transfer = True
                    quick_replies = ["继续等待", "留言", "电话联系"]
                    if t_span is not None:
                        t_span.update(output={"need_transfer": True, "intent": intent_result.intent_code})

            elif intent_result.handler_type == "tool":
                # 使用工具处理（订单、退款等）
                with observe.span(
                    name="handle-with-tools",
                    input={"intent_code": intent_result.intent_code, "content": content},
                ) as tool_span:
                    response_text = await self._handle_with_tools(session_id, content, intent_result, user_id)
                    quick_replies = self._get_followup_quick_replies(intent_result.intent_code)
                    if tool_span is not None:
                        tool_span.update(output=response_text[:200])

            elif intent_result.handler_type == "rag":
                # 知识检索：优先走 SearchKnowledgeTool（已接线），失败回退 LLM 生成
                tool_res = await agent.execute_tool("search_knowledge", {"user_message": content, "top_k": 3})
                if tool_res.get("success") and tool_res.get("results"):
                    response_text = tool_res.get("response", "")
                else:
                    context = await rag_service.retrieve(content, top_k=3)
                    response_text = await rag_service.generate(content, context)
                quick_replies = self._get_followup_quick_replies(intent_result.intent_code)

            else:
                # LLM 直接回答 — llm_service 内部已有追踪
                with observe.span(name="handle-with-llm") as llm_span:
                    response_text = await self._handle_with_llm(session_id, content, intent_result)
                    if llm_span is not None:
                        llm_span.update(output=response_text[:200])

            # 4. 添加情感响应前缀
            strategy = sentiment_service.get_response_strategy(sent_type, sent_score)
            if sent_type == SentimentType.NEGATIVE and strategy["prefix"]:
                response_text = strategy["emoji"] + " " + strategy["prefix"] + response_text
            elif sent_type == SentimentType.POSITIVE:
                response_text = strategy["emoji"] + " " + response_text

            # 构造统一的意图/情感载荷（供存储与返回复用，避免后续前向引用 result）
            intent_payload = {
                "intent_code": intent_result.intent_code,
                "intent_name": intent_result.intent_name,
                "confidence": intent_result.confidence,
                "entities": [e.model_dump() for e in intent_result.entities],
                "handler_type": intent_result.handler_type,
                "priority": intent_result.priority,
            }
            sentiment_value = sent_type.value
            sentiment_score_value = round(sent_score, 2)

            # 5. 存储对话历史（B2/B5：落库 intent/sentiment/sentiment_score）
            _conversations[session_id].append({
                "role": "user",
                "content": content,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "intent": None,
                "sentiment": None,
                "sentiment_score": None,
            })
            _conversations[session_id].append({
                "role": "assistant",
                "content": response_text,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "intent": intent_payload,
                "sentiment": sentiment_value,
                "sentiment_score": sentiment_score_value,
            })

            # 更新会话信息
            if session_id in _sessions:
                _sessions[session_id]["message_count"] += 1
                _sessions[session_id]["last_message_at"] = datetime.datetime.now(datetime.timezone.utc)

            result = {
                "response": response_text,
                "intent": intent_payload,
                "sentiment": sentiment_value,
                "sentiment_score": sentiment_score_value,
                "quick_replies": quick_replies,
                "need_transfer": need_transfer,
            }

            if root_span is not None:
                root_span.update(
                    output={
                        "response": response_text[:300],
                        "intent_code": intent_result.intent_code,
                        "sentiment": sent_type.value,
                        "need_transfer": need_transfer,
                    }
                )

            return result

    async def _handle_transfer(self, session_id: str, content: str, intent_result, user_id: Optional[int], reason: str = "用户主动请求") -> str:
        """转人工：委派 TransferHumanTool（ReAct 工具接线）"""
        agent = _agents.get(session_id)
        if agent is not None:
            result = await agent.execute_tool(
                "transfer_human",
                {"session_id": session_id, "user_id": user_id, "reason": reason},
            )
            return result.get("response", "已为您转接人工客服，请稍候～")
        return "已为您转接人工客服，请稍候～"

    async def _handle_with_tools(self, session_id: str, content: str, intent_result, user_id: Optional[int]) -> str:
        """按意图码分发到对应 Agent 工具（ReAct 工具接线）"""
        code = intent_result.intent_code
        agent = _agents.get(session_id)
        if agent is None:
            return "正在为您处理，请稍候…"

        tool_map = {
            "order_query": ("query_order", {"user_message": content, "user_id": user_id}),
            "refund_request": ("refund", {"user_message": content, "user_id": user_id}),
            "product_inquiry": ("query_product", {"user_message": content}),
            "ticket_create": (
                "create_ticket",
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "type": "consult",
                    "title": (content or "用户咨询")[:20],
                    "content": content or "",
                },
            ),
        }
        if code in tool_map:
            tool_name, params = tool_map[code]
            result = await agent.execute_tool(tool_name, params)
            return result.get("response", "正在为您处理，请稍候…")
        return "正在为您处理，请稍候…"

    async def _handle_with_llm(self, session_id: str, content: str, intent_result) -> str:
        """使用 LLM 直接回答"""
        history = _conversations.get(session_id, [])
        # 存储的每条消息现已含 intent/sentiment 等额外字段，
        # 发送给 LLM 时必须映射为纯 {role, content}，避免多余字段污染输入。
        clean_history = [
            {"role": m["role"], "content": m["content"]}
            for m in history[-6:]  # 最近 3 轮对话
        ]
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            *clean_history,
            {"role": "user", "content": content},
        ]
        return await llm_service.chat(messages)

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return (
            "你是电商平台的智能客服「小e」，专业、友好、有耐心。\n\n"
            "核心职责：\n"
            "1. 解答商品咨询、订单物流、支付等问题\n"
            "2. 处理退款退货申请\n"
            "3. 提供购物建议和个性化推荐\n"
            "4. 必要时引导转人工客服\n\n"
            "回复规范：\n"
            "- 使用 emoji 让回复更亲切\n"
            "- 结构化展示信息（📦订单 💰金额 🚚物流）\n"
            "- 回复结尾适当引导下一步\n"
            "- 遇到超出能力范围的问题，主动建议转人工\n"
            "- 不满意的用户优先安抚情绪"
        )

    def _get_followup_quick_replies(self, intent_code: str) -> List[str]:
        """根据意图生成后续快捷回复"""
        mapping = {
            "order_query": ["查物流", "修改地址", "我要退款"],
            "refund_request": ["查进度", "退货流程", "联系人工"],
            "product_inquiry": ["看评价", "比价格", "查库存"],
            "shipping_info": ["加急配送", "修改地址"],
            "payment_issue": ["支付失败", "退款到账时间"],
            "promotion": ["最新活动", "优惠券", "会员权益"],
        }
        return mapping.get(intent_code, ["查订单", "商品咨询", "转人工"])

    async def get_history(self, session_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取对话历史"""
        all_messages = _conversations.get(session_id, [])
        total = len(all_messages)
        start = (page - 1) * page_size
        end = start + page_size
        page_messages = all_messages[start:end]

        # 转换为带 ID 的格式（B5：回读 intent/sentiment/sentiment_score）
        result = []
        for i, msg in enumerate(page_messages):
            result.append({
                "id": start + i + 1,
                "session_id": session_id,
                "sender_type": "user" if msg["role"] == "user" else "bot",
                "content": msg["content"],
                "content_type": "text",
                "intent": msg.get("intent"),
                "sentiment": msg.get("sentiment"),
                "sentiment_score": msg.get("sentiment_score"),
                "created_at": msg.get("created_at", ""),
            })

        return {"items": result, "total": total, "page": page, "page_size": page_size}

    async def list_sessions(self) -> Dict[str, Any]:
        """获取会话列表"""
        sessions = []
        for sid, info in _sessions.items():
            sessions.append({
                "session_id": info.get("session_id", sid),
                "user_id": info.get("user_id"),
                "status": info.get("status", "active"),
                "started_at": info.get("started_at"),
                "message_count": info.get("message_count", 0),
                "last_message_at": info.get("last_message_at"),
                "bot_name": info.get("bot_name", "智能客服小e"),
            })
        return {"sessions": sessions, "total": len(sessions)}

    # ── 会话生命周期治理（M1）──
    def _remove_session(self, session_id: str) -> None:
        """同步清理三表，避免内存状态不一致"""
        _sessions.pop(session_id, None)
        _conversations.pop(session_id, None)
        _agents.pop(session_id, None)

    def _purge_expired(self) -> None:
        """惰性淘汰：删除空闲超过 TTL 的会话（在创建/发送时触发）"""
        now = datetime.datetime.now(datetime.timezone.utc)
        expired = [
            sid for sid, info in _sessions.items()
            if (now - (info.get("last_message_at") or info.get("started_at") or now)).total_seconds()
            > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            self._remove_session(sid)
            logger.info(f"会话因空闲超时已淘汰: {sid}")

    def _evict_lru(self) -> None:
        """容量上限：超过 MAX_SESSIONS 时按最旧活动淘汰"""
        sentinel = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        while len(_sessions) > MAX_SESSIONS:
            oldest_sid, oldest_info = min(
                _sessions.items(),
                key=lambda kv: kv[1].get("last_message_at") or kv[1].get("started_at") or sentinel,
            )
            self._remove_session(oldest_sid)
            logger.info(f"会话因超过容量上限已淘汰(LRU): {oldest_sid}")

    async def delete_session(self, session_id: str) -> bool:
        """删除会话：清理内存中的会话元数据、对话历史与 Agent 实例"""
        existed = session_id in _sessions or session_id in _conversations
        _sessions.pop(session_id, None)
        _conversations.pop(session_id, None)
        _agents.pop(session_id, None)
        logger.info(f"会话已删除: {session_id}")
        return True

    async def transfer_to_human(self, session_id: str, reason: str = "用户主动请求") -> Dict[str, Any]:
        """转人工"""
        if session_id in _sessions:
            _sessions[session_id]["status"] = "transferred"
        return {
            "success": True,
            "message": "已为您转接人工客服",
            "transfer_id": f"TRF_{uuid.uuid4().hex[:8]}",
            "queue_position": 1,
            "estimated_wait_time": 3,
        }

    async def rate_session(self, session_id: str, score: int, comment: Optional[str] = None) -> Dict[str, Any]:
        """评价会话"""
        if session_id in _sessions:
            _sessions[session_id]["satisfaction_score"] = score
        logger.info(f"会话评价: session={session_id}, score={score}, comment={comment}")
        return {"success": True, "message": "感谢您的评价！"}


# 全局单例
chat_service = ChatService()
