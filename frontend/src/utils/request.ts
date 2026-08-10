import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error?.response?.status
    const data = error?.response?.data

    // 401：令牌缺失/失效 → 清空登录态并跳转到登录页（F6）
    if (status === 401) {
      localStorage.removeItem('token')
      sessionStorage.removeItem('token')
      const path = window.location.pathname
      if (path !== '/login' && path !== '/register') {
        window.location.href = '/login'
      }
    }

    let msg = '请求失败，请稍后重试'
    if (data?.detail) {
      msg = typeof data.detail === 'string' ? data.detail : (data.detail.message || msg)
    } else if (typeof data?.message === 'string') {
      msg = data.message
    }
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default request
