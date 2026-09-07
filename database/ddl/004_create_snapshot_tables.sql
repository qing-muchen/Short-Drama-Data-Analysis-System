-- TASK-P3-06R / Observation slots and immutable snapshot revisions
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE drama_metric_snapshots (
  snapshot_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_platform_id BIGINT UNSIGNED NOT NULL,
  snapshot_time DATETIME(6) NOT NULL,
  current_revision_id BIGINT UNSIGNED NULL,
  source_import_job_id BIGINT UNSIGNED NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (snapshot_id),
  CONSTRAINT uq_snapshots_platform_time UNIQUE (drama_platform_id, snapshot_time),
  CONSTRAINT uq_snapshots_current_revision UNIQUE (current_revision_id),
  CONSTRAINT fk_snapshots_drama_platform FOREIGN KEY (drama_platform_id) REFERENCES drama_platforms (drama_platform_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE drama_metric_snapshot_revisions (
  snapshot_revision_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  snapshot_id BIGINT UNSIGNED NOT NULL,
  version_no INT UNSIGNED NOT NULL,
  previous_revision_id BIGINT UNSIGNED NULL,
  revision_action VARCHAR(16) NOT NULL,
  play_count BIGINT UNSIGNED NULL,
  like_count BIGINT UNSIGNED NULL,
  comment_count BIGINT UNSIGNED NULL,
  favorite_count BIGINT UNSIGNED NULL,
  share_count BIGINT UNSIGNED NULL,
  ranking INT UNSIGNED NULL,
  change_reason TEXT NULL,
  changed_by_user_id BIGINT UNSIGNED NOT NULL,
  changed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (snapshot_revision_id),
  CONSTRAINT uq_snapshot_revisions_version UNIQUE (snapshot_id, version_no),
  CONSTRAINT uq_snapshot_revisions_identity UNIQUE (snapshot_id, snapshot_revision_id),
  CONSTRAINT uq_snapshot_revisions_previous UNIQUE (previous_revision_id),
  CONSTRAINT fk_snapshot_revisions_snapshot FOREIGN KEY (snapshot_id) REFERENCES drama_metric_snapshots (snapshot_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_snapshot_revisions_previous_same_slot FOREIGN KEY (snapshot_id, previous_revision_id) REFERENCES drama_metric_snapshot_revisions (snapshot_id, snapshot_revision_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_snapshot_revisions_user FOREIGN KEY (changed_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_snapshot_revisions_version CHECK (version_no >= 1),
  CONSTRAINT chk_snapshot_revisions_action CHECK (revision_action IN ('INITIAL', 'CORRECTION', 'VOID')),
  CONSTRAINT chk_snapshot_revisions_chain CHECK (
    (revision_action = 'INITIAL' AND version_no = 1 AND previous_revision_id IS NULL)
    OR (revision_action IN ('CORRECTION', 'VOID') AND version_no > 1 AND previous_revision_id IS NOT NULL)
  ),
  CONSTRAINT chk_snapshot_revisions_metrics CHECK (
    revision_action = 'VOID' OR play_count IS NOT NULL
  ),
  CONSTRAINT chk_snapshot_revisions_reason CHECK (
    revision_action = 'INITIAL'
    OR (change_reason IS NOT NULL AND CHAR_LENGTH(TRIM(change_reason)) > 0)
  ),
  CONSTRAINT chk_snapshot_revisions_ranking CHECK (ranking IS NULL OR ranking > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE drama_metric_snapshots
  ADD CONSTRAINT fk_snapshots_current_revision
  FOREIGN KEY (snapshot_id, current_revision_id)
  REFERENCES drama_metric_snapshot_revisions (snapshot_id, snapshot_revision_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

DELIMITER $$

CREATE TRIGGER trg_snapshot_revisions_no_update
BEFORE UPDATE ON drama_metric_snapshot_revisions
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Snapshot revisions are immutable; append a new revision instead';
END$$

CREATE TRIGGER trg_snapshot_revisions_no_delete
BEFORE DELETE ON drama_metric_snapshot_revisions
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Snapshot revision history cannot be deleted';
END$$

DELIMITER ;
