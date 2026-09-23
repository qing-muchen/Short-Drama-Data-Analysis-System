<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { Refresh } from '@element-plus/icons-vue'

import {
  getGrowthRanking,
  getHeatRanking,
  getOverview,
  getPotentialRanking,
  getQuality,
  getTrend,
} from '../api/dashboard'
import { useUserStore } from '../stores/user'
import type {
  DashboardOverview,
  QualitySummary,
  RankingItem,
  TrendItem,
} from '../types/dashboard'
import { getApiErrorMessage } from '../utils/api-error'

interface QualityCard {
  label: string
  value: number | undefined
  tone: 'success' | 'info' | 'warning' | 'danger'
}

const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const loading = ref(false)
const errorMessage = ref('')
const overview = ref<DashboardOverview | null>(null)
const heatRanking = ref<RankingItem[]>([])
const growthRanking = ref<RankingItem[]>([])
const potentialRanking = ref<RankingItem[]>([])
const trend = ref<TrendItem[]>([])
const quality = ref<QualitySummary | null>(null)
const trendContainer = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null

const numberFormatter = new Intl.NumberFormat('zh-CN')
const percentFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'percent',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

const overviewCards = computed(() => [
  { label: '短剧数量', value: formatCount(overview.value?.drama_count) },
  { label: '演员数量', value: formatCount(overview.value?.actor_count) },
  { label: '导演数量', value: formatCount(overview.value?.director_count) },
  { label: '公司数量', value: formatCount(overview.value?.company_count) },
  { label: '平台数量', value: formatCount(overview.value?.platform_count) },
  { label: '总播放量', value: formatCount(overview.value?.total_play_count) },
  { label: '平均互动率', value: formatRate(overview.value?.average_engagement_rate) },
  { label: '质量问题', value: formatCount(overview.value?.quality_issue_count) },
])

const qualityCards = computed<QualityCard[]>(() => [
  { label: 'Warning', value: quality.value?.warning_count, tone: 'warning' },
  { label: 'Error', value: quality.value?.error_count, tone: 'danger' },
  { label: 'Fresh', value: quality.value?.freshness_summary.fresh, tone: 'success' },
  { label: 'Stale', value: quality.value?.freshness_summary.stale, tone: 'info' },
])

function formatCount(value: number | null | undefined): string {
  return value == null ? '--' : numberFormatter.format(value)
}

function formatRate(value: number | null | undefined): string {
  return value == null ? '--' : percentFormatter.format(value)
}

function formatScore(value: number | null): string {
  return value == null ? '--' : value.toFixed(2)
}

function readableError(error: unknown): string {
  return getApiErrorMessage(error, 'Dashboard 数据加载失败，请稍后重试。')
}

async function loadDashboard(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [overviewData, heatData, growthData, potentialData, trendData, qualityData] =
      await Promise.all([
        getOverview(),
        getHeatRanking(),
        getGrowthRanking(),
        getPotentialRanking(),
        getTrend(),
        getQuality(),
      ])
    overview.value = overviewData
    heatRanking.value = heatData
    growthRanking.value = growthData
    potentialRanking.value = potentialData
    trend.value = trendData
    quality.value = qualityData
  } catch (error: unknown) {
    errorMessage.value = readableError(error)
  } finally {
    loading.value = false
  }
}

function renderTrend(): void {
  if (!trendContainer.value || trend.value.length === 0) {
    trendChart?.dispose()
    trendChart = null
    return
  }

  trendChart ??= echarts.init(trendContainer.value)
  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['播放量', '互动率'] },
    grid: { left: 24, right: 28, top: 48, bottom: 18, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trend.value.map((item) => item.date),
    },
    yAxis: [
      {
        type: 'value',
        name: '播放量',
      },
      {
        type: 'value',
        name: '互动率',
        axisLabel: { formatter: '{value}' },
      },
    ],
    series: [
      {
        name: '播放量',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: trend.value.map((item) => item.play_count),
      },
      {
        name: '互动率',
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        data: trend.value.map((item) => item.engagement_rate),
      },
    ],
  }
  trendChart.setOption(option, true)
}

function resizeTrend(): void {
  trendChart?.resize()
}

watch(
  trend,
  async () => {
    await nextTick()
    renderTrend()
  },
  { deep: true },
)

onMounted(() => {
  window.addEventListener('resize', resizeTrend)
  void loadDashboard()
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeTrend)
  trendChart?.dispose()
})
</script>

<template>
  <main v-loading="loading" class="dashboard-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Short Drama Analytics</p>
        <h1>数据驾驶舱</h1>
        <p class="subtitle">运营概览、作品排行、趋势与数据质量</p>
      </div>
      <div class="header-actions">
        <router-link to="/dramas"><el-button>短剧管理</el-button></router-link>
        <router-link to="/actors"><el-button>演员管理</el-button></router-link>
        <router-link to="/platforms"><el-button>平台管理</el-button></router-link>
        <router-link to="/analytics"><el-button type="primary" plain>分析中心</el-button></router-link>
        <router-link to="/scores"><el-button type="success" plain>综合评分</el-button></router-link>
        <router-link to="/data-quality"><el-button type="warning" plain>数据质量治理</el-button></router-link>
        <router-link to="/predictions"><el-button type="info" plain>播放趋势预测</el-button></router-link>
        <router-link to="/anomalies"><el-button type="danger" plain>异常检测分析</el-button></router-link>
        <router-link to="/operation-actions"><el-button type="primary" plain>运营行动中心</el-button></router-link>
        <router-link to="/operation-analytics"><el-button type="primary" plain>运营分析中心</el-button></router-link>
        <router-link to="/dramas"><el-button type="success" plain>Drama 360° 全景画像（选择短剧）</el-button></router-link>
        <router-link v-if="isAdmin" to="/imports"><el-button>数据导入</el-button></router-link>
        <el-button :icon="Refresh" :loading="loading" @click="loadDashboard">刷新数据</el-button>
      </div>
    </header>

    <el-alert
      v-if="errorMessage"
      class="page-error"
      type="error"
      show-icon
      :title="errorMessage"
      :closable="false"
    >
      <template #default>
        <el-button text type="primary" @click="loadDashboard">重新加载</el-button>
      </template>
    </el-alert>

    <section class="overview-grid" aria-label="核心指标">
      <el-card v-for="card in overviewCards" :key="card.label" shadow="hover">
        <p class="metric-label">{{ card.label }}</p>
        <strong class="metric-value">{{ card.value }}</strong>
      </el-card>
    </section>

    <el-card shadow="never" class="prediction-entry">
      <div class="prediction-entry-content">
        <div>
          <strong>播放趋势预测</strong>
          <p>查看单剧下一日累计播放量预测与历史预测趋势。</p>
        </div>
        <router-link to="/predictions"><el-button type="primary" plain>进入预测分析</el-button></router-link>
      </div>
    </el-card>

    <el-card shadow="never" class="prediction-entry">
      <div class="prediction-entry-content">
        <div>
          <strong>短剧运营分析中心</strong>
          <p>查看行动前后指标变化、生命周期状态与同平台统计比较。</p>
        </div>
        <router-link to="/operation-analytics"><el-button type="primary" plain>进入运营分析</el-button></router-link>
      </div>
    </el-card>

    <section class="ranking-grid">
      <el-card shadow="never">
        <template #header><strong>Heat Top 10</strong></template>
        <el-table :data="heatRanking" height="340" empty-text="暂无 Heat 排行数据">
          <el-table-column type="index" label="#" width="54" />
          <el-table-column prop="drama_name" label="短剧" min-width="150" show-overflow-tooltip />
          <el-table-column label="Heat" width="92" align="right">
            <template #default="scope">{{ formatScore(scope.row.heat_score) }}</template>
          </el-table-column>
          <el-table-column prop="platform_count" label="平台" width="72" align="right" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><strong>Growth Top 10</strong></template>
        <el-table :data="growthRanking" height="340" empty-text="暂无增长排行数据">
          <el-table-column type="index" label="#" width="54" />
          <el-table-column prop="drama_name" label="短剧" min-width="150" show-overflow-tooltip />
          <el-table-column label="增长率" width="92" align="right">
            <template #default="scope">{{ formatRate(scope.row.growth_rate) }}</template>
          </el-table-column>
          <el-table-column label="播放量" width="110" align="right">
            <template #default="scope">{{ formatCount(scope.row.current_play_count) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><strong>Potential Top 10</strong></template>
        <el-table :data="potentialRanking" height="340" empty-text="暂无 Potential 排行数据">
          <el-table-column type="index" label="#" width="54" />
          <el-table-column prop="drama_name" label="短剧" min-width="150" show-overflow-tooltip />
          <el-table-column label="Potential" width="104" align="right">
            <template #default="scope">{{ formatScore(scope.row.potential_score) }}</template>
          </el-table-column>
          <el-table-column label="Growth 7D" width="104" align="right">
            <template #default="scope">{{ formatRate(scope.row.growth_7d) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>

    <section class="detail-grid">
      <el-card class="trend-card" shadow="never">
        <template #header><strong>近 30 日运营趋势</strong></template>
        <div v-if="trend.length" ref="trendContainer" class="trend-chart" />
        <el-empty v-else description="当前范围暂无趋势数据" />
      </el-card>

      <el-card shadow="never">
        <template #header><strong>数据质量</strong></template>
        <div class="quality-list">
          <div v-for="item in qualityCards" :key="item.label" class="quality-item">
            <span>{{ item.label }}</span>
            <el-tag :type="item.tone" effect="light">{{ formatCount(item.value) }}</el-tag>
          </div>
        </div>
        <el-divider />
        <p class="quality-total">
          当前质量问题总数
          <strong>{{ formatCount(quality?.quality_issue_count) }}</strong>
        </p>
      </el-card>
    </section>
  </main>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  padding: 28px;
  color: var(--el-text-color-primary);
  background: var(--el-bg-color-page);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.eyebrow,
.subtitle,
.metric-label {
  margin: 0;
  color: var(--el-text-color-secondary);
}

.eyebrow {
  margin-bottom: 8px;
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1 {
  margin: 0 0 8px;
  font-size: clamp(26px, 3vw, 38px);
}

.page-error {
  margin-bottom: 20px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.metric-value {
  display: block;
  margin-top: 12px;
  font-size: 28px;
  font-variant-numeric: tabular-nums;
}

.ranking-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.prediction-entry {
  margin-bottom: 20px;
}

.prediction-entry-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.prediction-entry-content strong {
  font-size: 18px;
}

.prediction-entry-content p {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
  gap: 20px;
}

.trend-chart {
  width: 100%;
  height: 360px;
}

.quality-list {
  display: grid;
  gap: 18px;
}

.quality-item,
.quality-total {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.quality-total {
  margin: 0;
}

@media (max-width: 1100px) {
  .overview-grid,
  .ranking-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .dashboard-page {
    padding: 18px;
  }

  .page-header,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .prediction-entry-content {
    align-items: flex-start;
    flex-direction: column;
  }

  .overview-grid,
  .ranking-grid {
    grid-template-columns: 1fr;
  }
}
</style>
