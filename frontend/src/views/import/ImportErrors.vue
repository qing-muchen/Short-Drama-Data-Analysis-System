<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getImportErrors } from '../../api/import'
import { useUserStore } from '../../stores/user'
import type { ImportErrorItem } from '../../types/import'
import { getApiErrorMessage } from '../../utils/api-error'

const route = useRoute()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const jobId = computed(() => Number(route.params.id))
const rows = ref<ImportErrorItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')

async function loadErrors(): Promise<void> {
  if (!isAdmin.value) return
  if (!Number.isInteger(jobId.value) || jobId.value < 1) { errorMessage.value = '无效的导入任务编号。'; return }
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await getImportErrors(jobId.value, page.value, pageSize.value)
    rows.value = result.items
    total.value = result.total
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '导入错误加载失败，请稍后重试。')
  } finally { loading.value = false }
}

function handlePageChange(nextPage: number): void { page.value = nextPage; void loadErrors() }
onMounted(() => void loadErrors())
</script>

<template>
  <main class="import-page">
    <header class="page-header"><div><p class="eyebrow">Validation Errors</p><h1>任务 #{{ route.params.id }} 校验错误</h1><p>仅展示定位和错误原因，不展示原始敏感值。</p></div><div class="actions"><router-link :to="`/imports/${route.params.id}`"><el-button>返回任务</el-button></router-link><el-button v-if="isAdmin" :loading="loading" @click="loadErrors">刷新</el-button></div></header>
    <el-alert v-if="!isAdmin" type="warning" show-icon :closable="false" title="当前后端导入错误接口仅允许管理员访问" />
    <template v-else>
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false"><template #default><el-button text type="primary" @click="loadErrors">重新加载</el-button></template></el-alert>
      <el-card shadow="never">
        <el-table v-loading="loading" :data="rows" empty-text="当前任务没有校验错误">
          <el-table-column prop="source_row_number" label="源行号" width="100"><template #default="scope">{{ scope.row.source_row_number ?? '--' }}</template></el-table-column>
          <el-table-column prop="column_name" label="字段" min-width="140"><template #default="scope">{{ scope.row.column_name ?? '--' }}</template></el-table-column>
          <el-table-column prop="error_code" label="错误类型" min-width="170" />
          <el-table-column prop="error_message" label="错误消息" min-width="320" show-overflow-tooltip />
        </el-table>
        <el-pagination v-if="total > 0" class="pagination" background layout="total, prev, pager, next" :current-page="page" :page-size="pageSize" :total="total" @current-change="handlePageChange" />
      </el-card>
    </template>
  </main>
</template>

<style scoped>
.import-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}.page-header,.actions{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-header{align-items:flex-start;margin-bottom:20px}.page-header h1{margin:0 0 8px}.page-header p{margin:0;color:var(--el-text-color-secondary)}.eyebrow{margin-bottom:8px!important;color:var(--el-color-primary)!important;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.pagination{justify-content:flex-end;margin-top:20px}
@media(max-width:720px){.import-page{padding:18px}.page-header{flex-direction:column}}
</style>
