-- Migration V004: import and data-quality governance tables
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE import_jobs (
  import_job_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  initiated_by_user_id BIGINT UNSIGNED NOT NULL,
  import_type VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING_VALIDATION',
  original_filename VARCHAR(255) NOT NULL,
  file_format VARCHAR(16) NOT NULL,
  file_hash CHAR(64) NULL,
  total_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  valid_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  error_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  imported_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  started_at DATETIME(6) NULL,
  finished_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (import_job_id),
  CONSTRAINT fk_import_jobs_user FOREIGN KEY (initiated_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_import_jobs_type CHECK (import_type IN ('MASTER_DATA', 'SNAPSHOT')),
  CONSTRAINT chk_import_jobs_status CHECK (status IN ('PENDING_VALIDATION', 'VALIDATION_FAILED', 'READY', 'IMPORTING', 'COMPLETED', 'COMPLETED_WITH_ERRORS', 'FAILED')),
  CONSTRAINT chk_import_jobs_format CHECK (file_format IN ('CSV', 'XLSX')),
  CONSTRAINT chk_import_jobs_filename CHECK (CHAR_LENGTH(TRIM(original_filename)) > 0),
  CONSTRAINT chk_import_jobs_row_totals CHECK (valid_rows + error_rows <= total_rows AND imported_rows <= valid_rows),
  CONSTRAINT chk_import_jobs_times CHECK (finished_at IS NULL OR started_at IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE import_errors (
  import_error_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  import_job_id BIGINT UNSIGNED NOT NULL,
  row_number BIGINT UNSIGNED NULL,
  column_name VARCHAR(128) NULL,
  error_code VARCHAR(64) NOT NULL,
  error_message VARCHAR(1000) NOT NULL,
  raw_value TEXT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (import_error_id),
  CONSTRAINT fk_import_errors_job FOREIGN KEY (import_job_id) REFERENCES import_jobs (import_job_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_import_errors_row CHECK (row_number IS NULL OR row_number > 0),
  CONSTRAINT chk_import_errors_code CHECK (CHAR_LENGTH(TRIM(error_code)) > 0),
  CONSTRAINT chk_import_errors_message CHECK (CHAR_LENGTH(TRIM(error_message)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE drama_metric_snapshots
  ADD CONSTRAINT fk_snapshots_source_import_job
  FOREIGN KEY (source_import_job_id)
  REFERENCES import_jobs (import_job_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE data_quality_issues (
  data_quality_issue_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  target_snapshot_revision_id BIGINT UNSIGNED NULL,
  target_drama_platform_id BIGINT UNSIGNED NULL,
  target_drama_id BIGINT UNSIGNED NULL,
  issue_type VARCHAR(64) NOT NULL,
  severity VARCHAR(16) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
  source VARCHAR(32) NOT NULL,
  rule_code VARCHAR(64) NOT NULL,
  evidence_summary TEXT NOT NULL,
  first_detected_at DATETIME(6) NOT NULL,
  last_detected_at DATETIME(6) NOT NULL,
  occurrence_count INT UNSIGNED NOT NULL DEFAULT 1,
  handled_by_user_id BIGINT UNSIGNED NULL,
  handled_at DATETIME(6) NULL,
  handling_note TEXT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (data_quality_issue_id),
  CONSTRAINT fk_quality_issues_snapshot_revision FOREIGN KEY (target_snapshot_revision_id) REFERENCES drama_metric_snapshot_revisions (snapshot_revision_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_quality_issues_drama_platform FOREIGN KEY (target_drama_platform_id) REFERENCES drama_platforms (drama_platform_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_quality_issues_drama FOREIGN KEY (target_drama_id) REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_quality_issues_handler FOREIGN KEY (handled_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_quality_issues_one_target CHECK ((target_snapshot_revision_id IS NOT NULL) + (target_drama_platform_id IS NOT NULL) + (target_drama_id IS NOT NULL) = 1),
  CONSTRAINT chk_quality_issues_type CHECK (issue_type IN ('MISSING_REQUIRED_DATA', 'INVALID_NEGATIVE_VALUE', 'INVALID_RANKING', 'INVALID_TIMESTAMP', 'UNKNOWN_REFERENCE', 'DUPLICATE_RECORD', 'CONFLICTING_SNAPSHOT', 'CUMULATIVE_REGRESSION', 'STATISTICAL_SPIKE', 'STATISTICAL_DROP', 'OTHER')),
  CONSTRAINT chk_quality_issues_severity CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
  CONSTRAINT chk_quality_issues_status CHECK (status IN ('OPEN', 'CONFIRMED', 'RESOLVED', 'IGNORED')),
  CONSTRAINT chk_quality_issues_source CHECK (source IN ('MANUAL_ENTRY', 'IMPORT', 'STATISTICAL_DETECTION', 'BUSINESS_RULE')),
  CONSTRAINT chk_quality_issues_rule CHECK (CHAR_LENGTH(TRIM(rule_code)) > 0),
  CONSTRAINT chk_quality_issues_evidence CHECK (CHAR_LENGTH(TRIM(evidence_summary)) > 0),
  CONSTRAINT chk_quality_issues_occurrences CHECK (occurrence_count >= 1),
  CONSTRAINT chk_quality_issues_detection_time CHECK (last_detected_at >= first_detected_at),
  CONSTRAINT chk_quality_issues_handling_tuple CHECK ((handled_by_user_id IS NULL AND handled_at IS NULL AND handling_note IS NULL) OR (handled_by_user_id IS NOT NULL AND handled_at IS NOT NULL AND handling_note IS NOT NULL AND CHAR_LENGTH(TRIM(handling_note)) > 0)),
  CONSTRAINT chk_quality_issues_closed_handling CHECK (status NOT IN ('RESOLVED', 'IGNORED') OR (handled_by_user_id IS NOT NULL AND handled_at IS NOT NULL AND handling_note IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
