<template>
  <div class="dashboard-page">
    <header class="page-header">
      <el-button @click="$router.push('/')" type="text">← 返回聊天</el-button>
      <h2>📊 数据看板</h2>
    </header>

    <!-- 骨架屏 -->
    <template v-if="loading">
      <div class="stats-grid">
        <div v-for="n in 5" :key="n" class="stat-card skeleton-card">
          <div class="skeleton-block skeleton-icon"></div>
          <div class="skeleton-block skeleton-value"></div>
          <div class="skeleton-block skeleton-label"></div>
        </div>
      </div>
      <div class="charts-section">
        <div class="chart-card skeleton-card">
          <div class="skeleton-block skeleton-title"></div>
          <div v-for="n in 4" :key="n" class="skeleton-bar"></div>
        </div>
        <div class="chart-card skeleton-card">
          <div class="skeleton-block skeleton-title"></div>
          <div v-for="n in 3" :key="n" class="skeleton-bar-sm"></div>
        </div>
        <div class="chart-card skeleton-card">
          <div class="skeleton-block skeleton-title"></div>
          <div v-for="n in 5" :key="n" class="skeleton-bar-sm"></div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon">📊</div>
          <div class="stat-value">{{ dashboard.overview.total_sessions.toLocaleString() }}</div>
          <div class="stat-label">会话总量</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">📅</div>
          <div class="stat-value">{{ dashboard.overview.today_sessions }}</div>
          <div class="stat-label">今日会话</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">🤖</div>
          <div class="stat-value">{{ dashboard.overview.ai_resolution_rate }}%</div>
          <div class="stat-label">AI 解决率</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">⏱️</div>
          <div class="stat-value">{{ dashboard.overview.avg_response_time }}s</div>
          <div class="stat-label">平均响应</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">👥</div>
          <div class="stat-value">{{ dashboard.overview.transfer_rate }}%</div>
          <div class="stat-label">转人工率</div>
        </div>
      </div>

      <div class="charts-section">
        <div class="chart-card">
          <h3>意图分布</h3>
          <div class="bar-list">
            <div v-for="(item, idx) in dashboard.intent_distribution" :key="item.name" class="bar-item" :style="{ animationDelay: idx * 0.1 + 's' }">
              <span class="bar-label">{{ item.name }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: (animated ? item.value : 0) + '%', background: getColor(item.name) }"></div>
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
              <span class="trend-date">{{ item.date }}</span>
              <span class="star-bar">
                <span class="star-fill" :style="{ width: (item.score / 5 * 100) + '%' }"></span>
              </span>
              <span class="trend-score">{{ item.score.toFixed(1) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import request from '@/utils/request'

const dashboard = reactive({
  overview: { total_sessions: 0, today_sessions: 0, ai_resolution_rate: 0, avg_response_time: 0, transfer_rate: 0 },
  intent_distribution: [] as any[],
  sentiment_distribution: [] as any[],
  satisfaction_trend: [] as any[],
})

const loading = ref(true)
const animated = ref(false)

async function loadDashboard() {
  loading.value = true
  try {
    const data = await request.get('/api/v1/analytics/dashboard')
    Object.assign(dashboard, data)
  } catch (e) {
    console.error('加载看板失败:', e)
  } finally {
    loading.value = false
    // 触发柱状图入场动画
    requestAnimationFrame(() => {
      animated.value = true
    })
  }
}

const COLORS = ['#667eea', '#f093fb', '#4facfe', '#43e97b', '#fa709a', '#fee140', '#764ba2']
const colorMap = new Map<string, string>()

function getColor(name: string) {
  if (colorMap.has(name)) return colorMap.get(name)!
  const color = COLORS[colorMap.size % COLORS.length]
  colorMap.set(name, color)
  return color
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
  padding: 20px 12px;
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}
.stat-icon { font-size: 28px; margin-bottom: 6px; }
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
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.chart-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}
.chart-card h3 { margin-bottom: 16px; font-size: 15px; color: #555; }

/* 意图分布柱状图 */
.bar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.bar-label { width: 70px; font-size: 12px; color: #666; text-align: right; }
.bar-track { flex: 1; height: 20px; background: #f0f0f0; border-radius: 10px; overflow: hidden; }
.bar-fill {
  height: 100%;
  border-radius: 10px;
  width: 0;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}
.bar-value { width: 40px; font-size: 12px; color: #999; }

/* 情感分布 */
.sentiment-pie { display: flex; flex-direction: column; gap: 12px; padding: 10px 0; }
.sentiment-item { display: flex; align-items: center; gap: 8px; }
.sentiment-dot { width: 12px; height: 12px; border-radius: 50%; }
.sentiment-dot.positive, .sentiment-dot.正面 { background: #4caf50; }
.sentiment-dot.neutral, .sentiment-dot.中性 { background: #ff9800; }
.sentiment-dot.negative, .sentiment-dot.负面 { background: #f44336; }
.sentiment-pct { margin-left: auto; color: #999; }

/* 满意度趋势 — CSS 五星评分条 */
.trend-list { display: flex; flex-direction: column; gap: 8px; }
.trend-item { display: flex; align-items: center; gap: 12px; font-size: 13px; }
.trend-date { width: 55px; color: #999; font-size: 12px; flex-shrink: 0; }
.star-bar {
  flex: 1;
  height: 18px;
  background: #eee;
  border-radius: 9px;
  overflow: hidden;
  position: relative;
}
.star-bar::before {
  content: '★★★★★';
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  font-size: 12px;
  color: #ddd;
  padding-left: 4px;
  letter-spacing: 4px;
}
.star-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, #ffc107, #ff9800);
  border-radius: 9px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}
.trend-score {
  width: 32px;
  margin-left: auto;
  color: #667eea;
  font-weight: 600;
  text-align: right;
}

/* 骨架屏 */
.skeleton-card { pointer-events: none; }
.skeleton-block {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px;
}
.skeleton-icon { width: 28px; height: 28px; margin: 0 auto 8px; border-radius: 50%; }
.skeleton-value { width: 60%; height: 24px; margin: 0 auto 6px; }
.skeleton-label { width: 40%; height: 12px; margin: 0 auto; }
.skeleton-title { width: 40%; height: 16px; margin-bottom: 14px; }
.skeleton-bar { height: 20px; background: #f0f0f0; border-radius: 10px; margin-bottom: 10px; }
.skeleton-bar-sm { height: 14px; background: #f0f0f0; border-radius: 7px; margin-bottom: 8px; }

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (max-width: 1023px) and (min-width: 768px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .charts-section { grid-template-columns: 1fr; }
}
</style>
