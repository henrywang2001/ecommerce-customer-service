"""对话服务 - 整合意图识别、情感分析、RAG、Agent（集成 Langfuse 追踪）"""
from typing import Dict, Any, Optional, List
import uuid
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
_conversations: Dict[str, List[Dict[str, str]]] = {}
_agents: Dict[str, CustomerServiceAgent] = {}


class ChatService:
    """对话服务"""

    async def create_session(
        self,
        user_id: Optional[int] = None,
        channel: str = "web",
        initial_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建新会话"""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        import datetime
        session_info = {
            "session_id": session_id,
            "user_id": user_id,
            "status": "active",
            "started_at": datetime.datetime.utcnow(),
            "message_count": 0,
            "bot_name": "智能客服小e",
        }
        _sessions[session_id] = session_info
        _conversations[session_id] = []

        # 创建 Agent 实例
        agent = CustomerServiceAgent(session_id, user_id)
        _agents[session_id] = agent

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
                # 转人工
                with observe.span(name="handle-transfer") as t_span:
                    response_text = await self._handle_transfer(content, intent_result)
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
                    response_text = await self._handle_with_tools(content, intent_result, user_id)
                    quick_replies = self._get_followup_quick_replies(intent_result.intent_code)
                    if tool_span is not None:
                        tool_span.update(output=response_text[:200])

            elif intent_result.handler_type == "rag":
                # RAG 检索回答 — rag_service 内部已有追踪
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

            # 5. 存储对话历史
            _conversations[session_id].append({"role": "user", "content": content})
            _conversations[session_id].append({"role": "assistant", "content": response_text})

            # 更新会话信息
            if session_id in _sessions:
                _sessions[session_id]["message_count"] += 1
                _sessions[session_id]["last_message_at"] = __import__("datetime").datetime.utcnow()

            result = {
                "response": response_text,
                "intent": {
                    "intent_code": intent_result.intent_code,
                    "intent_name": intent_result.intent_name,
                    "confidence": intent_result.confidence,
                    "entities": [e.model_dump() for e in intent_result.entities],
                    "handler_type": intent_result.handler_type,
                    "priority": intent_result.priority,
                },
                "sentiment": sent_type.value,
                "sentiment_score": round(sent_score, 2),
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

            # 确保数据刷新到 Langfuse
            observe.flush()
            return result

    async def _handle_transfer(self, content: str, intent_result) -> str:
        """处理转人工"""
        if intent_result.intent_code == "complaint":
            return (
                "非常抱歉给您带来不好的体验，已为您优先转接投诉处理专员。\n\n"
                "📞 如需紧急处理，可拨打客服热线 400-123-4567\n\n"
                "当前预计等待时间约 2 分钟，客服专员将尽快接入…"
            )
        return (
            "已为您转接人工客服，请稍候～\n\n"
            "💡 温馨提示：请保持当前页面，客服将自动接入。\n"
            "如需紧急帮助，可拨打客服热线 400-123-4567"
        )

    async def _handle_with_tools(self, content: str, intent_result, user_id: Optional[int]) -> str:
        """使用工具处理（Mock 实现，实际会调用 Agent 工具）"""
        code = intent_result.intent_code

        if code == "order_query":
            # 提取订单号
            import re
            match = re.search(r'ORDER[\w]{8,20}', content, re.IGNORECASE)
            if match:
                order_no = match.group().upper()
                return (
                    f"📦 订单详情\n━━━━━━━━━━━━━━━━━━━━\n"
                    f"订单号：{order_no}\n"
                    f"商品：Apple iPhone 15 Pro Max 256GB ×1\n"
                    f"实付金额：¥9,599.00\n"
                    f"订单状态：🚚 已发货\n"
                    f"快递公司：顺丰速运\n"
                    f"运单号：SF1234567890\n"
                    f"预计送达：2-3 天内\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📍 收货人：张先生 138****6789\n"
                    f"收货地址：北京市朝阳区建国路88号"
                )
            return (
                "📋 您的近期订单：\n\n"
                "1. 🚚 ORDER20260315001 Apple iPhone 15 Pro Max — ¥9,599 已发货\n"
                "2. 💳 ORDER20260401001 戴森吹风机 HD15 — ¥2,699 待发货\n"
                "3. ✅ ORDER20260310005 Nike Air Jordan 1 — ¥1,499 已收货\n\n"
                '回复「查订单 [订单号]」可查看详情'
            )

        if code == "refund_request":
            return (
                "📋 退款政策说明：\n\n"
                "【退款时效】\n"
                "• 取消订单：1-3 个工作日原路退回\n"
                "• 退货退款：收到商品后 1-3 个工作日处理\n"
                "• 退款路径：退回原支付账户\n\n"
                "【申请流程】\n"
                "1. 在订单详情页点击「申请退款」\n"
                "2. 选择退款原因并提交\n"
                "3. 等待审核（通常1小时内）\n\n"
                "需要帮您提交退款申请吗？请提供订单号。"
            )

        return "正在为您处理，请稍候…"

    async def _handle_with_llm(self, session_id: str, content: str, intent_result) -> str:
        """使用 LLM 直接回答"""
        history = _conversations.get(session_id, [])
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            *history[-6:],  # 最近 3 轮对话
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

        # 转换为带 ID 的格式
        result = []
        for i, msg in enumerate(page_messages):
            result.append({
                "id": start + i + 1,
                "session_id": session_id,
                "sender_type": "user" if msg["role"] == "user" else "bot",
                "content": msg["content"],
                "content_type": "text",
                "created_at": "",  # 简化处理
            })

        return {"messages": result, "total": total, "page": page, "page_size": page_size}

    async def transfer_to_human(self, session_id: str, reason: str = "用户主动请求") -> Dict[str, Any]:
        """转人工"""
        if session_id in _sessions:
            _sessions[session_id]["status"] = "transferred"
        return {
            "success": True,
            "message": "已为您转接人工客服",
            "transfer_id": f"TRF_{__import__('uuid').uuid4().hex[:8]}",
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
