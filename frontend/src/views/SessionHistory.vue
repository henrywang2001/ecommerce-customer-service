<template>
  <div class="history-page">
    <header class="page-header">
      <el-button @click="$router.push('/')" type="text">← 返回聊天</el-button>
      <h2>📋 历史会话</h2>
    </header>

    <!-- Session 选择器 -->
    <div v-if="sessions.length" style="margin-bottom: 16px;">
      <el-select
        v-model="currentSessionId"
        placeholder="选择会话"
        @change="onSessionChange"
        style="width: 100%;"
      >
        <el-option
          v-for="s in sessions"
          :key="s.session_id || s.id"
          :label="`会话 ${(s.session_id || s.id || '').toString().slice(-8)} — ${formatTimeText(s.started_at || s.created_at || '')}`"
          :value="s.session_id || s.id"
        />
      </el-select>
    </div>

    <!-- 骨架屏 -->
    <div v-if="loading" class="skeleton-list">
      <div v-for="n in 5" :key="n" class="skeleton-item">
        <el-skeleton :rows="2" animated />
      </div>
    </div>

    <el-card v-if="!messages.length && !loading" class="empty-card">
      <p>暂无历史会话记录</p>
      <el-button type="primary" @click="$router.push('/')">开始新对话</el-button>
    </el-card>

    <div v-if="messages.length" class="history-list">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="history-item"
        :class="{ 'is-user': msg.sender_type === 'user' }"
      >
        <div class="history-sender">{{ msg.sender_type === 'user' ? '👤 用户' : '🤖 客服' }}</div>
        <div class="history-content" v-html="formatContent(msg.content)"></div>
        <div class="history-time">{{ formatTimeText(msg.created_at) }}</div>
        <div v-if="msg.intent" class="history-intent">
          🏷️ {{ msg.intent.intent_name }} ({{ (msg.intent.confidence * 100).toFixed(0) }}%)
          <span v-if="msg.sentiment"> | {{ sentimentEmoji(msg.sentiment) }} {{ msg.sentiment }}</span>
        </div>
      </div>

      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadMessages"
        style="justify-content: center; margin-top: 16px;"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { chatApi } from '@/api/chat'

const messages = ref<any[]>([])
const sessions = ref<any[]>([])
const currentSessionId = ref<string>('')
const loading = ref(false)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)

async function loadSessions() {
  loading.value = true
  try {
    const data = await chatApi.getHistory('', 1, 50) as any
    if (data?.sessions) {
      sessions.value = data.sessions
    }
  } catch (e) {
    console.error('加载会话列表失败:', e)
  } finally {
    loading.value = false
  }
}

async function loadMessages(sid?: string) {
  const targetSid = typeof sid === 'string' ? sid : currentSessionId.value
  if (!targetSid) return
  loading.value = true
  try {
    const data = await chatApi.getHistory(targetSid, currentPage.value, pageSize) as any
    if (Array.isArray(data?.messages)) {
      messages.value = data.messages
      total.value = data.total || data.messages.length
    } else if (Array.isArray(data)) {
      messages.value = data
      total.value = data.length
    }
  } catch (e) {
    console.error('加载历史消息失败:', e)
  } finally {
    loading.value = false
  }
}

function onSessionChange(sid: string) {
  currentSessionId.value = sid
  loadMessages(sid)
}

function formatTimeText(ts: string) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  const isYesterday = d.toDateString() === yesterday.toDateString()
  if (isToday) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (isYesterday) return '昨天 ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return `${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')} ${d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
}

function formatContent(content: string) {
  return content.replace(/\n/g, '<br>')
}

function sentimentEmoji(s: string) {
  const map: Record<string, string> = { positive: '😊', neutral: '😐', negative: '😔' }
  return map[s] || ''
}

onMounted(() => {
  loadSessions()
})
</script>

<style scoped>
.history-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}
.empty-card {
  text-align: center;
  padding: 40px;
}
.history-list { display: flex; flex-direction: column; gap: 12px; }
.history-item {
  background: #fff;
  padding: 14px;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  border-left: 3px solid #ddd;
}
.history-item.is-user {
  border-left-color: #667eea;
}
.history-item.is-user .history-sender { color: #667eea; }
.history-sender { font-size: 12px; font-weight: 600; margin-bottom: 4px; }
.history-content { font-size: 14px; color: #333; line-height: 1.6; }
.history-time { font-size: 11px; color: #bbb; margin-top: 4px; }
.history-intent { font-size: 11px; color: #999; margin-top: 4px; }

.skeleton-list { display: flex; flex-direction: column; gap: 12px; }
.skeleton-item {
  background: #fff;
  padding: 16px;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
</style>
