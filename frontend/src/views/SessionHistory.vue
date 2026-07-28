<template>
  <div class="history-page">
    <header class="page-header">
      <el-button @click="$router.push('/')" type="text">← 返回聊天</el-button>
      <h2>📋 历史会话</h2>
    </header>

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
        <div class="history-time">{{ formatTime(msg.created_at) }}</div>
        <div v-if="msg.intent" class="history-intent">
          🏷️ {{ msg.intent.intent_name }} ({{ (msg.intent.confidence * 100).toFixed(0) }}%)
          <span v-if="msg.sentiment"> | {{ sentimentEmoji(msg.sentiment) }} {{ msg.sentiment }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { chatApi } from '@/api/chat'

const messages = ref<any[]>([])
const loading = ref(false)

function formatTime(ts: string) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

function formatContent(content: string) {
  return content.replace(/\n/g, '<br>')
}

function sentimentEmoji(s: string) {
  const map: Record<string, string> = { positive: '😊', neutral: '😐', negative: '😔' }
  return map[s] || ''
}
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
}
.history-item.is-user .history-sender { color: #667eea; }
.history-sender { font-size: 12px; font-weight: 600; margin-bottom: 4px; }
.history-content { font-size: 14px; color: #333; line-height: 1.6; }
.history-time { font-size: 11px; color: #bbb; margin-top: 4px; }
.history-intent { font-size: 11px; color: #999; margin-top: 4px; }
</style>
