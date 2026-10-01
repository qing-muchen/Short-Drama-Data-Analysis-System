<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { createTag, deactivateTag, getTags, updateTag } from '../../api/tag'
import { useUserStore } from '../../stores/user'
import type { EntityStatus, Tag, TagWrite } from '../../types/master'
import { getApiErrorMessage } from '../../utils/api-error'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const rows = ref<Tag[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const nameContains = ref('')
const statusFilter = ref<EntityStatus | ''>('')
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive<TagWrite>({ tag_name: '', status: 'ACTIVE' })
const rules: FormRules<TagWrite> = {
  tag_name: [
    { required: true, message: '请输入标签名称', trigger: 'blur' },
    { min: 1, max: 100, message: '名称长度不能超过 100 个字符', trigger: 'blur' },
  ],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

async function loadRows(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await getTags({
      page: page.value,
      page_size: pageSize.value,
      name_contains: nameContains.value.trim() || undefined,
      status: statusFilter.value || undefined,
    })
    rows.value = result.items
    total.value = result.total
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '标签列表加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

function search(): void {
  page.value = 1
  void loadRows()
}

function resetFilters(): void {
  nameContains.value = ''
  statusFilter.value = ''
  search()
}

function openCreate(): void {
  editingId.value = null
  Object.assign(form, { tag_name: '', status: 'ACTIVE' })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

function openEdit(row: Tag): void {
  editingId.value = row.tag_id
  Object.assign(form, { tag_name: row.tag_name, status: row.status })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

async function submitForm(): Promise<void> {
  if (!(await formRef.value?.validate().catch(() => false))) return
  saving.value = true
  const payload: TagWrite = { tag_name: form.tag_name.trim(), status: form.status }
  try {
    if (editingId.value === null) {
      await createTag(payload)
      ElMessage.success('标签创建成功')
    } else {
      await updateTag(editingId.value, payload)
      ElMessage.success('标签更新成功')
    }
    dialogVisible.value = false
    await loadRows()
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '保存标签失败，请稍后重试。'))
  } finally {
    saving.value = false
  }
}

async function confirmDeactivate(row: Tag): Promise<void> {
  const relationWarning = row.drama_count
    ? `当前仍关联 ${row.drama_count} 部短剧；删除后这些短剧将不再展示该标签。`
    : '该标签当前没有关联短剧。'
  try {
    await ElMessageBox.confirm(
      `${relationWarning}确认删除标签“${row.tag_name}”吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
    await deactivateTag(row.tag_id)
    ElMessage.success('标签已删除')
    await loadRows()
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '删除标签失败，请稍后重试。'))
  }
}

function handlePageChange(nextPage: number): void {
  page.value = nextPage
  void loadRows()
}

onMounted(() => void loadRows())
</script>

<template>
  <main class="management-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Data Management</p>
        <h1>标签管理</h1>
        <p>维护短剧分类标签并查看关联短剧数量。</p>
      </div>
      <div class="header-actions">
        <router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link>
        <router-link to="/dramas"><el-button>短剧管理</el-button></router-link>
        <el-button v-if="isAdmin" type="primary" @click="openCreate">新增标签</el-button>
      </div>
    </header>

    <el-card shadow="never">
      <div class="filters">
        <el-input
          v-model="nameContains"
          clearable
          placeholder="搜索标签名称"
          class="search-input"
          @keyup.enter="search"
        />
        <el-select v-model="statusFilter" clearable placeholder="全部状态" class="status-select">
          <el-option label="启用" value="ACTIVE" />
          <el-option label="停用" value="INACTIVE" />
        </el-select>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false">
        <template #default><el-button text type="primary" @click="loadRows">重新加载</el-button></template>
      </el-alert>

      <el-table v-loading="loading" :data="rows" empty-text="暂无标签数据" class="data-table">
        <el-table-column prop="tag_name" label="标签名称" min-width="220" />
        <el-table-column prop="drama_count" label="关联短剧数量" width="150" align="right" />
        <el-table-column label="状态" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'ACTIVE' ? 'success' : 'info'">
              {{ scope.row.status === 'ACTIVE' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="isAdmin ? 160 : 80" fixed="right">
          <template #default="scope">
            <el-button v-if="isAdmin" link type="primary" @click="openEdit(scope.row)">编辑</el-button>
            <el-button
              v-if="isAdmin"
              link
              type="danger"
              :disabled="scope.row.status === 'INACTIVE'"
              @click="confirmDeactivate(scope.row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > 0"
        class="pagination"
        background
        layout="total, prev, pager, next"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        @current-change="handlePageChange"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId === null ? '新增标签' : '编辑标签'" width="min(480px, 92vw)" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-form-item label="标签名称" prop="tag_name">
          <el-input v-model="form.tag_name" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" class="full-width">
            <el-option label="启用" value="ACTIVE" />
            <el-option label="停用" value="INACTIVE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<style scoped>
.management-page { min-height: 100vh; padding: 28px; background: var(--el-bg-color-page); color: var(--el-text-color-primary); }
.page-header { display: flex; justify-content: space-between; gap: 24px; margin-bottom: 20px; }
.page-header h1 { margin: 0 0 8px; font-size: 32px; }
.page-header p { margin: 0; color: var(--el-text-color-secondary); }
.eyebrow { margin-bottom: 8px !important; color: var(--el-color-primary) !important; font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.header-actions, .filters { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.filters { margin-bottom: 18px; }
.search-input { width: 260px; }
.status-select { width: 150px; }
.data-table { margin-top: 16px; }
.pagination { justify-content: flex-end; margin-top: 20px; }
.full-width { width: 100%; }
@media (max-width: 720px) { .management-page { padding: 18px; } .page-header { flex-direction: column; } .search-input, .status-select { width: 100%; } }
</style>
