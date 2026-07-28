import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const username = ref('访客')
  const userId = ref<number | null>(null)
  const isLoggedIn = ref(false)

  function setUser(name: string, id: number | null = null) {
    username.value = name
    userId.value = id
    isLoggedIn.value = true
  }

  function logout() {
    username.value = '访客'
    userId.value = null
    isLoggedIn.value = false
  }

  return { username, userId, isLoggedIn, setUser, logout }
})
