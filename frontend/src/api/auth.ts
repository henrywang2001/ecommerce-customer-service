import request from '@/utils/request'

export interface AuthUser {
  id: number
  username: string
  email?: string | null
  phone?: string | null
  user_type: string
  avatar_url?: string | null
  is_active: boolean
  created_at: string
}

export interface TokenResult {
  access_token: string
  token_type: string
  user: AuthUser
}

export const authApi = {
  /** 登录 */
  login(data: { username: string; password: string }) {
    return request.post<unknown, TokenResult>('/api/v1/auth/login', data)
  },
  /** 注册 */
  register(data: { username: string; password: string; email?: string; phone?: string }) {
    return request.post<unknown, TokenResult>('/api/v1/auth/register', data)
  },
  /** 获取当前登录用户 */
  me() {
    return request.get<unknown, AuthUser>('/api/v1/auth/me')
  },
}
