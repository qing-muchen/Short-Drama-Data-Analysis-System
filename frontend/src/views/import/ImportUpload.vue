<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type UploadFile, type UploadInstance, type UploadProps } from 'element-plus'

import { createImportJob } from '../../api/import'
import { useUserStore } from '../../stores/user'
import type { ImportJob, ImportType } from '../../types/import'
import { getApiErrorMessage } from '../../utils/api-error'
import { readRecentImportJobs, rememberImportJob } from '../../utils/import-history'

const MAX_FILE_SIZE = 20 * 1024 * 1024
const router = useRouter()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const uploadRef = ref<UploadInstance>()
const selectedFile = ref<File | null>(null)
const importType = ref<ImportType>('MASTER_DATA')
const uploading = ref(false)
const uploadError = ref('')
const recentJobs = ref<ImportJob[]>(readRecentImportJobs())

const statusLabels: Record<ImportJob['status'], string> = {
  PENDING_VALIDATION: '待校验', VALIDATION_FAILED: '校验失败', READY: '待确认',
  IMPORTING: '导入中', COMPLETED: '已完成', COMPLETED_WITH_ERRORS: '完成（含错误）', FAILED: '失败',
}

function statusLabel(status: ImportJob['status']): string {
  return statusLabels[status]
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

function validateFile(file: File): string | null {
  const extension = file.name.includes('.') ? file.name.split('.').pop()?.toLowerCase() : ''
  if (extension !== 'csv' && extension !== 'xlsx') return '仅支持 .csv 和 .xlsx 文件。'
  if (file.size > MAX_FILE_SIZE) return '文件大小不能超过 20 MiB。'
  return null
}

const handleChange: UploadProps['onChange'] = (uploadFile: UploadFile) => {
  uploadError.value = ''
  if (!uploadFile.raw) {
    selectedFile.value = null
    return
  }
  const message = validateFile(uploadFile.raw)
  if (message) {
    selectedFile.value = null
    uploadRef.value?.clearFiles()
    uploadError.value = message
    return
  }
  selectedFile.value = uploadFile.raw
}

const handleRemove: UploadProps['onRemove'] = () => { selectedFile.value = null }

async function submitUpload(): Promise<void> {
  if (!isAdmin.value) return
  if (!selectedFile.value) {
    uploadError.value = '请先选择需要导入的 CSV 或 XLSX 文件。'
    return
  }
  uploading.value = true
  uploadError.value = ''
  try {
    const job = await createImportJob(selectedFile.value, importType.value)
    rememberImportJob(job)
    recentJobs.value = readRecentImportJobs()
    ElMessage.success(`导入任务 #${job.import_job_id} 已创建`)
    await router.push(`/imports/${job.import_job_id}`)
  } catch (error: unknown) {
    uploadError.value = getApiErrorMessage(error, '创建导入任务失败，请检查文件后重试。')
  } finally {
    uploading.value = false
  }
}

function openJob(jobId: number): void { void router.push(`/imports/${jobId}`) }
</script>

<template>
  <main class="import-page">
    <header class="page-header">
      <div><p class="eyebrow">Data Import</p><h1>数据导入</h1><p>上传固定模板文件，完成校验后再确认写入正式数据。</p></div>
      <router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link>
    </header>

    <el-alert v-if="!isAdmin" type="warning" show-icon :closable="false" title="当前后端导入接口仅允许管理员访问">
      <p>普通用户暂时无法读取导入任务；请联系管理员查看或执行导入。</p>
    </el-alert>

    <template v-else>
      <el-card shadow="never" class="upload-card">
        <template #header><strong>创建导入任务</strong></template>
        <el-form label-width="92px">
          <el-form-item label="导入类型">
            <el-radio-group v-model="importType">
              <el-radio-button value="MASTER_DATA">基础资料</el-radio-button>
              <el-radio-button value="SNAPSHOT">运营快照</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="数据文件">
            <el-upload
              ref="uploadRef"
              drag
              :auto-upload="false"
              :limit="1"
              accept=".csv,.xlsx"
              :on-change="handleChange"
              :on-remove="handleRemove"
              class="upload-control"
            >
              <div class="upload-copy"><strong>拖放文件到这里，或点击选择</strong><span>支持 CSV / XLSX，最大 20 MiB、最多 50,000 行</span></div>
            </el-upload>
          </el-form-item>
          <el-alert v-if="uploadError" :title="uploadError" type="error" show-icon :closable="false" />
          <el-form-item class="submit-row"><el-button type="primary" :loading="uploading" @click="submitUpload">上传并校验</el-button></el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never">
        <template #header><div class="card-title"><strong>本浏览器近期任务</strong><small>仅用于快捷导航，不代表系统全量任务列表</small></div></template>
        <el-table :data="recentJobs" empty-text="暂无近期导入任务">
          <el-table-column prop="import_job_id" label="任务编号" width="110" />
          <el-table-column prop="original_filename" label="文件名" min-width="220" show-overflow-tooltip />
          <el-table-column label="状态" width="150"><template #default="scope">{{ statusLabel(scope.row.status) }}</template></el-table-column>
          <el-table-column label="创建时间" min-width="170"><template #default="scope">{{ formatDate(scope.row.created_at) }}</template></el-table-column>
          <el-table-column prop="error_rows" label="错误数" width="90" align="right" />
          <el-table-column label="操作" width="100"><template #default="scope"><el-button link type="primary" @click="openJob(scope.row.import_job_id)">查看</el-button></template></el-table-column>
        </el-table>
      </el-card>
    </template>
  </main>
</template>

<style scoped>
.import-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}.page-header{display:flex;justify-content:space-between;gap:24px;margin-bottom:20px}.page-header h1{margin:0 0 8px;font-size:32px}.page-header p{margin:0;color:var(--el-text-color-secondary)}.eyebrow{margin-bottom:8px!important;color:var(--el-color-primary)!important;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.upload-card{margin-bottom:20px}.upload-control{width:100%}.upload-copy{display:grid;gap:8px;color:var(--el-text-color-secondary)}.upload-copy strong{color:var(--el-text-color-primary)}.submit-row{margin-top:18px}.card-title{display:flex;align-items:baseline;justify-content:space-between;gap:16px}.card-title small{color:var(--el-text-color-secondary)}
@media(max-width:720px){.import-page{padding:18px}.page-header,.card-title{flex-direction:column}}
</style>
