export type BatchImportStatus =
  | 'CREATED'
  | 'UPLOADING'
  | 'VALIDATING'
  | 'READY'
  | 'IMPORTING'
  | 'COMPLETED'
  | 'VALIDATION_FAILED'
  | 'IMPORT_FAILED'

export type BatchFileType =
  | 'MASTER_DATA'
  | 'DRAMA_TAGS'
  | 'DRAMA_PLATFORMS'
  | 'SNAPSHOT'

export interface BatchImportFile {
  import_job_id: number
  batch_sequence: number
  batch_file_type: BatchFileType
  original_filename: string
  file_format: 'CSV'
  file_hash: string
  status: string
  total_rows: number
  valid_rows: number
  skipped_rows: number
  error_rows: number
  imported_rows: number
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export interface ImportBatch {
  import_batch_id: number
  batch_code: string
  status: BatchImportStatus
  created_by_user_id: number
  total_files: number
  total_rows: number
  valid_rows: number
  skipped_rows: number
  error_rows: number
  imported_rows: number
  validation_started_at: string | null
  validated_at: string | null
  import_started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  files: BatchImportFile[]
}
