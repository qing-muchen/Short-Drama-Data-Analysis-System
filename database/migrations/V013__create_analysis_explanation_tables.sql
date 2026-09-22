-- Migration V013: analysis explanation and data lineage center
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE analysis_explanations (
  explanation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  entity_type VARCHAR(24) NOT NULL,
  entity_id BIGINT UNSIGNED NOT NULL,
  module_type VARCHAR(32) NOT NULL,
  summary TEXT NOT NULL,
  detail JSON NOT NULL,
  algorithm_version VARCHAR(64) NOT NULL DEFAULT 'N/A',
  rule_set_version VARCHAR(64) NOT NULL DEFAULT 'N/A',
  analysis_as_of DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (explanation_id),
  CONSTRAINT uq_analysis_explanations_identity UNIQUE (
    module_type, entity_type, entity_id, analysis_as_of,
    algorithm_version, rule_set_version
  ),
  CONSTRAINT chk_analysis_explanations_entity_type CHECK (
    entity_type IN ('SCORE', 'QUALITY', 'PREDICTION', 'ANOMALY', 'ACTION')
  ),
  CONSTRAINT chk_analysis_explanations_module_type CHECK (
    module_type IN ('SCORE', 'QUALITY', 'PREDICTION', 'ANOMALY', 'OPERATION_ACTION')
  ),
  CONSTRAINT chk_analysis_explanations_entity_id CHECK (entity_id > 0),
  CONSTRAINT chk_analysis_explanations_summary CHECK (
    CHAR_LENGTH(TRIM(summary)) > 0
  ),
  CONSTRAINT chk_analysis_explanations_algorithm_version CHECK (
    CHAR_LENGTH(TRIM(algorithm_version)) > 0
  ),
  CONSTRAINT chk_analysis_explanations_rule_set_version CHECK (
    CHAR_LENGTH(TRIM(rule_set_version)) > 0
  ),
  INDEX idx_analysis_explanations_entity (
    entity_type, entity_id, analysis_as_of
  ),
  INDEX idx_analysis_explanations_module (
    module_type, analysis_as_of
  ),
  INDEX idx_analysis_explanations_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE analysis_lineage_records (
  lineage_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  target_type VARCHAR(24) NOT NULL,
  target_id BIGINT UNSIGNED NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  source_id BIGINT UNSIGNED NOT NULL,
  relationship_type VARCHAR(32) NOT NULL,
  analysis_as_of DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (lineage_id),
  CONSTRAINT uq_analysis_lineage_records_identity UNIQUE (
    target_type, target_id, source_type, source_id,
    relationship_type, analysis_as_of
  ),
  CONSTRAINT chk_analysis_lineage_records_target_type CHECK (
    target_type IN (
      'EXPLANATION', 'SCORE', 'QUALITY', 'PREDICTION', 'ANOMALY', 'ACTION'
    )
  ),
  CONSTRAINT chk_analysis_lineage_records_source_type CHECK (
    source_type IN (
      'METRIC', 'SNAPSHOT', 'RULE', 'PREDICTION_INPUT', 'ANOMALY_EVIDENCE'
    )
  ),
  CONSTRAINT chk_analysis_lineage_records_relationship_type CHECK (
    relationship_type IN (
      'DERIVED_FROM', 'USES_METRIC', 'USES_RULE', 'USES_WINDOW'
    )
  ),
  CONSTRAINT chk_analysis_lineage_records_target_id CHECK (target_id > 0),
  CONSTRAINT chk_analysis_lineage_records_source_id CHECK (source_id > 0),
  INDEX idx_analysis_lineage_records_target (
    target_type, target_id, analysis_as_of
  ),
  INDEX idx_analysis_lineage_records_source (source_type, source_id),
  INDEX idx_analysis_lineage_records_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE metric_dependencies (
  dependency_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  parent_metric VARCHAR(64) NOT NULL,
  child_metric VARCHAR(64) NOT NULL,
  module_type VARCHAR(32) NOT NULL,
  algorithm_version VARCHAR(64) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (dependency_id),
  CONSTRAINT uq_metric_dependencies_identity UNIQUE (
    parent_metric, child_metric, module_type, algorithm_version
  ),
  CONSTRAINT chk_metric_dependencies_parent CHECK (
    CHAR_LENGTH(TRIM(parent_metric)) > 0
  ),
  CONSTRAINT chk_metric_dependencies_child CHECK (
    CHAR_LENGTH(TRIM(child_metric)) > 0
  ),
  CONSTRAINT chk_metric_dependencies_module_type CHECK (
    module_type IN ('SCORE', 'QUALITY', 'PREDICTION', 'ANOMALY', 'OPERATION_ACTION')
  ),
  CONSTRAINT chk_metric_dependencies_algorithm_version CHECK (
    CHAR_LENGTH(TRIM(algorithm_version)) > 0
  ),
  CONSTRAINT chk_metric_dependencies_no_self_reference CHECK (
    parent_metric <> child_metric
  ),
  INDEX idx_metric_dependencies_parent (
    parent_metric, module_type, algorithm_version
  ),
  INDEX idx_metric_dependencies_child (
    child_metric, module_type, algorithm_version
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
