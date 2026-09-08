<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { confirmImportJob, getImportJob } from '../../api/import'
import { useUserStore } from '../../stores/user'
import type { ImportJob, ImportStatus } from '../../types/import'
import { getApiErrorMessage } from '../../utils/api-error'
import { rememberImportJob } from '../../utils/import-history'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const jobId = computed(() => Number(route.params.id))
const job = ref<ImportJob | null>(null)
const loading = ref(false)
const confirming = ref(false)
const errorMessage = ref('')

const statusMeta: Record<ImportStatus, { label: string; tone: 'info' | 'warning' | 'success' | 'danger' | 'primary' }> = {
  PENDING_VALIDATION: { label: '待校验', tone: 'info' }, VALIDATION_FAILED: { label: '校验失败', tone: 'danger' },
  READY: { label: '待确认', tone: 'warning' }, IMPORTING: { label: '导入中', tone: 'primary' },
  COMPLETED: { label: '已完成', tone: 'success' }, COMPLETED_WITH_ERRORS: { label: '完成（含错误）', tone: 'warning' },
  FAILED: { label: '失败', tone: 'danger' },
}

function formatDate(value: string | null): string {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value)) : '--'
}

async function loadJob(): Promise<void> {
  if (!isAdmin.value) return
  if (!Number.isInteger(jobId.value) || jobId.value < 1) { errorMessage.value = '无效的导入任务编号。'; return }
  loading.value = true
  errorMessage.value = ''
  try {
    job.value = await getImportJob(jobId.value)
    rememberImportJob(job.value)
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '导入任务加载失败，请稍后重试。')
  } finally { loading.value = false }
}

async function confirmJob(): Promise<void> {
  if (!job.value || job.value.status !== 'READY' || !isAdmin.value) return
  try {
    await ElMessageBox.confirm(
      `确认导入任务 #${job.value.import_job_id} 的 ${job.value.valid_rows} 条有效记录吗？正式写入将使用单一事务。`,
      '确认正式导入',
      { type: 'warning', confirmButtonText: '确认导入', cancelButtonText: '取消' },
    )
    confirming.value = true
    job.value = await confirmImportJob(job.value.import_job_id)
    rememberImportJob(job.value)
    ElMessage.success('导入任务已执行')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '确认导入失败，请稍后重试。'))
  } finally { confirming.value = false }
}

function openErrors(): void { if (job.value) void router.push(`/imports/${job.value.import_job_id}/errors`) }
onMounted(() => void loadJob())
</script>

<template>
  <main class="import-page">
    <header class="page-header"><div><p class="eyebrow">Import Job</p><h1>导入任务 #{{ route.params.id }}</h1><p>查看校验结果并确认正式写入。</p></div><div class="actions"><router-link to="/imports"><el-button>返回导入</el-button></router-link><el-button v-if="isAdmin" :loading="loading" @click="loadJob">刷新</el-button></div></header>
    <el-alert v-if="!isAdmin" type="warning" show-icon :closable="false" title="当前后端导入任务接口仅允许管理员访问" />
    <el-alert v-else-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false"><template #default><el-button text type="primary" @click="loadJob">重新加载</el-button></template></el-alert>
    <el-card v-else v-loading="loading" shadow="never">
      <el-empty v-if="!job && !loading" description="未找到导入任务" />
      <template v-else-if="job">
        <div class="job-heading"><div><h2>{{ job.original_filename }}</h2><p>{{ job.import_type === 'MASTER_DATA' ? '基础资料' : '运营快照' }} · {{ job.file_format }}</p></div><el-tag :type="statusMeta[job.status].tone" size="large">{{ statusMeta[job.status].label }}</el-tag></div>
        <el-descriptions :column="2" border class="descriptions">
          <el-descriptions-item label="任务编号">{{ job.import_job_id }}</el-descriptions-item><el-descriptions-item label="创建时间">{{ formatDate(job.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="总行数">{{ job.total_rows }}</el-descriptions-item><el-descriptions-item label="有效行数">{{ job.valid_rows }}</el-descriptions-item>
          <el-descriptions-item label="错误行数">{{ job.error_rows }}</el-descriptions-item><el-descriptions-item label="已导入行数">{{ job.imported_rows }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatDate(job.started_at) }}</el-descriptions-item><el-descriptions-item label="完成时间">{{ formatDate(job.finished_at) }}</el-descriptions-item>
        </el-descriptions>
        <div class="footer-actions"><el-button v-if="job.error_rows > 0" @click="openErrors">查看校验错误</el-button><el-button v-if="isAdmin && job.status === 'READY'" type="primary" :loading="confirming" @click="confirmJob">确认正式导入</el-button></div>
      </template>
    </el-card>
  </main>
</template>

<style scoped>
.import-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}.page-header,.job-heading,.footer-actions,.actions{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-header{align-items:flex-start;margin-bottom:20px}.page-header h1,.job-heading h2{margin:0 0 8px}.page-header p,.job-heading p{margin:0;color:var(--el-text-color-secondary)}.eyebrow{margin-bottom:8px!important;color:var(--el-color-primary)!important;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.descriptions{margin-top:24px}.footer-actions{justify-content:flex-end;margin-top:24px}
@media(max-width:720px){.import-page{padding:18px}.page-header,.job-heading{flex-direction:column;align-items:flex-start}:deep(.el-descriptions__body .el-descriptions__table){display:block}}
</style>
