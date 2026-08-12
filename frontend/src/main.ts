import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'

// ：Element Plus 改为按需自动导入（见 vite.config.ts 的 AutoImport / Components 插件），
// 模板内组件样式由解析器自动注入；此处仅保留函数式组件（ElMessage / ElMessageBox）
// 所需的样式——自动解析器不会为脚本中程序化调用的弹层注入样式，需显式引入。
import 'element-plus/theme-chalk/base.css'
// Element Plus 暗色主题：需配合 <html class="dark"> 生效（theme.ts 已同步切换）
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'element-plus/theme-chalk/el-overlay.css'
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'

const app = createApp(App)
// 插件注册保持不变（router / pinia 等）
app.use(router)
app.use(createPinia())
app.mount('#app')
