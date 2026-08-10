<template>
  <div class="auth-page">
    <!-- 左侧品牌叙事区 -->
    <aside class="auth-brand">
      <div class="brand-inner">
        <div class="brand-logo">
          <span class="logo-emoji">🤖</span>
          <span class="logo-text">智能客服小e</span>
        </div>
        <h1 class="brand-title">电商智能客服 · 小e</h1>
        <p class="brand-sub">7×24 小时在线的 AI 客服助手，让每一笔咨询都被温柔接住。</p>
        <ul class="brand-points">
          <li><span class="pt-icon">⚡</span> 秒级响应，订单 / 物流 / 退款一站式解答</li>
          <li><span class="pt-icon">🧠</span> 意图识别 + 情感分析，更懂你的所需</li>
          <li><span class="pt-icon">🔒</span> 账号登录，会话与数据按用户隔离</li>
        </ul>
      </div>
      <div class="brand-footer">© 2026 电商智能客服系统</div>
    </aside>

    <!-- 右侧表单区 -->
    <main class="auth-form-wrap">
      <div class="auth-card">
        <h2 class="auth-heading">欢迎回来</h2>
        <p class="auth-tip">登录以继续使用智能客服</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          @submit.prevent="onSubmit"
        >
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" autocomplete="username" />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="密码"
              autocomplete="current-password"
              @keyup.enter="onSubmit"
            />
          </el-form-item>

          <div class="auth-row">
            <el-checkbox v-model="remember">记住我</el-checkbox>
            <span class="auth-link" @click="goRegister">没有账号？去注册</span>
          </div>

          <el-button
            class="cta-btn"
            type="primary"
            :loading="loading"
            @click="onSubmit"
          >
            登 录
          </el-button>
        </el-form>

        <p class="auth-hint">
          演示账号：<code>alice / Alice@123</code> ·
          <code>bob / Bob@123</code> ·
          <code>admin / Admin@123</code>
        </p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const remember = ref(true)
const form = reactive({ username: '', password: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const user = await authStore.login(form.username, form.password, remember.value)
      ElMessage.success(`欢迎回来，${user.username}`)
      const redirect = (route.query.redirect as string) || '/'
      setTimeout(() => router.push(redirect), 400)
    } catch {
      // 错误详情已由响应拦截器提示
    } finally {
      loading.value = false
    }
  })
}

function goRegister() {
  router.push('/register')
}
</script>

<style scoped>
.auth-page {
  display: flex;
  min-height: 100vh;
  background: var(--bg-primary, #1a1a2e);
}

/* ===== 品牌区（42%） ===== */
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
  font-size: 30px;
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

/* ===== 表单区（58%） ===== */
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
  margin-bottom: 28px;
}
.auth-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4px 0 20px;
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

.auth-hint {
  margin-top: 22px;
  font-size: 12px;
  color: var(--text-muted, #999);
  text-align: center;
  line-height: 1.8;
}
.auth-hint code {
  background: var(--accent-light, rgba(124, 140, 248, 0.12));
  color: var(--accent, #7c8cf8);
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 11px;
}

/* ===== 响应式：单栏降级 ===== */
@media (max-width: 1024px) {
  .auth-brand { display: none; }
  .auth-form-wrap { max-width: 100%; }
}
</style>
