import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'theme'

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(localStorage.getItem(STORAGE_KEY) === 'dark')

  function apply() {
    // 同时切换 <html> 与 <body> 的 dark 类：
    // - Element Plus 暗色主题依赖 html.dark（css-vars.css 选择器）
    // - 项目自建组件的暗色覆盖依赖 body.dark
    document.documentElement.classList.toggle('dark', isDark.value)
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
