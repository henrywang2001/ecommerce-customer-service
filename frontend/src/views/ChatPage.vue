<template>
  <div class="chat-page">
    <!-- 顶部导航 -->
    <header class="chat-header">
      <div class="header-info">
        <span class="bot-name">🤖 智能客服小e</span>
        <span class="status" :class="chatStore.isConnected ? 'online' : 'offline'">
          {{ chatStore.isConnected ? '在线' : '离线' }}
        </span>
      </div>
      <div class="header-actions">
        <el-button size="small" @click="$router.push('/dashboard')">📊 看板</el-button>
        <el-button size="small" @click="$router.push('/history')">📋 历史</el-button>
      </div>
    </header>

    <!-- 情感指示器 -->
    <div v-if="chatStore.currentSentiment" class="emotion-bar" :class="chatStore.currentSentiment">
      <span>{{ sentimentEmoji }}</span>
      <span>{{ sentimentLabel }}</span>
    </div>

    <!-- 聊天消息区域 -->
    <div class="chat-messages" ref="messagesContainer">
      <!-- 欢迎消息 -->
      <div v-if="chatStore.messages.length === 0" class="welcome">
        <div class="welcome-icon">🤖</div>
        <h2>您好，我是智能客服小e</h2>
        <p>我可以帮您查询订单、了解商品信息、解答售后问题等</p>
        <div class="quick-services">
          <el-button v-for="s in quickServices" :key="s.code" @click="sendMessage(s.text)">
            {{ s.icon }} {{ s.name }}
          </el-button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div
        v-for="msg in chatStore.messages"
        :key="msg.id"
        class="message-row"
        :class="{ 'is-user': msg.isUser }"
      >
        <div class="avatar">{{ msg.isUser ? '👤' : '🤖' }}</div>
        <div class="bubble" :class="msg.isUser ? 'bubble-user' : 'bubble-bot'">
          <div class="message-text" v-html="formatContent(msg.content)"></div>
          <div class="message-time">{{ formatTime(msg.createdAt) }}</div>
          <div v-if="msg.intent && !msg.isUser" class="intent-tag">
            🏷️ {{ msg.intent.intent_name }} ({{ (msg.intent.confidence * 100).toFixed(0) }}%)
          </div>
        </div>
      </div>

      <!-- 正在输入中 -->
      <div v-if="chatStore.isTyping" class="message-row">
        <div class="avatar">🤖</div>
        <div class="bubble bubble-bot typing-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <!-- 快捷回复 -->
    <div v-if="chatStore.quickReplies.length > 0" class="quick-reply-bar">
      <el-button
        v-for="(reply, idx) in chatStore.quickReplies"
        :key="idx"
        size="small"
        @click="sendMessage(reply)"
      >
        {{ reply }}
      </el-button>
    </div>

    <!-- 输入框 -->
    <div class="chat-input">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        placeholder="输入您的问题，按 Ctrl+Enter 发送..."
        @keydown.enter.ctrl="sendMessage()"
        resize="none"
      />
      <el-button type="primary" @click="sendMessage()" :disabled="!inputText.trim()" :loading="chatStore.isTyping">
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement>()

const quickServices = [
  { code: 'order', icon: '📦', name: '查订单', text: '我想查一下我的订单' },
  { code: 'product', icon: '🛍️', name: '商品咨询', text: '有什么优惠活动吗' },
  { code: 'refund', icon: '💰', name: '退款退货', text: '如何申请退款' },
  { code: 'human', icon: '👤', name: '转人工', text: '转人工客服' },
]

const sentimentEmoji = computed(() => {
  const map: Record<string, string> = { positive: '😊', neutral: '🤖', negative: '😔' }
  return map[chatStore.currentSentiment || 'neutral'] || '🤖'
})

const sentimentLabel = computed(() => {
  const map: Record<string, string> = { positive: '心情不错', neutral: '情绪平和', negative: '需要关注' }
  return map[chatStore.currentSentiment || 'neutral'] || ''
})

function sendMessage(text?: string) {
  const content = text || inputText.value.trim()
  if (!content) return
  inputText.value = ''
  chatStore.sendMessage(content)
  nextTick(() => scrollToBottom())
}

function scrollToBottom() {
  if (messagesContainer.value) {
    const el = messagesContainer.value
    setTimeout(() => {
      el.scrollTop = el.scrollHeight
    }, 100)
  }
}

function formatTime(timeStr: string): string {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatContent(content: string): string {
  return content.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}

onMounted(() => {
  chatStore.initSession()
})
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 800px;
  margin: 0 auto;
  background: #f5f5f5;
  box-shadow: 0 0 20px rgba(0,0,0,0.05);
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  z-index: 10;
}
.header-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.bot-name {
  font-size: 16px;
  font-weight: 600;
}
.status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
}
.status.online { background: #e8f5e9; color: #4caf50; }
.status.offline { background: #ffebee; color: #f44336; }

.emotion-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  font-size: 12px;
}
.emotion-bar.positive { background: #e8f5e9; }
.emotion-bar.negative { background: #ffebee; }
.emotion-bar.neutral { background: #f5f5f5; }

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.chat-messages::-webkit-scrollbar { width: 6px; }
.chat-messages::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

.welcome {
  text-align: center;
  padding: 60px 20px;
}
.welcome-icon { font-size: 64px; margin-bottom: 16px; }
.welcome h2 { margin-bottom: 8px; color: #333; }
.welcome p { color: #999; margin-bottom: 24px; }
.quick-services { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 16px;
  max-width: 85%;
}
.message-row.is-user {
  flex-direction: row-reverse;
  margin-left: auto;
}
.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
  background: #f0f0f0;
}
.bubble {
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
}
.bubble-user {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.bubble-bot {
  background: #fff;
  color: #333;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.message-text { font-size: 14px; word-break: break-word; }
.message-time { font-size: 10px; color: #bbb; margin-top: 4px; }
.bubble-user .message-time { color: rgba(255,255,255,0.7); }
.intent-tag { font-size: 10px; color: #999; margin-top: 4px; }

.typing-dots { display: flex; gap: 4px; padding: 14px 18px; }
.typing-dots span {
  width: 7px; height: 7px; background: #ccc; border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
}
.typing-dots span:nth-child(2) { animation-delay: 0.16s; }
.typing-dots span:nth-child(3) { animation-delay: 0.32s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.5); opacity: 0.3; }
  40% { transform: scale(1); opacity: 1; }
}

.quick-reply-bar {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  background: #f8f9fa;
  border-top: 1px solid #eee;
  flex-wrap: wrap;
}

.chat-input {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid #eee;
}
.chat-input :deep(.el-textarea__inner) {
  resize: none;
}
</style>
