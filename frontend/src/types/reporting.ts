export type ReportType =
  | 'DRAMA_CATALOG'
  | 'SCORE_RESULTS'
  | 'DATA_QUALITY_RESULTS'
  | 'PREDICTION_RESULTS'
  | 'ANOMALY_RECORDS'
  | 'OPERATION_ACTIONS'

export type ExportFormat = 'CSV' | 'XLSX'

export type ReportAvailabilityStatus =
  | 'AVAILABLE'
  | 'PARTIAL'
  | 'EMPTY'
  | 'INSUFFICIENT'
  | 'NOT_AVAILABLE'

export type ReportAvailabilityReason =
  | 'NO_MATCHING_DATA'
  | 'MISSING_SOURCE'
  | 'UNSUPPORTED_FILTER'
  | 'SOURCE_VERSION_MISMATCH'
  | 'LIMIT_EXCEEDED'
  | 'EXPORT_FAILED'
  | 'INSUFFICIENT_DATA'

export type ReportColumnType =
  | 'STRING'
  | 'INTEGER'
  | 'DECIMAL'
  | 'BOOLEAN'
  | 'DATE'
  | 'DATETIME'

export type ReportFilterValueType = 'STRING' | 'INTEGER' | 'DATETIME' | 'ENUM'

export type SnapshotSemantics = 'AS_OF_RECONSTRUCTED' | 'CURRENT_STATE_AT_REQUEST'

export type ReportCellValue = string | number | boolean | null
export type ReportRow = Record<string, ReportCellValue>
export type ReportFilterValue = string | number
export type ReportFilters = Record<string, ReportFilterValue>

export interface ReportColumn {
  name: string
  display_name: string
  data_type: ReportColumnType
  nullable: boolean
  format: string | null
}

export interface ReportFilterDefinition {
  key: string
  value_type: ReportFilterValueType
  required: boolean
  default: string | number | null
  allowed_values: string[]
}

export interface ReportCatalog {
  report_type: ReportType
  title: string
  description: string
  schema_version: string
  columns: ReportColumn[]
  filters: ReportFilterDefinition[]
  supported_formats: ExportFormat[]
  snapshot_semantics: SnapshotSemantics
}

export interface ReportAvailability {
  status: ReportAvailabilityStatus
  reasons: ReportAvailabilityReason[]
  message: string | null
}

export interface AnalysisSnapshot {
  requested_at: string
  analysis_as_of: string
  timezone: string
  semantics: SnapshotSemantics
}

export interface ReportMetadata {
  report_type: ReportType
  title: string
  description: string
  schema_version: string
  snapshot: AnalysisSnapshot
  total_rows: number
  source_versions: string[]
}

export interface ReportPreview {
  metadata: ReportMetadata
  columns: ReportColumn[]
  rows: ReportRow[]
  availability: ReportAvailability
}

export interface ReportPreviewParams {
  report_type: ReportType
  filters?: ReportFilters
  analysis_as_of?: string
  page_size?: number
}

export interface ReportExportParams {
  report_type: ReportType
  filters?: ReportFilters
  analysis_as_of?: string
  export_format: ExportFormat
  confirmation?: number
}

export interface ReportDownload {
  blob: Blob
  filename: string
  mime_type: string
}

export type DownloadStatus = 'idle' | 'loading' | 'success' | 'error'

export interface ReportingApiErrorBody {
  code?: string
  message?: string
  details?: Record<string, unknown> | null
}
