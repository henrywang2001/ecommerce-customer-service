import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi, streamSend } from '@/api/chat'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import type { Message, SentimentType, SessionInfo } from '@/types/chat'

// ===== 本地持久化常量 =====
const CACHE_KEY = 'ecommerce-chat-cache-v1'
const MAX_CACHED_SESSIONS = 10
const MAX_MESSAGES_PER_SESSION = 200

export const useChatStore = defineStore('chat', () => {
  // ===== State =====
  const messages = ref<Message[]>([])
  const sessionId = ref<string>('')
  const activeSessionId = ref<string>('')
  const sessions = ref<SessionInfo[]>([])
  const currentSentiment = ref<SentimentType | null>(null)
  const sentimentScore = ref(0)
  const quickReplies = ref<string[]>([])
  const isConnected = ref(false)
  const isTyping = ref(false)
  const sessionError = ref<string | null>(null)

  // 本地消息缓存（按 sessionId 存储，供 selectSession / restoreFromLocal 复用）
  const messagesBySession = ref<Record<string, Message[]>>({})

  // ===== Getters =====
  const lastMessage = computed(() => messages.value[messages.value.length - 1] || null)

  // ===== 映射辅助 =====
  function mapSession(raw: any): SessionInfo {
    return {
      sessionId: raw.session_id,
      userId: raw.user_id,
      status: raw.status,
      startedAt: raw.started_at,
      lastMessageAt: raw.last_message_at,
      message_count: raw.message_count ?? 0,
      bot_name: raw.bot_name ?? '智能客服小e',
    }
  }

  function mapHistoryItem(m: any): Message {
    return {
      id: String(m.id),
      sessionId: m.session_id,
      senderType: m.sender_type === 'user' ? 'user' : 'bot',
      content: m.content,
      createdAt: m.created_at,
      isUser: m.sender_type === 'user',
      intent: m.intent,
      sentiment: m.sentiment,
      sentiment_score: m.sentiment_score,
    }
  }

  async function fetchHistory(id: string): Promise<Message[]> {
    const data: any = await chatApi.getHistory(id)
    const items = Array.isArray(data?.items) ? data.items : []
    return items.map(mapHistoryItem)
  }

  // ===== Actions =====
  async function initSession() {
    isTyping.value = false
    // 幂等守卫：已有激活会话则直接返回，避免重复欢迎语/重复建会话
    if (activeSessionId.value) return
    try {
      // ：携带已登录用户身份，使后端可按用户隔离会话/强制 requires_auth
      const authStore = useAuthStore()
      const result: any = await chatApi.createSession({ user_id: authStore.user?.id })
      const sid = result.session.session_id
      sessionId.value = sid
      activeSessionId.value = sid
      isConnected.value = true
      quickReplies.value = result.quick_replies || []
      const mapped = mapSession(result.session)
      if (!sessions.value.find((s) => s.sessionId === sid)) {
        sessions.value.push(mapped)
      }
      clearMessages()
      messages.value.push({
        id: 'welcome',
        sessionId: sid,
        senderType: 'bot',
        content: result.welcome_message,
        createdAt: new Date().toISOString(),
        isUser: false,
      })
      persistToLocal()
    } catch (error) {
      console.error('初始化会话失败:', error)
      isConnected.value = false
      sessionError.value = '会话连接失败，请检查网络后重试'
      ElMessage.error('会话连接失败，请稍后重试')
    }
  }

  async function retryInit() {
    sessionError.value = null
    await initSession()
  }

  async function sendMessage(content: string) {
    const sid = sessionId.value
    if (!sid) {
      if (!sessionError.value) ElMessage.warning('会话未建立，请稍后再试')
      return
    }

    // 该会话的权威缓冲区（缺失时用当前视图初始化，保留欢迎语/历史）
    const buf =
      messagesBySession.value[sid] ||
      (messagesBySession.value[sid] = sid === sessionId.value ? messages.value : [])

    const userMsg: Message = {
      id: Date.now().toString(),
      sessionId: sid,
      senderType: 'user',
      content,
      createdAt: new Date().toISOString(),
      isUser: true,
    }
    buf.push(userMsg)
    if (sid === sessionId.value && messages.value !== buf) messages.value = buf
    // 健壮性：用户消息落盘立即持久化，避免机器人回复前刷新导致输入丢失
    persistToLocal()
    isTyping.value = true

    try {
      const authStore = useAuthStore()
      const result = await chatApi.sendMessage({
        session_id: sid,
        content,
        user_id: authStore.user?.id,
      })

      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        sessionId: sid,
        senderType: 'bot',
        content: result.response,
        createdAt: new Date().toISOString(),
        isUser: false,
        intent: result.intent,
        sentiment: result.sentiment,
        sentiment_score: result.sentiment_score,
      }
      buf.push(botMsg)
      if (sid === sessionId.value && messages.value !== buf) messages.value = buf
      if (sid === sessionId.value) {
        currentSentiment.value = result.sentiment
        sentimentScore.value = result.sentiment_score
        quickReplies.value = result.quick_replies || []
      }
      persistToLocal()
    } catch (error) {
      console.error('发送消息失败:', error)
      const errMsg: Message = {
        id: (Date.now() + 2).toString(),
        sessionId: sid,
        senderType: 'bot',
        content: '抱歉，消息发送失败，请稍后重试。',
        createdAt: new Date().toISOString(),
        isUser: false,
        isError: true,
      }
      buf.push(errMsg)
      if (sid === sessionId.value && messages.value !== buf) messages.value = buf
      persistToLocal()
    } finally {
      if (sid === sessionId.value) isTyping.value = false
    }
  }

  async function sendMessageStream(content: string) {
    const sid = sessionId.value
    if (!sid) {
      if (!sessionError.value) ElMessage.warning('会话未建立，请稍后再试')
      return
    }

    const buf =
      messagesBySession.value[sid] ||
      (messagesBySession.value[sid] = sid === sessionId.value ? messages.value : [])

    const userMsg: Message = {
      id: Date.now().toString(),
      sessionId: sid,
      senderType: 'user',
      content,
      createdAt: new Date().toISOString(),
      isUser: true,
    }
    buf.push(userMsg)
    if (sid === sessionId.value && messages.value !== buf) messages.value = buf
    // 健壮性：用户消息落盘立即持久化，避免机器人回复前刷新导致输入丢失
    persistToLocal()
    isTyping.value = true

    const botId = (Date.now() + 1).toString()
    const botMsg: Message = {
      id: botId,
      sessionId: sid,
      senderType: 'bot',
      content: '',
      createdAt: new Date().toISOString(),
      isUser: false,
    }
    buf.push(botMsg)
    if (sid === sessionId.value && messages.value !== buf) messages.value = buf

    let gotToken = false

    const fallbackToNonStreaming = () => {
      const ui = buf.indexOf(userMsg)
      if (ui !== -1) buf.splice(ui, 1)
      const bi = buf.indexOf(botMsg)
      if (bi !== -1) buf.splice(bi, 1)
      if (sid === sessionId.value && messages.value !== buf) messages.value = buf
      void sendMessage(content)
    }

    try {
      const authStore = useAuthStore()
      await streamSend(
        { session_id: sid, content, user_id: authStore.user?.id },
        {
          onToken: (t: string) => {
            gotToken = true
            botMsg.content += t
            if (sid === sessionId.value && messages.value !== buf) messages.value = buf
          },
          onDone: (payload: any) => {
            botMsg.content = payload.response
            botMsg.intent = payload.intent
            botMsg.sentiment = payload.sentiment
            botMsg.sentiment_score = payload.sentiment_score
            if (sid === sessionId.value) {
              currentSentiment.value = payload.sentiment
              sentimentScore.value = payload.sentiment_score
              quickReplies.value = payload.quick_replies || []
            }
            persistToLocal()
          },
          onError: (msg: string) => {
            if (!gotToken) {
              fallbackToNonStreaming()
            } else {
              botMsg.content += `\n\n⚠️ ${msg}`
              persistToLocal()
            }
          },
        },
      )
    } catch (error) {
      console.error('流式发送失败:', error)
      if (!gotToken) fallbackToNonStreaming()
    } finally {
      if (sid === sessionId.value) isTyping.value = false
    }
  }

  // ：历史合并——按消息 id 去重，并按时间排序，避免本地缓存与后端历史重复或乱序
  function mergeMessages(existing: Message[], incoming: Message[]): Message[] {
    const byId = new Map<string, Message>()
    for (const m of existing) byId.set(m.id, m)
    for (const m of incoming) if (!byId.has(m.id)) byId.set(m.id, m)
    return Array.from(byId.values()).sort(
      (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
    )
  }

  async function loadSessions() {
    try {
      const data: any = await request.get('/api/v1/chat/sessions')
      const fresh = Array.isArray(data?.sessions) ? data.sessions.map(mapSession) : []
      // 与本地缓存去重合并（按 sessionId）
      const merged = new Map<string, SessionInfo>()
      for (const s of sessions.value) merged.set(s.sessionId, s)
      for (const s of fresh) merged.set(s.sessionId, s)
      sessions.value = Array.from(merged.values())
    } catch (error) {
      console.error('加载会话列表失败:', error)
    }
  }

  async function startNewSession() {
    isTyping.value = false
    try {
      const authStore = useAuthStore()
      const result: any = await chatApi.createSession({ user_id: authStore.user?.id })
      const sid = result.session.session_id
      const mapped = mapSession(result.session)
      if (!sessions.value.find((s) => s.sessionId === sid)) {
        sessions.value.push(mapped)
      }
      activeSessionId.value = sid
      sessionId.value = sid
      clearMessages()
      messages.value.push({
        id: 'welcome',
        sessionId: sid,
        senderType: 'bot',
        content: result.welcome_message,
        createdAt: new Date().toISOString(),
        isUser: false,
      })
      quickReplies.value = result.quick_replies || []
      isConnected.value = true
      persistToLocal()
    } catch (error) {
      console.error('新建会话失败:', error)
    }
  }

  async function selectSession(id: string) {
    isTyping.value = false
    activeSessionId.value = id
    sessionId.value = id
    // 优先从本地缓存恢复，缺失则回源后端历史接口并与本地缓冲去重合并
    const cached = messagesBySession.value[id]
    if (cached && cached.length) {
      messages.value = cached
    } else {
      try {
        const incoming = await fetchHistory(id)
        const buf = messagesBySession.value[id] || []
        messages.value = mergeMessages(buf, incoming)
      } catch (error) {
        console.error('切换会话加载失败:', error)
        messages.value = messagesBySession.value[id] || []
      }
    }
    persistToLocal()
  }

  // ===== 本地持久化 =====
  // ：节流（带尾随补偿）——避免每次状态变更都同步序列化全部会话，降低主线程卡顿
  let _lastPersist = 0
  let _persistTimer: ReturnType<typeof setTimeout> | null = null
  const PERSIST_INTERVAL = 400
  function persistToLocal() {
    const now = Date.now()
    const remaining = PERSIST_INTERVAL - (now - _lastPersist)
    if (remaining <= 0) {
      _lastPersist = now
      doPersist()
    } else if (_persistTimer === null) {
      _persistTimer = setTimeout(() => {
        _persistTimer = null
        _lastPersist = Date.now()
        doPersist()
      }, remaining)
    }
  }

  function doPersist() {
    try {
      if (sessionId.value && messages.value.length) {
        messagesBySession.value[sessionId.value] = messages.value
      }
      // 会话数上限：按最近活跃时间淘汰最旧的会话
      let entries = Object.entries(messagesBySession.value)
      if (entries.length > MAX_CACHED_SESSIONS) {
        entries.sort((a, b) => sessionLastTime(a[0]) - sessionLastTime(b[0]))
        const dropCount = entries.length - MAX_CACHED_SESSIONS
        for (const [sid] of entries.slice(0, dropCount)) {
          delete messagesBySession.value[sid]
        }
      }
      // 单会话消息数上限
      for (const sid of Object.keys(messagesBySession.value)) {
        const arr = messagesBySession.value[sid]
        if (arr.length > MAX_MESSAGES_PER_SESSION) {
          messagesBySession.value[sid] = arr.slice(arr.length - MAX_MESSAGES_PER_SESSION)
        }
      }
      const payload = {
        activeSessionId: activeSessionId.value,
        sessions: sessions.value,
        messagesBySession: messagesBySession.value,
        // ：持久化快捷回复，刷新后可直接恢复（无需再发一条消息才出现）
        quickReplies: quickReplies.value,
      }
      localStorage.setItem(CACHE_KEY, JSON.stringify(payload))
    } catch (error) {
      console.error('本地持久化失败:', error)
    }
  }

  function sessionLastTime(sid: string): number {
    const arr = messagesBySession.value[sid]
    if (arr && arr.length) {
      const t = new Date(arr[arr.length - 1].createdAt).getTime()
      if (!isNaN(t)) return t
    }
    const s = sessions.value.find((x) => x.sessionId === sid)
    if (s?.lastMessageAt) {
      const t = new Date(s.lastMessageAt).getTime()
      if (!isNaN(t)) return t
    }
    if (s?.startedAt) {
      const t = new Date(s.startedAt).getTime()
      if (!isNaN(t)) return t
    }
    return 0
  }

  function restoreFromLocal(): boolean {
    try {
      const raw = localStorage.getItem(CACHE_KEY)
      if (!raw) return false
      const data = JSON.parse(raw)
      if (!data || typeof data !== 'object') return false
      sessions.value = Array.isArray(data.sessions) ? data.sessions : []
      // ：恢复快捷回复，避免刷新后快捷回复消失
      quickReplies.value = Array.isArray(data.quickReplies) ? data.quickReplies : []
      messagesBySession.value =
        data.messagesBySession && typeof data.messagesBySession === 'object'
          ? data.messagesBySession
          : {}
      const active = data.activeSessionId
      if (!active) return false
      activeSessionId.value = active
      sessionId.value = active
      const restored = messagesBySession.value[active]
      messages.value = Array.isArray(restored) ? restored : []
      isConnected.value = true
      return true
    } catch (error) {
      console.error('本地恢复失败:', error)
      return false
    }
  }

  function clearMessages() {
    messages.value = []
  }

  async function deleteSession(id: string) {
    // 1. 调用后端删除（失败也继续清理本地，保持 UI 一致）
    try {
      await chatApi.deleteSession(id)
    } catch (error) {
      console.error('删除会话请求失败，将继续清理本地数据:', error)
    }
    // 2. 从会话列表移除
    sessions.value = sessions.value.filter((s) => s.sessionId !== id)
    // 3. 移除本地消息缓存
    delete messagesBySession.value[id]
    // 4. 若删除的是当前会话，切换到其它会话或兜底新建
    if (activeSessionId.value === id) {
      const remaining = [...sessions.value]
      remaining.sort(
        (a, b) => sessionLastTime(b.sessionId) - sessionLastTime(a.sessionId),
      )
      const next = remaining[0]
      if (next) {
        await selectSession(next.sessionId)
      } else {
        clearMessages()
        await startNewSession()
      }
    }
    // 5. 同步本地持久化
    persistToLocal()
  }

  // ：提交会话满意度评价（接线此前未使用的 chatApi.rateSession）
  async function rateSession(score: number, comment?: string) {
    if (!sessionId.value) return
    try {
      await chatApi.rateSession(sessionId.value, score, comment)
    } catch (error) {
      console.error('评价提交失败:', error)
      throw error
    }
  }

  return {
    messages,
    sessionId,
    activeSessionId,
    sessions,
    currentSentiment,
    sentimentScore,
    quickReplies,
    isConnected,
    isTyping,
    sessionError,
    lastMessage,
    initSession,
    sendMessage,
    sendMessageStream,
    loadSessions,
    startNewSession,
    selectSession,
    rateSession,
    persistToLocal,
    restoreFromLocal,
    clearMessages,
    deleteSession,
    retryInit,
  }
})
