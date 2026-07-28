import request from '@/utils/request'

export const intentApi = {
  recognize(text: string) {
    return request.post('/api/v1/intent/recognize', { text })
  },
}
