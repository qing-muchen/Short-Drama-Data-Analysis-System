-- Migration V007: additive batch-import orchestration metadata
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE import_batches (
  import_batch_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  batch_code VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
  created_by_user_id BIGINT UNSIGNED NOT NULL,
  total_files INT UNSIGNED NOT NULL DEFAULT 0,
  total_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  valid_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  error_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  imported_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  validation_started_at DATETIME(6) NULL,
  validated_at DATETIME(6) NULL,
  import_started_at DATETIME(6) NULL,
  completed_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (import_batch_id),
  CONSTRAINT uq_import_batches_code UNIQUE (batch_code),
  CONSTRAINT fk_import_batches_user FOREIGN KEY (created_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_import_batches_code CHECK (CHAR_LENGTH(TRIM(batch_code)) > 0),
  CONSTRAINT chk_import_batches_status CHECK (status IN ('CREATED', 'UPLOADING', 'VALIDATING', 'READY', 'IMPORTING', 'COMPLETED', 'VALIDATION_FAILED', 'IMPORT_FAILED')),
  CONSTRAINT chk_import_batches_row_totals CHECK (valid_rows + error_rows <= total_rows AND imported_rows <= valid_rows),
  CONSTRAINT chk_import_batches_validation_times CHECK (validated_at IS NULL OR validation_started_at IS NOT NULL),
  CONSTRAINT chk_import_batches_completion_time CHECK (completed_at IS NULL OR status IN ('COMPLETED', 'VALIDATION_FAILED', 'IMPORT_FAILED')),
  INDEX idx_import_batches_status_created (status, created_at),
  INDEX idx_import_batches_user_created (created_by_user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE import_jobs
  ADD COLUMN import_batch_id BIGINT UNSIGNED NULL AFTER import_job_id,
  ADD COLUMN batch_sequence SMALLINT UNSIGNED NULL AFTER import_batch_id,
  ADD COLUMN batch_file_type VARCHAR(32) NULL AFTER batch_sequence,
  ADD CONSTRAINT fk_import_jobs_batch FOREIGN KEY (import_batch_id) REFERENCES import_batches (import_batch_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT uq_import_jobs_batch_sequence UNIQUE (import_batch_id, batch_sequence),
  ADD CONSTRAINT uq_import_jobs_batch_file_type UNIQUE (import_batch_id, batch_file_type),
  ADD CONSTRAINT chk_import_jobs_batch_fields CHECK (
    (import_batch_id IS NULL AND batch_sequence IS NULL AND batch_file_type IS NULL)
    OR
    (import_batch_id IS NOT NULL AND batch_sequence IS NOT NULL AND batch_sequence > 0
      AND batch_file_type IN ('MASTER_DATA', 'DRAMA_TAGS', 'DRAMA_PLATFORMS', 'SNAPSHOT'))
  ),
  ADD INDEX idx_import_jobs_batch_status (import_batch_id, status);
