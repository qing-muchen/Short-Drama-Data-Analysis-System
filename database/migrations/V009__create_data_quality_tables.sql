-- Migration V009: versioned data-quality rules, execution results, and scores
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE data_quality_rules (
  quality_rule_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  rule_code VARCHAR(64) NOT NULL,
  rule_version VARCHAR(32) NOT NULL,
  rule_name VARCHAR(200) NOT NULL,
  dimension VARCHAR(32) NOT NULL,
  target_entity_type VARCHAR(32) NOT NULL,
  evaluator_key VARCHAR(64) NOT NULL,
  scoring_method VARCHAR(32) NOT NULL,
  weight DECIMAL(7,6) NOT NULL,
  severity VARCHAR(16) NOT NULL,
  configuration JSON NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
  valid_from DATETIME(6) NOT NULL,
  valid_to DATETIME(6) NULL,
  description TEXT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (quality_rule_id),
  CONSTRAINT uq_data_quality_rules_code_version UNIQUE (rule_code, rule_version),
  CONSTRAINT chk_data_quality_rules_code CHECK (CHAR_LENGTH(TRIM(rule_code)) > 0),
  CONSTRAINT chk_data_quality_rules_version CHECK (CHAR_LENGTH(TRIM(rule_version)) > 0),
  CONSTRAINT chk_data_quality_rules_name CHECK (CHAR_LENGTH(TRIM(rule_name)) > 0),
  CONSTRAINT chk_data_quality_rules_dimension CHECK (dimension IN ('COMPLETENESS', 'ACCURACY', 'CONSISTENCY', 'TIMELINESS')),
  CONSTRAINT chk_data_quality_rules_target CHECK (target_entity_type IN ('DRAMA', 'DRAMA_PLATFORM', 'SNAPSHOT', 'IMPORT_JOB')),
  CONSTRAINT chk_data_quality_rules_evaluator CHECK (CHAR_LENGTH(TRIM(evaluator_key)) > 0),
  CONSTRAINT chk_data_quality_rules_scoring CHECK (scoring_method IN ('PASS_RATE', 'BUCKET_AVERAGE')),
  CONSTRAINT chk_data_quality_rules_weight CHECK (weight > 0 AND weight <= 1),
  CONSTRAINT chk_data_quality_rules_severity CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
  CONSTRAINT chk_data_quality_rules_status CHECK (status IN ('DRAFT', 'ACTIVE', 'INACTIVE')),
  CONSTRAINT chk_data_quality_rules_validity CHECK (valid_to IS NULL OR valid_to > valid_from),
  INDEX idx_data_quality_rules_active (status, dimension, valid_from, valid_to),
  INDEX idx_data_quality_rules_target (target_entity_type, dimension, status),
  INDEX idx_data_quality_rules_code_status (rule_code, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE data_quality_scores (
  quality_score_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  score_date DATE NOT NULL,
  score_scope_type VARCHAR(16) NOT NULL DEFAULT 'ALL',
  score_scope_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
  analysis_as_of DATETIME(6) NOT NULL,
  completeness_score DECIMAL(5,2) NOT NULL,
  accuracy_score DECIMAL(5,2) NOT NULL,
  consistency_score DECIMAL(5,2) NOT NULL,
  timeliness_score DECIMAL(5,2) NOT NULL,
  total_score DECIMAL(5,2) NOT NULL,
  quality_grade CHAR(1) NOT NULL,
  algorithm_version VARCHAR(64) NOT NULL,
  rule_set_version VARCHAR(64) NOT NULL,
  rule_set_hash CHAR(64) NOT NULL,
  evaluated_entity_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  open_issue_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  source_watermark JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (quality_score_id),
  CONSTRAINT uq_data_quality_scores_identity UNIQUE (
    score_date,
    algorithm_version,
    rule_set_version,
    rule_set_hash,
    score_scope_type,
    score_scope_id
  ),
  CONSTRAINT chk_data_quality_scores_scope CHECK (score_scope_type = 'ALL' AND score_scope_id = 0),
  CONSTRAINT chk_data_quality_scores_dimensions CHECK (
    completeness_score BETWEEN 0 AND 100
    AND accuracy_score BETWEEN 0 AND 100
    AND consistency_score BETWEEN 0 AND 100
    AND timeliness_score BETWEEN 0 AND 100
  ),
  CONSTRAINT chk_data_quality_scores_total CHECK (total_score BETWEEN 0 AND 100),
  CONSTRAINT chk_data_quality_scores_grade CHECK (quality_grade IN ('S', 'A', 'B', 'C')),
  CONSTRAINT chk_data_quality_scores_algorithm CHECK (CHAR_LENGTH(TRIM(algorithm_version)) > 0),
  CONSTRAINT chk_data_quality_scores_rule_set CHECK (CHAR_LENGTH(TRIM(rule_set_version)) > 0),
  CONSTRAINT chk_data_quality_scores_hash CHECK (CHAR_LENGTH(rule_set_hash) = 64),
  CONSTRAINT chk_data_quality_scores_counts CHECK (evaluated_entity_count >= 0 AND open_issue_count >= 0),
  INDEX idx_data_quality_scores_scope_date (score_scope_type, score_scope_id, score_date DESC),
  INDEX idx_data_quality_scores_version_date (algorithm_version, rule_set_version, score_date DESC),
  INDEX idx_data_quality_scores_grade_date (quality_grade, score_date DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE data_quality_rule_results (
  quality_rule_result_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  quality_score_id BIGINT UNSIGNED NOT NULL,
  quality_rule_id BIGINT UNSIGNED NOT NULL,
  result_status VARCHAR(24) NOT NULL,
  applicable_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  passed_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  failed_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  rule_score DECIMAL(5,2) NULL,
  not_applicable_reason VARCHAR(255) NULL,
  evidence_summary VARCHAR(1000) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (quality_rule_result_id),
  CONSTRAINT uq_data_quality_rule_results_score_rule UNIQUE (quality_score_id, quality_rule_id),
  CONSTRAINT fk_data_quality_rule_results_score FOREIGN KEY (quality_score_id) REFERENCES data_quality_scores (quality_score_id) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT fk_data_quality_rule_results_rule FOREIGN KEY (quality_rule_id) REFERENCES data_quality_rules (quality_rule_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_data_quality_rule_results_status CHECK (result_status IN ('APPLIED', 'NOT_APPLICABLE')),
  CONSTRAINT chk_data_quality_rule_results_counts CHECK (applicable_count = passed_count + failed_count),
  CONSTRAINT chk_data_quality_rule_results_score CHECK (rule_score IS NULL OR rule_score BETWEEN 0 AND 100),
  CONSTRAINT chk_data_quality_rule_results_state CHECK (
    (
      result_status = 'APPLIED'
      AND applicable_count > 0
      AND rule_score IS NOT NULL
      AND not_applicable_reason IS NULL
    )
    OR
    (
      result_status = 'NOT_APPLICABLE'
      AND applicable_count = 0
      AND passed_count = 0
      AND failed_count = 0
      AND rule_score IS NULL
      AND not_applicable_reason IS NOT NULL
      AND CHAR_LENGTH(TRIM(not_applicable_reason)) > 0
    )
  ),
  INDEX idx_data_quality_rule_results_score_status (quality_score_id, result_status),
  INDEX idx_data_quality_rule_results_rule_score (quality_rule_id, quality_score_id),
  INDEX idx_data_quality_rule_results_failures (quality_score_id, failed_count DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
