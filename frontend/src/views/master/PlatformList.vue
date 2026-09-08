<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { createPlatform, deactivatePlatform, getPlatforms, updatePlatform } from '../../api/platform'
import { useUserStore } from '../../stores/user'
import type { EntityStatus, Platform, PlatformWrite } from '../../types/master'
import { getApiErrorMessage } from '../../utils/api-error'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const rows = ref<Platform[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const nameContains = ref('')
const statusFilter = ref<EntityStatus | ''>('')
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive<PlatformWrite>({ platform_name: '', description: '', status: 'ACTIVE' })
const rules: FormRules<PlatformWrite> = {
  platform_name: [
    { required: true, message: '请输入平台名称', trigger: 'blur' },
    { min: 1, max: 100, message: '名称长度不能超过 100 个字符', trigger: 'blur' },
  ],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

async function loadRows(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await getPlatforms({
      page: page.value, page_size: pageSize.value,
      name_contains: nameContains.value.trim() || undefined,
      status: statusFilter.value || undefined,
    })
    rows.value = result.items
    total.value = result.total
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '平台列表加载失败，请稍后重试。')
  } finally { loading.value = false }
}

function search(): void { page.value = 1; void loadRows() }
function resetFilters(): void { nameContains.value = ''; statusFilter.value = ''; search() }
function openCreate(): void {
  editingId.value = null
  Object.assign(form, { platform_name: '', description: '', status: 'ACTIVE' })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}
function openEdit(row: Platform): void {
  editingId.value = row.platform_id
  Object.assign(form, { platform_name: row.platform_name, description: row.description ?? '', status: row.status })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

async function submitForm(): Promise<void> {
  if (!(await formRef.value?.validate().catch(() => false))) return
  saving.value = true
  const payload: PlatformWrite = {
    platform_name: form.platform_name.trim(), description: form.description?.trim() || null, status: form.status,
  }
  try {
    if (editingId.value === null) { await createPlatform(payload); ElMessage.success('平台创建成功') }
    else { await updatePlatform(editingId.value, payload); ElMessage.success('平台更新成功') }
    dialogVisible.value = false
    await loadRows()
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '保存平台失败，请稍后重试。'))
  } finally { saving.value = false }
}

async function confirmDeactivate(row: Platform): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认停用平台“${row.platform_name}”吗？历史发行和快照数据仍会保留。`, '停用确认', {
      type: 'warning', confirmButtonText: '确认停用', cancelButtonText: '取消',
    })
    await deactivatePlatform(row.platform_id)
    ElMessage.success('平台已停用')
    await loadRows()
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '停用平台失败，请稍后重试。'))
  }
}

function handlePageChange(nextPage: number): void { page.value = nextPage; void loadRows() }
onMounted(() => void loadRows())
</script>

<template>
  <main class="management-page">
    <header class="page-header">
      <div><p class="eyebrow">Master Data</p><h1>平台管理</h1><p>维护平台资料及启用状态。</p></div>
      <div class="header-actions">
        <router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link>
        <el-button v-if="isAdmin" type="primary" @click="openCreate">新增平台</el-button>
      </div>
    </header>
    <el-card shadow="never">
      <div class="filters">
        <el-input v-model="nameContains" clearable placeholder="搜索平台名称" class="search-input" @keyup.enter="search" />
        <el-select v-model="statusFilter" clearable placeholder="全部状态" class="status-select"><el-option label="启用" value="ACTIVE" /><el-option label="停用" value="INACTIVE" /></el-select>
        <el-button type="primary" @click="search">查询</el-button><el-button @click="resetFilters">重置</el-button>
      </div>
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false"><template #default><el-button text type="primary" @click="loadRows">重新加载</el-button></template></el-alert>
      <el-table v-loading="loading" :data="rows" empty-text="暂无平台数据" class="data-table">
        <el-table-column prop="platform_name" label="平台名称" min-width="180" />
        <el-table-column label="状态" width="110"><template #default="scope"><el-tag :type="scope.row.status === 'ACTIVE' ? 'success' : 'info'">{{ scope.row.status === 'ACTIVE' ? '启用' : '停用' }}</el-tag></template></el-table-column>
        <el-table-column prop="description" label="说明" min-width="260" show-overflow-tooltip />
        <el-table-column v-if="isAdmin" label="操作" width="150" fixed="right"><template #default="scope"><el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button><el-button link type="danger" :disabled="scope.row.status === 'INACTIVE'" @click="confirmDeactivate(scope.row)">停用</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-if="total > 0" class="pagination" background layout="total, prev, pager, next" :current-page="page" :page-size="pageSize" :total="total" @current-change="handlePageChange" />
    </el-card>
    <el-dialog v-model="dialogVisible" :title="editingId === null ? '新增平台' : '编辑平台'" width="min(520px, 92vw)" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="platform_name"><el-input v-model="form.platform_name" maxlength="100" show-word-limit /></el-form-item>
        <el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="状态" prop="status"><el-select v-model="form.status" class="full-width"><el-option label="启用" value="ACTIVE" /><el-option label="停用" value="INACTIVE" /></el-select></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitForm">保存</el-button></template>
    </el-dialog>
  </main>
</template>

<style scoped>
.management-page{min-height:100vh;padding:28px;background:var(--el-bg-color-page);color:var(--el-text-color-primary)}
.page-header{display:flex;justify-content:space-between;gap:24px;margin-bottom:20px}.page-header h1{margin:0 0 8px;font-size:32px}.page-header p{margin:0;color:var(--el-text-color-secondary)}
.eyebrow{margin-bottom:8px!important;color:var(--el-color-primary)!important;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.header-actions,.filters{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.filters{margin-bottom:18px}.search-input{width:260px}.status-select{width:150px}.data-table{margin-top:16px}.pagination{justify-content:flex-end;margin-top:20px}.full-width{width:100%}
@media(max-width:720px){.management-page{padding:18px}.page-header{flex-direction:column}.search-input,.status-select{width:100%}}
</style>
