<template>
  <div class="main-layout">
    <!-- 左侧边栏（U1：会话侧边栏重构） -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">🤖</span>
        <span class="logo-text">智能客服小e</span>
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
          @click="chatStore.selectSession(s.sessionId); router.push('/')"
        >
          <div class="session-label">{{ sessionLabel(s) }}</div>
          <div class="session-time">{{ sessionTime(s) }}</div>
          <button
            class="session-del"
            title="删除会话"
            @click="onDeleteSession(s, $event)"
          >🗑️</button>
        </div>

        <div v-if="!chatStore.sessions.length" class="session-empty">
          暂无历史会话
        </div>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-entry" @click="router.push('/dashboard')">
          📊 看板
        </div>
        <div class="nav-entry" @click="router.push('/knowledge')">
          📚 知识库
        </div>
      </nav>
    </aside>

    <!-- 右侧内容区：keep-alive 命中 ChatPage（F1 守卫） -->
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
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { ElMessageBox } from 'element-plus'
import type { SessionInfo } from '@/types/chat'

const router = useRouter()
const chatStore = useChatStore()

onMounted(async () => {
  // B1/F1：优先从本地缓存恢复最近会话与消息，命中则免后端调用
  const restored = await chatStore.restoreFromLocal()
  if (!restored) {
    await chatStore.loadSessions()
    await chatStore.initSession()
  }
})

function sessionLabel(s: SessionInfo): string {
  // 用 sessionId 片段做标签，避免裸 ID（F4）
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
}

// 新建对话：先建会话（会设为当前会话），若当前不在聊天页则切回，避免在面板页停留
async function handleNewChat() {
  await chatStore.startNewSession()
  if (router.currentRoute.value.path !== '/') {
    router.push('/')
  }
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
.session-item:hover .session-del {
  opacity: 1;
}
.session-del:hover {
  background: rgba(0, 0, 0, 0.06);
}

.sidebar-nav {
  border-top: 1px solid var(--border-color);
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav-entry {
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  transition: background 0.2s ease;
}
.nav-entry:hover {
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
</style>
