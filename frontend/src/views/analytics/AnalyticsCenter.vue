<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getDramaAnalysisSummary } from '../../api/analytics'
import { getDrama, getDramas } from '../../api/drama'
import type {
  AnalysisGranularity,
  DramaAnalysisSummary,
  InsightItem,
  InsightType,
} from '../../types/analytics'
import type { Drama } from '../../types/drama'
import { getApiErrorMessage } from '../../utils/api-error'

const route = useRoute()
const router = useRouter()
const dramaOptions = ref<Drama[]>([])
const selectedDramaId = ref<number | null>(null)
const selectedDrama = computed(() =>
  dramaOptions.value.find((item) => item.drama_id === selectedDramaId.value) ?? null,
)
const summary = ref<DramaAnalysisSummary | null>(null)
const loadingOptions = ref(false)
const loading = ref(false)
const errorMessage = ref('')

const numberFormatter = new Intl.NumberFormat('zh-CN')
const percentFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'percent', minimumFractionDigits: 0, maximumFractionDigits: 2,
})

const insightLabels: Record<InsightType, string> = {
  PERFORMANCE: '表现', GROWTH: '增长', POTENTIAL: '潜力', RISK: '风险',
  PLATFORM: '平台', TAG: '标签', DATA_QUALITY: '数据质量',
}

function formatCount(value: number | null): string {
  return value == null ? '暂无数据' : numberFormatter.format(value)
}

function formatRate(value: number | null): string {
  return value == null ? '暂无数据' : percentFormatter.format(value)
}

function formatScore(value: number | null | undefined): string {
  return value == null ? '暂无数据' : value.toFixed(2)
}

function formatDate(value: string | null): string {
  return value
    ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value))
    : '暂无数据'
}

function formatScope(values: number[]): string {
  return values.length ? values.join('、') : '全部'
}

function granularityLabel(value: AnalysisGranularity): string {
  return value === 'DRAMA_OVERALL' ? 'Drama Overall' : 'Drama Platform'
}

function insightTone(type: InsightType): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (type === 'RISK') return 'danger'
  if (type === 'DATA_QUALITY') return 'warning'
  if (type === 'POTENTIAL') return 'success'
  if (type === 'GROWTH') return 'primary'
  return 'info'
}

function evidenceText(insight: InsightItem): string {
  return JSON.stringify(insight.evidence, null, 2)
}

async function loadDramaOptions(query = ''): Promise<void> {
  loadingOptions.value = true
  try {
    const result = await getDramas({
      page: 1, page_size: 50, name_contains: query.trim() || undefined,
    })
    dramaOptions.value = result.items
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '短剧选项加载失败，请稍后重试。')
  } finally {
    loadingOptions.value = false
  }
}

async function ensureDramaOption(dramaId: number): Promise<void> {
  if (dramaOptions.value.some((item) => item.drama_id === dramaId)) return
  const drama = await getDrama(dramaId)
  dramaOptions.value = [drama, ...dramaOptions.value]
}

async function loadAnalysis(): Promise<void> {
  if (selectedDramaId.value === null) {
    errorMessage.value = '请先选择需要分析的短剧。'
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    summary.value = await getDramaAnalysisSummary(selectedDramaId.value)
    await router.replace({ query: { drama_id: String(selectedDramaId.value) } })
  } catch (error: unknown) {
    summary.value = null
    errorMessage.value = getApiErrorMessage(error, '分析结果加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadDramaOptions()
  const queryDramaId = Number(route.query.drama_id)
  if (Number.isInteger(queryDramaId) && queryDramaId > 0) {
    try {
      await ensureDramaOption(queryDramaId)
      selectedDramaId.value = queryDramaId
      await loadAnalysis()
    } catch (error: unknown) {
      errorMessage.value = getApiErrorMessage(error, '指定短剧加载失败，请重新选择。')
    }
  }
})
</script>

<template>
  <main class="analytics-page">
    <header class="page-header">
      <div><p class="eyebrow">Analytics Center</p><h1>分析中心</h1><p>展示确定性指标、模型结果与可追溯分析结论。</p></div>
      <div class="header-actions"><router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link><router-link to="/dramas"><el-button>短剧管理</el-button></router-link></div>
    </header>

    <el-card shadow="never" class="selector-card">
      <div class="selector-row">
        <el-select
          v-model="selectedDramaId"
          filterable remote reserve-keyword clearable
          :remote-method="loadDramaOptions"
          :loading="loadingOptions"
          placeholder="输入短剧名称搜索"
          class="drama-select"
          @clear="summary = null"
        >
          <el-option v-for="drama in dramaOptions" :key="drama.drama_id" :label="`${drama.drama_name}（${drama.drama_code}）`" :value="drama.drama_id" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadAnalysis">开始分析</el-button>
      </div>
      <p class="selector-note">分析结果由后端 Analytics Service 计算，前端不重新计算或修改模型输出。</p>
    </el-card>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" class="page-alert">
      <template #default><el-button v-if="selectedDramaId" text type="primary" @click="loadAnalysis">重新加载</el-button></template>
    </el-alert>

    <div v-loading="loading" class="result-area">
      <el-empty v-if="!summary && !loading" description="请选择短剧查看分析结果" />
      <template v-else-if="summary">
        <section>
          <h2>分析上下文</h2>
          <el-card shadow="never">
            <el-descriptions :column="3" border>
              <el-descriptions-item label="作品">{{ selectedDrama?.drama_name ?? summary.metrics.drama_code }}</el-descriptions-item>
              <el-descriptions-item label="As-of 时间">{{ formatDate(summary.context.analysis_as_of) }}</el-descriptions-item>
              <el-descriptions-item label="分析粒度">{{ granularityLabel(summary.context.granularity) }}</el-descriptions-item>
              <el-descriptions-item label="时间窗口">{{ summary.context.time_window }}</el-descriptions-item>
              <el-descriptions-item label="平台范围">{{ formatScope(summary.context.platform_scope) }}</el-descriptions-item>
              <el-descriptions-item label="标签范围">{{ formatScope(summary.context.tag_scope) }}</el-descriptions-item>
            </el-descriptions>
            <div class="version-list">
              <el-tag v-for="(version, key) in summary.context.model_versions" :key="key" effect="plain">{{ key }}：{{ version }}</el-tag>
            </div>
          </el-card>
        </section>

        <section>
          <h2>核心指标</h2>
          <div class="metric-grid">
            <el-card shadow="hover"><span>播放量</span><strong>{{ formatCount(summary.metrics.raw.play_count) }}</strong></el-card>
            <el-card shadow="hover"><span>点赞量</span><strong>{{ formatCount(summary.metrics.raw.like_count) }}</strong></el-card>
            <el-card shadow="hover"><span>评论量</span><strong>{{ formatCount(summary.metrics.raw.comment_count) }}</strong></el-card>
            <el-card shadow="hover"><span>收藏量</span><strong>{{ formatCount(summary.metrics.raw.favorite_count) }}</strong></el-card>
            <el-card shadow="hover"><span>分享量</span><strong>{{ formatCount(summary.metrics.raw.share_count) }}</strong></el-card>
            <el-card shadow="hover"><span>互动率</span><strong>{{ formatRate(summary.metrics.engagement.engagement_rate) }}</strong></el-card>
          </div>
        </section>

        <section class="model-grid">
          <el-card shadow="never">
            <template #header><strong>Heat 分析</strong></template>
            <div v-if="summary.heat" class="model-value"><strong>{{ formatScore(summary.heat.score) }}</strong><span>{{ selectedDrama?.drama_name ?? summary.metrics.drama_code }} · {{ granularityLabel(summary.metrics.granularity) }}</span><small>排名 {{ summary.heat.rank }} / {{ summary.heat.candidate_count }} · {{ summary.heat.model_version }}</small></div>
            <el-empty v-else description="暂无 Heat 数据" />
          </el-card>

          <el-card shadow="never">
            <template #header><strong>Growth 分析</strong></template>
            <p class="section-subject">{{ selectedDrama?.drama_name ?? summary.metrics.drama_code }}</p>
            <div class="growth-list"><div><span>Growth 24H</span><strong>{{ formatRate(summary.metrics.growth_24h) }}</strong></div><div><span>Growth 7D</span><strong>{{ formatRate(summary.metrics.growth_7d) }}</strong></div><div><span>Growth 30D</span><strong>{{ formatRate(summary.metrics.growth_30d) }}</strong></div></div>
          </el-card>

          <el-card shadow="never">
            <template #header><strong>Potential 分析</strong></template>
            <div v-if="summary.potential" class="model-value"><strong>{{ formatScore(summary.potential.score) }}</strong><span>候选状态：已进入候选集合</span><small>排名 {{ summary.potential.rank }} / {{ summary.potential.candidate_count }} · {{ summary.potential.model_version }}</small></div>
            <div v-else class="not-candidate"><strong>暂无数据</strong><span>候选状态：当前不满足后端候选条件</span></div>
            <el-alert class="potential-note" type="info" :closable="false" title="Potential 仅表示当前数据中的增长潜力信号，不构成预测、推荐或结果保证。" />
          </el-card>
        </section>

        <section>
          <h2>自动分析结论</h2>
          <el-empty v-if="summary.insights.length === 0" description="当前没有分析结论" />
          <div v-else class="insight-list">
            <el-card v-for="insight in summary.insights" :key="insight.rule_code" shadow="never">
              <div class="insight-heading"><el-tag :type="insightTone(insight.insight_type)">{{ insightLabels[insight.insight_type] }}</el-tag><code>{{ insight.rule_code }}</code></div>
              <p class="conclusion">{{ insight.conclusion }}</p>
              <el-collapse><el-collapse-item title="查看 Trigger 与 Evidence"><p><strong>Trigger：</strong>{{ insight.trigger }}</p><pre>{{ evidenceText(insight) }}</pre></el-collapse-item></el-collapse>
            </el-card>
          </div>
        </section>
      </template>
    </div>
  </main>
</template>

<style scoped>
.analytics-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}.page-header,.header-actions,.selector-row,.insight-heading{display:flex;align-items:center;justify-content:space-between;gap:14px}.page-header{align-items:flex-start;margin-bottom:20px}.page-header h1{margin:0 0 8px;font-size:32px}.page-header p,.selector-note{margin:0;color:var(--el-text-color-secondary)}.eyebrow{margin-bottom:8px!important;color:var(--el-color-primary)!important;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.selector-card,.page-alert{margin-bottom:20px}.selector-row{justify-content:flex-start}.drama-select{width:min(520px,100%)}.selector-note{margin-top:12px;font-size:13px}.result-area{min-height:220px}section{margin-top:24px}section h2{margin:0 0 12px;font-size:19px}.version-list{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.metric-grid span,.growth-list span,.model-value span,.not-candidate span{color:var(--el-text-color-secondary)}.metric-grid strong{display:block;margin-top:10px;font-size:25px}.model-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.model-value,.not-candidate{display:grid;gap:10px}.model-value>strong,.not-candidate>strong{font-size:36px}.model-value small{color:var(--el-text-color-secondary)}.section-subject{margin:0 0 16px;font-weight:600}.growth-list{display:grid;gap:16px}.growth-list>div{display:flex;justify-content:space-between;gap:12px}.potential-note{margin-top:18px}.insight-list{display:grid;gap:12px}.insight-heading{justify-content:flex-start}.insight-heading code{color:var(--el-text-color-secondary);font-size:12px}.conclusion{font-size:16px;line-height:1.7}pre{overflow:auto;padding:12px;border-radius:6px;background:var(--el-fill-color-light);font-size:12px;white-space:pre-wrap;word-break:break-word}
@media(max-width:900px){.model-grid,.metric-grid{grid-template-columns:1fr 1fr}}@media(max-width:620px){.analytics-page{padding:18px}.page-header,.selector-row{align-items:stretch;flex-direction:column}.metric-grid,.model-grid{grid-template-columns:1fr}.drama-select{width:100%}:deep(.el-descriptions__body .el-descriptions__table){display:block}}
</style>
