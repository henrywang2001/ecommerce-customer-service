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
        <el-button size="small" class="nav-btn theme-toggle" @click="toggleTheme">
          {{ isDark ? '☀️' : '🌙' }}
        </el-button>
      </div>
    </header>

    <!-- 情感指示器 -->
    <transition name="emotion-slide">
      <div v-if="chatStore.currentSentiment" class="emotion-bar" :class="chatStore.currentSentiment">
        <span>{{ sentimentEmoji }}</span>
        <span>{{ sentimentLabel }}</span>
      </div>
    </transition>

    <!-- 聊天消息区域 -->
    <div class="chat-messages" ref="messagesContainer" @scroll="onScroll">
      <!-- 欢迎消息 -->
      <div v-if="chatStore.messages.length === 0" class="welcome">
        <div class="welcome-icon">🤖</div>
        <h2>您好！我是智能客服小e，很高兴为您服务～请问有什么可以帮到您的？</h2>
        <p>我可以帮您查询订单、了解商品信息、解答售后问题等</p>
        <div class="quick-services">
          <el-button v-for="s in quickServices" :key="s.code" @click="sendMessage(s.text)" class="quick-service-btn">
            {{ s.icon }} {{ s.name }}
          </el-button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div
        v-for="msg in chatStore.messages"
        :key="msg.id"
        class="message-row"
        :class="{ 'is-user': msg.isUser, 'is-error': msg.isError }"
      >
        <div class="avatar">{{ msg.isUser ? '👤' : '🤖' }}</div>
        <div class="bubble" :class="[msg.isUser ? 'bubble-user' : 'bubble-bot', { 'bubble-error': msg.isError }]">
          <div class="message-text">{{ msg.content }}</div>
          <div class="message-time">{{ formatTime(msg.createdAt) }}</div>
          <div v-if="msg.intent && !msg.isUser" class="intent-tag">
            <span class="intent-dot"></span>
            <span>{{ msg.intent.intent_name }} ({{ (msg.intent.confidence * 100).toFixed(0) }}%)</span>
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

    <!-- 回到底部按钮 -->
    <transition name="scroll-btn-fade">
      <button v-if="showScrollBtn" class="scroll-to-bottom" @click="scrollToBottom()">
        ↓ 回到底部
      </button>
    </transition>

    <!-- 快捷回复 -->
    <div v-if="chatStore.quickReplies.length > 0" class="quick-reply-bar">
      <el-button
        v-for="(reply, idx) in chatStore.quickReplies"
        :key="idx"
        size="small"
        class="quick-reply-btn"
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
        :rows="inputRows"
        placeholder="输入您的问题，按 Ctrl+Enter 发送..."
        @keydown.enter.ctrl="sendMessage()"
        @input="autoResize"
        resize="none"
        class="chat-textarea"
      />
      <el-button type="primary" class="send-btn" @click="sendMessage()" :disabled="!inputText.trim()" :loading="chatStore.isTyping">
        <span v-if="!chatStore.isTyping">➤ 发送</span>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'

// F1 守卫：必须显式声明组件名，否则 keep-alive include="ChatPage" 无法命中
defineOptions({ name: 'ChatPage' })

const chatStore = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement>()
const showScrollBtn = ref(false)
const inputRows = ref(2)
const isDark = ref(localStorage.getItem('theme') === 'dark')

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

function toggleTheme() {
  isDark.value = !isDark.value
  document.body.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

function onScroll() {
  if (!messagesContainer.value) return
  const el = messagesContainer.value
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  showScrollBtn.value = distFromBottom > 200
}

function autoResize() {
  const lines = inputText.value.split('\n').length
  inputRows.value = Math.min(Math.max(lines, 2), 6)
}

function sendMessage(text?: string) {
  const content = text || inputText.value.trim()
  if (!content) return
  inputText.value = ''
  inputRows.value = 2
  chatStore.sendMessage(content)
  nextTick(() => scrollToBottom())
}

function scrollToBottom() {
  if (messagesContainer.value) {
    const el = messagesContainer.value
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }
  showScrollBtn.value = false
}

function formatTime(timeStr: string): string {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 800px;
  margin: 0 auto;
  background:
    repeating-linear-gradient(0deg, transparent, transparent 19px, rgba(102, 126, 234, 0.03) 19px, rgba(102, 126, 234, 0.03) 20px),
    repeating-linear-gradient(90deg, transparent, transparent 19px, rgba(102, 126, 234, 0.03) 19px, rgba(102, 126, 234, 0.03) 20px),
    #f5f5f5;
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

.nav-btn {
  border: none !important;
  background: transparent !important;
  transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}
.nav-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
}

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

.emotion-slide-enter-active { transition: all 0.3s ease; }
.emotion-slide-leave-active { transition: all 0.2s ease; }
.emotion-slide-enter-from,
.emotion-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  scroll-behavior: smooth;
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

.quick-service-btn {
  transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}
.quick-service-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 16px;
}
.message-row:not(.is-user) {
  max-width: 85%;
}
.message-row.is-user {
  flex-direction: row-reverse;
  margin-left: auto;
  max-width: 70%;
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
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.bubble:hover {
  transform: scale(1.01);
}
.bubble-user {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}
.bubble-user:hover {
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.45);
}
.bubble-bot {
  background: #fff;
  color: #333;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.bubble-bot:hover {
  box-shadow: 0 3px 12px rgba(0,0,0,0.12);
}
.bubble-error {
  background: #fff0f0 !important;
  color: #c0392b !important;
  box-shadow: 0 1px 4px rgba(244, 67, 54, 0.15) !important;
}

.message-text { font-size: 14px; word-break: break-word; white-space: pre-wrap; }
.message-text :deep(a) {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.bubble-user .message-text :deep(a) { color: #fff; }
.bubble-bot .message-text :deep(a) { color: #667eea; }
.message-time { font-size: 10px; color: #bbb; margin-top: 4px; }
.bubble-user .message-time { color: rgba(255,255,255,0.7); }

.intent-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: #999;
  margin-top: 6px;
  background: rgba(102, 126, 234, 0.08);
  padding: 2px 10px;
  border-radius: 10px;
}
.intent-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #667eea;
}

.typing-dots { display: flex; gap: 4px; padding: 14px 18px; }
.typing-dots span {
  width: 7px; height: 7px; background: #ccc; border-radius: 50%;
  animation: wave 1.4s infinite ease-in-out;
}
.typing-dots span:nth-child(1) { animation-delay: 0s; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes wave {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.3; }
  40% { transform: translateY(-6px); opacity: 1; }
}

.scroll-to-bottom {
  position: absolute;
  bottom: 100px;
  right: 50%;
  transform: translateX(50%);
  background: rgba(102, 126, 234, 0.85);
  color: #fff;
  border: none;
  border-radius: 20px;
  padding: 6px 16px;
  font-size: 12px;
  cursor: pointer;
  z-index: 20;
  transition: transform 0.2s ease, background 0.2s ease;
  white-space: nowrap;
}
.chat-messages { position: relative; }
.scroll-to-bottom:hover {
  background: rgba(102, 126, 234, 1);
  transform: translateX(50%) translateY(-1px);
}

.scroll-btn-fade-enter-active,
.scroll-btn-fade-leave-active { transition: opacity 0.25s ease; }
.scroll-btn-fade-enter-from,
.scroll-btn-fade-leave-to { opacity: 0; }

.quick-reply-bar {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  background: #f8f9fa;
  border-top: 1px solid #eee;
  flex-wrap: wrap;
}
.quick-reply-btn {
  transition: transform 0.2s ease, box-shadow 0.2s ease !important;
  border-radius: 16px !important;
}
.quick-reply-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
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
.send-btn {
  transition: transform 0.2s ease, box-shadow 0.2s ease !important;
  border-radius: 8px !important;
  flex-shrink: 0;
}
.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
}

@media (max-width: 768px) {
  .message-row:not(.is-user) { max-width: 90%; }
  .message-row.is-user { max-width: 90%; }
  .chat-header { padding: 8px 12px; }
  .chat-input { padding: 8px 12px; }
  .chat-textarea :deep(.el-textarea__inner) { font-size: 14px; }
  .header-actions .el-button { padding: 4px 8px; font-size: 12px; }
}
</style>
