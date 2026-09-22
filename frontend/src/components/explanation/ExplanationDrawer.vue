<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getExplanations, getLineage } from '../../api/explanation'
import type {
  Explanation,
  ExplanationEntityType,
  ExplanationModuleType,
  LineageRecord,
  LineageTargetType,
} from '../../types/explanation'
import { getApiErrorMessage } from '../../utils/api-error'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    entityType: ExplanationEntityType
    entityId: number | null
    moduleType: ExplanationModuleType
  }>(),
  { entityId: null },
)

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const loading = ref(false)
const errorMessage = ref('')
const explanation = ref<Explanation | null>(null)
const lineage = ref<LineageRecord[]>([])
const empty = computed(() => !loading.value && !errorMessage.value && !explanation.value)

function close(): void {
  emit('update:modelValue', false)
}

function stringify(value: unknown): string {
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function formatDateTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(parsed)
}

async function load(): Promise<void> {
  if (props.entityId == null) return
  loading.value = true
  errorMessage.value = ''
  explanation.value = null
  lineage.value = []
  try {
    const result = await getExplanations(props.entityType, props.entityId, {
      module_type: props.moduleType,
      page: 1,
      page_size: 1,
    })
    explanation.value = result.items[0] ?? null
    if (explanation.value) {
      const lineageTarget: LineageTargetType = 'EXPLANATION'
      const lineageResult = await getLineage(lineageTarget, explanation.value.explanation_id, {
        page: 1,
        page_size: 100,
      })
      lineage.value = lineageResult.items
    }
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '解释信息加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.modelValue, props.entityId, props.entityType, props.moduleType] as const,
  ([visible]) => {
    if (visible) void load()
  },
)
</script>

<template>
  <el-drawer :model-value="modelValue" title="分析解释" size="460px" @close="close">
    <div v-loading="loading" class="explanation-panel">
      <el-alert v-if="errorMessage" type="error" show-icon :closable="false" :title="errorMessage">
        <template #default><el-button text type="primary" @click="load">重新加载</el-button></template>
      </el-alert>
      <el-empty v-else-if="empty" description="暂无解释信息" />
      <template v-else-if="explanation">
        <el-card shadow="never" class="summary-card">
          <template #header><strong>解释摘要</strong></template>
          <p class="summary">{{ explanation.summary }}</p>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="分析时间">{{ formatDateTime(explanation.analysis_as_of) }}</el-descriptions-item>
            <el-descriptions-item label="算法版本">{{ explanation.algorithm_version }}</el-descriptions-item>
            <el-descriptions-item label="规则集版本">{{ explanation.rule_set_version }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-card shadow="never" class="detail-card">
          <template #header><strong>解释依据</strong></template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="原因">{{ explanation.detail.reason }}</el-descriptions-item>
            <el-descriptions-item label="规则"><div v-for="(item, index) in explanation.detail.rules" :key="index" class="evidence-item">{{ stringify(item) }}</div></el-descriptions-item>
            <el-descriptions-item label="证据"><div v-for="(item, index) in explanation.detail.evidence" :key="index" class="evidence-item">{{ stringify(item) }}</div></el-descriptions-item>
            <el-descriptions-item label="版本">{{ stringify(explanation.detail.versions) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-card shadow="never" class="lineage-card">
          <template #header><strong>数据来源</strong></template>
          <el-empty v-if="lineage.length === 0" description="暂无来源记录" />
          <el-timeline v-else>
            <el-timeline-item v-for="item in lineage" :key="item.lineage_id" :timestamp="formatDateTime(item.analysis_as_of)">
              <strong>{{ item.relationship_type }}</strong>
              <p>{{ item.source_type }} #{{ item.source_id }}</p>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </template>
    </div>
  </el-drawer>
</template>

<style scoped>
.explanation-panel { min-height: 180px; }
.summary-card, .detail-card, .lineage-card { margin-bottom: 16px; }
.summary { margin: 0 0 16px; color: var(--el-text-color-primary); line-height: 1.8; }
.evidence-item { white-space: pre-wrap; line-height: 1.6; }
.lineage-card p { margin: 4px 0 0; color: var(--el-text-color-secondary); }
</style>
