<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type UploadFile, type UploadInstance, type UploadProps } from 'element-plus'

import {
  confirmImportBatch,
  createImportBatch,
  getImportBatch,
  uploadImportBatchFiles,
  validateImportBatch,
} from '../../api/batch-import'
import { useUserStore } from '../../stores/user'
import type { BatchFileType, BatchImportStatus, ImportBatch } from '../../types/batch-import'
import { getApiErrorMessage } from '../../utils/api-error'

const MAX_FILE_SIZE = 20 * 1024 * 1024
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const batchId = computed(() => Number(route.params.id))
const batchCode = ref('')
const batch = ref<ImportBatch | null>(null)
const selectedFiles = ref<File[]>([])
const uploadRef = ref<UploadInstance>()
const loading = ref(false)
const creating = ref(false)
const uploading = ref(false)
const validating = ref(false)
const confirming = ref(false)
const errorMessage = ref('')

const statusLabels: Record<BatchImportStatus, string> = {
  CREATED: '已创建', UPLOADING: '待继续/待校验', VALIDATING: '校验中', READY: '待确认',
  IMPORTING: '导入中', COMPLETED: '已完成', VALIDATION_FAILED: '校验失败', IMPORT_FAILED: '导入失败',
}
const fileTypeLabels: Record<BatchFileType, string> = {
  MASTER_DATA: '主数据', DRAMA_TAGS: '短剧标签关系', DRAMA_PLATFORMS: '短剧平台关系', SNAPSHOT: '运营快照',
}
const phaseLabels: Record<BatchFileType, string> = {
  MASTER_DATA: 'Phase 1', DRAMA_TAGS: 'Phase 2', DRAMA_PLATFORMS: 'Phase 2', SNAPSHOT: 'Phase 3',
}
const activeStep = computed(() => {
  const status = batch.value?.status
  if (!status || status === 'CREATED') return 1
  if (status === 'UPLOADING') return 2
  if (status === 'VALIDATING' || status === 'VALIDATION_FAILED') return 3
  if (status === 'READY') return 4
  return 5
})
const terminalFailure = computed(() => ['VALIDATION_FAILED', 'IMPORT_FAILED'].includes(batch.value?.status ?? ''))

function validateSelectedFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith('.csv')) return 'Batch Import V1 仅支持 CSV 文件。'
  if (file.size > MAX_FILE_SIZE) return `${file.name} 超过 20 MiB。`
  return null
}

const handleChange: UploadProps['onChange'] = (uploadFile: UploadFile, uploadFiles) => {
  errorMessage.value = ''
  if (!uploadFile.raw) return
  const message = validateSelectedFile(uploadFile.raw)
  if (message) {
    errorMessage.value = message
    selectedFiles.value = uploadFiles.flatMap((item) =>
      item.uid !== uploadFile.uid && item.raw ? [item.raw] : [],
    )
    uploadRef.value?.handleRemove(uploadFile)
    return
  }
  selectedFiles.value = uploadFiles.flatMap((item) => item.raw ? [item.raw] : [])
}
const handleRemove: UploadProps['onRemove'] = (_file, uploadFiles) => {
  selectedFiles.value = uploadFiles.flatMap((item) => item.raw ? [item.raw] : [])
}

async function createBatch(): Promise<void> {
  if (!isAdmin.value) return
  creating.value = true
  errorMessage.value = ''
  try {
    batch.value = await createImportBatch(batchCode.value || undefined)
    await router.replace(`/imports/batches/${batch.value.import_batch_id}`)
    ElMessage.success('批次已创建，请上传数据文件')
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '创建批次失败。')
  } finally { creating.value = false }
}

async function uploadFiles(): Promise<void> {
  if (!batch.value || selectedFiles.value.length === 0) return
  uploading.value = true
  errorMessage.value = ''
  try {
    batch.value = await uploadImportBatchFiles(batch.value.import_batch_id, selectedFiles.value)
    selectedFiles.value = []
    uploadRef.value?.clearFiles()
    ElMessage.success('文件上传成功，系统已自动识别文件类型')
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '批量文件上传失败。')
  } finally { uploading.value = false }
}

async function runValidation(): Promise<void> {
  if (!batch.value || batch.value.status !== 'UPLOADING') return
  validating.value = true
  errorMessage.value = ''
  try {
    batch.value = await validateImportBatch(batch.value.import_batch_id)
    if (batch.value.status === 'READY') ElMessage.success('全部文件验证通过，可以确认导入')
    else ElMessage.warning('批次存在校验错误，请查看对应文件')
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '批次校验失败。')
    await loadBatch()
  } finally { validating.value = false }
}

async function confirmBatch(): Promise<void> {
  if (!batch.value || batch.value.status !== 'READY') return
  try {
    await ElMessageBox.confirm(
      `确认按依赖顺序导入 ${batch.value.valid_rows} 条数据吗？任意阶段失败将回滚整个批次。`,
      '确认批次导入',
      { type: 'warning', confirmButtonText: '确认导入', cancelButtonText: '取消' },
    )
    confirming.value = true
    batch.value = await confirmImportBatch(batch.value.import_batch_id)
    ElMessage.success('批次已完整导入')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    errorMessage.value = getApiErrorMessage(error, '批次导入失败，正式数据已回滚。')
    await loadBatch()
  } finally { confirming.value = false }
}

async function loadBatch(): Promise<void> {
  if (!Number.isInteger(batchId.value) || batchId.value < 1 || !isAdmin.value) return
  loading.value = true
  errorMessage.value = ''
  try { batch.value = await getImportBatch(batchId.value) }
  catch (error: unknown) { errorMessage.value = getApiErrorMessage(error, '批次加载失败。') }
  finally { loading.value = false }
}

function openErrors(jobId: number): void { void router.push(`/imports/${jobId}/errors`) }
onMounted(() => void loadBatch())
</script>

<template>
  <main class="batch-page">
    <header class="page-header">
      <div><p class="eyebrow">Batch Import V1</p><h1>批量数据导入</h1><p>主数据 → 标签/平台关系 → 运营快照，确认时使用同一事务。</p></div>
      <div class="actions"><router-link to="/imports"><el-button>单文件导入</el-button></router-link><el-button v-if="batch" :loading="loading" @click="loadBatch">刷新</el-button></div>
    </header>

    <el-alert v-if="!isAdmin" type="warning" show-icon :closable="false" title="仅管理员可以执行批量导入" />
    <template v-else>
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" class="section" />
      <el-steps :active="activeStep" finish-status="success" align-center class="section">
        <el-step title="创建批次" /><el-step title="上传文件" /><el-step title="依赖校验" /><el-step title="确认" /><el-step title="完成" />
      </el-steps>

      <el-card v-if="!batch" shadow="never">
        <template #header><strong>Step 1 · 创建批次</strong></template>
        <el-form label-width="100px" @submit.prevent="createBatch">
          <el-form-item label="批次编码"><el-input v-model="batchCode" maxlength="64" placeholder="留空则由系统自动生成" /></el-form-item>
          <el-form-item><el-button type="primary" :loading="creating" @click="createBatch">创建批次</el-button></el-form-item>
        </el-form>
      </el-card>

      <template v-else>
        <el-card shadow="never" class="section">
          <div class="batch-heading"><div><h2>{{ batch.batch_code }}</h2><small>Batch #{{ batch.import_batch_id }}</small></div><el-tag size="large" :type="terminalFailure ? 'danger' : batch.status === 'COMPLETED' ? 'success' : 'primary'">{{ statusLabels[batch.status] }}</el-tag></div>
          <el-descriptions :column="5" border class="summary"><el-descriptions-item label="文件">{{ batch.total_files }}</el-descriptions-item><el-descriptions-item label="总行数">{{ batch.total_rows }}</el-descriptions-item><el-descriptions-item label="新增行">{{ batch.valid_rows }}</el-descriptions-item><el-descriptions-item label="跳过行">{{ batch.skipped_rows }}</el-descriptions-item><el-descriptions-item label="错误行">{{ batch.error_rows }}</el-descriptions-item></el-descriptions>
        </el-card>

        <el-card v-if="['CREATED', 'UPLOADING'].includes(batch.status)" shadow="never" class="section">
          <template #header><strong>Step 2 · 上传多个 CSV 文件</strong></template>
          <el-upload ref="uploadRef" drag multiple :auto-upload="false" :limit="4" accept=".csv" :on-change="handleChange" :on-remove="handleRemove">
            <div class="upload-copy"><strong>拖放文件到这里，或点击选择</strong><span>最多四类文件，每类一个，单文件最大 20 MiB</span></div>
          </el-upload>
          <div class="footer-actions"><el-button type="primary" :disabled="selectedFiles.length === 0" :loading="uploading" @click="uploadFiles">上传所选文件</el-button></div>
        </el-card>

        <el-card shadow="never" class="section">
          <template #header><div class="card-title"><strong>文件和依赖阶段</strong><span>文件类型由服务端表头识别</span></div></template>
          <el-table :data="batch.files" empty-text="尚未上传文件">
            <el-table-column prop="batch_sequence" label="#" width="60" />
            <el-table-column prop="original_filename" label="文件名" min-width="220" show-overflow-tooltip />
            <el-table-column label="类型" min-width="150"><template #default="scope">{{ fileTypeLabels[scope.row.batch_file_type as BatchFileType] }}</template></el-table-column>
            <el-table-column label="阶段" width="100"><template #default="scope">{{ phaseLabels[scope.row.batch_file_type as BatchFileType] }}</template></el-table-column>
            <el-table-column prop="total_rows" label="总行" width="85" align="right" /><el-table-column prop="valid_rows" label="新增" width="85" align="right" /><el-table-column prop="skipped_rows" label="跳过" width="85" align="right" /><el-table-column prop="error_rows" label="错误" width="85" align="right" />
            <el-table-column prop="status" label="状态" width="150" />
            <el-table-column label="操作" width="100"><template #default="scope"><el-button v-if="scope.row.error_rows > 0 || scope.row.status === 'VALIDATION_FAILED'" link type="danger" @click="openErrors(scope.row.import_job_id)">错误详情</el-button></template></el-table-column>
          </el-table>
          <div class="footer-actions">
            <el-button v-if="batch.status === 'UPLOADING'" type="primary" :loading="validating" @click="runValidation">开始依赖校验</el-button>
            <el-button v-if="batch.status === 'READY'" type="success" :loading="confirming" @click="confirmBatch">确认批次导入</el-button>
          </div>
        </el-card>
      </template>
    </template>
  </main>
</template>

<style scoped>
.batch-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}.page-header,.batch-heading,.card-title,.footer-actions,.actions{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-header{align-items:flex-start;margin-bottom:20px}.page-header h1,.batch-heading h2{margin:0 0 8px}.page-header p{margin:0;color:var(--el-text-color-secondary)}.eyebrow{margin-bottom:8px!important;color:var(--el-color-primary)!important;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.section{margin-bottom:20px}.summary{margin-top:20px}.upload-copy{display:grid;gap:8px;color:var(--el-text-color-secondary)}.upload-copy strong{color:var(--el-text-color-primary)}.footer-actions{justify-content:flex-end;margin-top:20px}.card-title span,.batch-heading small{color:var(--el-text-color-secondary)}
@media(max-width:760px){.batch-page{padding:18px}.page-header,.batch-heading,.card-title{align-items:flex-start;flex-direction:column}}
</style>
