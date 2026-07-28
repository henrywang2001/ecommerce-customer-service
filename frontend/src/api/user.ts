import request from '@/utils/request'

export const userApi = {
  login(username: string, password: string) {
    return request.post('/api/v1/user/login', { username, password })
  },
  register(data: { username: string; password: string; email?: string }) {
    return request.post('/api/v1/user/register', data)
  },
}
