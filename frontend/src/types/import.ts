export type ImportType = 'MASTER_DATA' | 'SNAPSHOT'
export type ImportFileFormat = 'CSV' | 'XLSX'
export type ImportStatus =
  | 'PENDING_VALIDATION'
  | 'VALIDATION_FAILED'
  | 'READY'
  | 'IMPORTING'
  | 'COMPLETED'
  | 'COMPLETED_WITH_ERRORS'
  | 'FAILED'

export interface ImportJob {
  import_job_id: number
  initiated_by_user_id: number
  import_type: ImportType
  status: ImportStatus
  original_filename: string
  file_format: ImportFileFormat
  file_hash: string | null
  total_rows: number
  valid_rows: number
  error_rows: number
  imported_rows: number
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export interface ImportErrorItem {
  import_error_id: number
  import_job_id: number
  source_row_number: number | null
  column_name: string | null
  error_code: string
  error_message: string
  created_at: string
}

export type ImportError = ImportErrorItem
