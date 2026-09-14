-- Migration V008: scoped composite score result table
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE drama_scores (
  score_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_id BIGINT UNSIGNED NOT NULL,
  score_date DATE NOT NULL,
  score_scope_type VARCHAR(16) NOT NULL DEFAULT 'ALL',
  score_scope_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
  analysis_as_of DATETIME(6) NOT NULL,
  heat_score DECIMAL(5,2) NOT NULL,
  growth_score DECIMAL(5,2) NOT NULL,
  engagement_score DECIMAL(5,2) NOT NULL,
  lifecycle_score DECIMAL(5,2) NOT NULL,
  total_score DECIMAL(5,2) NOT NULL,
  level CHAR(1) NOT NULL,
  algorithm_version VARCHAR(64) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (score_id),
  CONSTRAINT uq_drama_scores_identity UNIQUE (
    drama_id,
    score_date,
    algorithm_version,
    score_scope_type,
    score_scope_id
  ),
  CONSTRAINT fk_drama_scores_drama FOREIGN KEY (drama_id) REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_drama_scores_scope CHECK (
    score_scope_type = 'ALL' AND score_scope_id = 0
  ),
  CONSTRAINT chk_drama_scores_components CHECK (
    heat_score BETWEEN 0 AND 100
    AND growth_score BETWEEN 0 AND 100
    AND engagement_score BETWEEN 0 AND 100
    AND lifecycle_score BETWEEN 0 AND 100
  ),
  CONSTRAINT chk_drama_scores_total CHECK (total_score BETWEEN 0 AND 100),
  CONSTRAINT chk_drama_scores_level CHECK (level IN ('S', 'A', 'B', 'C')),
  CONSTRAINT chk_drama_scores_algorithm_version CHECK (
    CHAR_LENGTH(TRIM(algorithm_version)) > 0
  ),
  INDEX idx_drama_scores_ranking (
    score_date,
    algorithm_version,
    score_scope_type,
    score_scope_id,
    total_score DESC,
    drama_id
  ),
  INDEX idx_drama_scores_level_distribution (
    score_date,
    algorithm_version,
    score_scope_type,
    score_scope_id,
    level
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
