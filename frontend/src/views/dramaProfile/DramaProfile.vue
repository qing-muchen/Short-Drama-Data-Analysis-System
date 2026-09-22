<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getDramaProfile } from '../../api/dramaProfile'
import type { AvailabilityReason, DramaProfileResponse, ModuleAvailability } from '../../types/dramaProfile'
import { getApiErrorMessage } from '../../utils/api-error'

const route = useRoute()
const router = useRouter()
const profile = ref<DramaProfileResponse | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const dramaId = computed(() => Number(route.params.id))

const reasonLabels: Record<AvailabilityReason, string> = {
  NOT_CALCULATED: '尚未计算',
  INSUFFICIENT_HISTORY: '历史数据不足',
  NO_ANOMALY: '暂无异常',
  NOT_DETECTED: '尚未检测',
  NOT_AVAILABLE: '暂不可用',
}

function availabilityText(status: ModuleAvailability | undefined): string {
  if (!status) return '暂无状态'
  return status.available ? '有数据' : reasonLabels[status.reason ?? 'NOT_AVAILABLE']
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

async function load(): Promise<void> {
  if (!Number.isInteger(dramaId.value) || dramaId.value <= 0) {
    errorMessage.value = '短剧 ID 无效。'
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    profile.value = await getDramaProfile(dramaId.value)
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '全景画像加载失败，请稍后重试。')
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function go(path: string): void {
  void router.push(path)
}

onMounted(() => { void load() })
</script>

<template>
  <main class="profile-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">DRAMA 360° PROFILE</p>
        <h1>短剧全景画像</h1>
        <p class="subtitle">以短剧为中心汇总已有分析结果与运营状态。</p>
      </div>
      <el-button @click="go('/dramas')">返回短剧列表</el-button>
    </header>

    <el-alert v-if="errorMessage" type="error" show-icon :closable="false" :title="errorMessage">
      <template #default><el-button text type="primary" @click="load">重新加载</el-button></template>
    </el-alert>
    <el-card v-loading="loading" shadow="never" class="profile-shell">
      <el-empty v-if="!loading && !profile && !errorMessage" description="暂无画像数据" />
      <template v-else-if="profile">
        <section class="drama-header">
          <div>
            <p class="eyebrow">DRAMA</p>
            <h2>{{ profile.drama.title }}</h2>
            <p>Drama ID：{{ profile.drama.drama_id }} · 平台：{{ profile.drama.platform || '--' }}</p>
          </div>
          <div class="tags"><el-tag v-for="tag in profile.drama.tags" :key="tag" effect="plain">{{ tag }}</el-tag></div>
        </section>

        <section class="card-grid">
          <el-card shadow="hover" class="module-card">
            <template #header><div class="card-heading"><strong>综合评分</strong><el-tag :type="profile.availability.score?.available ? 'success' : 'info'">{{ availabilityText(profile.availability.score) }}</el-tag></div></template>
            <template v-if="profile.performance">
              <div class="headline">{{ profile.performance.score_level || '--' }}</div>
              <p>算法：{{ profile.performance.algorithm_version || '--' }}</p><p>分析时间：{{ formatDate(profile.performance.analysis_as_of) }}</p>
              <div class="dimension-list"><span v-for="(value, key) in profile.performance.dimensions" :key="key">{{ key }} <b>{{ value }}</b></span></div>
            </template><el-empty v-else :description="availabilityText(profile.availability.score)" />
            <el-button link type="primary" @click="go(`/scores?drama_id=${profile.drama.drama_id}`)">查看评分详情</el-button>
          </el-card>

          <el-card shadow="hover" class="module-card">
            <template #header><div class="card-heading"><strong>数据质量</strong><el-tag :type="profile.availability.quality?.available ? 'success' : 'info'">{{ availabilityText(profile.availability.quality) }}</el-tag></div></template>
            <template v-if="profile.quality"><div class="headline">{{ profile.quality.quality_level || '--' }}</div><p>状态：{{ profile.quality.quality_status || '--' }}</p><p>{{ profile.quality.risk_message || '暂无风险提示' }}</p></template>
            <el-empty v-else :description="availabilityText(profile.availability.quality)" />
          </el-card>

          <el-card shadow="hover" class="module-card">
            <template #header><div class="card-heading"><strong>趋势预测</strong><el-tag :type="profile.availability.prediction?.available ? 'success' : 'info'">{{ availabilityText(profile.availability.prediction) }}</el-tag></div></template>
            <template v-if="profile.trend"><div class="headline">{{ profile.trend.trend_direction || '--' }}</div><p>状态：{{ profile.trend.prediction_status || '--' }}</p><p>算法：{{ profile.trend.algorithm_version || '--' }}</p></template>
            <el-empty v-else :description="availabilityText(profile.availability.prediction)" />
            <el-button link type="primary" @click="go(`/predictions?drama_id=${profile.drama.drama_id}`)">查看预测详情</el-button>
          </el-card>

          <el-card shadow="hover" class="module-card">
            <template #header><div class="card-heading"><strong>异常风险</strong><el-tag :type="profile.availability.anomaly?.available ? 'warning' : 'info'">{{ availabilityText(profile.availability.anomaly) }}</el-tag></div></template>
            <template v-if="profile.risk"><div class="headline">{{ profile.risk.active_count }}</div><p>当前活动异常</p><p>最高等级：{{ profile.risk.highest_severity || '--' }}</p><p>最近分析：{{ formatDate(profile.risk.analysis_as_of) }}</p></template>
            <el-empty v-else :description="availabilityText(profile.availability.anomaly)" />
            <el-button link type="primary" @click="go(`/anomalies?drama_id=${profile.drama.drama_id}`)">查看异常详情</el-button>
          </el-card>

          <el-card shadow="hover" class="module-card">
            <template #header><div class="card-heading"><strong>运营行动</strong><el-tag type="success">{{ availabilityText(profile.availability.action) }}</el-tag></div></template>
            <template v-if="profile.operations"><div class="action-counts"><span>OPEN <b>{{ profile.operations.open_count }}</b></span><span>处理中 <b>{{ profile.operations.in_progress_count }}</b></span></div><p v-if="profile.operations.recent_actions.length">最近：{{ profile.operations.recent_actions[0]?.title || '--' }}</p><p v-else>暂无运营行动</p></template>
            <el-empty v-else description="暂无运营行动" />
            <el-button link type="primary" @click="go('/operation-actions')">查看行动中心</el-button>
          </el-card>

          <el-card shadow="hover" class="module-card">
            <template #header><div class="card-heading"><strong>分析解释</strong><el-tag :type="profile.availability.explanation?.available ? 'success' : 'info'">{{ availabilityText(profile.availability.explanation) }}</el-tag></div></template>
            <template v-if="profile.explanations?.latest_explanation"><p class="explanation-summary">{{ String(profile.explanations.latest_explanation.summary || '--') }}</p><p>血缘：{{ profile.explanations.lineage_available ? '可查看' : '暂无' }}</p></template>
            <el-empty v-else :description="availabilityText(profile.availability.explanation)" />
          </el-card>
        </section>
      </template>
    </el-card>
  </main>
</template>

<style scoped>
.profile-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}
.page-header,.card-heading,.drama-header{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-header{align-items:flex-start;margin-bottom:20px}.page-header h1{margin:0 0 8px;font-size:clamp(28px,3vw,38px)}
.eyebrow{margin:0 0 8px;color:var(--el-color-primary);font-size:12px;font-weight:700;letter-spacing:.12em}.subtitle,.drama-header p{color:var(--el-text-color-secondary)}.profile-shell{min-height:500px}.drama-header{align-items:flex-start;padding-bottom:22px;border-bottom:1px solid var(--el-border-color-lighter)}.drama-header h2{margin:0 0 8px;font-size:28px}.tags{display:flex;flex-wrap:wrap;gap:8px}.card-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:22px}.module-card{min-height:250px}.headline{margin:14px 0;color:var(--el-color-primary);font-size:42px;font-weight:700}.module-card p{color:var(--el-text-color-secondary)}.dimension-list,.action-counts{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.dimension-list span,.action-counts span{padding:8px 10px;background:var(--el-fill-color-light);border-radius:6px;color:var(--el-text-color-secondary)}.dimension-list b,.action-counts b{color:var(--el-text-color-primary);margin-left:4px}.explanation-summary{line-height:1.8;color:var(--el-text-color-primary)!important}.module-card :deep(.el-card__header){padding-bottom:12px}@media(max-width:1000px){.card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:680px){.card-grid{grid-template-columns:1fr}.drama-header{flex-direction:column}}
</style>
