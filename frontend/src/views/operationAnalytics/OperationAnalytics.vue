<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  getDramaBenchmark,
  getDramaLifecycle,
  getOperationEffectiveness,
} from '../../api/operationAnalytics'
import type {
  AnalysisAvailability,
  AvailabilityReason,
  AvailabilityStatus,
  BenchmarkResult,
  LifecycleResult,
  OperationEffectivenessPage,
  OperationEffectivenessResult,
} from '../../types/operationAnalytics'
import { getApiErrorMessage } from '../../utils/api-error'

type TagTone = 'success' | 'warning' | 'info' | 'danger'

const effectData = ref<OperationEffectivenessPage | null>(null)
const lifecycleData = ref<LifecycleResult | null>(null)
const benchmarkData = ref<BenchmarkResult | null>(null)
const effectLoading = ref(false)
const lifecycleLoading = ref(false)
const benchmarkLoading = ref(false)
const effectError = ref('')
const lifecycleError = ref('')
const benchmarkError = ref('')

const effectActionId = ref<number | undefined>()
const effectDramaId = ref<number | undefined>()
const lifecycleDramaId = ref<number | undefined>()
const benchmarkPlatformId = ref<number | undefined>()
const benchmarkDramaIds = ref('')

const reasonLabels: Record<AvailabilityReason, string> = {
  NOT_CALCULATED: '尚未计算',
  INSUFFICIENT_HISTORY: '历史数据不足',
  INCOMPLETE_BEFORE_WINDOW: '行动前窗口不完整',
  INCOMPLETE_AFTER_WINDOW: '行动后窗口不完整',
  INCOMPARABLE_SCOPE: '比较范围不可比',
  MISSING_METRIC: '指标缺失',
  ZERO_BASELINE: '基线为零',
  OVERLAPPING_ACTIONS: '存在重叠行动',
  MIXED_SOURCE_VERSIONS: '来源版本不一致',
  INVALID_CUMULATIVE_SEQUENCE: '累计指标序列无效',
  NOT_COMPLETED: '行动尚未完成',
  GLOBAL_ACTION_UNSUPPORTED: '暂不支持全局行动',
  NOT_AVAILABLE: '暂不可用',
}

const lifecycleStageLabels: Record<string, string> = {
  LAUNCH: '上线期',
  GROWTH: '增长期',
  STABLE: '稳定期',
  DECLINE: '衰退期',
  ARCHIVED: '归档期',
}

const benchmarkIds = computed(() =>
  benchmarkDramaIds.value
    .split(',')
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isInteger(value) && value > 0),
)

function availabilityTone(status: AvailabilityStatus): TagTone {
  if (status === 'AVAILABLE') return 'success'
  if (status === 'PARTIAL') return 'warning'
  if (status === 'INSUFFICIENT') return 'info'
  return 'danger'
}

function availabilityLabel(availability: AnalysisAvailability): string {
  const statusLabel: Record<AvailabilityStatus, string> = {
    AVAILABLE: '数据可用',
    PARTIAL: '部分数据缺失',
    INSUFFICIENT: '历史数据不足',
    NOT_AVAILABLE: '暂不可用',
  }
  if (availability.reasons.length === 0) return statusLabel[availability.status]
  return `${statusLabel[availability.status]}：${availability.reasons
    .map((reason) => reasonLabels[reason])
    .join('、')}`
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

function formatValue(value: number | string | null): string {
  return value == null ? '--' : String(value)
}

function windowLabel(item: OperationEffectivenessResult, kind: 'before' | 'after'): string {
  const window = kind === 'before' ? item.before_window : item.after_window
  return `${window.start_date} — ${window.end_date}`
}

async function loadEffects(page = 1): Promise<void> {
  effectLoading.value = true
  effectError.value = ''
  try {
    effectData.value = await getOperationEffectiveness({
      action_id: effectActionId.value,
      drama_id: effectDramaId.value,
      page,
      page_size: 10,
    })
  } catch (error: unknown) {
    effectError.value = getApiErrorMessage(error, '行动效果分析加载失败。')
  } finally {
    effectLoading.value = false
  }
}

async function loadLifecycle(): Promise<void> {
  if (!lifecycleDramaId.value) {
    ElMessage.warning('请输入有效的 Drama ID。')
    return
  }
  lifecycleLoading.value = true
  lifecycleError.value = ''
  try {
    lifecycleData.value = await getDramaLifecycle(lifecycleDramaId.value)
  } catch (error: unknown) {
    lifecycleError.value = getApiErrorMessage(error, '生命周期分析加载失败。')
  } finally {
    lifecycleLoading.value = false
  }
}

async function loadBenchmark(): Promise<void> {
  if (!benchmarkPlatformId.value || benchmarkIds.value.length < 2 || benchmarkIds.value.length > 20) {
    ElMessage.warning('请输入平台 ID，并提供 2 至 20 个以逗号分隔的 Drama ID。')
    return
  }
  benchmarkLoading.value = true
  benchmarkError.value = ''
  try {
    benchmarkData.value = await getDramaBenchmark({
      drama_ids: benchmarkIds.value,
      platform_id: benchmarkPlatformId.value,
    })
  } catch (error: unknown) {
    benchmarkError.value = getApiErrorMessage(error, 'Benchmark 分析加载失败。')
  } finally {
    benchmarkLoading.value = false
  }
}

onMounted(() => void loadEffects())
</script>

<template>
  <main class="analytics-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">OPERATION ANALYTICS</p>
        <h1>短剧运营分析中心</h1>
        <p class="subtitle">展示行动前后指标变化、生命周期状态与同平台统计比较。</p>
      </div>
      <router-link to="/dashboard"><el-button>返回数据驾驶舱</el-button></router-link>
    </header>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="页面仅描述观察到的指标变化，不表示运营行动与变化之间存在因果关系。"
    />

    <section class="analysis-section">
      <div class="section-heading">
        <div><p class="section-index">01</p><h2>运营行动效果复盘</h2></div>
        <el-form inline class="query-form" @submit.prevent="loadEffects(1)">
          <el-form-item label="Action ID"><el-input-number v-model="effectActionId" :min="1" controls-position="right" /></el-form-item>
          <el-form-item label="Drama ID"><el-input-number v-model="effectDramaId" :min="1" controls-position="right" /></el-form-item>
          <el-button type="primary" :loading="effectLoading" native-type="submit">查询</el-button>
        </el-form>
      </div>
      <el-alert v-if="effectError" type="error" :closable="false" show-icon :title="effectError"><template #default><el-button text type="primary" @click="loadEffects(effectData?.page ?? 1)">重试</el-button></template></el-alert>
      <el-card v-loading="effectLoading" shadow="never">
        <el-empty v-if="!effectLoading && !effectData?.items.length" description="当前条件暂无已完成行动分析" />
        <template v-else-if="effectData">
          <div class="availability-row"><el-tag :type="availabilityTone(effectData.availability.status)">{{ availabilityLabel(effectData.availability) }}</el-tag><span>分析截止：{{ formatDate(effectData.analysis_as_of) }}</span></div>
          <el-table :data="effectData.items" row-key="action_id">
            <el-table-column type="expand">
              <template #default="scope">
                <div class="detail-panel">
                  <p><b>Before：</b>{{ windowLabel(scope.row, 'before') }}</p>
                  <p><b>After：</b>{{ windowLabel(scope.row, 'after') }}</p>
                  <el-table :data="scope.row.metric_changes" size="small">
                    <el-table-column prop="metric_type" label="指标" min-width="150" />
                    <el-table-column label="行动前"><template #default="metric">{{ formatValue(metric.row.before_value) }}</template></el-table-column>
                    <el-table-column label="行动后"><template #default="metric">{{ formatValue(metric.row.after_value) }}</template></el-table-column>
                    <el-table-column label="变化"><template #default="metric">{{ formatValue(metric.row.absolute_change) }}</template></el-table-column>
                    <el-table-column prop="direction" label="方向" />
                  </el-table>
                  <p class="disclaimer">{{ scope.row.disclaimer }}</p>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="action_id" label="Action ID" width="110" />
            <el-table-column prop="drama_id" label="Drama ID" width="110" />
            <el-table-column label="锚点时间" min-width="170"><template #default="scope">{{ formatDate(scope.row.anchor_time) }}</template></el-table-column>
            <el-table-column label="可用性" min-width="220"><template #default="scope"><el-tag :type="availabilityTone(scope.row.availability.status)">{{ availabilityLabel(scope.row.availability) }}</el-tag></template></el-table-column>
          </el-table>
          <el-pagination class="pagination" layout="total, prev, pager, next" :total="effectData.total" :page-size="effectData.page_size" :current-page="effectData.page" @current-change="loadEffects" />
        </template>
      </el-card>
    </section>

    <section class="analysis-section">
      <div class="section-heading">
        <div><p class="section-index">02</p><h2>生命周期分析</h2></div>
        <el-form inline class="query-form" @submit.prevent="loadLifecycle">
          <el-form-item label="Drama ID"><el-input-number v-model="lifecycleDramaId" :min="1" controls-position="right" /></el-form-item>
          <el-button type="primary" :loading="lifecycleLoading" native-type="submit">查询</el-button>
        </el-form>
      </div>
      <el-alert v-if="lifecycleError" type="error" :closable="false" show-icon :title="lifecycleError"><template #default><el-button text type="primary" @click="loadLifecycle">重试</el-button></template></el-alert>
      <el-card v-loading="lifecycleLoading" shadow="never" class="lifecycle-card">
        <el-empty v-if="!lifecycleLoading && !lifecycleData" description="输入 Drama ID 查看生命周期" />
        <template v-else-if="lifecycleData">
          <div class="availability-row"><el-tag :type="availabilityTone(lifecycleData.availability.status)">{{ availabilityLabel(lifecycleData.availability) }}</el-tag><span>评估时间：{{ formatDate(lifecycleData.evaluated_as_of) }}</span></div>
          <div class="lifecycle-summary"><span class="stage">{{ lifecycleData.lifecycle_stage ? lifecycleStageLabels[lifecycleData.lifecycle_stage] : '--' }}</span><div><p>规则版本：{{ lifecycleData.rule_version }}</p><p v-if="lifecycleData.evidence">前窗口均值 {{ lifecycleData.evidence.previous_average ?? '--' }} · 当前窗口均值 {{ lifecycleData.evidence.current_average ?? '--' }}</p></div></div>
        </template>
      </el-card>
    </section>

    <section class="analysis-section">
      <div class="section-heading benchmark-heading">
        <div><p class="section-index">03</p><h2>Benchmark 统计比较</h2></div>
        <el-form inline class="query-form" @submit.prevent="loadBenchmark">
          <el-form-item label="Platform ID"><el-input-number v-model="benchmarkPlatformId" :min="1" controls-position="right" /></el-form-item>
          <el-form-item label="Drama IDs"><el-input v-model="benchmarkDramaIds" placeholder="例如：1,2,3" clearable /></el-form-item>
          <el-button type="primary" :loading="benchmarkLoading" native-type="submit">比较</el-button>
        </el-form>
      </div>
      <el-alert v-if="benchmarkError" type="error" :closable="false" show-icon :title="benchmarkError"><template #default><el-button text type="primary" @click="loadBenchmark">重试</el-button></template></el-alert>
      <el-card v-loading="benchmarkLoading" shadow="never">
        <el-empty v-if="!benchmarkLoading && !benchmarkData" description="输入平台与 2-20 个 Drama ID 开始比较" />
        <template v-else-if="benchmarkData">
          <div class="availability-row"><el-tag :type="availabilityTone(benchmarkData.availability.status)">{{ availabilityLabel(benchmarkData.availability) }}</el-tag><span>窗口：{{ benchmarkData.window.start_date }} — {{ benchmarkData.window.end_date }}</span></div>
          <el-table :data="benchmarkData.metrics" row-key="drama_id">
            <el-table-column prop="drama_id" label="Drama ID" width="120" />
            <el-table-column label="统计指标" min-width="500">
              <template #default="scope"><div class="metric-pills"><span v-for="metric in scope.row.metrics" :key="metric.metric_type"><b>{{ metric.metric_type }}</b> {{ formatValue(metric.value) }} <small>组中位数 {{ metric.group_median ?? '--' }}</small></span></div></template>
            </el-table-column>
            <el-table-column label="可用性" min-width="220"><template #default="scope"><el-tag :type="availabilityTone(scope.row.availability.status)">{{ availabilityLabel(scope.row.availability) }}</el-tag></template></el-table-column>
          </el-table>
          <p class="version-line">Benchmark：{{ benchmarkData.benchmark_version }} · Lifecycle：{{ benchmarkData.lifecycle_rule_version }} · 分析截止：{{ formatDate(benchmarkData.analysis_as_of) }}</p>
        </template>
      </el-card>
    </section>
  </main>
</template>

<style scoped>
.analytics-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}
.page-header,.section-heading,.availability-row,.lifecycle-summary{display:flex;align-items:center;justify-content:space-between;gap:20px}.page-header{align-items:flex-start;margin-bottom:20px}.page-header h1,.section-heading h2{margin:0}.eyebrow,.section-index{margin:0 0 8px;color:var(--el-color-primary);font-size:12px;font-weight:700;letter-spacing:.12em}.subtitle,.availability-row,.version-line,.disclaimer{color:var(--el-text-color-secondary)}.analysis-section{margin-top:24px}.section-heading{margin-bottom:12px}.section-heading>div:first-child{flex:none}.query-form{display:flex;justify-content:flex-end}.availability-row{justify-content:flex-start;margin-bottom:18px}.detail-panel{padding:8px 38px 18px}.disclaimer{font-size:13px}.pagination{justify-content:flex-end;margin-top:18px}.lifecycle-card{min-height:180px}.lifecycle-summary{justify-content:flex-start}.stage{min-width:150px;color:var(--el-color-primary);font-size:40px;font-weight:700}.metric-pills{display:flex;flex-wrap:wrap;gap:8px}.metric-pills span{padding:8px 10px;border-radius:6px;background:var(--el-fill-color-light)}.metric-pills small{margin-left:8px;color:var(--el-text-color-secondary)}.version-line{margin:18px 0 0;font-size:13px}@media(max-width:900px){.page-header,.section-heading{align-items:stretch;flex-direction:column}.query-form{justify-content:flex-start}.benchmark-heading .query-form{display:grid;grid-template-columns:1fr}.analytics-page{padding:18px}}
</style>
