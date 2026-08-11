<template>
  <div class="main-layout">
    <!-- 左侧边栏（：会话侧边栏重构） -->
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="sidebar-logo">
        <span class="logo-icon">🤖</span>
        <span class="logo-text">智能客服小e</span>
        <button class="menu-toggle" type="button" aria-label="打开/关闭菜单" @click="sidebarOpen = !sidebarOpen">☰</button>
        <button class="theme-btn" type="button"
          :aria-label="themeStore.isDark ? '切换到浅色模式' : '切换到深色模式'"
          @click="themeStore.toggle">
          {{ themeStore.isDark ? '☀️' : '🌙' }}
        </button>
      </div>

      <el-button class="new-chat-btn" type="primary" @click="handleNewChat">
        <span class="new-chat-icon">＋</span> 新建对话
      </el-button>

      <div class="session-list">
        <div
          v-for="s in chatStore.sessions"
          :key="s.sessionId"
          class="session-item"
          :class="{ active: s.sessionId === chatStore.sessionId }"
          role="button"
          tabindex="0"
          :aria-current="s.sessionId === chatStore.sessionId ? 'page' : undefined"
          :aria-label="`选择会话 ${sessionLabel(s)}，点击进入对话`"
          @click="onSelectSession(s)"
          @keydown.enter.prevent="onSelectSession(s)"
          @keydown.space.prevent="onSelectSession(s)"
        >
          <div class="session-label">{{ sessionLabel(s) }}</div>
          <div class="session-time">{{ sessionTime(s) }}</div>
          <button
            class="session-del"
            type="button"
            title="删除会话"
            aria-label="删除会话"
            @click="onDeleteSession(s, $event)"
          >🗑️</button>
        </div>

        <div v-if="!chatStore.sessions.length" class="session-empty">
          暂无历史会话
        </div>
      </div>

      <nav class="sidebar-nav">
        <button class="nav-entry" type="button" @click="router.push('/dashboard'); sidebarOpen = false">
          📊 看板
        </button>
        <button class="nav-entry" type="button" @click="router.push('/knowledge'); sidebarOpen = false">
          📚 知识库
        </button>
      </nav>

      <!-- 用户区（：登录态展示与退出） -->
      <div class="sidebar-user" v-if="authStore.user">
        <div class="user-meta">
          <span class="user-avatar">👤</span>
          <span class="user-name">{{ authStore.user.username }}</span>
        </div>
        <button class="user-logout" title="退出登录" @click="onLogout">退出</button>
      </div>
    </aside>

    <!-- 移动端遮罩：点击关闭抽屉 -->
    <div class="sidebar-backdrop" v-if="sidebarOpen" @click="sidebarOpen = false" aria-hidden="true"></div>

    <!-- 右侧内容区：keep-alive 命中 ChatPage（ 守卫） -->
    <main class="content">
      <router-view v-slot="{ Component }">
        <keep-alive include="ChatPage">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import type { SessionInfo } from '@/types/chat'

const router = useRouter()
const chatStore = useChatStore()
const authStore = useAuthStore()
const sidebarOpen = ref(false)
const themeStore = useThemeStore()

onMounted(async () => {
  // ：用本地令牌恢复最新用户信息（刷新后保持登录态）
  await authStore.fetchMe()
  // ：优先从本地缓存恢复最近会话与消息，命中则免后端调用
  const restored = await chatStore.restoreFromLocal()
  if (!restored) {
    await chatStore.loadSessions()
    await chatStore.initSession()
  }
})

async function onLogout() {
  try {
    await ElMessageBox.confirm('确定退出当前账号吗？', '退出登录', { type: 'warning' })
  } catch {
    return
  }
  authStore.logout()
  router.push('/login')
}

function sessionLabel(s: SessionInfo): string {
  // 用 sessionId 片段做标签，避免裸 ID
  return `会话 #${(s.sessionId || '').slice(-6).toUpperCase()}`
}

function sessionTime(s: SessionInfo): string {
  const ts = s.lastMessageAt || s.startedAt || ''
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return `${(d.getMonth() + 1).toString().padStart(2, '0')}-${d
    .getDate()
    .toString()
    .padStart(2, '0')} ${d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })}`
}

function onSelectSession(s: SessionInfo) {
  chatStore.selectSession(s.sessionId)
  router.push('/')
  sidebarOpen.value = false
}

async function onDeleteSession(s: SessionInfo, event: Event) {
  // 阻止冒泡，避免触发 .session-item 的选中跳转
  event.stopPropagation()
  try {
    await ElMessageBox.confirm('确定删除该会话吗？删除后不可恢复', '确认删除', {
      type: 'warning',
    })
  } catch {
    return // 用户取消删除
  }
  await chatStore.deleteSession(s.sessionId)
  // 若删除的是当前会话且已切换/新建，回到聊天页确保视图正确
  router.push('/')
  sidebarOpen.value = false
}

// 新建对话：先建会话（会设为当前会话），若当前不在聊天页则切回，避免在面板页停留
async function handleNewChat() {
  await chatStore.startNewSession()
  if (router.currentRoute.value.path !== '/') {
    router.push('/')
  }
  sidebarOpen.value = false
}
</script>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  background: var(--bg-primary);
}

/* ===== 侧边栏 ===== */
.sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: 16px 12px;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 16px;
}
.logo-icon { font-size: 22px; }
.logo-text { font-size: 16px; font-weight: 600; color: var(--text-primary); }

.new-chat-btn {
  width: 100%;
  margin-bottom: 16px;
  border-radius: 10px;
}
.new-chat-icon { font-size: 15px; margin-right: 2px; }

.session-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.session-item {
  position: relative;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
  border: 1px solid transparent;
}
.session-item:hover {
  background: var(--accent-light);
}
.session-item.active {
  background: var(--accent-light);
  border-color: var(--accent);
}
.session-label {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
.session-empty {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  padding: 24px 0;
}

.session-del {
  position: absolute;
  top: 8px;
  right: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 6px;
  opacity: 0;
  transition: opacity 0.2s ease, background 0.2s ease;
}
.session-item:hover .session-del,
.session-item:focus-within .session-del {
  opacity: 1;
}
.session-del:hover {
  background: rgba(0, 0, 0, 0.06);
}
.session-del:focus-visible {
  opacity: 1;
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
/* 触屏设备无 hover 态，删除按钮常驻可见 */
@media (hover: none) {
  .session-del { opacity: 1; }
}

.session-item:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.sidebar-nav {
  border-top: 1px solid var(--border-color);
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav-entry {
  display: block;
  width: 100%;
  padding: 10px 12px;
  border: none;
  background: transparent;
  border-radius: 10px;
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  text-align: left;
  color: var(--text-secondary);
  transition: background 0.2s ease, color 0.2s ease;
}
.nav-entry:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.nav-entry:hover {
  background: var(--accent-light);
  color: var(--accent);
}

/* ===== 用户区 ===== */
.sidebar-user {
  margin-top: 12px;
  padding: 10px 12px;
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.user-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.user-avatar { font-size: 18px; }
.user-name {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.user-logout {
  flex-shrink: 0;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}
.user-logout:hover {
  background: var(--accent-light);
  color: var(--accent);
}

/* ===== 内容区 ===== */
.content {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 深色模式 */
body.dark .sidebar { background: var(--bg-secondary); }
body.dark .session-label { color: var(--text-primary); }

.menu-toggle {
  margin-left: auto;
  border: none;
  background: transparent;
  font-size: 20px;
  cursor: pointer;
  color: var(--text-primary);
  display: none; /* 仅移动端显示 */
}
.sidebar-backdrop {
  display: none;
}
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    z-index: 1000;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    box-shadow: 0 0 20px rgba(0,0,0,0.2);
  }
  .sidebar.open { transform: translateX(0); }
  .content { width: 100%; }
  .menu-toggle { display: block; }
  .sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.4);
    z-index: 999;
  }
}

.theme-btn {
  margin-left: auto;
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  line-height: 1;
}
</style>
