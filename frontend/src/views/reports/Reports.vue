<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import {
  ReportingApiError,
  exportReport,
  getReportCatalog,
  getReportPreview,
} from '../../api/reporting'
import type {
  DownloadStatus,
  ExportFormat,
  ReportAvailabilityStatus,
  ReportCatalog,
  ReportCellValue,
  ReportFilters,
  ReportPreview,
  ReportType,
} from '../../types/reporting'
import { getApiErrorMessage } from '../../utils/api-error'

type RequestStatus = 'idle' | 'loading' | 'success' | 'error'

const catalog = ref<ReportCatalog[]>([])
const catalogStatus = ref<RequestStatus>('idle')
const catalogError = ref('')
const selectedReportType = ref<ReportType | ''>('')
const filterInputs = reactive<Record<string, string>>({})
const analysisAsOf = ref('')
const pageSize = ref(20)

const preview = ref<ReportPreview | null>(null)
const previewStatus = ref<RequestStatus>('idle')
const previewError = ref('')

const exportFormat = ref<ExportFormat | ''>('')
const exportDialogVisible = ref(false)
const confirmationCount = ref<number | null>(null)
const downloadStatus = ref<DownloadStatus>('idle')
const downloadMessage = ref('')

const selectedReport = computed(
  () => catalog.value.find((item) => item.report_type === selectedReportType.value) ?? null,
)

function resetFilters(report: ReportCatalog | null): void {
  Object.keys(filterInputs).forEach((key) => delete filterInputs[key])
  report?.filters.forEach((filter) => {
    filterInputs[filter.key] = filter.default == null ? '' : String(filter.default)
  })
}

watch(selectedReportType, () => {
  resetFilters(selectedReport.value)
  preview.value = null
  previewStatus.value = 'idle'
  previewError.value = ''
  analysisAsOf.value = ''
  exportFormat.value = selectedReport.value?.supported_formats[0] ?? ''
  downloadStatus.value = 'idle'
  downloadMessage.value = ''
})

function filterPayload(): ReportFilters | undefined {
  const report = selectedReport.value
  if (!report) {
    return undefined
  }
  const filters: ReportFilters = {}
  report.filters.forEach((definition) => {
    const rawValue = filterInputs[definition.key]?.trim() ?? ''
    if (!rawValue) {
      return
    }
    filters[definition.key] = definition.value_type === 'INTEGER' ? Number(rawValue) : rawValue
  })
  return Object.keys(filters).length > 0 ? filters : undefined
}

async function loadCatalog(): Promise<void> {
  catalogStatus.value = 'loading'
  catalogError.value = ''
  try {
    catalog.value = await getReportCatalog()
    catalogStatus.value = 'success'
    if (!selectedReportType.value && catalog.value[0]) {
      selectedReportType.value = catalog.value[0].report_type
    }
  } catch (error: unknown) {
    catalogStatus.value = 'error'
    catalogError.value = getApiErrorMessage(error, '报告目录加载失败，请稍后重试。')
  }
}

async function loadPreview(): Promise<void> {
  if (!selectedReportType.value || previewStatus.value === 'loading') {
    return
  }
  previewStatus.value = 'loading'
  previewError.value = ''
  try {
    preview.value = await getReportPreview({
      report_type: selectedReportType.value,
      filters: filterPayload(),
      analysis_as_of: analysisAsOf.value.trim() || undefined,
      page_size: pageSize.value,
    })
    previewStatus.value = 'success'
  } catch (error: unknown) {
    preview.value = null
    previewStatus.value = 'error'
    previewError.value = getApiErrorMessage(error, '报告预览加载失败，请检查参数后重试。')
  }
}

function openExportConfirmation(): void {
  if (!preview.value || !exportFormat.value) {
    return
  }
  confirmationCount.value = preview.value.metadata.total_rows
  downloadStatus.value = 'idle'
  downloadMessage.value = ''
  exportDialogVisible.value = true
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

async function confirmExport(): Promise<void> {
  if (
    !selectedReportType.value ||
    !exportFormat.value ||
    confirmationCount.value == null ||
    downloadStatus.value === 'loading'
  ) {
    return
  }
  downloadStatus.value = 'loading'
  downloadMessage.value = ''
  try {
    const download = await exportReport({
      report_type: selectedReportType.value,
      filters: filterPayload(),
      analysis_as_of: analysisAsOf.value.trim() || undefined,
      export_format: exportFormat.value,
      confirmation: confirmationCount.value,
    })
    triggerDownload(download.blob, download.filename)
    downloadStatus.value = 'success'
    downloadMessage.value = `已开始下载 ${download.filename}`
    exportDialogVisible.value = false
  } catch (error: unknown) {
    downloadStatus.value = 'error'
    if (error instanceof ReportingApiError) {
      const serverCount = error.details?.confirmed_row_count
      if (error.code === 'EXPORT_CONFIRMATION_REQUIRED' && typeof serverCount === 'number') {
        confirmationCount.value = serverCount
        downloadMessage.value = `服务器确认当前导出共 ${serverCount} 行，请再次确认。`
        return
      }
      downloadMessage.value = error.message
      return
    }
    downloadMessage.value = getApiErrorMessage(error, '报告导出失败，请稍后重试。')
  }
}

function displayCell(value: ReportCellValue | undefined): string {
  if (value == null) {
    return '—'
  }
  return typeof value === 'boolean' ? String(value) : `${value}`
}

function availabilityType(
  status: ReportAvailabilityStatus,
): 'success' | 'warning' | 'info' | 'danger' {
  if (status === 'AVAILABLE') return 'success'
  if (status === 'PARTIAL' || status === 'INSUFFICIENT') return 'warning'
  if (status === 'EMPTY') return 'info'
  return 'danger'
}

onMounted(() => {
  void loadCatalog()
})
</script>

<template>
  <main class="reports-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Reporting / Read Model</p>
        <h1>分析报告与导出中心</h1>
        <p class="subtitle">按已注册 Schema 预览并导出系统既有分析事实。</p>
      </div>
      <router-link to="/dashboard"><el-button>返回驾驶舱</el-button></router-link>
    </header>

    <el-alert
      v-if="catalogError"
      class="section-alert"
      type="error"
      show-icon
      :closable="false"
      :title="catalogError"
    >
      <template #default><el-button text type="primary" @click="loadCatalog">重新加载</el-button></template>
    </el-alert>

    <section class="workspace-grid">
      <el-card v-loading="catalogStatus === 'loading'" shadow="never" class="catalog-card">
        <template #header>
          <div class="card-heading">
            <strong>报告目录</strong>
            <el-tag effect="plain">{{ catalog.length }} 项</el-tag>
          </div>
        </template>
        <el-radio-group v-if="catalog.length" v-model="selectedReportType" class="catalog-list">
          <el-radio-button
            v-for="item in catalog"
            :key="item.report_type"
            :value="item.report_type"
            class="catalog-option"
          >
            <span>{{ item.title }}</span>
            <small>{{ item.schema_version }}</small>
          </el-radio-button>
        </el-radio-group>
        <el-empty v-else-if="catalogStatus === 'success'" description="暂无可用报告" />
      </el-card>

      <el-card v-if="selectedReport" shadow="never" class="configuration-card">
        <template #header>
          <div class="card-heading">
            <div>
              <strong>{{ selectedReport.title }}</strong>
              <p>{{ selectedReport.description }}</p>
            </div>
            <el-tag effect="plain">{{ selectedReport.schema_version }}</el-tag>
          </div>
        </template>

        <el-descriptions :column="2" border class="report-meta">
          <el-descriptions-item label="Report Type">{{ selectedReport.report_type }}</el-descriptions-item>
          <el-descriptions-item label="Snapshot">{{ selectedReport.snapshot_semantics }}</el-descriptions-item>
          <el-descriptions-item label="支持格式">
            {{ selectedReport.supported_formats.join(' / ') }}
          </el-descriptions-item>
          <el-descriptions-item label="字段数量">{{ selectedReport.columns.length }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">筛选条件</el-divider>
        <el-form label-position="top" class="filter-grid">
          <el-form-item v-for="filter in selectedReport.filters" :key="filter.key">
            <template #label>
              {{ filter.key }}
              <el-tag size="small" effect="plain">{{ filter.value_type }}</el-tag>
            </template>
            <el-select
              v-if="filter.value_type === 'ENUM'"
              v-model="filterInputs[filter.key]"
              clearable
              placeholder="请选择"
            >
              <el-option v-for="value in filter.allowed_values" :key="value" :label="value" :value="value" />
            </el-select>
            <el-input
              v-else
              v-model="filterInputs[filter.key]"
              clearable
              :placeholder="filter.value_type === 'DATETIME' ? 'ISO 8601（含时区）' : '请输入'"
            />
          </el-form-item>
          <el-form-item label="analysis_as_of">
            <el-input v-model="analysisAsOf" clearable placeholder="可选：ISO 8601（含时区）" />
          </el-form-item>
          <el-form-item label="预览行数">
            <el-input-number v-model="pageSize" :min="1" :max="100" controls-position="right" />
          </el-form-item>
        </el-form>
        <div class="form-actions">
          <el-button type="primary" :loading="previewStatus === 'loading'" @click="loadPreview">
            查看预览
          </el-button>
        </div>
      </el-card>
    </section>

    <el-alert
      v-if="previewError"
      class="section-alert"
      type="error"
      show-icon
      :closable="false"
      :title="previewError"
    />

    <el-card v-if="preview" shadow="never" class="preview-card">
      <template #header>
        <div class="card-heading">
          <div>
            <strong>报告预览</strong>
            <p>数据截点：{{ preview.metadata.snapshot.analysis_as_of }}</p>
          </div>
          <div class="preview-actions">
            <el-select v-model="exportFormat" class="format-select" aria-label="导出格式">
              <el-option
                v-for="format in selectedReport?.supported_formats ?? []"
                :key="format"
                :label="format"
                :value="format"
              />
            </el-select>
            <el-button type="primary" plain :disabled="!exportFormat" @click="openExportConfirmation">
              确认导出
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        class="availability-alert"
        :type="availabilityType(preview.availability.status)"
        show-icon
        :closable="false"
      >
        <template #title>
          Availability：{{ preview.availability.status }}
        </template>
        <p v-if="preview.availability.message">{{ preview.availability.message }}</p>
        <p v-if="preview.availability.reasons.length">
          Reasons：{{ preview.availability.reasons.join('、') }}
        </p>
      </el-alert>

      <el-descriptions :column="3" border class="snapshot-panel">
        <el-descriptions-item label="analysis_as_of">
          {{ preview.metadata.snapshot.analysis_as_of }}
        </el-descriptions-item>
        <el-descriptions-item label="timezone">{{ preview.metadata.snapshot.timezone }}</el-descriptions-item>
        <el-descriptions-item label="semantics">{{ preview.metadata.snapshot.semantics }}</el-descriptions-item>
        <el-descriptions-item label="总行数">{{ preview.metadata.total_rows }}</el-descriptions-item>
        <el-descriptions-item label="Schema">{{ preview.metadata.schema_version }}</el-descriptions-item>
        <el-descriptions-item label="来源版本">
          {{ preview.metadata.source_versions.join('、') || '—' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-table :data="preview.rows" border stripe empty-text="报告无匹配数据" class="preview-table">
        <el-table-column
          v-for="column in preview.columns"
          :key="column.name"
          :label="column.display_name"
          :prop="column.name"
          min-width="150"
          show-overflow-tooltip
        >
          <template #default="scope">{{ displayCell(scope.row[column.name]) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="exportDialogVisible" title="确认导出报告" width="min(520px, 92vw)">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="Report Type">{{ selectedReportType }}</el-descriptions-item>
        <el-descriptions-item label="Format">{{ exportFormat }}</el-descriptions-item>
        <el-descriptions-item label="确认行数">{{ confirmationCount ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="数据截点">
          {{ preview?.metadata.snapshot.analysis_as_of ?? '—' }}
        </el-descriptions-item>
      </el-descriptions>
      <el-alert
        class="export-notice"
        type="info"
        :closable="false"
        title="导出限制由服务端策略校验；前端不会绕过确认或生成文件。"
      />
      <el-alert
        v-if="downloadMessage && downloadStatus === 'error'"
        class="export-notice"
        type="error"
        :closable="false"
        :title="downloadMessage"
      />
      <template #footer>
        <el-button :disabled="downloadStatus === 'loading'" @click="exportDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="downloadStatus === 'loading'" @click="confirmExport">
          确认并下载
        </el-button>
      </template>
    </el-dialog>

    <el-alert
      v-if="downloadMessage && downloadStatus === 'success'"
      class="download-status"
      type="success"
      show-icon
      :closable="false"
      :title="downloadMessage"
    />
  </main>
</template>

<style scoped>
.reports-page {
  min-height: 100vh;
  padding: 28px;
  background: var(--el-bg-color-page);
}

.page-header,
.card-heading,
.preview-actions,
.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header {
  align-items: flex-start;
  margin-bottom: 24px;
}

.eyebrow,
.subtitle,
.card-heading p {
  margin: 0;
  color: var(--el-text-color-secondary);
}

.eyebrow {
  margin-bottom: 8px;
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1 {
  margin: 0 0 8px;
  font-size: clamp(26px, 3vw, 38px);
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.8fr) minmax(0, 2fr);
  gap: 20px;
}

.catalog-list {
  display: grid;
  gap: 10px;
  width: 100%;
}

.catalog-option :deep(.el-radio-button__inner) {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  width: 100%;
  gap: 6px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  text-align: left;
  white-space: normal;
}

.catalog-option small {
  color: var(--el-text-color-secondary);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.filter-grid :deep(.el-select),
.filter-grid :deep(.el-input-number) {
  width: 100%;
}

.form-actions {
  justify-content: flex-end;
}

.section-alert,
.preview-card,
.download-status {
  margin-top: 20px;
}

.report-meta,
.snapshot-panel,
.availability-alert {
  margin-bottom: 20px;
}

.availability-alert p {
  margin: 6px 0 0;
}

.format-select {
  width: 110px;
}

.preview-table {
  width: 100%;
}

.export-notice {
  margin-top: 16px;
}

@media (max-width: 860px) {
  .reports-page {
    padding: 18px;
  }

  .workspace-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .page-header,
  .card-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .preview-actions {
    width: 100%;
  }
}
</style>
