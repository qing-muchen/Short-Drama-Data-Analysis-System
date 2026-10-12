<script setup lang="ts">
import * as echarts from 'echarts'
import { Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  calculatePrediction,
  getPrediction,
  getPredictionHistory,
} from '../../api/prediction'
import ExplanationDrawer from '../../components/explanation/ExplanationDrawer.vue'
import { useUserStore } from '../../stores/user'
import type { Prediction } from '../../types/prediction'
import { getApiErrorDetail, getApiErrorMessage, getApiErrorStatus } from '../../utils/api-error'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')

const selectedDramaId = ref<number | null>(readDramaId(route.query.drama_id))
const currentPrediction = ref<Prediction | null>(null)
const explanationVisible = ref(false)
const history = ref<Prediction[]>([])
const loading = ref(false)
const calculating = ref(false)
const errorMessage = ref('')
const chartContainer = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null

function readDramaId(value: unknown): number | null {
  const parsed = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function formatNumber(value: number | null | undefined): string {
  return value == null ? '--' : new Intl.NumberFormat('zh-CN').format(value)
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
  }).format(parsed)
}

function formatMetric(metric: string): string {
  return metric === 'PLAY_COUNT' ? '播放量（PLAY_COUNT）' : metric
}

async function loadPrediction(): Promise<void> {
  const dramaId = selectedDramaId.value
  if (dramaId == null || loading.value) return

  loading.value = true
  errorMessage.value = ''
  const [latestResult, historyResult] = await Promise.allSettled([
    getPrediction(dramaId),
    getPredictionHistory(dramaId),
  ])

  currentPrediction.value = latestResult.status === 'fulfilled' ? latestResult.value : null
  history.value = historyResult.status === 'fulfilled' ? historyResult.value.items : []

  const failures = [
    latestResult.status === 'rejected' && getApiErrorStatus(latestResult.reason) !== 404
      ? latestResult
      : null,
    historyResult.status === 'rejected' ? historyResult : null,
  ].filter((result) => result != null)
  if (failures.length > 0) {
    const firstFailure = failures[0]
    errorMessage.value = getApiErrorMessage(
      firstFailure?.status === 'rejected' ? firstFailure.reason : null,
      failures.length === 2
        ? '预测数据加载失败，请稍后重试。'
        : '部分预测数据加载失败，已保留可用结果。',
    )
  }
  loading.value = false
}

async function calculate(): Promise<void> {
  const dramaId = selectedDramaId.value
  if (!isAdmin.value || dramaId == null || calculating.value) return

  calculating.value = true
  errorMessage.value = ''
  try {
    const result = await calculatePrediction(dramaId, new Date().toISOString())
    currentPrediction.value = result
    await loadPrediction()
    ElMessage.success(`预测生成成功：${formatNumber(result.predicted_value)}`)
  } catch (error: unknown) {
    const reason = getApiErrorDetail(error, 'reason')
    const reasonMessages: Record<string, string> = {
      NO_HISTORY: '尚无可用于预测的历史指标快照。',
      INSUFFICIENT_HISTORY: '历史数据不足：预测需要连续 8 天且累计播放量单调不下降的数据。',
      DATA_QUALITY_BLOCKED: '历史数据未通过预测所需的数据质量检查。',
    }
    errorMessage.value =
      typeof reason === 'string' && reasonMessages[reason]
        ? reasonMessages[reason]
        : getApiErrorMessage(error, '预测生成失败，请稍后重试。')
  } finally {
    calculating.value = false
  }
}

function openPrediction(): void {
  if (selectedDramaId.value == null) return
  void router.replace({
    query: { ...route.query, drama_id: String(selectedDramaId.value) },
  })
  void loadPrediction()
}

function renderTrend(): void {
  if (!chartContainer.value || history.value.length === 0) {
    trendChart?.dispose()
    trendChart = null
    return
  }

  trendChart ??= echarts.init(chartContainer.value)
  trendChart.setOption(
    {
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) => formatNumber(value),
      },
      grid: { left: 56, right: 30, top: 32, bottom: 54, containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: history.value.map((item) => item.target_date),
        axisLabel: { hideOverlap: true, rotate: 25 },
      },
      yAxis: {
        type: 'value',
        name: '预测累计播放量',
        min: 0,
      },
      series: [
        {
          name: '预测累计播放量',
          type: 'line',
          smooth: true,
          showSymbol: history.value.length <= 30,
          data: history.value.map((item) => item.predicted_value),
          lineStyle: { color: '#409eff', width: 3 },
          itemStyle: { color: '#409eff' },
          areaStyle: { color: 'rgba(64, 158, 255, 0.12)' },
        },
      ],
    },
    true,
  )
}

function resizeChart(): void {
  trendChart?.resize()
}

watch(
  history,
  async () => {
    await nextTick()
    renderTrend()
  },
  { deep: true },
)

onMounted(() => {
  window.addEventListener('resize', resizeChart)
  if (selectedDramaId.value != null) void loadPrediction()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  trendChart?.dispose()
  trendChart = null
})
</script>

<template>
  <main class="prediction-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Moving Average V1.0</p>
        <h1>播放趋势预测</h1>
        <p class="subtitle">基于历史累计播放量变化趋势，辅助短剧运营分析决策。</p>
      </div>
      <div class="header-actions">
        <router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link>
        <router-link to="/scores"><el-button>综合评分</el-button></router-link>
        <el-button :icon="Refresh" :loading="loading" @click="loadPrediction">刷新</el-button>
      </div>
    </header>

    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <div class="selector">
          <span class="toolbar-label">短剧 ID</span>
          <el-input-number
            v-model="selectedDramaId"
            :min="1"
            :step="1"
            controls-position="right"
            placeholder="请输入短剧 ID"
            @keyup.enter="openPrediction"
          />
          <el-button type="primary" :icon="Search" :disabled="selectedDramaId == null" @click="openPrediction">
            查询预测
          </el-button>
        </div>
        <el-button
          v-if="isAdmin"
          type="success"
          :loading="calculating"
          :disabled="selectedDramaId == null"
          @click="calculate"
        >
          重新预测
        </el-button>
      </div>
      <p class="source-note">页面只展示 Prediction API 结果，不在浏览器中重新计算趋势。</p>
    </el-card>

    <el-alert
      v-if="errorMessage"
      class="page-alert"
      type="error"
      show-icon
      :closable="false"
      :title="errorMessage"
    >
      <template #default><el-button text type="primary" @click="loadPrediction">重新加载</el-button></template>
    </el-alert>

    <el-card v-if="selectedDramaId == null" shadow="never" class="empty-card">
      <el-empty description="请输入短剧 ID 查看预测数据" />
    </el-card>

    <template v-else>
      <section class="summary-grid" aria-label="当前预测">
        <el-card v-loading="loading" shadow="never" class="summary-card">
          <template #header><strong>当前预测</strong></template>
          <el-empty v-if="!currentPrediction" description="暂无预测数据" />
          <div v-else class="prediction-summary">
            <span class="summary-label">下一日预测播放量</span>
            <strong class="prediction-value">{{ formatNumber(currentPrediction.predicted_value) }}</strong>
            <span class="target-date">目标日期：{{ currentPrediction.target_date }}</span>
            <el-descriptions :column="1" border class="prediction-meta">
              <el-descriptions-item label="算法版本">{{ currentPrediction.algorithm_version }}</el-descriptions-item>
              <el-descriptions-item label="数据截止时间">{{ formatDateTime(currentPrediction.analysis_as_of) }}</el-descriptions-item>
              <el-descriptions-item label="指标">{{ formatMetric(currentPrediction.metric_type) }}</el-descriptions-item>
            </el-descriptions>
            <el-button class="explanation-button" type="primary" plain @click="explanationVisible = true">查看解释</el-button>
          </div>
        </el-card>

        <el-card shadow="never" class="explain-card">
          <template #header><strong>预测结果说明</strong></template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="短剧 ID">{{ selectedDramaId }}</el-descriptions-item>
            <el-descriptions-item label="指标">PLAY_COUNT（累计播放量）</el-descriptions-item>
            <el-descriptions-item label="模型">Moving Average V1.0</el-descriptions-item>
            <el-descriptions-item label="数据来源">历史累计播放量日点</el-descriptions-item>
          </el-descriptions>
          <p class="reference-note">预测结果基于历史累计播放量变化趋势生成，仅用于运营分析参考。</p>
        </el-card>
      </section>

      <el-card v-loading="loading" shadow="never" class="trend-card">
        <template #header>
          <div class="card-heading">
            <strong>历史预测趋势</strong>
            <span>{{ history.length ? `共 ${history.length} 个目标日期` : '暂无数据' }}</span>
          </div>
        </template>
        <div v-if="history.length" ref="chartContainer" class="trend-chart" aria-label="预测累计播放量趋势图" />
        <el-empty v-else description="暂无预测数据" />
      </el-card>
    </template>
    <ExplanationDrawer
      v-model="explanationVisible"
      entity-type="PREDICTION"
      :entity-id="currentPrediction?.prediction_id ?? null"
      module-type="PREDICTION"
    />
  </main>
</template>

<style scoped>
.prediction-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}
.page-header,.header-actions,.toolbar,.selector,.card-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}
.page-header{align-items:flex-start;margin-bottom:20px}.page-header h1{margin:0 0 8px;font-size:clamp(28px,3vw,38px)}
.header-actions{justify-content:flex-end;flex-wrap:wrap}.toolbar-card,.page-alert{margin-bottom:20px}.toolbar{align-items:flex-start}.selector{justify-content:flex-start}.toolbar-label{font-weight:600}.source-note,.subtitle,.reference-note{margin:12px 0 0;color:var(--el-text-color-secondary);font-size:13px}
.eyebrow{margin:0 0 8px;color:var(--el-color-primary);font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.subtitle{margin:0;font-size:14px}
.empty-card{margin-bottom:20px}.summary-grid{display:grid;grid-template-columns:minmax(280px,.9fr) minmax(320px,1.1fr);gap:20px;margin-bottom:20px}.summary-card,.explain-card{min-height:300px}
.prediction-summary{display:flex;flex-direction:column;align-items:flex-start}.summary-label,.target-date{color:var(--el-text-color-secondary)}.prediction-value{display:block;margin:18px 0 8px;color:var(--el-color-primary);font-size:48px;line-height:1;font-variant-numeric:tabular-nums}.prediction-meta{width:100%;margin-top:22px}.reference-note{line-height:1.8}.trend-card{margin-bottom:20px}.trend-chart{width:100%;height:380px}.card-heading span{color:var(--el-text-color-secondary);font-size:13px}
@media(max-width:800px){.prediction-page{padding:18px}.page-header,.toolbar{align-items:stretch;flex-direction:column}.header-actions,.selector{justify-content:flex-start;flex-wrap:wrap}.summary-grid{grid-template-columns:1fr}.prediction-value{font-size:40px}}
</style>
