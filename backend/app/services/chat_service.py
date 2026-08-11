"""对话服务 - 整合意图识别、情感分析、RAG、Agent（集成 Langfuse 追踪）

会话内存态治理（B1/B7/B14）：
- 三张内存表（_sessions / _conversations / _agents）统一收拢到 SessionManager，
  所有写操作经 asyncio.Lock 串行化，消除并发数据竞争（B7）。
- send_message 采用「准备(加锁 ensure + 防 purge 当前会话) → 长耗时 LLM → 提交(加锁落库)」
  三段式：准备阶段即保证三表一致并把当前会话 last_message_at 刷新为 now，
  使当前会话在 LLM 处理期间不会被 _purge_expired 误删（B1），
  同时 send_message 路径新建的会话也会写入 _sessions 元数据（B14）。
"""
from typing import Dict, Any, Optional, List
import uuid
import datetime
import asyncio
import json
import logging
from app.services.intent_service import intent_service
from app.services.sentiment_service import sentiment_service, SentimentType
from app.services.rag_service import rag_service
from app.services.llm_service import llm_service
from app.services.observe_service import observe
from app.agents.customer_agent import CustomerServiceAgent

logger = logging.getLogger(__name__)

# 会话生命周期治理（M1）：容量上限 + 空闲 TTL 惰性淘汰
MAX_SESSIONS: int = 200
SESSION_TTL_SECONDS: int = 86400  # 24 小时


# 默认 Agent 构造路径（CustomerServiceAgent），供 SessionManager / ChatService 默认注入
_DEFAULT_AGENT_FACTORY = lambda sid, user_id=None: CustomerServiceAgent(sid, user_id)


class SessionManager:
    """会话状态管理器：统一持有三张内存表，并以锁保护所有写操作。

    说明：会话/Agent 实例为进程内对象（Agent 不可序列化），横向扩展时
    本管理器负责单进程内的正确性与并发安全；跨进程共享由缓存/限流器
    的 Redis 后端承接（见 utils/cache.py、utils/rate_limiter.py，对应 P3/P8）。
    """

    def __init__(self, agent_factory=None):
        if agent_factory is None:
            agent_factory = _DEFAULT_AGENT_FACTORY
        self._agent_factory = agent_factory
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}
        self._agents: Dict[str, CustomerServiceAgent] = {}
        self._lock = asyncio.Lock()

    # ── 内部工具 ──
    @staticmethod
    def _now() -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    def _remove(self, sid: str) -> None:
        """同步清理三表，避免内存状态不一致"""
        self._sessions.pop(sid, None)
        self._conversations.pop(sid, None)
        self._agents.pop(sid, None)

    def _ensure(self, sid: str, user_id: Optional[int], touch: bool = True) -> CustomerServiceAgent:
        """确保三表存在且一致（幂等）；返回 Agent 实例。

        touch=True 时刷新 last_message_at 为 now，使当前会话在 LLM 处理期间
        不会被 _purge_expired 判定为过期而误删（B1）。
        """
        if sid not in self._sessions:
            self._sessions[sid] = {
                "session_id": sid,
                "user_id": user_id,
                "status": "active",
                "started_at": self._now(),
                "last_message_at": self._now(),
                "message_count": 0,
                "bot_name": "智能客服小e",
            }
        if sid not in self._conversations:
            self._conversations[sid] = []
        if sid not in self._agents:
            self._agents[sid] = self._agent_factory(sid, user_id)
        elif user_id is not None:
            # 后续消息若携带已登录身份，同步到 Agent，保证 requires_auth 校验一致 (F1)
            self._agents[sid].user_id = user_id
        if touch:
            self._sessions[sid]["last_message_at"] = self._now()
        return self._agents[sid]

    def _purge_expired(self, exclude: Optional[str] = None) -> None:
        """惰性淘汰：删除空闲超过 TTL 的会话。

        exclude 指定的会话（通常是「正在处理的当前会话」）不会被淘汰，
        从根上消除 B1 的 KeyError 崩溃。
        """
        now = self._now()
        expired = [
            s for s, info in self._sessions.items()
            if s != exclude and (
                now - (info.get("last_message_at") or info.get("started_at") or now)
            ).total_seconds() > SESSION_TTL_SECONDS
        ]
        for s in expired:
            self._remove(s)
            logger.info(f"会话因空闲超时已淘汰: {s}")

    def _evict_lru(self) -> None:
        """容量上限：超过 MAX_SESSIONS 时按最旧活动淘汰"""
        sentinel = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        while len(self._sessions) > MAX_SESSIONS:
            oldest_sid, oldest_info = min(
                self._sessions.items(),
                key=lambda kv: kv[1].get("last_message_at") or kv[1].get("started_at") or sentinel,
            )
            self._remove(oldest_sid)
            logger.info(f"会话因超过容量上限已淘汰(LRU): {oldest_sid}")

    # ── 对外（加锁）接口 ──
    async def prepare(self, session_id: str, user_id: Optional[int]) -> CustomerServiceAgent:
        """发送前准备：确保三表一致 + 刷新活跃时间 + 惰性淘汰（排除当前会话）。"""
        async with self._lock:
            agent = self._ensure(session_id, user_id, touch=True)
            self._purge_expired(exclude=session_id)
            self._evict_lru()
            return agent

    async def commit(self, session_id: str, user_msg: Dict[str, Any], assistant_msg: Dict[str, Any]) -> None:
        """发送后提交：落库对话历史 + 更新会话统计（加锁，防并发写竞争）。"""
        async with self._lock:
            self._conversations.setdefault(session_id, []).append(user_msg)
            self._conversations.setdefault(session_id, []).append(assistant_msg)
            if session_id in self._sessions:
                self._sessions[session_id]["message_count"] = (
                    self._sessions[session_id].get("message_count", 0) + 1
                )
                self._sessions[session_id]["last_message_at"] = self._now()

    def get_agent(self, session_id: str) -> Optional[CustomerServiceAgent]:
        return self._agents.get(session_id)

    def get_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        return self._conversations.get(session_id, [])

    async def delete(self, session_id: str) -> bool:
        """删除会话：返回是否真实存在（修复 delete 恒返回 True 的隐患）。"""
        async with self._lock:
            existed = session_id in self._sessions or session_id in self._conversations
            self._remove(session_id)
            return existed

    async def list_all(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        async with self._lock:
            sessions = []
            for sid, info in self._sessions.items():
                # F4: 指定 user_id 时仅返回该用户的会话，实现用户隔离
                if user_id is not None and info.get("user_id") != user_id:
                    continue
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

    async def mark_transferred(self, session_id: str) -> None:
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["status"] = "transferred"

    async def mark_satisfaction(self, session_id: str, score: int) -> None:
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["satisfaction_score"] = score


# 全局会话管理器单例：默认 Agent 构造路径，供 ChatService 默认注入（保持进程内会话态一致）
SESSION_MANAGER = SessionManager()


class ChatService:
    """对话服务"""

    def __init__(self, session_manager=None, agent_factory=None):
        # agent_factory 默认走现有 CustomerServiceAgent 构造路径
        if agent_factory is None:
            agent_factory = _DEFAULT_AGENT_FACTORY
        self.agent_factory = agent_factory
        if session_manager is None:
            # 未注入 session_manager：默认复用模块级全局单例；
            # 若同时传入自定义 agent_factory 则新构建 SessionManager 以应用之（测试友好）。
            if agent_factory is _DEFAULT_AGENT_FACTORY:
                session_manager = SESSION_MANAGER
            else:
                session_manager = SessionManager(agent_factory=self.agent_factory)
        self.session_manager = session_manager

    async def create_session(
        self,
        user_id: Optional[int] = None,
        channel: str = "web",
        initial_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建新会话"""
        # 临界区：淘汰过期 + 新建会话元数据 + 容量淘汰
        async with self.session_manager._lock:
            self.session_manager._purge_expired()
            session_id = f"sess_{uuid.uuid4().hex[:12]}"
            self.session_manager._ensure(session_id, user_id, touch=True)
            self.session_manager._evict_lru()

        logger.info(f"会话已创建: {session_id}")

        # 欢迎消息
        welcome = "您好！我是智能客服小e，很高兴为您服务～请问有什么可以帮到您的？"
        quick_replies = ["查订单", "商品咨询", "退款退货", "促销活动", "转人工"]

        if initial_message:
            result = await self.send_message(session_id, initial_message, user_id)
            return {
                "session": self.session_manager._sessions.get(session_id),
                "welcome_message": welcome,
                "quick_replies": quick_replies,
                "initial_response": result,
            }

        return {
            "session": self.session_manager._sessions.get(session_id),
            "welcome_message": welcome,
            "quick_replies": quick_replies,
        }

    async def send_message(
        self,
        session_id: str,
        content: str,
        user_id: Optional[int] = None,
        content_type: str = "text",
        preferred_intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """处理用户消息并返回回复 — 全链路 Langfuse 追踪"""
        logger.info(f"处理消息: session={session_id}, content={(content or '')[:50]}...")

        # 1) 进入临界区：确保会话存在（含 _sessions 元数据，修复 B14）、
        #    刷新活跃时间并排除当前会话做惰性淘汰（修复 B1），随后释放锁。
        await self.session_manager.prepare(session_id, user_id)

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
                "session_message_count": len(self.session_manager.get_conversation(session_id)),
            },
        ) as root_span:

            # 2 & 3. 意图识别 + 情感分析（P14：两者相互独立，并发执行省去一次串行等待）
            async def _recognize():
                with observe.span(name="intent-recognition", input={"text": content}) as span:
                    res = await intent_service.recognize(
                        content, user_id, preferred_intent=preferred_intent
                    )
                    if span is not None:
                        span.update(output={
                            "intent_code": res.intent_code,
                            "intent_name": res.intent_name,
                            "confidence": res.confidence,
                            "handler_type": res.handler_type,
                        })
                    return res

            async def _sentiment():
                with observe.span(name="sentiment-analysis", input={"text": content}) as span:
                    s_type, s_score = await sentiment_service.analyze(content)
                    if span is not None:
                        span.update(output={
                            "sentiment": s_type.value,
                            "score": round(s_score, 2),
                        })
                    return s_type, s_score

            intent_result, (sent_type, sent_score) = await asyncio.gather(
                _recognize(), _sentiment()
            )

            # 4. 根据意图类型处理
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
                agent = self.session_manager.get_agent(session_id)
                if agent is not None:
                    tool_res = await agent.execute_tool("search_knowledge", {"user_message": content, "top_k": 3})
                else:
                    tool_res = {"success": False}
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

            # 5. 添加情感响应前缀
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

            # 6. 存储对话历史（B2/B5：落库 intent/sentiment/sentiment_score）
            now_iso = self.session_manager._now().isoformat()
            user_msg = {
                "role": "user",
                "content": content,
                "created_at": now_iso,
                "intent": None,
                "sentiment": None,
                "sentiment_score": None,
            }
            assistant_msg = {
                "role": "assistant",
                "content": response_text,
                "created_at": now_iso,
                "intent": intent_payload,
                "sentiment": sentiment_value,
                "sentiment_score": sentiment_score_value,
            }

            # 7) 提交阶段：加锁落库 + 更新统计（修复 B7 并发写竞争；B1 防 KeyError）
            await self.session_manager.commit(session_id, user_msg, assistant_msg)

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

    async def stream_message(
        self,
        session_id: str,
        content: str,
        user_id: Optional[int] = None,
        content_type: str = "text",
        preferred_intent: Optional[str] = None,
    ):
        """流式处理用户消息，逐 token 产出 SSE 片段（P6）。

        与 send_message 保持相同的意图识别/情感分析/处理分支/落库语义，
        区别仅在于：LLM 与 RAG 分支边生成边推送 token，tool/transfer 分支
        一次性推送整段；结束时再推送一条 done 事件（含意图/情感/快捷回复等元数据）。
        """
        await self.session_manager.prepare(session_id, user_id)

        def _sse(event_type: str, **payload) -> str:
            return f"data: {json.dumps({'type': event_type, **payload}, ensure_ascii=False)}\n\n"

        with observe.span(name="chat-stream-message", input={"session_id": session_id, "content": content}) as root_span:
            # 意图识别 + 情感分析（P14：并发执行，省去一次串行等待）
            intent_result, (sent_type, sent_score) = await asyncio.gather(
                intent_service.recognize(content, user_id, preferred_intent=preferred_intent),
                sentiment_service.analyze(content),
            )

            response_text = ""
            quick_replies: List[str] = []
            need_transfer = False
            handler = intent_result.handler_type

            if handler == "transfer":
                reason = "投诉" if intent_result.intent_code == "complaint" else "用户主动请求"
                response_text = await self._handle_transfer(session_id, content, intent_result, user_id, reason)
                need_transfer = True
                quick_replies = ["继续等待", "留言", "电话联系"]
                yield _sse("token", content=response_text)

            elif handler == "tool":
                response_text = await self._handle_with_tools(session_id, content, intent_result, user_id)
                quick_replies = self._get_followup_quick_replies(intent_result.intent_code)
                yield _sse("token", content=response_text)

            elif handler == "rag":
                agent = self.session_manager.get_agent(session_id)
                if agent is not None:
                    tool_res = await agent.execute_tool("search_knowledge", {"user_message": content, "top_k": 3})
                else:
                    tool_res = {"success": False}
                if tool_res.get("success") and tool_res.get("results"):
                    response_text = tool_res.get("response", "")
                    yield _sse("token", content=response_text)
                else:
                    context = await rag_service.retrieve(content, top_k=3)
                    async for piece in rag_service.generate_stream(content, context):
                        response_text += piece
                        yield _sse("token", content=piece)

            else:
                history = self.session_manager.get_conversation(session_id)
                clean_history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in history[-6:]
                ]
                messages = [
                    {"role": "system", "content": self._get_system_prompt()},
                    *clean_history,
                    {"role": "user", "content": content},
                ]
                async for piece in llm_service.chat_stream(messages):
                    response_text += piece
                    yield _sse("token", content=piece)

            # 情感响应前缀
            strategy = sentiment_service.get_response_strategy(sent_type, sent_score)
            if sent_type == SentimentType.NEGATIVE and strategy["prefix"]:
                response_text = strategy["emoji"] + " " + strategy["prefix"] + response_text
            elif sent_type == SentimentType.POSITIVE:
                response_text = strategy["emoji"] + " " + response_text

            # 构造意图/情感载荷（与 send_message 一致）
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

            # 落库（与 send_message 一致）
            now_iso = self.session_manager._now().isoformat()
            user_msg = {
                "role": "user", "content": content, "created_at": now_iso,
                "intent": None, "sentiment": None, "sentiment_score": None,
            }
            assistant_msg = {
                "role": "assistant", "content": response_text, "created_at": now_iso,
                "intent": intent_payload, "sentiment": sentiment_value,
                "sentiment_score": sentiment_score_value,
            }
            await self.session_manager.commit(session_id, user_msg, assistant_msg)

            if root_span is not None:
                root_span.update(output={"response": response_text[:300], "intent_code": intent_result.intent_code})

            # 结束事件：推送完整信息与元数据，供前端最终对齐
            yield _sse(
                "done",
                response=response_text,
                intent=intent_payload,
                sentiment=sentiment_value,
                sentiment_score=sentiment_score_value,
                quick_replies=quick_replies,
                need_transfer=need_transfer,
            )

    async def _handle_transfer(self, session_id: str, content: str, intent_result, user_id: Optional[int], reason: str = "用户主动请求") -> str:
        """转人工：委派 TransferHumanTool（ReAct 工具接线）。

        F11 修复：聊天文本触发的转人工（intent=transfer）此前不会更新会话状态，
        导致状态机与实际流转脱节（看板/列表无法反映「已转人工」）。此处复用
        SessionManager.mark_transferred 将会话状态置为 transferred，与 /chat/transfer
        端点（transfer_to_human）保持一致。
        """
        await self.session_manager.mark_transferred(session_id)
        agent = self.session_manager.get_agent(session_id)
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
        agent = self.session_manager.get_agent(session_id)
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
        history = self.session_manager.get_conversation(session_id)
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
        """获取对话历史（B10：对分页参数做非负/上限裁剪，作为路由 Query 约束的防御性兜底）"""
        try:
            page = max(1, int(page))
            page_size = max(1, min(int(page_size), 100))
        except (TypeError, ValueError):
            page, page_size = 1, 20
        all_messages = self.session_manager.get_conversation(session_id)
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

    async def list_sessions(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """获取会话列表（F4：传入 user_id 时按用户隔离）"""
        return await self.session_manager.list_all(user_id=user_id)

    async def delete_session(self, session_id: str) -> bool:
        """删除会话：清理内存中的会话元数据、对话历史与 Agent 实例"""
        return await self.session_manager.delete(session_id)

    async def transfer_to_human(self, session_id: str, reason: str = "用户主动请求") -> Dict[str, Any]:
        """转人工"""
        await self.session_manager.mark_transferred(session_id)
        return {
            "success": True,
            "message": "已为您转接人工客服",
            "transfer_id": f"TRF_{uuid.uuid4().hex[:8]}",
            "queue_position": 1,
            "estimated_wait_time": 3,
        }

    async def rate_session(self, session_id: str, score: int, comment: Optional[str] = None) -> Dict[str, Any]:
        """评价会话"""
        await self.session_manager.mark_satisfaction(session_id, score)
        logger.info(f"会话评价: session={session_id}, score={score}, comment={comment}")
        return {"success": True, "message": "感谢您的评价！"}


# 全局单例
chat_service = ChatService()
