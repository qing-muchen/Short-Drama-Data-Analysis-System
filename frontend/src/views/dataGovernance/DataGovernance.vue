<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  getCompletenessQuality,
  getConsistencyQuality,
  getDataGovernanceOverview,
  getFreshnessQuality,
} from '../../api/dataGovernance'
import type {
  AvailabilityReason,
  AvailabilityStatus,
  CompletenessResult,
  ConsistencyResult,
  DataGovernanceResponse,
  DataQualityAvailability,
  EvidenceItem,
  FreshnessResult,
  QualityStatus,
} from '../../types/dataGovernance'
import { getApiErrorMessage } from '../../utils/api-error'

type TagTone = 'success' | 'warning' | 'info' | 'danger'

const overview = ref<DataGovernanceResponse | null>(null)
const freshness = ref<FreshnessResult | null>(null)
const completeness = ref<CompletenessResult | null>(null)
const consistency = ref<ConsistencyResult | null>(null)

const overviewLoading = ref(false)
const freshnessLoading = ref(false)
const completenessLoading = ref(false)
const consistencyLoading = ref(false)

const overviewError = ref('')
const freshnessError = ref('')
const completenessError = ref('')
const consistencyError = ref('')

const evidenceDrawerVisible = ref(false)
const evidenceDrawerTitle = ref('Evidence')
const selectedEvidence = ref<EvidenceItem[]>([])

const anyLoading = computed(
  () =>
    overviewLoading.value ||
    freshnessLoading.value ||
    completenessLoading.value ||
    consistencyLoading.value,
)

const availabilityLabels: Record<AvailabilityStatus, string> = {
  AVAILABLE: '数据可用',
  PARTIAL: '部分数据不可用',
  INSUFFICIENT: '历史数据不足',
  NOT_AVAILABLE: '暂不可用',
}

const reasonLabels: Record<AvailabilityReason, string> = {
  NO_DATA: '无可见数据',
  MISSING_SOURCE: '来源缺失',
  INSUFFICIENT_HISTORY: '历史数据不足',
  MISSING_REQUIRED_FIELD: '必要字段缺失',
  INCOMPLETE_TIME_SERIES: '时间序列不完整',
  UNRESOLVED_RELATION: '关联无法解析',
  REVISION_NOT_VISIBLE: '修订版本不可见',
  UNSUPPORTED_SCOPE: '检查范围不支持',
  EVALUATION_FAILED: '评估执行失败',
  NOT_AVAILABLE: '暂不可用',
}

const qualityLabels: Record<QualityStatus, string> = {
  HEALTHY: '健康',
  WARNING: '警告',
  FAILED: '失败',
  NOT_AVAILABLE: '不可评估',
}

function availabilityTone(status: AvailabilityStatus): TagTone {
  if (status === 'AVAILABLE') return 'success'
  if (status === 'PARTIAL') return 'warning'
  if (status === 'INSUFFICIENT') return 'info'
  return 'danger'
}

function qualityTone(status: QualityStatus): TagTone {
  if (status === 'HEALTHY') return 'success'
  if (status === 'WARNING') return 'warning'
  if (status === 'FAILED') return 'danger'
  return 'info'
}

function availabilityText(value: DataQualityAvailability): string {
  const reasons = value.reasons.map((reason) => reasonLabels[reason]).join('、')
  return reasons
    ? `${availabilityLabels[value.status]}：${reasons}`
    : availabilityLabels[value.status]
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

function formatMetadata(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2)
}

function showEvidence(title: string, evidence: EvidenceItem[]): void {
  evidenceDrawerTitle.value = title
  selectedEvidence.value = evidence
  evidenceDrawerVisible.value = true
}

async function loadOverview(): Promise<void> {
  overviewLoading.value = true
  overviewError.value = ''
  try {
    overview.value = await getDataGovernanceOverview()
  } catch (error: unknown) {
    overviewError.value = getApiErrorMessage(error, '数据健康概览加载失败。')
  } finally {
    overviewLoading.value = false
  }
}

async function loadFreshness(page = 1): Promise<void> {
  freshnessLoading.value = true
  freshnessError.value = ''
  try {
    freshness.value = await getFreshnessQuality({ page, page_size: 20 })
  } catch (error: unknown) {
    freshnessError.value = getApiErrorMessage(error, 'Freshness 状态加载失败。')
  } finally {
    freshnessLoading.value = false
  }
}

async function loadCompleteness(page = 1): Promise<void> {
  completenessLoading.value = true
  completenessError.value = ''
  try {
    completeness.value = await getCompletenessQuality({ page, page_size: 20 })
  } catch (error: unknown) {
    completenessError.value = getApiErrorMessage(error, 'Completeness 状态加载失败。')
  } finally {
    completenessLoading.value = false
  }
}

async function loadConsistency(page = 1): Promise<void> {
  consistencyLoading.value = true
  consistencyError.value = ''
  try {
    consistency.value = await getConsistencyQuality({ page, page_size: 20 })
  } catch (error: unknown) {
    consistencyError.value = getApiErrorMessage(error, 'Consistency 状态加载失败。')
  } finally {
    consistencyLoading.value = false
  }
}

async function loadAll(): Promise<void> {
  await Promise.allSettled([
    loadOverview(),
    loadFreshness(),
    loadCompleteness(),
    loadConsistency(),
  ])
}

onMounted(() => void loadAll())
</script>

<template>
  <main class="governance-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">DATA GOVERNANCE</p>
        <h1>数据治理与质量监控中心</h1>
        <p class="subtitle">只读展示数据新鲜度、完整性、一致性及其检查依据。</p>
      </div>
      <div class="header-actions">
        <router-link to="/dashboard"><el-button>返回数据驾驶舱</el-button></router-link>
        <el-button type="primary" plain :loading="anyLoading" @click="loadAll">刷新</el-button>
      </div>
    </header>

    <section class="overview-section">
      <el-alert
        v-if="overviewError"
        type="error"
        show-icon
        :closable="false"
        :title="overviewError"
      >
        <template #default><el-button text type="primary" @click="loadOverview">重试</el-button></template>
      </el-alert>
      <el-card v-loading="overviewLoading" shadow="never">
        <template #header><strong>数据健康概览</strong></template>
        <el-empty
          v-if="!overviewLoading && !overview && !overviewError"
          description="暂无治理概览数据"
        />
        <div v-else-if="overview" class="overview-grid">
          <div>
            <span class="field-label">整体可用性</span>
            <el-tag :type="availabilityTone(overview.availability.status)">
              {{ availabilityText(overview.availability) }}
            </el-tag>
          </div>
          <div><span class="field-label">检查范围</span><strong>{{ overview.scope }}</strong></div>
          <div>
            <span class="field-label">分析截止时间</span>
            <strong>{{ formatDate(overview.analysis_as_of) }}</strong>
          </div>
          <div><span class="field-label">规则集版本</span><strong>{{ overview.rule_set_version }}</strong></div>
        </div>
      </el-card>
    </section>

    <section class="quality-grid">
      <el-card v-loading="freshnessLoading" shadow="never" class="quality-card">
        <template #header><div class="card-header"><strong>Freshness</strong><el-button text @click="loadFreshness(freshness?.page ?? 1)">重试</el-button></div></template>
        <el-alert v-if="freshnessError" type="error" :closable="false" show-icon :title="freshnessError" />
        <el-empty v-else-if="!freshnessLoading && !freshness" description="暂无 Freshness 数据" />
        <div v-else-if="freshness" class="result-body">
          <div class="tag-row">
            <el-tag :type="qualityTone(freshness.status)">{{ qualityLabels[freshness.status] }}</el-tag>
            <el-tag :type="availabilityTone(freshness.availability.status)" effect="plain">{{ availabilityText(freshness.availability) }}</el-tag>
          </div>
          <dl>
            <div><dt>延迟秒数</dt><dd>{{ freshness.delay_seconds ?? '--' }}</dd></div>
            <div><dt>规则版本</dt><dd>{{ freshness.rule_version }}</dd></div>
            <div><dt>分析时间</dt><dd>{{ formatDate(freshness.analysis_as_of) }}</dd></div>
          </dl>
          <el-button @click="showEvidence('Freshness Evidence', freshness.evidence)">查看 Evidence（{{ freshness.total }}）</el-button>
        </div>
      </el-card>

      <el-card v-loading="completenessLoading" shadow="never" class="quality-card">
        <template #header><div class="card-header"><strong>Completeness</strong><el-button text @click="loadCompleteness(completeness?.page ?? 1)">重试</el-button></div></template>
        <el-alert v-if="completenessError" type="error" :closable="false" show-icon :title="completenessError" />
        <el-empty v-else-if="!completenessLoading && !completeness" description="暂无 Completeness 数据" />
        <div v-else-if="completeness" class="result-body">
          <div class="tag-row">
            <el-tag :type="qualityTone(completeness.status)">{{ qualityLabels[completeness.status] }}</el-tag>
            <el-tag :type="availabilityTone(completeness.availability.status)" effect="plain">{{ availabilityText(completeness.availability) }}</el-tag>
          </div>
          <dl>
            <div><dt>覆盖率</dt><dd>{{ completeness.coverage_ratio ?? '--' }}</dd></div>
            <div><dt>规则版本</dt><dd>{{ completeness.rule_version }}</dd></div>
            <div><dt>分析时间</dt><dd>{{ formatDate(completeness.analysis_as_of) }}</dd></div>
          </dl>
          <div class="missing-items">
            <span class="field-label">缺失项</span>
            <el-tag v-for="item in completeness.missing_items" :key="item" type="warning" effect="plain">{{ item }}</el-tag>
            <span v-if="completeness.missing_items.length === 0">无</span>
          </div>
          <el-button @click="showEvidence('Completeness Evidence', completeness.evidence)">查看 Evidence（{{ completeness.total }}）</el-button>
        </div>
      </el-card>

      <el-card v-loading="consistencyLoading" shadow="never" class="quality-card">
        <template #header><div class="card-header"><strong>Consistency</strong><el-button text @click="loadConsistency(consistency?.page ?? 1)">重试</el-button></div></template>
        <el-alert v-if="consistencyError" type="error" :closable="false" show-icon :title="consistencyError" />
        <el-empty v-else-if="!consistencyLoading && !consistency" description="暂无 Consistency 数据" />
        <div v-else-if="consistency" class="result-body">
          <div class="tag-row">
            <el-tag :type="qualityTone(consistency.status)">{{ qualityLabels[consistency.status] }}</el-tag>
            <el-tag :type="availabilityTone(consistency.availability.status)" effect="plain">{{ availabilityText(consistency.availability) }}</el-tag>
          </div>
          <dl>
            <div><dt>问题数量</dt><dd>{{ consistency.issue_count }}</dd></div>
            <div><dt>规则版本</dt><dd>{{ consistency.rule_version }}</dd></div>
            <div><dt>分析时间</dt><dd>{{ formatDate(consistency.analysis_as_of) }}</dd></div>
          </dl>
          <el-button @click="showEvidence('Consistency Evidence', consistency.evidence)">查看 Evidence（{{ consistency.total }}）</el-button>
        </div>
      </el-card>
    </section>

    <el-drawer v-model="evidenceDrawerVisible" :title="evidenceDrawerTitle" size="min(720px, 92vw)">
      <el-empty v-if="selectedEvidence.length === 0" description="当前结果没有 Evidence" />
      <div v-else class="evidence-list">
        <article v-for="(item, index) in selectedEvidence" :key="`${item.evidence_type}-${index}`" class="evidence-item">
          <div class="evidence-heading">
            <el-tag effect="plain">{{ item.evidence_type }}</el-tag>
            <span>{{ item.source }}</span>
          </div>
          <p>{{ item.message }}</p>
          <pre>{{ formatMetadata(item.metadata) }}</pre>
        </article>
      </div>
    </el-drawer>
  </main>
</template>

<style scoped>
.governance-page { min-height: 100vh; padding: 28px; color: var(--el-text-color-primary); background: var(--el-bg-color-page); }
.page-header, .header-actions, .card-header, .tag-row, .evidence-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.page-header { align-items: flex-start; margin-bottom: 22px; }
.header-actions, .tag-row { justify-content: flex-start; flex-wrap: wrap; }
.eyebrow, .subtitle, .field-label, dt, .evidence-heading span { color: var(--el-text-color-secondary); }
.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-size: 12px; font-weight: 700; letter-spacing: .12em; }
h1 { margin: 0 0 8px; }
.subtitle { margin: 0; }
.overview-section { margin-bottom: 20px; }
.overview-section > .el-alert { margin-bottom: 12px; }
.overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; }
.overview-grid > div, dl > div { display: grid; gap: 8px; }
.quality-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
.quality-card { min-height: 360px; }
.result-body { display: grid; gap: 18px; }
dl { display: grid; gap: 13px; margin: 0; }
dl > div { grid-template-columns: 100px minmax(0, 1fr); }
dt, dd { margin: 0; }
.missing-items { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.evidence-list { display: grid; gap: 16px; }
.evidence-item { padding: 16px; border: 1px solid var(--el-border-color); border-radius: 8px; }
.evidence-item p { line-height: 1.6; }
pre { overflow: auto; margin: 0; padding: 12px; border-radius: 6px; background: var(--el-fill-color-light); white-space: pre-wrap; word-break: break-word; }
@media (max-width: 1100px) { .overview-grid, .quality-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) { .governance-page { padding: 18px; } .page-header { align-items: stretch; flex-direction: column; } .overview-grid, .quality-grid { grid-template-columns: 1fr; } }
</style>
