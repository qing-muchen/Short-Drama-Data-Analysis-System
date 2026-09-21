-- Migration V012: operation action and resolution history
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE operation_actions (
  action_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_id BIGINT UNSIGNED NULL,
  title VARCHAR(200) NOT NULL,
  description TEXT NULL,
  priority VARCHAR(16) NOT NULL DEFAULT 'MEDIUM',
  status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
  assignee_user_id BIGINT UNSIGNED NULL,
  created_by_user_id BIGINT UNSIGNED NOT NULL,
  due_date DATE NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (action_id),
  CONSTRAINT fk_operation_actions_drama FOREIGN KEY (drama_id)
    REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_actions_assignee FOREIGN KEY (assignee_user_id)
    REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_actions_creator FOREIGN KEY (created_by_user_id)
    REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_operation_actions_title CHECK (CHAR_LENGTH(TRIM(title)) > 0),
  CONSTRAINT chk_operation_actions_priority CHECK (
    priority IN ('LOW', 'MEDIUM', 'HIGH')
  ),
  CONSTRAINT chk_operation_actions_status CHECK (
    status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
  ),
  INDEX idx_operation_actions_status_priority_due (status, priority, due_date),
  INDEX idx_operation_actions_assignee_status (assignee_user_id, status, due_date),
  INDEX idx_operation_actions_drama_status (drama_id, status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE operation_action_sources (
  source_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  action_id BIGINT UNSIGNED NOT NULL,
  source_type VARCHAR(16) NOT NULL,
  source_reference_id BIGINT UNSIGNED NULL,
  source_evidence_summary TEXT NOT NULL,
  source_analysis_as_of DATETIME(6) NULL,
  source_algorithm_version VARCHAR(64) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (source_id),
  CONSTRAINT fk_operation_action_sources_action FOREIGN KEY (action_id)
    REFERENCES operation_actions (action_id) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT chk_operation_action_sources_type CHECK (
    source_type IN ('ANOMALY', 'QUALITY', 'SCORE', 'MANUAL')
  ),
  CONSTRAINT chk_operation_action_sources_reference CHECK (
    (source_type = 'MANUAL' AND source_reference_id IS NULL)
    OR (source_type <> 'MANUAL' AND source_reference_id IS NOT NULL AND source_reference_id > 0)
  ),
  CONSTRAINT chk_operation_action_sources_summary CHECK (
    CHAR_LENGTH(TRIM(source_evidence_summary)) > 0
  ),
  CONSTRAINT chk_operation_action_sources_algorithm CHECK (
    source_algorithm_version IS NULL OR CHAR_LENGTH(TRIM(source_algorithm_version)) > 0
  ),
  CONSTRAINT uq_operation_action_sources_identity UNIQUE (
    action_id,
    source_type,
    source_reference_id
  ),
  INDEX idx_operation_action_sources_reference (source_type, source_reference_id, action_id),
  INDEX idx_operation_action_sources_action (action_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE operation_action_history (
  history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  action_id BIGINT UNSIGNED NOT NULL,
  event_type VARCHAR(24) NOT NULL,
  old_status VARCHAR(16) NULL,
  new_status VARCHAR(16) NULL,
  operator_user_id BIGINT UNSIGNED NOT NULL,
  comment TEXT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (history_id),
  CONSTRAINT fk_operation_action_history_action FOREIGN KEY (action_id)
    REFERENCES operation_actions (action_id) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_action_history_operator FOREIGN KEY (operator_user_id)
    REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_operation_action_history_event_type CHECK (
    event_type IN ('CREATE', 'ASSIGN', 'STATUS_CHANGE', 'COMMENT', 'CLOSE')
  ),
  CONSTRAINT chk_operation_action_history_old_status CHECK (
    old_status IS NULL OR old_status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
  ),
  CONSTRAINT chk_operation_action_history_new_status CHECK (
    new_status IS NULL OR new_status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
  ),
  INDEX idx_operation_action_history_action_created (action_id, created_at, history_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
