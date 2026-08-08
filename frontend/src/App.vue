<template>
  <div id="app">
    <router-view v-slot="{ Component }">
      <transition name="page-fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

// 页面加载时从 localStorage 恢复深色模式
onMounted(() => {
  const saved = localStorage.getItem('theme')
  if (saved === 'dark') {
    document.body.classList.add('dark')
  }
})
</script>

<style>
/* ===== CSS 变量 ===== */
:root {
  --bg-primary: #f5f5f5;
  --bg-secondary: #ffffff;
  --text-primary: #333333;
  --text-secondary: #666666;
  --text-muted: #999999;
  --border-color: #eeeeee;
  --bubble-user: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --bubble-bot: #ffffff;
  --shadow-sm: 0 1px 4px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.1);
  --accent: #667eea;
  --accent-light: rgba(102, 126, 234, 0.08);
}

/* 深色主题 */
body.dark {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --text-primary: #e0e0e0;
  --text-secondary: #a0a0a0;
  --text-muted: #777777;
  --border-color: #2a2a4a;
  --bubble-user: linear-gradient(135deg, #667eea 0%, #9b59b6 100%);
  --bubble-bot: #1e2a45;
  --shadow-sm: 0 1px 4px rgba(0,0,0,0.2);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.3);
  --accent: #7c8cf8;
  --accent-light: rgba(124, 140, 248, 0.12);
  background: #0f0f23;
  color: #e0e0e0;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: background 0.3s ease, color 0.3s ease;
}

::selection {
  background: rgba(102, 126, 234, 0.25);
  color: inherit;
}

/* ===== 页面切换过渡 ===== */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* ===== 全局按钮微交互 ===== */
.el-button {
  transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}
.el-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
}
.el-button--primary:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
}

/* 卡片通用 hover */
.stat-card, .chart-card, .kb-card, .history-item {
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.3s ease !important;
}

/* ===== 深色模式覆盖 ===== */
body.dark .chat-page,
body.dark .dashboard-page,
body.dark .kb-page {
  background: var(--bg-primary);
}
body.dark .chat-header,
body.dark .chat-input,
body.dark .stat-card,
body.dark .chart-card,
body.dark .kb-card,
body.dark .history-item,
body.dark .bubble-bot {
  background: var(--bg-secondary);
  color: var(--text-primary);
}
body.dark .stat-value,
body.dark .kb-question,
body.dark .history-content,
body.dark .bubble-bot,
body.dark h2,
body.dark h3,
body.dark .bot-name {
  color: var(--text-primary);
}
body.dark .stat-label,
body.dark .kb-answer,
body.dark .history-time,
body.dark .message-time,
body.dark .history-intent,
body.dark .intent-tag,
body.dark .bar-label,
body.dark .bar-value,
body.dark .trend-date,
body.dark .sentiment-pct {
  color: var(--text-muted);
}
body.dark .quick-reply-bar,
body.dark .emotion-bar.neutral {
  background: rgba(255,255,255,0.03);
}
body.dark .bar-track {
  background: rgba(255,255,255,0.08);
}
body.dark .chat-messages::-webkit-scrollbar-thumb {
  background: #444;
}
body.dark .typing-dots span {
  background: #555;
}
body.dark .skeleton-bar,
body.dark .skeleton-bar-sm,
body.dark .skeleton-block {
  background: linear-gradient(90deg, #1e2a45 25%, #2a3a55 50%, #1e2a45 75%);
  background-size: 200% 100%;
}
</style>
