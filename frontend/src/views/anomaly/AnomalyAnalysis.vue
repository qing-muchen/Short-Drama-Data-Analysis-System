<script setup lang="ts">
import * as echarts from 'echarts'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  getAnomalies,
  getAnomalyStatistics,
  updateAnomalyStatus,
} from '../../api/anomaly'
import { useUserStore } from '../../stores/user'
import type {
  AnomalyRecord,
  AnomalySeverity,
  AnomalyStatistics,
  AnomalyStatus,
  AnomalyQuery,
  MetricType,
} from '../../types/anomaly'
import { getApiErrorMessage } from '../../utils/api-error'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const loading = ref(false)
const errorMessage = ref('')
const records = ref<AnomalyRecord[]>([])
const statistics = ref<AnomalyStatistics | null>(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const severity = ref<AnomalySeverity | ''>('')
const status = ref<AnomalyStatus | ''>('')
const metricType = ref<MetricType | ''>('')
const detail = ref<AnomalyRecord | null>(null)
const statusUpdating = ref<number | null>(null)
const chartContainer = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const severityLabels: Record<AnomalySeverity, string> = { A: 'A级', B: 'B级', C: 'C级' }
const statusLabels: Record<AnomalyStatus, string> = {
  OPEN: '待处理', ACKNOWLEDGED: '已确认', RESOLVED: '已解决', IGNORED: '已忽略',
}
const metricLabels: Record<MetricType, string> = {
  PLAY_COUNT: '播放量', ENGAGEMENT_RATE: '互动率',
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN').format(date)
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function metricLabel(value: MetricType): string { return metricLabels[value] }
function statusLabel(value: AnomalyStatus): string { return statusLabels[value] }
function openDetail(record: AnomalyRecord): void { detail.value = record }

function readableError(error: unknown): string {
  return getApiErrorMessage(error, '异常检测数据加载失败，请稍后重试。')
}

function query(): AnomalyQuery {
  return {
    page: page.value,
    page_size: pageSize.value,
    ...(severity.value ? { severity: severity.value } : {}),
    ...(status.value ? { status: status.value } : {}),
    ...(metricType.value ? { metric_type: metricType.value } : {}),
  }
}

async function load(): Promise<void> {
  if (loading.value) return
  loading.value = true
  errorMessage.value = ''
  const [listResult, statisticsResult, trendResult] = await Promise.allSettled([
    getAnomalies(query()),
    getAnomalyStatistics(),
    getAnomalies({ page: 1, page_size: 100 }),
  ])
  if (listResult.status === 'fulfilled') {
    records.value = listResult.value.items
    total.value = listResult.value.total
  }
  if (statisticsResult.status === 'fulfilled') statistics.value = statisticsResult.value
  if (trendResult.status === 'fulfilled') renderTrend(trendResult.value.items)
  const failures = [listResult, statisticsResult, trendResult].filter((item) => item.status === 'rejected')
  if (failures.length) {
    const first = failures[0]
    errorMessage.value = readableError(first?.status === 'rejected' ? first.reason : null)
  }
  loading.value = false
}

async function changeFilter(): Promise<void> {
  page.value = 1
  await load()
}

async function changeStatus(record: AnomalyRecord, nextStatus: AnomalyStatus): Promise<void> {
  if (!isAdmin.value || statusUpdating.value != null || record.status === nextStatus) return
  statusUpdating.value = record.record_id
  try {
    await updateAnomalyStatus(record.record_id, nextStatus)
    ElMessage.success('异常状态已更新。')
    await load()
  } catch (error: unknown) {
    errorMessage.value = readableError(error)
  } finally {
    statusUpdating.value = null
  }
}

function renderTrend(items: AnomalyRecord[]): void {
  if (!chartContainer.value || items.length === 0) {
    chart?.dispose(); chart = null; return
  }
  const counts = new Map<string, number>()
  items.forEach((item) => {
    const date = item.analysis_as_of.slice(0, 10)
    counts.set(date, (counts.get(date) ?? 0) + 1)
  })
  const dates = [...counts.keys()].sort()
  chart ??= echarts.init(chartContainer.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: 24, bottom: 46, containLabel: true },
    xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true, rotate: 25 } },
    yAxis: { type: 'value', minInterval: 1, name: '异常数' },
    series: [{ name: '异常数量', type: 'line', smooth: true, data: dates.map((date) => counts.get(date) ?? 0), lineStyle: { color: '#e6a23c', width: 3 }, itemStyle: { color: '#e6a23c' } }],
  }, true)
}

function resizeChart(): void { chart?.resize() }

watch(records, async () => { await nextTick() }, { deep: true })
onMounted(() => { window.addEventListener('resize', resizeChart); void load() })
onBeforeUnmount(() => { window.removeEventListener('resize', resizeChart); chart?.dispose(); chart = null })
</script>

<template>
  <main class="anomaly-page">
    <header class="page-header">
      <div><p class="eyebrow">Anomaly Detection</p><h1>异常检测分析</h1><p class="subtitle">识别短剧运营行为偏离，辅助定位需要关注的数据。</p></div>
      <div class="header-actions"><router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button></div>
    </header>
    <el-alert v-if="errorMessage" class="page-error" type="error" show-icon :title="errorMessage" :closable="false" />
    <section v-loading="loading" class="stats-grid">
      <el-card v-for="item in [{ label: '总异常数', value: statistics?.total_count }, { label: 'A级', value: statistics?.severity_distribution.A }, { label: 'B级', value: statistics?.severity_distribution.B }, { label: 'C级', value: statistics?.severity_distribution.C }, { label: '待处理', value: statistics?.status_distribution.OPEN }]" :key="item.label" shadow="hover"><span class="metric-label">{{ item.label }}</span><strong class="metric-value">{{ item.value ?? '--' }}</strong></el-card>
    </section>
    <section class="content-grid">
      <el-card shadow="never" class="list-card">
        <template #header><div class="card-header"><strong>异常列表</strong><div class="filters"><el-select v-model="severity" clearable placeholder="严重等级" @change="changeFilter"><el-option v-for="item in ['A','B','C']" :key="item" :label="severityLabels[item as AnomalySeverity]" :value="item" /></el-select><el-select v-model="status" clearable placeholder="状态" @change="changeFilter"><el-option v-for="item in ['OPEN','ACKNOWLEDGED','RESOLVED','IGNORED']" :key="item" :label="statusLabels[item as AnomalyStatus]" :value="item" /></el-select><el-select v-model="metricType" clearable placeholder="指标" @change="changeFilter"><el-option v-for="item in ['PLAY_COUNT','ENGAGEMENT_RATE']" :key="item" :label="metricLabels[item as MetricType]" :value="item" /></el-select></div></div></template>
        <el-table v-loading="loading" :data="records" row-key="record_id" empty-text="暂无异常记录" @row-click="openDetail">
          <el-table-column prop="drama_name" label="短剧" min-width="130" show-overflow-tooltip /><el-table-column label="指标" width="100"><template #default="scope">{{ metricLabel(scope.row.metric_type) }}</template></el-table-column><el-table-column prop="anomaly_type" label="异常类型" min-width="190" show-overflow-tooltip /><el-table-column label="等级" width="74"><template #default="scope"><el-tag :type="scope.row.severity === 'A' ? 'danger' : scope.row.severity === 'B' ? 'warning' : 'info'">{{ scope.row.severity }}</el-tag></template></el-table-column><el-table-column label="状态" width="110"><template #default="scope">{{ statusLabel(scope.row.status) }}</template></el-table-column><el-table-column label="分析时间" width="130"><template #default="scope">{{ formatDate(scope.row.analysis_as_of) }}</template></el-table-column><el-table-column prop="evidence_summary" label="证据说明" min-width="220" show-overflow-tooltip /><el-table-column v-if="isAdmin" label="操作" width="170" fixed="right"><template #default="scope"><el-select :model-value="scope.row.status" size="small" :loading="statusUpdating === scope.row.record_id" @change="(value: AnomalyStatus) => changeStatus(scope.row, value)"><el-option v-for="item in ['OPEN','ACKNOWLEDGED','RESOLVED','IGNORED']" :key="item" :label="statusLabels[item as AnomalyStatus]" :value="item" /></el-select></template></el-table-column>
        </el-table>
        <el-pagination v-if="total" v-model:current-page="page" v-model:page-size="pageSize" class="pagination" layout="total, sizes, prev, pager, next" :total="total" :page-sizes="[20, 50, 100]" @current-change="load" @size-change="changeFilter" />
      </el-card>
      <el-card shadow="never" class="trend-card"><template #header><strong>异常趋势</strong></template><div v-if="records.length || total" ref="chartContainer" class="trend-chart" /><el-empty v-else description="暂无趋势数据" /></el-card>
    </section>
    <el-drawer :model-value="detail !== null" title="异常详情" size="420px" @close="detail = null"><template v-if="detail"><el-descriptions :column="1" border><el-descriptions-item label="短剧">{{ detail.drama_name }}</el-descriptions-item><el-descriptions-item label="异常类型">{{ detail.anomaly_type }}</el-descriptions-item><el-descriptions-item label="指标">{{ metricLabel(detail.metric_type) }}</el-descriptions-item><el-descriptions-item label="严重等级">{{ detail.severity }}</el-descriptions-item><el-descriptions-item label="状态">{{ statusLabel(detail.status) }}</el-descriptions-item><el-descriptions-item label="证据">{{ detail.evidence_summary }}</el-descriptions-item><el-descriptions-item label="算法版本">{{ detail.algorithm_version }}</el-descriptions-item><el-descriptions-item label="分析时间">{{ formatDateTime(detail.analysis_as_of) }}</el-descriptions-item></el-descriptions></template></el-drawer>
  </main>
</template>

<style scoped>
.anomaly-page { min-height: 100vh; padding: 28px; color: var(--el-text-color-primary); background: var(--el-bg-color-page); }
.page-header, .card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.header-actions, .filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.eyebrow, .subtitle, .metric-label { margin: 0; color: var(--el-text-color-secondary); }
.eyebrow { margin-bottom: 8px; color: var(--el-color-warning); font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
h1 { margin: 0 0 8px; font-size: clamp(26px, 3vw, 38px); }.page-error { margin: 20px 0; }
.stats-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 16px; margin: 24px 0; }.metric-value { display: block; margin-top: 12px; font-size: 28px; }
.content-grid { display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(300px, 1fr); gap: 20px; }.trend-chart { width: 100%; height: 360px; }.pagination { justify-content: flex-end; margin-top: 18px; }
@media (max-width: 1000px) { .stats-grid { grid-template-columns: repeat(3, 1fr); }.content-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .anomaly-page { padding: 18px; }.page-header { flex-direction: column; }.stats-grid { grid-template-columns: repeat(2, 1fr); }.card-header { align-items: stretch; flex-direction: column; } }
</style>
