import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi } from '@/api/chat'
import type { Message, SentimentType } from '@/types/chat'

export const useChatStore = defineStore('chat', () => {
  // State
  const messages = ref<Message[]>([])
  const sessionId = ref<string>('')
  const currentSentiment = ref<SentimentType | null>(null)
  const sentimentScore = ref(0)
  const quickReplies = ref<string[]>([])
  const isConnected = ref(false)
  const isTyping = ref(false)

  // Getters
  const lastMessage = computed(() => messages.value[messages.value.length - 1] || null)

  // Actions
  async function initSession() {
    try {
      const result = await chatApi.createSession()
      sessionId.value = result.session.session_id
      isConnected.value = true
      quickReplies.value = result.quick_replies || []
      // 添加欢迎消息
      messages.value.push({
        id: 'welcome',
        sessionId: sessionId.value,
        senderType: 'bot',
        content: result.welcome_message,
        createdAt: new Date().toISOString(),
        isUser: false,
      })
    } catch (error) {
      console.error('初始化会话失败:', error)
    }
  }

  async function sendMessage(content: string) {
    if (!sessionId.value) return

    // 添加用户消息
    const userMsg: Message = {
      id: Date.now().toString(),
      sessionId: sessionId.value,
      senderType: 'user',
      content,
      createdAt: new Date().toISOString(),
      isUser: true,
    }
    messages.value.push(userMsg)
    isTyping.value = true

    try {
      const result = await chatApi.sendMessage({
        session_id: sessionId.value,
        content,
      })

      // 添加机器人回复
      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        sessionId: sessionId.value,
        senderType: 'bot',
        content: result.response,
        createdAt: new Date().toISOString(),
        isUser: false,
        intent: result.intent,
        sentiment: result.sentiment,
        sentiment_score: result.sentiment_score,
      }
      messages.value.push(botMsg)

      // 更新状态
      currentSentiment.value = result.sentiment
      sentimentScore.value = result.sentiment_score
      quickReplies.value = result.quick_replies || []
    } catch (error) {
      console.error('发送消息失败:', error)
      // 添加错误提示
      messages.value.push({
        id: (Date.now() + 2).toString(),
        sessionId: sessionId.value,
        senderType: 'bot',
        content: '抱歉，消息发送失败，请稍后重试。',
        createdAt: new Date().toISOString(),
        isUser: false,
        isError: true,
      })
    } finally {
      isTyping.value = false
    }
  }

  async function loadHistory() {
    if (!sessionId.value) return
    try {
      const history = await chatApi.getHistory(sessionId.value) as any
      messages.value = history.messages.map((m: any) => ({
        ...m,
        isUser: m.sender_type === 'user',
      }))
    } catch (error) {
      console.error('加载历史记录失败:', error)
    }
  }

  function clearMessages() {
    messages.value = []
  }

  return {
    messages,
    sessionId,
    currentSentiment,
    sentimentScore,
    quickReplies,
    isConnected,
    isTyping,
    lastMessage,
    initSession,
    sendMessage,
    loadHistory,
    clearMessages,
  }
})
