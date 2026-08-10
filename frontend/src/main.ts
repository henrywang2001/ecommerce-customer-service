import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'

// P11：Element Plus 按需引入——仅注册实际使用的组件，避免整包 JS 被打入 bundle
import {
  ElButton,
  ElInput,
  ElDialog,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElCheckbox,
} from 'element-plus'
// 保留整份样式表，确保 ElMessage / ElMessageBox 等函数式组件的弹层样式不丢失
import 'element-plus/dist/index.css'

const app = createApp(App)
app.component(ElButton.name!, ElButton)
app.component(ElInput.name!, ElInput)
app.component(ElDialog.name!, ElDialog)
app.component(ElForm.name!, ElForm)
app.component(ElFormItem.name!, ElFormItem)
app.component(ElSelect.name!, ElSelect)
app.component(ElOption.name!, ElOption)
app.component(ElCheckbox.name!, ElCheckbox)
app.use(router)
app.use(createPinia())
app.mount('#app')
