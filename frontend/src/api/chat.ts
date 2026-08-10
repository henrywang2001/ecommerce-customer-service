import request from '@/utils/request'
import type {
  SendMessageRequest,
  SendMessageResponse,
  CreateSessionResponse,
} from '@/types/chat'

export const chatApi = {
  /** 创建会话 */
  createSession(data?: { user_id?: number; channel?: string }) {
    return request.post<any, CreateSessionResponse>('/api/v1/chat/session', data || {})
  },

  /** 发送消息 */
  sendMessage(data: SendMessageRequest) {
    return request.post<any, SendMessageResponse>('/api/v1/chat/send', data)
  },

  /** 获取历史消息 */
  getHistory(sessionId: string, page = 1, pageSize = 20) {
    return request.get('/api/v1/chat/history', {
      params: { session_id: sessionId, page, page_size: pageSize },
    })
  },

  /** 转人工 */
  transferToHuman(sessionId: string, reason?: string) {
    return request.post('/api/v1/chat/transfer', { session_id: sessionId, reason })
  },

  /** 评价会话 */
  rateSession(sessionId: string, score: number, comment?: string) {
    return request.post('/api/v1/chat/rate', { session_id: sessionId, score, comment })
  },

  /** 删除会话 */
  deleteSession(sessionId: string) {
    return request.delete(`/api/v1/chat/sessions/${sessionId}`)
  },
}

/**
 * 流式发送消息（P6）：用 fetch + ReadableStream 解析 SSE，逐 token 回调。
 * 不使用 axios（拦截器对流式响应不友好），手动携带 Authorization。
 */
export async function streamSend(
  data: SendMessageRequest,
  handlers: {
    onToken: (content: string) => void
    onDone: (payload: any) => void
    onError: (message: string) => void
  },
): Promise<void> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const baseURL = (import.meta.env.VITE_API_BASE_URL as string) || ''
  const resp = await fetch(`${baseURL}/api/v1/chat/send_stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })
  if (!resp.ok || !resp.body) {
    handlers.onError(`请求失败 (${resp.status})`)
    return
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const dataLine = block.split('\n').find((l) => l.startsWith('data:'))
      if (!dataLine) continue
      const jsonStr = dataLine.slice(5).trim()
      try {
        const evt = JSON.parse(jsonStr)
        if (evt.type === 'token') handlers.onToken(evt.content)
        else if (evt.type === 'done') handlers.onDone(evt)
        else if (evt.type === 'error') handlers.onError(evt.message)
      } catch {
        /* 忽略不完整/非法块 */
      }
    }
  }
}
