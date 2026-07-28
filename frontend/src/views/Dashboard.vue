<template>
  <div class="dashboard-page">
    <header class="page-header">
      <el-button @click="$router.push('/')" type="text">← 返回聊天</el-button>
      <h2>📊 数据看板</h2>
    </header>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{{ dashboard.overview.total_sessions.toLocaleString() }}</div>
        <div class="stat-label">会话总量</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ dashboard.overview.today_sessions }}</div>
        <div class="stat-label">今日会话</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ dashboard.overview.ai_resolution_rate }}%</div>
        <div class="stat-label">AI 解决率</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ dashboard.overview.avg_response_time }}s</div>
        <div class="stat-label">平均响应</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ dashboard.overview.transfer_rate }}%</div>
        <div class="stat-label">转人工率</div>
      </div>
    </div>

    <div class="charts-section">
      <div class="chart-card">
        <h3>意图分布</h3>
        <div class="bar-list">
          <div v-for="item in dashboard.intent_distribution" :key="item.name" class="bar-item">
            <span class="bar-label">{{ item.name }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: item.value + '%', background: getColor(item.name) }"></div>
            </div>
            <span class="bar-value">{{ item.value }}%</span>
          </div>
        </div>
      </div>

      <div class="chart-card">
        <h3>情感分布</h3>
        <div class="sentiment-pie">
          <div
            v-for="item in dashboard.sentiment_distribution"
            :key="item.name"
            class="sentiment-item"
          >
            <span class="sentiment-dot" :class="item.name"></span>
            <span>{{ item.name }}</span>
            <span class="sentiment-pct">{{ item.value }}%</span>
          </div>
        </div>
      </div>

      <div class="chart-card">
        <h3>满意度趋势</h3>
        <div class="trend-list">
          <div v-for="item in dashboard.satisfaction_trend" :key="item.date" class="trend-item">
            <span>{{ item.date }}</span>
            <span>{{ '⭐'.repeat(Math.round(item.score)) }}</span>
            <span>{{ item.score.toFixed(1) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import request from '@/utils/request'

const dashboard = reactive({
  overview: { total_sessions: 0, today_sessions: 0, ai_resolution_rate: 0, avg_response_time: 0, transfer_rate: 0 },
  intent_distribution: [] as any[],
  sentiment_distribution: [] as any[],
  satisfaction_trend: [] as any[],
})

async function loadDashboard() {
  try {
    const data = await request.get('/api/v1/analytics/dashboard')
    Object.assign(dashboard, data)
  } catch (e) {
    console.error('加载看板失败:', e)
  }
}

const colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a', '#fee140']
function getColor(name: string) {
  return colors[Math.abs(name.split('').reduce((a, c) => a + c.charCodeAt(0), 0)) % colors.length]
}

onMounted(loadDashboard)
</script>

<style scoped>
.dashboard-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}
.stat-card {
  background: #fff;
  padding: 20px 16px;
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.stat-value { font-size: 24px; font-weight: 700; color: #333; }
.stat-label { font-size: 12px; color: #999; margin-top: 4px; }

.charts-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.chart-card {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.chart-card h3 { margin-bottom: 16px; font-size: 15px; color: #555; }

.bar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.bar-label { width: 70px; font-size: 12px; color: #666; text-align: right; }
.bar-track { flex: 1; height: 20px; background: #f0f0f0; border-radius: 10px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 10px; transition: width 0.5s ease; }
.bar-value { width: 40px; font-size: 12px; color: #999; }

.sentiment-pie { display: flex; flex-direction: column; gap: 12px; padding: 10px 0; }
.sentiment-item { display: flex; align-items: center; gap: 8px; }
.sentiment-dot { width: 12px; height: 12px; border-radius: 50%; }
.sentiment-dot.正面 { background: #4caf50; }
.sentiment-dot.中性 { background: #ff9800; }
.sentiment-dot.负面 { background: #f44336; }
.sentiment-pct { margin-left: auto; color: #999; }

.trend-list { display: flex; flex-direction: column; gap: 8px; }
.trend-item { display: flex; align-items: center; gap: 12px; font-size: 13px; }
.trend-item span:last-child { margin-left: auto; color: #667eea; font-weight: 600; }

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .charts-section { grid-template-columns: 1fr; }
}
</style>
