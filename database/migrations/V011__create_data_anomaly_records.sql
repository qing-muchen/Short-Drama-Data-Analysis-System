-- Migration V011: rule-based anomaly detection findings
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE data_anomaly_records (
  anomaly_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_id BIGINT UNSIGNED NOT NULL,
  metric_type VARCHAR(32) NOT NULL,
  anomaly_type VARCHAR(64) NOT NULL,
  severity CHAR(1) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
  analysis_as_of DATETIME(6) NOT NULL,
  detected_at DATETIME(6) NOT NULL,
  algorithm_version VARCHAR(64) NOT NULL,
  baseline_value DECIMAL(18,4) NULL,
  actual_value DECIMAL(18,4) NULL,
  deviation_value DECIMAL(18,4) NULL,
  evidence_summary TEXT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (anomaly_id),
  CONSTRAINT uq_data_anomaly_records_identity UNIQUE (
    drama_id,
    metric_type,
    anomaly_type,
    analysis_as_of,
    algorithm_version
  ),
  CONSTRAINT fk_data_anomaly_records_drama FOREIGN KEY (drama_id)
    REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_data_anomaly_records_metric_type CHECK (
    metric_type IN ('PLAY_COUNT', 'ENGAGEMENT_RATE')
  ),
  CONSTRAINT chk_data_anomaly_records_anomaly_type CHECK (
    anomaly_type IN (
      'PLAY_COUNT_GROWTH_ANOMALY',
      'PLAY_COUNT_DROP_ANOMALY',
      'ENGAGEMENT_RATE_ANOMALY',
      'DATA_SPIKE_ANOMALY'
    )
  ),
  CONSTRAINT chk_data_anomaly_records_severity CHECK (severity IN ('A', 'B', 'C')),
  CONSTRAINT chk_data_anomaly_records_status CHECK (
    status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'IGNORED')
  ),
  CONSTRAINT chk_data_anomaly_records_algorithm_version CHECK (
    CHAR_LENGTH(TRIM(algorithm_version)) > 0
  ),
  INDEX idx_anomaly_query (
    analysis_as_of,
    status,
    severity,
    metric_type
  ),
  INDEX idx_anomaly_trend (
    drama_id,
    analysis_as_of
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
