<script setup lang="ts">
import * as echarts from 'echarts'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import {
  calculateDataQuality,
  getCurrentDataQualityScore,
  getDataQualityHistory,
  getDataQualityRules,
} from '../../api/dataQuality'
import { useUserStore } from '../../stores/user'
import type {
  DataQualityCalculationResult,
  DataQualityHistoryItem,
  DataQualityRule,
  DataQualityScore,
  QualityAlgorithmVersion,
  QualityDimension,
  QualityGrade,
  QualityRuleStatus,
} from '../../types/dataQuality'
import { getApiErrorDetail, getApiErrorMessage, getApiErrorStatus } from '../../utils/api-error'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const scoreDate = ref(localDateString(new Date()))
const algorithmVersion = ref<QualityAlgorithmVersion>('Quality Score V2.0')
const currentScore = ref<DataQualityScore | null>(null)
const history = ref<DataQualityHistoryItem[]>([])
const rules = ref<DataQualityRule[]>([])
const calculationResult = ref<DataQualityCalculationResult | null>(null)
const loading = ref(false)
const calculating = ref(false)
const errorMessage = ref('')
const radarContainer = ref<HTMLDivElement | null>(null)
const trendContainer = ref<HTMLDivElement | null>(null)
let radarChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null

const hasLimitedHistoricalReplay = computed(
  () => currentScore.value?.source_watermark?.replay_capability === 'LIMITED_CURRENT_MASTER',
)

const gradeTone: Record<QualityGrade, 'danger' | 'warning' | 'success' | 'info'> = {
  S: 'danger',
  A: 'warning',
  B: 'success',
  C: 'info',
}

const dimensionLabels: Record<QualityDimension, string> = {
  COMPLETENESS: '完整性',
  ACCURACY: '准确性',
  CONSISTENCY: '一致性',
  TIMELINESS: '及时性',
}

const ruleStatusTone: Record<QualityRuleStatus, 'success' | 'info' | 'warning'> = {
  ACTIVE: 'success',
  DRAFT: 'warning',
  INACTIVE: 'info',
}

function localDateString(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatScore(value: number | null | undefined): string {
  return value == null ? '--' : value.toFixed(2)
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

function formatWeight(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

async function loadDataQualityDashboard(): Promise<void> {
  if (loading.value) return
  loading.value = true
  errorMessage.value = ''
  calculationResult.value = null

  const [scoreResult, historyResult, rulesResult] = await Promise.allSettled([
    getCurrentDataQualityScore(algorithmVersion.value),
    getDataQualityHistory({ limit: 90, algorithm_version: algorithmVersion.value }),
    getDataQualityRules(algorithmVersion.value),
  ])

  currentScore.value = scoreResult.status === 'fulfilled' ? scoreResult.value : null
  history.value = historyResult.status === 'fulfilled' ? historyResult.value.items : []
  rules.value = rulesResult.status === 'fulfilled' ? rulesResult.value.items : []

  const failures = [
    scoreResult.status === 'rejected' && getApiErrorStatus(scoreResult.reason) !== 404
      ? scoreResult
      : null,
    historyResult.status === 'rejected' ? historyResult : null,
    rulesResult.status === 'rejected' ? rulesResult : null,
  ].filter((result) => result != null)
  if (failures.length > 0) {
    const firstFailure = failures[0]
    errorMessage.value = getApiErrorMessage(
      firstFailure?.status === 'rejected' ? firstFailure.reason : null,
      failures.length === 3
        ? '数据质量分析加载失败，请稍后重试。'
        : '部分数据质量模块加载失败，已保留可用结果。',
    )
  }
  loading.value = false
}

async function recalculate(): Promise<void> {
  if (!isAdmin.value || !scoreDate.value || calculating.value) return
  calculating.value = true
  errorMessage.value = ''
  try {
    const result = await calculateDataQuality(scoreDate.value, algorithmVersion.value)
    await loadDataQualityDashboard()
    calculationResult.value = result
    ElMessage.success(`数据质量评分完成：${formatScore(result.total_score)} / ${result.quality_grade}`)
  } catch (error: unknown) {
    const reason = getApiErrorDetail(error, 'reason')
    errorMessage.value =
      reason === 'NO_ACTIVE_RULE_SET'
        ? '尚未发布可执行的数据质量规则，当前仅可查看已有评分与历史记录。'
        : reason === 'INSUFFICIENT_QUALITY_DATA'
          ? '当前没有可覆盖四个质量维度的适用证据，本次评分未保存。'
        : getApiErrorMessage(error, '数据质量评分失败，请稍后重试。')
  } finally {
    calculating.value = false
  }
}

function renderRadar(): void {
  if (!radarContainer.value || !currentScore.value) {
    radarChart?.dispose()
    radarChart = null
    return
  }

  radarChart ??= echarts.init(radarContainer.value)
  radarChart.setOption(
    {
      tooltip: { trigger: 'item' },
      radar: {
        radius: '68%',
        splitNumber: 5,
        indicator: [
          { name: '完整性', max: 100 },
          { name: '准确性', max: 100 },
          { name: '一致性', max: 100 },
          { name: '及时性', max: 100 },
        ],
      },
      series: [
        {
          name: '数据质量四维评分',
          type: 'radar',
          data: [
            {
              name: currentScore.value.score_date,
              value: [
                currentScore.value.completeness_score,
                currentScore.value.accuracy_score,
                currentScore.value.consistency_score,
                currentScore.value.timeliness_score,
              ],
              areaStyle: { color: 'rgba(103, 194, 58, 0.24)' },
              lineStyle: { color: '#67c23a', width: 2 },
              itemStyle: { color: '#67c23a' },
            },
          ],
        },
      ],
    },
    true,
  )
}

function renderTrend(): void {
  if (!trendContainer.value || history.value.length === 0) {
    trendChart?.dispose()
    trendChart = null
    return
  }

  trendChart ??= echarts.init(trendContainer.value)
  trendChart.setOption(
    {
      tooltip: { trigger: 'axis' },
      grid: { left: 48, right: 28, top: 32, bottom: 54, containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: history.value.map((item) => item.score_date),
        axisLabel: { hideOverlap: true, rotate: 28 },
      },
      yAxis: { type: 'value', min: 0, max: 100, name: '质量分' },
      series: [
        {
          name: '综合质量分',
          type: 'line',
          smooth: true,
          showSymbol: history.value.length <= 30,
          data: history.value.map((item) => item.total_score),
          lineStyle: { color: '#409eff', width: 3 },
          itemStyle: { color: '#409eff' },
          areaStyle: { color: 'rgba(64, 158, 255, 0.12)' },
        },
      ],
    },
    true,
  )
}

function resizeCharts(): void {
  radarChart?.resize()
  trendChart?.resize()
}

watch(
  currentScore,
  async () => {
    await nextTick()
    renderRadar()
  },
)

watch(
  history,
  async () => {
    await nextTick()
    renderTrend()
  },
  { deep: true },
)

watch(algorithmVersion, () => {
  void loadDataQualityDashboard()
})

onMounted(() => {
  window.addEventListener('resize', resizeCharts)
  void loadDataQualityDashboard()
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCharts)
  radarChart?.dispose()
  trendChart?.dispose()
})
</script>

<template>
  <main class="quality-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">数据质量治理</p>
        <h1>数据质量治理分析</h1>
        <p class="subtitle">从完整性、准确性、一致性和及时性观察全局数据治理成效。</p>
      </div>
      <div class="header-actions">
        <router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link>
        <router-link to="/scores"><el-button>综合评分</el-button></router-link>
        <el-button :icon="Refresh" :loading="loading" @click="loadDataQualityDashboard">
          刷新
        </el-button>
      </div>
    </header>

    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <div>
          <span class="toolbar-label">评分日期</span>
          <el-date-picker
            v-model="scoreDate"
            type="date"
            value-format="YYYY-MM-DD"
            :clearable="false"
            :disabled-date="(value: Date) => value.getTime() > Date.now()"
          />
        </div>
        <div>
          <span class="toolbar-label">评分算法</span>
          <el-select v-model="algorithmVersion" style="width: 210px">
            <el-option label="Quality Score V2.0（规则分加权）" value="Quality Score V2.0" />
            <el-option label="Quality Score V1.0（二元兼容）" value="Quality Score V1.0" />
          </el-select>
        </div>
        <el-button
          v-if="isAdmin"
          type="primary"
          :loading="calculating"
          @click="recalculate"
        >
          重新计算质量评分
        </el-button>
      </div>
      <p class="source-note">页面只展示所选算法版本的 API 结果，不混合 V1/V2 趋势，也不在前端重新计算评分或等级。</p>
    </el-card>

    <el-alert
      v-if="errorMessage"
      class="page-alert"
      type="error"
      show-icon
      :closable="false"
      :title="errorMessage"
    >
      <template #default>
        <el-button text type="primary" @click="loadDataQualityDashboard">重新加载</el-button>
      </template>
    </el-alert>

    <el-alert
      v-if="calculationResult"
      class="page-alert"
      type="success"
      show-icon
      :closable="false"
      :title="`评分完成：${formatScore(calculationResult.total_score)} / ${calculationResult.quality_grade}`"
      :description="`规则 ${calculationResult.applied_rule_count}/${calculationResult.rule_count} 已应用，评估 ${calculationResult.evaluated_entity_count} 条实体记录。`"
    />

    <el-alert
      v-if="hasLimitedHistoricalReplay"
      class="page-alert"
      type="warning"
      show-icon
      :closable="false"
      title="历史范围使用当前主数据状态"
      description="快照与修订可按分析时间重放，但短剧、平台及上线关系不是完整双时态数据，不能视为严格历史复现。"
    />

    <section class="score-grid" aria-label="当前数据质量评分">
      <el-card v-loading="loading" shadow="never" class="score-card">
        <template #header><strong>当前质量评分</strong></template>
        <el-empty v-if="!currentScore" description="暂无数据质量评分" />
        <div v-else class="score-content">
          <div>
            <strong class="total-score">{{ formatScore(currentScore.total_score) }}</strong>
            <span class="score-caption">综合质量分</span>
          </div>
          <el-tag :type="gradeTone[currentScore.quality_grade]" effect="dark" size="large">
            {{ currentScore.quality_grade }}级
          </el-tag>
          <el-descriptions :column="1" border class="score-meta">
            <el-descriptions-item label="规则集版本">
              {{ currentScore.rule_set_version }}
            </el-descriptions-item>
            <el-descriptions-item label="分析时间">
              {{ formatDateTime(currentScore.analysis_as_of) }}
            </el-descriptions-item>
            <el-descriptions-item label="评分日期">
              {{ currentScore.score_date }}
            </el-descriptions-item>
            <el-descriptions-item label="算法版本">
              {{ currentScore.algorithm_version }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </el-card>

      <el-card v-loading="loading" shadow="never" class="chart-card">
        <template #header><strong>四维质量雷达图</strong></template>
        <el-empty v-if="!currentScore" description="暂无四维评分数据" />
        <div v-else>
          <div ref="radarContainer" class="radar-chart" aria-label="数据质量四维雷达图" />
          <div class="dimension-grid">
            <span>完整性<strong>{{ formatScore(currentScore.completeness_score) }}</strong></span>
            <span>准确性<strong>{{ formatScore(currentScore.accuracy_score) }}</strong></span>
            <span>一致性<strong>{{ formatScore(currentScore.consistency_score) }}</strong></span>
            <span>及时性<strong>{{ formatScore(currentScore.timeliness_score) }}</strong></span>
          </div>
        </div>
      </el-card>
    </section>

    <el-card v-loading="loading" shadow="never" class="section-card">
      <template #header>
        <div class="card-heading">
          <strong>历史质量趋势</strong>
          <span>最近 {{ history.length }} 个评分日</span>
        </div>
      </template>
      <div v-if="history.length" ref="trendContainer" class="trend-chart" aria-label="历史质量评分趋势图" />
      <el-empty v-else description="暂无历史质量趋势" />
    </el-card>

    <el-card v-loading="loading" shadow="never" class="section-card">
      <template #header>
        <div class="card-heading">
          <strong>当前规则列表</strong>
          <span>{{ rules.length }} 条规则</span>
        </div>
      </template>
      <el-table v-if="rules.length" :data="rules" stripe>
        <el-table-column prop="rule_code" label="规则编码" min-width="190" show-overflow-tooltip />
        <el-table-column label="维度" width="120">
          <template #default="scope">
            {{ dimensionLabels[scope.row.dimension as QualityDimension] }}
          </template>
        </el-table-column>
        <el-table-column label="权重" width="100" align="right">
          <template #default="scope">{{ formatWeight(scope.row.weight) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="scope">
            <el-tag :type="ruleStatusTone[scope.row.status as QualityRuleStatus]" effect="light">
              {{ scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="当前没有可展示的质量规则" />
    </el-card>
  </main>
</template>

<style scoped>
.quality-page {
  min-height: 100vh;
  padding: 28px;
  color: var(--el-text-color-primary);
  background: var(--el-bg-color-page);
}

.page-header,
.header-actions,
.toolbar,
.card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header {
  align-items: flex-start;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0 0 8px;
  font-size: clamp(28px, 3vw, 38px);
}

.header-actions {
  justify-content: flex-end;
  flex-wrap: wrap;
}

.eyebrow,
.subtitle,
.source-note,
.card-heading span,
.score-caption {
  margin: 0;
  color: var(--el-text-color-secondary);
}

.eyebrow {
  margin-bottom: 8px;
  color: var(--el-color-success);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.toolbar-card,
.page-alert,
.section-card {
  margin-bottom: 20px;
}

.toolbar-label {
  margin-right: 12px;
  font-weight: 600;
}

.source-note {
  margin-top: 12px;
  font-size: 13px;
}

.score-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.75fr) minmax(0, 1.35fr);
  gap: 20px;
  margin-bottom: 20px;
}

.score-card,
.chart-card {
  min-height: 490px;
}

.score-content {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: start;
  gap: 18px;
}

.total-score {
  display: block;
  color: var(--el-color-success);
  font-size: 58px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.score-caption {
  display: block;
  margin-top: 8px;
}

.score-meta {
  grid-column: 1 / -1;
  margin-top: 18px;
}

.radar-chart {
  width: 100%;
  height: 350px;
}

.trend-chart {
  width: 100%;
  height: 360px;
}

.dimension-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.dimension-grid span {
  padding: 10px;
  border-radius: 6px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  text-align: center;
}

.dimension-grid strong {
  display: block;
  margin-top: 5px;
  color: var(--el-text-color-primary);
}

.card-heading span {
  font-size: 13px;
}

@media (max-width: 900px) {
  .score-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .quality-page {
    padding: 18px;
  }

  .page-header,
  .toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .header-actions {
    justify-content: flex-start;
  }

  .dimension-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
