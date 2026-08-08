// 对话相关类型定义

export interface Message {
  id: string
  sessionId: string
  senderType: 'user' | 'bot' | 'agent'
  content: string
  content_type?: string
  createdAt: string
  isUser: boolean
  isError?: boolean
  intent?: IntentInfo
  sentiment?: SentimentType
  sentiment_score?: number
}

export interface IntentInfo {
  intent_code: string
  intent_name: string
  confidence: number
  entities?: Entity[]
  handler_type: string
  priority: number
}

export interface Entity {
  type: string
  value: string
  start: number
  end: number
}

export type SentimentType = 'positive' | 'neutral' | 'negative'

export interface SessionInfo {
  sessionId: string
  userId?: number
  status: string
  startedAt: string
  lastMessageAt?: string
  message_count: number
  bot_name: string
}

export interface SendMessageRequest {
  session_id: string
  content: string
  user_id?: number
  content_type?: string
}

export interface SendMessageResponse {
  response: string
  intent: IntentInfo
  sentiment: SentimentType
  sentiment_score: number
  quick_replies: string[]
  need_transfer: boolean
}

export interface CreateSessionResponse {
  session: {
    session_id: string
    user_id?: number
    status: string
    started_at: string
    message_count: number
    bot_name: string
  }
  welcome_message: string
  quick_replies: string[]
  initial_response?: Record<string, any> | null
}
