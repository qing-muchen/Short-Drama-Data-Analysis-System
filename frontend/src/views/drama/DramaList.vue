<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { useRouter } from 'vue-router'

import { createDrama, deactivateDrama, getDramas, updateDrama } from '../../api/drama'
import { getTags } from '../../api/tag'
import { useUserStore } from '../../stores/user'
import type { Drama, DramaCreate, DramaStatus } from '../../types/drama'
import type { Tag } from '../../types/master'
import { getApiErrorMessage } from '../../utils/api-error'

interface DramaForm {
  drama_code: string
  drama_name: string
  synopsis: string
  status: DramaStatus
  tags: number[]
}

const userStore = useUserStore()
const router = useRouter()
const isAdmin = computed(() => userStore.currentUser?.role_code === 'ADMINISTRATOR')
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const rows = ref<Drama[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const nameContains = ref('')
const statusFilter = ref<DramaStatus | ''>('')
const availableTags = ref<Tag[]>([])
const selectedTagIds = ref<number[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive<DramaForm>({
  drama_code: '',
  drama_name: '',
  synopsis: '',
  status: 'DRAFT',
  tags: [],
})

const formRules: FormRules<DramaForm> = {
  drama_name: [
    { required: true, message: '请输入短剧名称', trigger: 'blur' },
    { min: 1, max: 200, message: '名称长度不能超过 200 个字符', trigger: 'blur' },
  ],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

const statusOptions: Array<{ value: DramaStatus; label: string }> = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'SERIALIZING', label: '连载中' },
  { value: 'COMPLETED', label: '已完结' },
  { value: 'INACTIVE', label: '已停用' },
]

function statusLabel(status: DramaStatus): string {
  return statusOptions.find((item) => item.value === status)?.label ?? status
}

function statusTone(status: DramaStatus): 'success' | 'warning' | 'info' | 'danger' {
  return {
    DRAFT: 'info',
    SERIALIZING: 'warning',
    COMPLETED: 'success',
    INACTIVE: 'danger',
  }[status] as 'success' | 'warning' | 'info' | 'danger'
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

async function loadRows(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await getDramas({
      page: page.value,
      page_size: pageSize.value,
      name_contains: nameContains.value.trim() || undefined,
      status: statusFilter.value || undefined,
      tag_ids: selectedTagIds.value.length ? selectedTagIds.value.join(',') : undefined,
    })
    rows.value = result.items
    total.value = result.total
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '短剧列表加载失败，请稍后重试。')
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
  selectedTagIds.value = []
  search()
}

async function loadTags(): Promise<void> {
  try {
    const result = await getTags({ page: 1, page_size: 100, status: 'ACTIVE' })
    availableTags.value = result.items
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '标签列表加载失败，请稍后重试。'))
  }
}

function clearTagFilter(): void {
  selectedTagIds.value = []
  search()
}

function openCreate(): void {
  editingId.value = null
  Object.assign(form, {
    drama_code: '',
    drama_name: '',
    synopsis: '',
    status: 'DRAFT',
    tags: [],
  })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

function openEdit(row: Drama): void {
  editingId.value = row.drama_id
  Object.assign(form, {
    drama_code: row.drama_code,
    drama_name: row.drama_name,
    synopsis: row.synopsis ?? '',
    status: row.status,
    tags: row.tags.map((tag) => tag.tag_id),
  })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

async function submitForm(): Promise<void> {
  if (!(await formRef.value?.validate().catch(() => false))) return
  saving.value = true
  try {
    const payload: DramaCreate = {
      drama_name: form.drama_name.trim(),
      synopsis: form.synopsis.trim() || null,
      status: form.status,
      tags: [...form.tags],
    }
    if (editingId.value === null) {
      await createDrama(payload)
      ElMessage.success('短剧创建成功')
    } else {
      await updateDrama(editingId.value, payload)
      ElMessage.success('短剧更新成功')
    }
    dialogVisible.value = false
    await loadRows()
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '保存短剧失败，请稍后重试。'))
  } finally {
    saving.value = false
  }
}

async function confirmDeactivate(row: Drama): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认停用短剧“${row.drama_name}”吗？历史数据仍会保留。`,
      '停用确认',
      { type: 'warning', confirmButtonText: '确认停用', cancelButtonText: '取消' },
    )
    await deactivateDrama(row.drama_id)
    ElMessage.success('短剧已停用')
    await loadRows()
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '停用短剧失败，请稍后重试。'))
  }
}

function handlePageChange(nextPage: number): void {
  page.value = nextPage
  void loadRows()
}

function openAnalysis(row: Drama): void {
  void router.push({ path: '/analytics', query: { drama_id: String(row.drama_id) } })
}

function openDetail(row: Drama): void {
  void router.push(`/dramas/${row.drama_id}`)
}

onMounted(() => {
  void Promise.all([loadTags(), loadRows()])
})
</script>

<template>
  <main class="management-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Data Management</p>
        <h1>短剧管理</h1>
        <p>维护短剧基础资料；业务编码由系统生成并保持稳定。</p>
      </div>
      <div class="header-actions">
        <router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link>
        <router-link to="/tags"><el-button>标签管理</el-button></router-link>
        <el-button v-if="isAdmin" type="primary" @click="openCreate">新增短剧</el-button>
      </div>
    </header>

    <el-card shadow="never">
      <div class="filters">
        <el-input
          v-model="nameContains"
          clearable
          placeholder="搜索短剧名称"
          class="search-input"
          @keyup.enter="search"
        />
        <el-select v-model="statusFilter" clearable placeholder="全部状态" class="status-select">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <div class="tag-filter" aria-label="标签筛选">
        <span class="tag-filter-label">标签：</span>
        <el-button
          size="small"
          :type="selectedTagIds.length === 0 ? 'primary' : 'default'"
          plain
          @click="clearTagFilter"
        >全部</el-button>
        <el-checkbox-group v-model="selectedTagIds" class="tag-options" @change="search">
          <el-checkbox-button
            v-for="tag in availableTags"
            :key="tag.tag_id"
            :value="tag.tag_id"
          >{{ tag.tag_name }}</el-checkbox-button>
        </el-checkbox-group>
      </div>

      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false">
        <template #default><el-button text type="primary" @click="loadRows">重新加载</el-button></template>
      </el-alert>

      <el-table v-loading="loading" :data="rows" empty-text="暂无短剧数据" class="data-table">
        <el-table-column prop="drama_code" label="业务编码" min-width="130" />
        <el-table-column prop="drama_name" label="短剧名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="标签" min-width="220">
          <template #default="scope">
            <div class="row-tags">
              <el-tag v-for="tag in scope.row.tags" :key="tag.tag_id" size="small" effect="plain">
                {{ tag.tag_name }}
              </el-tag>
              <span v-if="scope.row.tags.length === 0" class="muted">暂无标签</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="scope">
            <el-tag :type="statusTone(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="170">
          <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" :width="isAdmin ? 210 : 80" fixed="right">
          <template #default="scope">
            <el-button link @click="openDetail(scope.row)">详情</el-button>
            <el-button link type="success" @click="openAnalysis(scope.row)">分析</el-button>
            <el-button v-if="isAdmin" link type="primary" @click="openEdit(scope.row)">编辑</el-button>
            <el-button
              v-if="isAdmin"
              link
              type="danger"
              :disabled="scope.row.status === 'INACTIVE'"
              @click="confirmDeactivate(scope.row)"
            >停用</el-button>
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

    <el-dialog v-model="dialogVisible" :title="editingId === null ? '新增短剧' : '编辑短剧'" width="min(560px, 92vw)" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="88px">
        <el-form-item label="业务编码">
          <el-input :model-value="form.drama_code || '保存后由系统生成'" disabled />
        </el-form-item>
        <el-form-item label="短剧名称" prop="drama_name">
          <el-input v-model="form.drama_name" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.synopsis" type="textarea" :rows="4" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" class="full-width">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="form.tags"
            class="full-width"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="请选择一个或多个标签"
          >
            <el-option
              v-for="tag in availableTags"
              :key="tag.tag_id"
              :label="tag.tag_name"
              :value="tag.tag_id"
            />
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
.tag-filter { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 18px; }
.tag-filter-label { flex: 0 0 auto; line-height: 32px; color: var(--el-text-color-secondary); }
.tag-options, .row-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.muted { color: var(--el-text-color-secondary); }
.search-input { width: 260px; }
.status-select { width: 150px; }
.data-table { margin-top: 16px; }
.pagination { justify-content: flex-end; margin-top: 20px; }
.full-width { width: 100%; }
@media (max-width: 720px) { .management-page { padding: 18px; } .page-header { flex-direction: column; } .search-input, .status-select { width: 100%; } }
</style>
