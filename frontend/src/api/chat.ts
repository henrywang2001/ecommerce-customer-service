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
}
