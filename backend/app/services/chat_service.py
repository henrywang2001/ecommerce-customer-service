"""对话服务 - 整合意图识别、情感分析、RAG、Agent（集成 Langfuse 追踪）

KEYSTONE 重构（ / / / / / / ）：
- 会话态外移 Redis（ / / ）：会话上下文（元数据 + 对话历史）不再驻留进程内
  字典，而是序列化为 `SessionContext`（dataclass）存入 Redis（复用 utils/cache.py 的既有
  Redis 封装 `cache`，不再单独开连接），key=`session:{session_id}`，TTL=24h。
  进程重启 / 多副本下会话不丢失、不漂移（权威副本在 Redis）。
- Agent 无状态：`CustomerServiceAgent` 不再持有任何会话可变状态；每次请求经
  `SessionManager.prepare` 按会话元数据重建一个纯执行器（仅含 session_id/user_id/工具）。
- 三层分发：意图路由器 `IntentRouter` + 已注册策略 `IntentHandler` 对象 + 会话门面
  `SessionManager`。`ChatService` 不再写 if/elif 大分支；新增意图/处理器只需向 `intent_router`
  注册一个 handler，无需改动 `ChatService` 内部。
- 单一真相源：`_core_process` 抽取非流式核心链路，返回
  `(response_text, intent_result, sentiment, sentiment_score, quick_replies, need_transfer)`；
  `send_message` 调用它持久化并返回；`stream_message` 在 handler 内逐 token 产出，并以同一
  `_build_messages_and_payload` 构造 done 事件，保证流式/非流式强一致。
- 追踪下沉：意图/情感 `observe.span` 收敛进 `_recognize_intent_and_sentiment`，
  send/stream 两条路径共用；流式 LLM/RAG 额外包 `observe.generation`，两条路径自动获得追踪。
"""
from typing import Dict, Any, Optional, List, Tuple
import uuid
import datetime
import asyncio
import json
import time
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from app.services.intent_service import intent_service
from app.services.sentiment_service import sentiment_service, SentimentType
from app.services.rag_service import rag_service
from app.services.llm_service import llm_service
from app.services.observe_service import observe
from app.agents.customer_agent import CustomerServiceAgent
from app.core.config import settings
from app.utils.cache import cache as _redis_cache  # 复用既有 Redis 封装，不再单独开连接

logger = logging.getLogger(__name__)

# 会话生命周期治理：容量上限 + 空闲 TTL（参数已收口至 config.py）
# SESSION_MAX_COUNT / SESSION_TTL / HISTORY_TURNS 见 app.core.config.settings
REDIS_SESSION_PREFIX: str = "session:"

# 默认 Agent 构造路径（CustomerServiceAgent），供 SessionManager / ChatService 默认注入
_DEFAULT_AGENT_FACTORY = lambda sid, user_id=None: CustomerServiceAgent(sid, user_id)


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 字符串（跨进程/跨重启稳定）。"""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# 会话上下文（可序列化，存入 Redis）
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SessionContext:
    """会话上下文：会话元数据 + 对话历史。可 JSON 序列化后存入 Redis。"""

    meta: Dict[str, Any]
    conversation: List[Dict[str, Any]] = field(default_factory=list)

    def to_payload(self) -> Dict[str, Any]:
        return {"meta": self.meta, "conversation": self.conversation}

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "SessionContext":
        return cls(
            meta=payload.get("meta", {}) or {},
            conversation=payload.get("conversation", []) or [],
        )

    @classmethod
    def new(cls, session_id: str, user_id: Optional[int]) -> "SessionContext":
        now = _now_iso()
        meta = {
            "session_id": session_id,
            "user_id": user_id,
            "status": "active",
            "started_at": now,
            "last_message_at": now,
            "message_count": 0,
            "bot_name": "智能客服小e",
            "satisfaction_score": None,
        }
        return cls(meta=meta, conversation=[])


# ─────────────────────────────────────────────────────────────────────────────
# 会话门面（ 第三层）：会话状态的唯一临界区来源；权威副本在 Redis/cache。
# ─────────────────────────────────────────────────────────────────────────────
class SessionManager:
    """会话状态管理器：会话上下文的外部化（Redis）门面 + 进程内锁串行化写操作。

    说明：
    - 会话上下文（meta + 对话历史）的权威副本存于 Redis（经 utils/cache.py，无 Redis 时
      自动 fallback 到「有界 + TTL」内存缓存，见 utils/cache.py）。
    - `_index` 仅为进程内轻量索引（session_id→最后活跃时间戳），用于 LRU 容量淘汰与存在性
      快检；它不是权威数据，不影响跨副本/重启后的会话正确性（数据以 Redis 为准）。
    - 所有写操作经 `asyncio.Lock` 串行化，消除并发数据竞争。
    - Agent 不在此持有：每次 `prepare` 按会话元数据重建无状态执行器（见 ）。
    """

    def __init__(self, agent_factory=None):
        if agent_factory is None:
            agent_factory = _DEFAULT_AGENT_FACTORY
        self._agent_factory = agent_factory
        self._index: "OrderedDict[str, float]" = OrderedDict()
        self._lock = asyncio.Lock()

    # ── 内部读写（Redis/cache 为权威） ──
    async def _load(self, sid: str) -> Optional[SessionContext]:
        try:
            payload = await _redis_cache.get(REDIS_SESSION_PREFIX + sid)
        except Exception:
            payload = None
        if not payload:
            return None
        try:
            return SessionContext.from_payload(payload)
        except Exception:
            return None

    async def _save(self, ctx: SessionContext) -> None:
        await _redis_cache.set(
            REDIS_SESSION_PREFIX + ctx.meta["session_id"],
            ctx.to_payload(),
            expire=settings.SESSION_TTL,
        )

    def _touch_index(self, sid: str) -> None:
        self._index.pop(sid, None)
        self._index[sid] = time.time()

    async def _async_delete(self, sid: str) -> None:
        try:
            await _redis_cache.delete(REDIS_SESSION_PREFIX + sid)
        except Exception:
            pass

    async def _purge_expired(self, exclude: Optional[str] = None) -> None:
        """惰性淘汰：删除空闲超过 TTL 的会话（排除当前会话）。"""
        now = time.time()
        expired = [
            s for s, t in self._index.items()
            if s != exclude and (now - t) > settings.SESSION_TTL
        ]
        for s in expired:
            self._index.pop(s, None)
            logger.info(f"会话因空闲超时已淘汰: {s}")
            await self._async_delete(s)

    async def _evict_lru(self) -> None:
        """容量上限：超过 SESSION_MAX_COUNT 时按最旧活动淘汰。"""
        while len(self._index) > settings.SESSION_MAX_COUNT:
            oldest, _ = self._index.popitem(last=False)
            logger.info(f"会话因超过容量上限已淘汰(LRU): {oldest}")
            await self._async_delete(oldest)

    # ── 对外（加锁）接口 ──
    async def prepare(self, session_id: str, user_id: Optional[int]) -> CustomerServiceAgent:
        """发送前准备：加载/创建会话上下文 + 刷新活跃时间 + 惰性淘汰（排除当前会话）。

        返回：按会话元数据重建的「无状态」Agent 执行器（不持有会话可变状态，见 ）。
        """
        async with self._lock:
            ctx = await self._load(session_id)
            if ctx is None:
                ctx = SessionContext.new(session_id, user_id)
            elif user_id is not None:
                # 后续消息若携带已登录身份，同步到会话元数据（ 一致性）
                ctx.meta["user_id"] = user_id
            ctx.meta["last_message_at"] = _now_iso()
            await self._save(ctx)
            self._touch_index(session_id)
            await self._purge_expired(exclude=session_id)
            await self._evict_lru()
            return self._agent_factory(session_id, ctx.meta.get("user_id"))

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """读取会话元数据（不存在返回 None）。"""
        ctx = await self._load(session_id)
        return ctx.meta if ctx is not None else None

    async def commit(self, session_id: str, user_msg: Dict[str, Any], assistant_msg: Dict[str, Any]) -> None:
        """发送后提交：落库对话历史 + 更新会话统计（加锁，防并发写竞争）。"""
        async with self._lock:
            ctx = await self._load(session_id)
            if ctx is None:
                ctx = SessionContext.new(session_id, None)
            ctx.conversation.append(user_msg)
            ctx.conversation.append(assistant_msg)
            ctx.meta["message_count"] = ctx.meta.get("message_count", 0) + 1
            ctx.meta["last_message_at"] = _now_iso()
            await self._save(ctx)
            self._touch_index(session_id)

    async def get_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        """读取对话历史（：与 get_history 共用）。"""
        ctx = await self._load(session_id)
        return ctx.conversation if ctx is not None else []

    async def delete(self, session_id: str) -> bool:
        """删除会话：返回是否真实存在（修复 delete 恒返回 True 的隐患）。"""
        async with self._lock:
            existed = await self._load(session_id) is not None
            await self._async_delete(session_id)
            self._index.pop(session_id, None)
            return existed

    async def list_all(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        async with self._lock:
            sessions = []
            for sid in list(self._index.keys()):
                ctx = await self._load(sid)
                if ctx is None:
                    self._index.pop(sid, None)
                    continue
                info = ctx.meta
                # ：指定 user_id 时仅返回该用户的会话，实现用户隔离
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
            ctx = await self._load(session_id)
            if ctx is None:
                return
            ctx.meta["status"] = "transferred"
            await self._save(ctx)
            self._touch_index(session_id)

    async def mark_satisfaction(self, session_id: str, score: int) -> None:
        async with self._lock:
            ctx = await self._load(session_id)
            if ctx is None:
                return
            ctx.meta["satisfaction_score"] = score
            await self._save(ctx)
            self._touch_index(session_id)


# 全局会话管理器单例：默认 Agent 构造路径，供 ChatService 默认注入（保持进程内会话态一致）
SESSION_MANAGER = SessionManager()


# ─────────────────────────────────────────────────────────────────────────────
# 意图路由 + 处理器策略（ 第一/二层）：handler 作为已注册策略对象。
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class HandlerContext:
    """传递给 handler 的上下文（不含任何可变会话状态，Agent 为无状态执行器）。"""
    session_id: str
    content: str
    user_id: Optional[int]
    intent_result: Any
    agent: Optional[CustomerServiceAgent]


@dataclass
class HandlerOutcome:
    """非流式处理结果：仅含最终回复文本（quick_replies/need_transfer 由 _outcome_meta 单源推导）。"""
    response_text: str


class IntentHandler(ABC):
    """意图处理器策略接口：每个 handler_type 注册一个实例。"""

    handler_type: str = "unknown"

    @abstractmethod
    async def run(self, svc: "ChatService", ctx: HandlerContext) -> HandlerOutcome:
        """非流式：返回最终回复文本。"""

    async def run_stream(self, svc: "ChatService", ctx: HandlerContext):
        """流式：逐 token 产出（默认实现为一次性产出非流式结果）。"""
        outcome = await self.run(svc, ctx)
        yield outcome.response_text


class _TransferHandler(IntentHandler):
    handler_type = "transfer"

    async def run(self, svc: "ChatService", ctx: HandlerContext) -> HandlerOutcome:
        await svc.session_manager.mark_transferred(ctx.session_id)
        reason = "投诉" if ctx.intent_result.intent_code == "complaint" else "用户主动请求"
        if ctx.agent is not None:
            result = await ctx.agent.execute_tool(
                "transfer_human",
                {"session_id": ctx.session_id, "user_id": ctx.user_id, "reason": reason},
            )
            text = result.get("response", "已为您转接人工客服，请稍候～")
        else:
            text = "已为您转接人工客服，请稍候～"
        return HandlerOutcome(response_text=text)

    async def run_stream(self, svc: "ChatService", ctx: HandlerContext):
        outcome = await self.run(svc, ctx)
        yield outcome.response_text


class _ToolHandler(IntentHandler):
    handler_type = "tool"

    _TOOL_MAP = {
        "order_query": ("query_order", lambda c, u: {"user_message": c, "user_id": u}),
        "refund_request": ("refund", lambda c, u: {"user_message": c, "user_id": u}),
        "product_inquiry": ("query_product", lambda c, u: {"user_message": c}),
        "ticket_create": (
            "create_ticket",
            lambda c, u: {
                "session_id": None,  # 由 ChatService 注入（此处占位，run 内补）
                "user_id": u,
                "type": "consult",
                "title": (c or "用户咨询")[:20],
                "content": c or "",
            },
        ),
    }

    async def run(self, svc: "ChatService", ctx: HandlerContext) -> HandlerOutcome:
        if ctx.agent is None:
            return HandlerOutcome(response_text="正在为您处理，请稍候…")
        code = ctx.intent_result.intent_code
        if code not in self._TOOL_MAP:
            return HandlerOutcome(response_text="正在为您处理，请稍候…")
        tool_name, params_factory = self._TOOL_MAP[code]
        params = params_factory(ctx.content, ctx.user_id)
        if code == "ticket_create":
            params["session_id"] = ctx.session_id
        result = await ctx.agent.execute_tool(tool_name, params)
        text = result.get("response", "正在为您处理，请稍候…")
        return HandlerOutcome(response_text=text)

    async def run_stream(self, svc: "ChatService", ctx: HandlerContext):
        outcome = await self.run(svc, ctx)
        yield outcome.response_text


class _RagHandler(IntentHandler):
    handler_type = "rag"

    async def _search_knowledge(self, ctx: HandlerContext) -> Dict[str, Any]:
        if ctx.agent is None:
            return {"success": False}
        return await ctx.agent.execute_tool(
            "search_knowledge", {"user_message": ctx.content, "top_k": 3}
        )

    async def run(self, svc: "ChatService", ctx: HandlerContext) -> HandlerOutcome:
        tool_res = await self._search_knowledge(ctx)
        if tool_res.get("success") and tool_res.get("results"):
            text = tool_res.get("response", "")
        else:
            context = await rag_service.retrieve(ctx.content, top_k=3)
            text = await rag_service.generate(ctx.content, context)
        return HandlerOutcome(response_text=text)

    async def run_stream(self, svc: "ChatService", ctx: HandlerContext):
        tool_res = await self._search_knowledge(ctx)
        if tool_res.get("success") and tool_res.get("results"):
            yield tool_res.get("response", "")
            return
        context = await rag_service.retrieve(ctx.content, top_k=3)
        # ：流式 RAG 生成包 observe.generation，与 send 路径共享追踪体系
        with observe.generation(
            name="rag-stream-generate",
            model=getattr(llm_service, "model", "unknown"),
            input={"query": ctx.content, "context_length": len(context)},
        ):
            async for piece in rag_service.generate_stream(ctx.content, context):
                yield piece


class _LlmHandler(IntentHandler):
    handler_type = "llm"

    async def _build_messages(self, svc: "ChatService", ctx: HandlerContext) -> List[Dict[str, str]]:
        # 读取最近 HISTORY_TURNS 轮对话（：存储的每条消息含 intent/sentiment 等额外字段，
        # 发送给 LLM 时必须映射为纯 {role, content}，避免多余字段污染输入）。
        history = await svc.session_manager.get_conversation(ctx.session_id)
        clean_history = [
            {"role": m["role"], "content": m["content"]}
            for m in history[-settings.HISTORY_TURNS:]
        ]
        return [
            {"role": "system", "content": svc._get_system_prompt()},
            *clean_history,
            {"role": "user", "content": ctx.content},
        ]

    async def run(self, svc: "ChatService", ctx: HandlerContext) -> HandlerOutcome:
        messages = await self._build_messages(svc, ctx)
        text = await llm_service.chat(messages)
        return HandlerOutcome(response_text=text)

    async def run_stream(self, svc: "ChatService", ctx: HandlerContext):
        messages = await self._build_messages(svc, ctx)
        # ：流式 LLM 对话包 observe.generation，与 send 路径共享追踪体系
        with observe.generation(
            name="chat-stream",
            model=getattr(llm_service, "model", "unknown"),
            input={"messages": messages},
        ):
            async for piece in llm_service.chat_stream(messages):
                yield piece


class IntentRouter:
    """意图路由器（ 第一层）：按 handler_type 分发到已注册 handler。

    新增意图/处理器：向本路由注册一个 `IntentHandler` 实例即可，无需修改 ChatService 内部分发逻辑。
    """

    def __init__(self):
        self._registry: Dict[str, IntentHandler] = {}

    def register(self, handler_type: str, handler: IntentHandler) -> None:
        self._registry[handler_type] = handler

    def route(self, handler_type: str) -> Optional[IntentHandler]:
        handler = self._registry.get(handler_type)
        if handler is None:
            # 未知 handler_type 兜底走通用 LLM
            handler = self._registry.get("llm")
        return handler


# 模块级默认路由：四个内置 handler 注册于此；外部可通过 `intent_router.register(...)` 扩展。
intent_router = IntentRouter()
intent_router.register("transfer", _TransferHandler())
intent_router.register("tool", _ToolHandler())
intent_router.register("rag", _RagHandler())
intent_router.register("llm", _LlmHandler())


# ─────────────────────────────────────────────────────────────────────────────
# 处理结果
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class _ProcessResult:
    response_text: str
    intent_result: Any
    sent_type: SentimentType
    sent_score: float
    quick_replies: List[str]
    need_transfer: bool


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
        # 意图路由：默认复用模块级路由，可注入扩展。
        self.router = intent_router

    async def create_session(
        self,
        user_id: Optional[int] = None,
        channel: str = "web",
        initial_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建新会话：生成 session_id → 经 SessionManager.prepare 落库会话上下文。"""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        # ：删除原手搓临界区（_purge_expired/_ensure/_evict_lru 直触 _lock/_sessions）；
        # 单一临界区来源 = SessionManager.prepare。
        await self.session_manager.prepare(session_id, user_id)

        logger.info(f"会话已创建: {session_id}")

        # 欢迎消息
        welcome = "您好！我是智能客服小e，很高兴为您服务～请问有什么可以帮到您的？"
        quick_replies = ["查订单", "商品咨询", "退款退货", "促销活动", "转人工"]

        if initial_message:
            result = await self.send_message(session_id, initial_message, user_id)
            return {
                "session": await self.session_manager.get_session(session_id),
                "welcome_message": welcome,
                "quick_replies": quick_replies,
                "initial_response": result,
            }

        return {
            "session": await self.session_manager.get_session(session_id),
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

        # 1) 进入临界区：确保会话上下文存在（Redis/cache 权威副本）+ 刷新活跃时间 + 惰性淘汰
        agent = await self.session_manager.prepare(session_id, user_id)

        msg_count = len(await self.session_manager.get_conversation(session_id))

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
                "session_message_count": msg_count,
            },
        ) as root_span:

            # 2) 核心处理（ 单一真相源）：意图+情感+分发，返回统一结果
            proc = await self._core_process(session_id, content, user_id, agent, preferred_intent)

            # 3) 情感响应前缀（单源：_apply_sentiment_prefix）
            response_text = self._apply_sentiment_prefix(proc.response_text, proc.sent_type, proc.sent_score)

            # 4) 构造消息 + 统一载荷（send / stream 共用，保证强一致）
            user_msg, assistant_msg, result = self._build_messages_and_payload(
                session_id, content, response_text,
                proc.intent_result, proc.sent_type, proc.sent_score,
                proc.quick_replies, proc.need_transfer,
            )

            # 5) 持久化（//）
            await self.session_manager.commit(session_id, user_msg, assistant_msg)

            if root_span is not None:
                root_span.update(
                    output={
                        "response": response_text[:300],
                        "intent_code": proc.intent_result.intent_code,
                        "sentiment": proc.sent_type.value,
                        "need_transfer": proc.need_transfer,
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
        """流式处理用户消息，逐 token 产出 SSE 片段（ / 强一致）。

        与 send_message 保持相同的意图识别/情感分析/分发/落库语义：
        - 意图/情感 span 经 `_recognize_intent_and_sentiment` 共享；
        - 同一 handler 的 `run_stream` 在 handler 内逐 token 产出；
        - 结束时以 `_build_messages_and_payload` 构造 done 事件，载荷与 send_message 完全一致。
        """
        # 进入临界区，获取无状态 Agent 执行器
        agent = await self.session_manager.prepare(session_id, user_id)

        def _sse(event_type: str, **payload) -> str:
            return f"data: {json.dumps({'type': event_type, **payload}, ensure_ascii=False)}\n\n"

        with observe.span(name="chat-stream-message", input={"session_id": session_id, "content": content}) as root_span:
            # 意图识别 + 情感分析（：与 send 路径共用同一 span 来源）
            intent_result, (sent_type, sent_score) = await self._recognize_intent_and_sentiment(
                content, user_id, preferred_intent
            )

            handler = self.router.route(intent_result.handler_type)
            ctx = HandlerContext(
                session_id=session_id,
                content=content,
                user_id=user_id,
                intent_result=intent_result,
                agent=agent,
            )

            response_text = ""
            try:
                # 在 handler 内逐 token 产出（：流式单一真相源）
                async for piece in handler.run_stream(self, ctx):
                    response_text += piece
                    yield _sse("token", content=piece)
            except Exception as e:
                # ：工具/生成异常 → 产出 error 事件（不抛出，保证 SSE 正常结束）
                logger.error(f"流式处理异常: {e}")
                yield _sse("error", message=str(e))
                return

            # 情感响应前缀（与 send 路径同一单源）
            response_text = self._apply_sentiment_prefix(response_text, sent_type, sent_score)

            # 统一载荷（与 send_message 一致）
            quick_replies, need_transfer = self._outcome_meta(intent_result)
            user_msg, assistant_msg, result = self._build_messages_and_payload(
                session_id, content, response_text,
                intent_result, sent_type, sent_score,
                quick_replies, need_transfer,
            )

            # 持久化
            await self.session_manager.commit(session_id, user_msg, assistant_msg)

            if root_span is not None:
                root_span.update(output={"response": response_text[:300], "intent_code": intent_result.intent_code})

            # 结束事件：推送完整信息与元数据，供前端最终对齐
            yield _sse(
                "done",
                response=response_text,
                intent=result["intent"],
                sentiment=result["sentiment"],
                sentiment_score=result["sentiment_score"],
                quick_replies=quick_replies,
                need_transfer=need_transfer,
            )

    # ── ：核心处理（非流式单一真相源） ──
    async def _core_process(
        self,
        session_id: str,
        content: str,
        user_id: Optional[int],
        agent: CustomerServiceAgent,
        preferred_intent: Optional[str] = None,
    ) -> _ProcessResult:
        """意图+情感识别 → 按 handler_type 分发 → 返回统一处理结果。

        send_message 调用本方法；stream_message 复用同一意图/情感识别与 _outcome_meta，
        保证两条路径强一致。
        """
        intent_result, (sent_type, sent_score) = await self._recognize_intent_and_sentiment(
            content, user_id, preferred_intent
        )
        handler = self.router.route(intent_result.handler_type)
        ctx = HandlerContext(
            session_id=session_id,
            content=content,
            user_id=user_id,
            intent_result=intent_result,
            agent=agent,
        )
        outcome = await handler.run(self, ctx)
        quick_replies, need_transfer = self._outcome_meta(intent_result)
        return _ProcessResult(
            response_text=outcome.response_text,
            intent_result=intent_result,
            sent_type=sent_type,
            sent_score=sent_score,
            quick_replies=quick_replies,
            need_transfer=need_transfer,
        )

    # ── ：意图/情感 span 下沉（send/stream 共用同一来源） ──
    async def _recognize_intent_and_sentiment(
        self,
        content: str,
        user_id: Optional[int],
        preferred_intent: Optional[str] = None,
    ) -> Tuple[Any, Tuple[SentimentType, float]]:
        """并发执行意图识别 + 情感分析，并各自包 observe.span（两条路径共用）。"""

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

        intent_result, sent = await asyncio.gather(_recognize(), _sentiment())
        return intent_result, sent

    def _outcome_meta(self, intent_result: Any) -> Tuple[List[str], bool]:
        """由 handler_type/intent_code 单源推导 quick_replies 与 need_transfer。"""
        htype = intent_result.handler_type
        if htype == "transfer":
            return ["继续等待", "留言", "电话联系"], True
        if htype in ("tool", "rag"):
            return self._get_followup_quick_replies(intent_result.intent_code), False
        return [], False

    def _apply_sentiment_prefix(self, response_text: str, sent_type: SentimentType, sent_score: float) -> str:
        """按情感类型追加安抚/积极前缀（单源，send/stream 共用）。"""
        strategy = sentiment_service.get_response_strategy(sent_type, sent_score)
        if sent_type == SentimentType.NEGATIVE and strategy["prefix"]:
            return strategy["emoji"] + " " + strategy["prefix"] + response_text
        if sent_type == SentimentType.POSITIVE:
            return strategy["emoji"] + " " + response_text
        return response_text

    def _build_messages_and_payload(
        self,
        session_id: str,
        content: str,
        response_text: str,
        intent_result: Any,
        sent_type: SentimentType,
        sent_score: float,
        quick_replies: List[str],
        need_transfer: bool,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """构造 user/assistant 消息与统一返回载荷（send/stream 共用，保证强一致）。"""
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
        now_iso = _now_iso()

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
        result = {
            "response": response_text,
            "intent": intent_payload,
            "sentiment": sentiment_value,
            "sentiment_score": sentiment_score_value,
            "quick_replies": quick_replies,
            "need_transfer": need_transfer,
        }
        return user_msg, assistant_msg, result

    # ── 系统提示词 / 快捷回复 ──
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
        """获取对话历史（：对分页参数做非负/上限裁剪，作为路由 Query 约束的防御性兜底）"""
        try:
            page = max(1, int(page))
            page_size = max(1, min(int(page_size), 100))
        except (TypeError, ValueError):
            page, page_size = 1, 20
        all_messages = await self.session_manager.get_conversation(session_id)
        total = len(all_messages)
        start = (page - 1) * page_size
        end = start + page_size
        page_messages = all_messages[start:end]

        # 转换为带 ID 的格式（：回读 intent/sentiment/sentiment_score）
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
        """获取会话列表（：传入 user_id 时按用户隔离）"""
        return await self.session_manager.list_all(user_id=user_id)

    async def delete_session(self, session_id: str) -> bool:
        """删除会话：清理 Redis/cache 中的会话上下文。"""
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
