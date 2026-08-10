import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type AuthUser } from '@/api/auth'

const TOKEN_KEY = 'token'
const USER_KEY = 'auth_user'

function _readToken(): string {
  // 优先 localStorage（记住我），回退 sessionStorage（临时登录）
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) || ''
}

function _loadUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as AuthUser) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(_readToken())
  const user = ref<AuthUser | null>(_loadUser())
  const isLoggedIn = computed(() => !!token.value)

  function _persist(remember: boolean = true) {
    // 清理两种存储，避免残留导致状态不一致
    localStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(TOKEN_KEY)
    if (token.value) {
      const store = remember ? localStorage : sessionStorage
      store.setItem(TOKEN_KEY, token.value)
    }
    if (user.value) localStorage.setItem(USER_KEY, JSON.stringify(user.value))
    else localStorage.removeItem(USER_KEY)
  }

  async function login(
    username: string,
    password: string,
    remember = true,
  ): Promise<AuthUser> {
    const res = await authApi.login({ username, password })
    token.value = res.access_token
    user.value = res.user
    _persist(remember)
    return res.user
  }

  async function register(payload: {
    username: string
    password: string
    email?: string
    phone?: string
    remember?: boolean
  }): Promise<AuthUser> {
    const res = await authApi.register(payload)
    token.value = res.access_token
    user.value = res.user
    _persist(payload.remember ?? true)
    return res.user
  }

  /** 用本地令牌拉取最新用户信息（用于刷新页面后恢复登录态） */
  async function fetchMe(): Promise<AuthUser | null> {
    if (!token.value) return null
    try {
      user.value = await authApi.me()
      _persist()
    } catch {
      // 令牌失效：清空登录态
      token.value = ''
      user.value = null
      _persist()
    }
    return user.value
  }

  function logout() {
    token.value = ''
    user.value = null
    _persist(true)
    // 兜底清理临时登录态
    sessionStorage.removeItem(TOKEN_KEY)
  }

  return { token, user, isLoggedIn, login, register, fetchMe, logout }
})
