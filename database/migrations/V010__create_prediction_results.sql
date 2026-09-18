-- Migration V010: drama-level operating trend prediction results
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE prediction_results (
  prediction_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_id BIGINT UNSIGNED NOT NULL,
  metric_type VARCHAR(32) NOT NULL,
  prediction_date DATE NOT NULL,
  target_date DATE NOT NULL,
  predicted_value DECIMAL(20,2) NOT NULL,
  algorithm_version VARCHAR(64) NOT NULL,
  analysis_as_of DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (prediction_id),
  CONSTRAINT uq_prediction_results_identity UNIQUE (
    drama_id,
    metric_type,
    target_date,
    algorithm_version
  ),
  CONSTRAINT fk_prediction_results_drama FOREIGN KEY (drama_id) REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_prediction_results_metric_type CHECK (
    CHAR_LENGTH(TRIM(metric_type)) > 0
  ),
  CONSTRAINT chk_prediction_results_predicted_value CHECK (
    predicted_value >= 0
  ),
  CONSTRAINT chk_prediction_results_algorithm_version CHECK (
    CHAR_LENGTH(TRIM(algorithm_version)) > 0
  ),
  INDEX idx_prediction_results_drama_metric_target (
    drama_id,
    metric_type,
    target_date
  ),
  INDEX idx_prediction_results_metric_target (
    metric_type,
    target_date
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
