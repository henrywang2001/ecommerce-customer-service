import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'theme'

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(localStorage.getItem(STORAGE_KEY) === 'dark')

  function apply() {
    document.body.classList.toggle('dark', isDark.value)
  }
  apply() // 创建时立即应用，避免首屏闪烁

  watch(isDark, () => {
    apply()
    localStorage.setItem(STORAGE_KEY, isDark.value ? 'dark' : 'light')
  })

  function toggle() {
    isDark.value = !isDark.value
  }

  return { isDark, toggle }
})
