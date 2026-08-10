<template>
  <div class="auth-page">
    <aside class="auth-brand">
      <div class="brand-inner">
        <div class="brand-logo">
          <span class="logo-emoji">🤖</span>
          <span class="logo-text">智能客服小e</span>
        </div>
        <h1 class="brand-title">创建你的智能客服账号</h1>
        <p class="brand-sub">注册后即可享受按用户隔离的会话与订单服务，数据更私密、体验更连贯。</p>
        <ul class="brand-points">
          <li><span class="pt-icon">⚡</span> 秒级响应，订单 / 物流 / 退款一站式解答</li>
          <li><span class="pt-icon">🧠</span> 意图识别 + 情感分析，更懂你的所需</li>
          <li><span class="pt-icon">🔒</span> 账号登录，会话与数据按用户隔离</li>
        </ul>
      </div>
      <div class="brand-footer">© 2026 电商智能客服系统</div>
    </aside>

    <main class="auth-form-wrap">
      <div class="auth-card">
        <h2 class="auth-heading">注册账号</h2>
        <p class="auth-tip">填写信息，开启你的智能客服之旅</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          @submit.prevent="onSubmit"
        >
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名（2-50 位）" autocomplete="username" />
          </el-form-item>
          <el-form-item prop="email">
            <el-input v-model="form.email" placeholder="邮箱（选填）" autocomplete="email" />
          </el-form-item>
          <el-form-item prop="phone">
            <el-input v-model="form.phone" placeholder="手机号（选填）" autocomplete="tel" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="密码（至少 6 位）"
              autocomplete="new-password"
            />
          </el-form-item>
          <el-form-item prop="confirm">
            <el-input
              v-model="form.confirm"
              type="password"
              show-password
              placeholder="确认密码"
              autocomplete="new-password"
              @keyup.enter="onSubmit"
            />
          </el-form-item>

          <div class="auth-row">
            <el-checkbox v-model="remember">记住我</el-checkbox>
            <span class="auth-link" @click="goLogin">已有账号？去登录</span>
          </div>

          <el-button class="cta-btn" type="primary" :loading="loading" @click="onSubmit">
            注 册
          </el-button>
        </el-form>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const remember = ref(true)
const form = reactive({
  username: '',
  email: '',
  phone: '',
  password: '',
  confirm: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' }],
  confirm: [
    {
      required: true,
      trigger: 'blur',
      validator: (_r, value: string, cb) => {
        if (value !== form.password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
    },
  ],
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const user = await authStore.register({
        username: form.username,
        password: form.password,
        email: form.email || undefined,
        phone: form.phone || undefined,
        remember: remember.value,
      })
      ElMessage.success(`注册成功，欢迎你，${user.username}`)
      setTimeout(() => router.push('/'), 400)
    } catch {
      // 错误详情已由响应拦截器提示（如用户名已存在）
    } finally {
      loading.value = false
    }
  })
}

function goLogin() {
  router.push('/login')
}
</script>

<style scoped>
.auth-page {
  display: flex;
  min-height: 100vh;
  background: var(--bg-primary, #1a1a2e);
}

.auth-brand {
  flex: 0 0 42%;
  max-width: 42%;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 56px 48px;
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  overflow: hidden;
}
.auth-brand::after {
  content: '';
  position: absolute;
  right: -120px;
  bottom: -120px;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
}
.brand-inner { position: relative; z-index: 1; }
.brand-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 700;
}
.logo-emoji { font-size: 26px; }
.brand-title {
  margin: 28px 0 12px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.brand-sub {
  font-size: 15px;
  line-height: 1.7;
  opacity: 0.92;
  max-width: 420px;
}
.brand-points {
  list-style: none;
  margin: 32px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.brand-points li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  opacity: 0.95;
}
.pt-icon {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.16);
  font-size: 15px;
}
.brand-footer {
  position: relative;
  z-index: 1;
  font-size: 12px;
  opacity: 0.8;
}

.auth-form-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}
.auth-card {
  width: 100%;
  max-width: 380px;
}
.auth-heading {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary, #e0e0e0);
  margin-bottom: 6px;
}
.auth-tip {
  font-size: 14px;
  color: var(--text-muted, #999);
  margin-bottom: 24px;
}
.auth-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4px 0 18px;
}
.auth-link {
  font-size: 13px;
  color: var(--accent, #7c8cf8);
  cursor: pointer;
}
.auth-link:hover { text-decoration: underline; }

.cta-btn {
  width: 100%;
  border: none;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
  border-radius: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 6px 18px rgba(102, 126, 234, 0.35);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.cta-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(102, 126, 234, 0.45);
}

@media (max-width: 1024px) {
  .auth-brand { display: none; }
  .auth-form-wrap { max-width: 100%; }
}
</style>
