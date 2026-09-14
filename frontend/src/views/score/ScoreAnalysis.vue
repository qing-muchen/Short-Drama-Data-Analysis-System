<script setup lang="ts">
import * as echarts from 'echarts'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import {
  calculateScores,
  getDramaScore,
  getScoreLevelDistribution,
  getScoreRanking,
} from '../../api/score'
import { useUserStore } from '../../stores/user'
import type {
  DramaScore,
  ScoreCalculationResult,
  ScoreLevel,
  ScoreLevelCount,
  ScoreRankingItem,
} from '../../types/score'
import { getApiErrorMessage } from '../../utils/api-error'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const scoreDate = ref(localDateString(new Date()))
const ranking = ref<ScoreRankingItem[]>([])
const levelDistribution = ref<ScoreLevelCount[]>(defaultDistribution())
const selectedScore = ref<DramaScore | null>(null)
const selectedDramaId = ref<number | null>(null)
const calculationResult = ref<ScoreCalculationResult | null>(null)
const loading = ref(false)
const detailLoading = ref(false)
const calculating = ref(false)
const errorMessage = ref('')
const detailError = ref('')
const radarContainer = ref<HTMLDivElement | null>(null)
let radarChart: echarts.ECharts | null = null

const levelTone: Record<ScoreLevel, 'danger' | 'warning' | 'success' | 'info'> = {
  S: 'danger',
  A: 'warning',
  B: 'success',
  C: 'info',
}

const skippedReasonLabels: Record<string, string> = {
  NO_VALID_SNAPSHOT: '无有效快照',
  INCOMPLETE_METRICS: '指标不完整',
  ZERO_PLAY_COUNT: '播放量为零',
  INSUFFICIENT_HISTORY: '历史数据不足',
  MISSING_RELEASE_DATE: '缺少发布日期',
  DATA_QUALITY_ERROR: '数据质量异常',
}

function localDateString(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function defaultDistribution(): ScoreLevelCount[] {
  return (['S', 'A', 'B', 'C'] as const).map((level) => ({ level, count: 0 }))
}

function formatScore(value: number): string {
  return value.toFixed(2)
}

function formatDateTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
  }).format(parsed)
}

function skippedReasonText(result: ScoreCalculationResult): string {
  const entries = Object.entries(result.skipped_reasons)
  if (entries.length === 0) return '无跳过记录'
  return entries
    .map(([reason, count]) => `${skippedReasonLabels[reason] ?? reason} ${count ?? 0} 部`)
    .join('、')
}

async function loadScoreDashboard(): Promise<void> {
  if (!scoreDate.value || loading.value) return
  loading.value = true
  errorMessage.value = ''
  detailError.value = ''
  calculationResult.value = null

  const [rankingResult, distributionResult] = await Promise.allSettled([
    getScoreRanking({ score_date: scoreDate.value, page: 1, page_size: 10 }),
    getScoreLevelDistribution(scoreDate.value),
  ])

  if (rankingResult.status === 'fulfilled') {
    ranking.value = rankingResult.value.items
  } else {
    ranking.value = []
  }
  if (distributionResult.status === 'fulfilled') {
    levelDistribution.value = distributionResult.value.items
  } else {
    levelDistribution.value = defaultDistribution()
  }

  const failures = [rankingResult, distributionResult].filter(
    (result) => result.status === 'rejected',
  )
  if (failures.length > 0) {
    const firstFailure = failures[0]
    errorMessage.value = getApiErrorMessage(
      firstFailure?.status === 'rejected' ? firstFailure.reason : null,
      failures.length === 2
        ? '评分排行和等级分布加载失败，请稍后重试。'
        : '部分评分数据加载失败，已保留可用结果。',
    )
  }

  const firstDramaId = ranking.value[0]?.drama_id ?? null
  if (firstDramaId === null) {
    selectedDramaId.value = null
    selectedScore.value = null
  } else if (!ranking.value.some((item) => item.drama_id === selectedDramaId.value)) {
    await loadScoreDetail(firstDramaId)
  } else if (selectedDramaId.value !== null) {
    await loadScoreDetail(selectedDramaId.value)
  }
  loading.value = false
}

async function loadScoreDetail(dramaId: number): Promise<void> {
  selectedDramaId.value = dramaId
  detailLoading.value = true
  detailError.value = ''
  try {
    selectedScore.value = await getDramaScore(dramaId)
  } catch (error: unknown) {
    selectedScore.value = null
    detailError.value = getApiErrorMessage(error, '评分详情加载失败，请稍后重试。')
  } finally {
    detailLoading.value = false
  }
}

async function recalculate(): Promise<void> {
  if (!isAdmin.value || !scoreDate.value || calculating.value) return
  calculating.value = true
  errorMessage.value = ''
  try {
    const result = await calculateScores(scoreDate.value)
    ElMessage.success(`评分计算完成：成功 ${result.calculated_count} 部`)
    await loadScoreDashboard()
    calculationResult.value = result
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '评分计算失败，请稍后重试。')
  } finally {
    calculating.value = false
  }
}

function renderRadar(): void {
  if (!radarContainer.value || !selectedScore.value) {
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
          { name: 'Heat', max: 100 },
          { name: 'Growth', max: 100 },
          { name: 'Engagement', max: 100 },
          { name: 'Lifecycle', max: 100 },
        ],
      },
      series: [
        {
          name: selectedScore.value.drama_name,
          type: 'radar',
          data: [
            {
              name: '评分维度',
              value: [
                selectedScore.value.heat_score,
                selectedScore.value.growth_score,
                selectedScore.value.engagement_score,
                selectedScore.value.lifecycle_score,
              ],
              areaStyle: { color: 'rgba(64, 158, 255, 0.24)' },
              lineStyle: { color: '#409eff', width: 2 },
              itemStyle: { color: '#409eff' },
            },
          ],
        },
      ],
    },
    true,
  )
}

function resizeRadar(): void {
  radarChart?.resize()
}

watch(
  selectedScore,
  async () => {
    await nextTick()
    renderRadar()
  },
)

onMounted(() => {
  window.addEventListener('resize', resizeRadar)
  void loadScoreDashboard()
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeRadar)
  radarChart?.dispose()
})
</script>

<template>
  <main class="score-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Composite Score V1.0</p>
        <h1>短剧综合评分分析</h1>
        <p class="subtitle">基于运营指标、增长表现、互动质量和生命周期阶段的综合评价结果。</p>
      </div>
      <div class="header-actions">
        <router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link>
        <router-link to="/analytics"><el-button>分析中心</el-button></router-link>
        <el-button :icon="Refresh" :loading="loading" @click="loadScoreDashboard">刷新</el-button>
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
            :disabled-date="(date: Date) => date.getTime() > Date.now()"
            @change="loadScoreDashboard"
          />
        </div>
        <el-button
          v-if="isAdmin"
          type="primary"
          :loading="calculating"
          @click="recalculate"
        >
          重新计算所选日期评分
        </el-button>
      </div>
      <p class="source-note">页面仅展示Score API返回结果，不在浏览器中重新计算评分或划分等级。</p>
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
        <el-button text type="primary" @click="loadScoreDashboard">重新加载</el-button>
      </template>
    </el-alert>

    <el-alert
      v-if="calculationResult"
      class="page-alert"
      type="success"
      show-icon
      :closable="false"
      :title="`计算完成：成功 ${calculationResult.calculated_count} 部，跳过 ${calculationResult.skipped_count} 部`"
      :description="skippedReasonText(calculationResult)"
    />

    <section aria-labelledby="level-title">
      <div class="section-heading">
        <div><h2 id="level-title">等级分布</h2><p>S / A / B / C作品数量</p></div>
      </div>
      <div class="level-grid">
        <el-card
          v-for="item in levelDistribution"
          :key="item.level"
          v-loading="loading"
          shadow="hover"
          class="level-card"
        >
          <el-tag :type="levelTone[item.level]" effect="dark" round>{{ item.level }}</el-tag>
          <strong>{{ item.count }}</strong>
          <span>部短剧</span>
        </el-card>
      </div>
    </section>

    <section aria-labelledby="ranking-title">
      <div class="section-heading">
        <div><h2 id="ranking-title">综合评分 Top 10</h2><p>点击作品查看四维评分详情</p></div>
      </div>
      <el-card v-loading="loading" shadow="never">
        <el-table
          v-if="ranking.length"
          :data="ranking"
          highlight-current-row
          :current-row-key="selectedDramaId ?? undefined"
          row-key="drama_id"
          @row-click="(row: ScoreRankingItem) => loadScoreDetail(row.drama_id)"
        >
          <el-table-column prop="rank" label="排名" width="72" align="center" />
          <el-table-column prop="drama_name" label="短剧名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="综合评分" width="110" align="right">
            <template #default="scope">{{ formatScore(scope.row.total_score) }}</template>
          </el-table-column>
          <el-table-column label="等级" width="80" align="center">
            <template #default="scope"><el-tag :type="levelTone[scope.row.level as ScoreLevel]" effect="light">{{ scope.row.level }}</el-tag></template>
          </el-table-column>
          <el-table-column label="Heat" width="96" align="right">
            <template #default="scope">{{ formatScore(scope.row.heat_score) }}</template>
          </el-table-column>
          <el-table-column label="Growth" width="96" align="right">
            <template #default="scope">{{ formatScore(scope.row.growth_score) }}</template>
          </el-table-column>
          <el-table-column label="Engagement" width="116" align="right">
            <template #default="scope">{{ formatScore(scope.row.engagement_score) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="当前日期暂无综合评分数据" />
      </el-card>
    </section>

    <section aria-labelledby="detail-title">
      <div class="section-heading">
        <div><h2 id="detail-title">单剧评分详情</h2><p>Lifecycle为规则化生命周期阶段评分，不是预测结果</p></div>
      </div>
      <el-alert
        v-if="detailError"
        class="page-alert"
        type="error"
        show-icon
        :closable="false"
        :title="detailError"
      />
      <el-card v-loading="detailLoading" shadow="never" class="detail-card">
        <el-empty v-if="!selectedScore" description="请选择有评分结果的短剧" />
        <div v-else class="detail-grid">
          <div class="score-summary">
            <div class="score-heading">
              <div><h3>{{ selectedScore.drama_name }}</h3><small>{{ selectedScore.drama_code }}</small></div>
              <el-tag :type="levelTone[selectedScore.level]" effect="dark" size="large">{{ selectedScore.level }}</el-tag>
            </div>
            <strong class="total-score">{{ formatScore(selectedScore.total_score) }}</strong>
            <span class="total-label">综合评分</span>
            <el-descriptions :column="1" border class="score-meta">
              <el-descriptions-item label="评分日期">{{ selectedScore.score_date }}</el-descriptions-item>
              <el-descriptions-item label="分析时间">{{ formatDateTime(selectedScore.analysis_as_of) }}</el-descriptions-item>
              <el-descriptions-item label="算法版本">{{ selectedScore.algorithm_version }}</el-descriptions-item>
              <el-descriptions-item label="作用域">{{ selectedScore.score_scope_type }} / {{ selectedScore.score_scope_id }}</el-descriptions-item>
            </el-descriptions>
          </div>
          <div class="radar-panel">
            <div ref="radarContainer" class="radar-chart" aria-label="综合评分四维雷达图" />
            <div class="dimension-list">
              <span>Heat <strong>{{ formatScore(selectedScore.heat_score) }}</strong></span>
              <span>Growth <strong>{{ formatScore(selectedScore.growth_score) }}</strong></span>
              <span>Engagement <strong>{{ formatScore(selectedScore.engagement_score) }}</strong></span>
              <span>Lifecycle <strong>{{ formatScore(selectedScore.lifecycle_score) }}</strong></span>
            </div>
          </div>
        </div>
      </el-card>
    </section>
  </main>
</template>

<style scoped>
.score-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}
.page-header,.header-actions,.toolbar,.section-heading,.score-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}
.page-header{align-items:flex-start;margin-bottom:20px}.page-header h1{margin:0 0 8px;font-size:clamp(28px,3vw,38px)}
.eyebrow,.subtitle,.source-note,.section-heading p,.total-label,.score-heading small{margin:0;color:var(--el-text-color-secondary)}
.eyebrow{margin-bottom:8px;color:var(--el-color-primary);font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.header-actions{justify-content:flex-end;flex-wrap:wrap}.toolbar-card,.page-alert{margin-bottom:20px}.toolbar-label{margin-right:12px;font-weight:600}.source-note{margin-top:12px;font-size:13px}
section{margin-top:24px}.section-heading{align-items:flex-end;margin-bottom:12px}.section-heading h2{margin:0 0 5px;font-size:20px}.section-heading p{font-size:13px}
.level-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.level-card :deep(.el-card__body){display:flex;align-items:center;gap:12px}.level-card strong{margin-left:auto;font-size:28px;font-variant-numeric:tabular-nums}.level-card span:last-child{color:var(--el-text-color-secondary)}
.detail-grid{display:grid;grid-template-columns:minmax(260px,.8fr) minmax(0,1.4fr);gap:28px}.score-heading{align-items:flex-start}.score-heading h3{margin:0 0 4px;font-size:22px}.total-score{display:block;margin-top:26px;color:var(--el-color-primary);font-size:52px;line-height:1;font-variant-numeric:tabular-nums}.total-label{display:block;margin-top:8px}.score-meta{margin-top:24px}
.radar-panel{min-width:0}.radar-chart{width:100%;height:380px}.dimension-list{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.dimension-list span{padding:10px;border-radius:6px;background:var(--el-fill-color-light);text-align:center;color:var(--el-text-color-secondary)}.dimension-list strong{display:block;margin-top:5px;color:var(--el-text-color-primary)}
@media(max-width:900px){.level-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.detail-grid{grid-template-columns:1fr}}
@media(max-width:620px){.score-page{padding:18px}.page-header,.toolbar{align-items:stretch;flex-direction:column}.header-actions{justify-content:flex-start}.level-grid,.dimension-list{grid-template-columns:1fr 1fr}:deep(.el-descriptions__body .el-descriptions__table){display:block}}
</style>
