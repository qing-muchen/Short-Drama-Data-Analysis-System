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
  getTagDistribution,
  getTrend,
} from '../api/dashboard'
import { useUserStore } from '../stores/user'
import type {
  DashboardOverview,
  QualitySummary,
  RankingItem,
  TagDistributionItem,
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
const errorMessage = ref('')
const overviewLoading = ref(false)
const heatLoading = ref(false)
const growthLoading = ref(false)
const potentialLoading = ref(false)
const trendLoading = ref(false)
const qualityLoading = ref(false)
const tagLoading = ref(false)
const isLoading = computed(
  () =>
    overviewLoading.value ||
    heatLoading.value ||
    growthLoading.value ||
    potentialLoading.value ||
    trendLoading.value ||
    qualityLoading.value ||
    tagLoading.value,
)
const overview = ref<DashboardOverview | null>(null)
const heatRanking = ref<RankingItem[]>([])
const growthRanking = ref<RankingItem[]>([])
const potentialRanking = ref<RankingItem[]>([])
const trend = ref<TrendItem[]>([])
const quality = ref<QualitySummary | null>(null)
const tagDistribution = ref<TagDistributionItem[]>([])
const trendContainer = ref<HTMLDivElement | null>(null)
const tagChartContainer = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null
let tagChart: echarts.ECharts | null = null

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
  if (isLoading.value) {
    return
  }

  const analysisAsOf = new Date().toISOString()
  const failures: Array<{ label: string; reason: unknown }> = []
  errorMessage.value = ''

  overviewLoading.value = true
  try {
    overview.value = await getOverview(analysisAsOf)
  } catch (error: unknown) {
    failures.push({ label: '运营概览', reason: error })
    errorMessage.value = readableError(error)
  } finally {
    overviewLoading.value = false
  }

  heatLoading.value = true
  growthLoading.value = true
  potentialLoading.value = true
  trendLoading.value = true
  qualityLoading.value = true
  tagLoading.value = true

  const requests: Array<{ label: string; promise: Promise<void> }> = [
    {
      label: 'Heat 排行',
      promise: getHeatRanking(analysisAsOf)
        .then((data) => {
          heatRanking.value = data
        })
        .finally(() => {
          heatLoading.value = false
        }),
    },
    {
      label: '增长排行',
      promise: getGrowthRanking(analysisAsOf)
        .then((data) => {
          growthRanking.value = data
        })
        .finally(() => {
          growthLoading.value = false
        }),
    },
    {
      label: '潜力排行',
      promise: getPotentialRanking(analysisAsOf)
        .then((data) => {
          potentialRanking.value = data
        })
        .finally(() => {
          potentialLoading.value = false
        }),
    },
    {
      label: '运营趋势',
      promise: getTrend(analysisAsOf)
        .then((data) => {
          trend.value = data
        })
        .finally(() => {
          trendLoading.value = false
        }),
    },
    {
      label: '数据质量',
      promise: getQuality(analysisAsOf)
        .then((data) => {
          quality.value = data
        })
        .finally(() => {
          qualityLoading.value = false
        }),
    },
    {
      label: '热门标签',
      promise: getTagDistribution()
        .then((data) => {
          tagDistribution.value = data
        })
        .finally(() => {
          tagLoading.value = false
        }),
    },
  ]
  const results = await Promise.allSettled(requests.map((request) => request.promise))
  results.forEach((result, index) => {
    if (result.status === 'rejected') {
      failures.push({ label: requests[index]?.label ?? '未知模块', reason: result.reason })
    }
  })

  if (failures.length === requests.length + 1) {
    errorMessage.value = readableError(failures[0]?.reason)
  } else if (failures.length > 0) {
    errorMessage.value = `部分 Dashboard 数据加载失败：${failures
      .map((failure) => failure.label)
      .join('、')}。已保留其他模块数据。`
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
    legend: {
      data: ['播放量', '互动率'],
      type: 'scroll',
      left: 'center',
      bottom: 8,
    },
    grid: { left: 64, right: 64, top: 52, bottom: 88, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trend.value.map((item) => item.date),
      axisLabel: { hideOverlap: true, rotate: 30, margin: 16 },
    },
    yAxis: [
      {
        type: 'value',
        name: '播放量',
        nameGap: 18,
        axisLabel: { margin: 12 },
      },
      {
        type: 'value',
        name: '互动率',
        nameGap: 18,
        axisLabel: {
          margin: 12,
          formatter: (value: number) => percentFormatter.format(value),
        },
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
  tagChart?.resize()
}

function renderTagChart(): void {
  if (!tagChartContainer.value || tagDistribution.value.length === 0) {
    tagChart?.dispose()
    tagChart = null
    return
  }

  tagChart ??= echarts.init(tagChartContainer.value)
  const ordered = [...tagDistribution.value].reverse()
  tagChart.setOption(
    {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        valueFormatter: (value: number) => `${numberFormatter.format(value)} 部`,
      },
      grid: { left: 20, right: 36, top: 16, bottom: 24, containLabel: true },
      xAxis: { type: 'value', minInterval: 1 },
      yAxis: {
        type: 'category',
        data: ordered.map((item) => item.tag_name),
        axisLabel: { width: 90, overflow: 'truncate' },
      },
      series: [
        {
          name: '短剧数量',
          type: 'bar',
          data: ordered.map((item) => item.drama_count),
          barMaxWidth: 24,
          itemStyle: { color: '#409eff', borderRadius: [0, 4, 4, 0] },
        },
      ],
    },
    true,
  )
}

watch(
  trend,
  async () => {
    await nextTick()
    renderTrend()
  },
  { deep: true },
)

watch(
  tagDistribution,
  async () => {
    await nextTick()
    renderTagChart()
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
  tagChart?.dispose()
})
</script>

<template>
  <main class="dashboard-page">
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
        <router-link to="/tags"><el-button>标签管理</el-button></router-link>
        <router-link to="/analytics"><el-button type="primary" plain>分析中心</el-button></router-link>
        <router-link to="/scores"><el-button type="success" plain>综合评分</el-button></router-link>
        <router-link to="/data-quality"><el-button type="warning" plain>数据质量治理</el-button></router-link>
        <router-link to="/predictions"><el-button type="info" plain>播放趋势预测</el-button></router-link>
        <router-link to="/anomalies"><el-button type="danger" plain>异常检测分析</el-button></router-link>
        <router-link to="/operation-actions"><el-button type="primary" plain>运营行动中心</el-button></router-link>
        <router-link to="/operation-analytics"><el-button type="primary" plain>运营分析中心</el-button></router-link>
        <router-link to="/data-governance"><el-button type="warning" plain>数据治理中心</el-button></router-link>
        <router-link to="/reports"><el-button type="primary" plain>分析报告中心</el-button></router-link>
        <router-link to="/dramas"><el-button type="success" plain>Drama 360° 全景画像（选择短剧）</el-button></router-link>
        <router-link v-if="isAdmin" to="/imports"><el-button>数据导入</el-button></router-link>
        <el-button :icon="Refresh" :loading="isLoading" @click="loadDashboard">刷新数据</el-button>
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

    <section v-loading="overviewLoading" class="overview-grid" aria-label="核心指标">
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
          <strong>运营行动与告警处置</strong>
          <p>跟踪分析结果的分派、处理记录与状态闭环。</p>
        </div>
        <router-link to="/operation-actions"><el-button type="primary" plain>进入行动中心</el-button></router-link>
      </div>
    </el-card>

    <el-card shadow="never" class="prediction-entry">
      <div class="prediction-entry-content">
        <div>
          <strong>运营异常检测</strong>
          <p>查看异常数量、严重等级、变化趋势与可解释检测证据。</p>
        </div>
        <router-link to="/anomalies"><el-button type="danger" plain>进入异常分析</el-button></router-link>
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
      <el-card v-loading="heatLoading" shadow="never">
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

      <el-card v-loading="growthLoading" shadow="never">
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

      <el-card v-loading="potentialLoading" shadow="never">
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
      <el-card v-loading="trendLoading" class="trend-card" shadow="never">
        <template #header><strong>近 30 日运营趋势</strong></template>
        <div v-if="trend.length" ref="trendContainer" class="trend-chart" />
        <el-empty v-else description="当前范围暂无趋势数据" />
      </el-card>

      <el-card v-loading="qualityLoading" shadow="never">
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

    <el-card v-loading="tagLoading" class="tag-analysis-card" shadow="never">
      <template #header><strong>热门标签 Top 10</strong></template>
      <div v-if="tagDistribution.length" class="tag-analysis">
        <el-table :data="tagDistribution" height="340">
          <el-table-column type="index" label="排名" width="70" />
          <el-table-column prop="tag_name" label="标签" min-width="140" />
          <el-table-column prop="drama_count" label="短剧数量" width="110" align="right" />
          <el-table-column label="占比" width="90" align="right">
            <template #default="scope">{{ scope.row.percentage.toFixed(2) }}%</template>
          </el-table-column>
        </el-table>
        <div ref="tagChartContainer" class="tag-chart" aria-label="热门标签分布图" />
      </div>
      <el-empty v-else description="暂无标签统计数据" />
    </el-card>
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

.tag-analysis-card {
  margin-top: 20px;
}

.tag-analysis {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(0, 1.4fr);
  gap: 24px;
}

.tag-chart {
  width: 100%;
  height: 340px;
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

@media (max-width: 1500px) {
  .page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .header-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .dashboard-page {
    padding: 18px;
  }

  .page-header,
  .detail-grid,
  .tag-analysis {
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
