-- Migration V005: immutable business audit log
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE operation_logs (
  operation_log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  actor_user_id BIGINT UNSIGNED NOT NULL,
  target_user_id BIGINT UNSIGNED NULL,
  target_drama_id BIGINT UNSIGNED NULL,
  target_actor_id BIGINT UNSIGNED NULL,
  target_director_id BIGINT UNSIGNED NULL,
  target_company_id BIGINT UNSIGNED NULL,
  target_platform_id BIGINT UNSIGNED NULL,
  target_tag_id BIGINT UNSIGNED NULL,
  target_drama_actor_id BIGINT UNSIGNED NULL,
  target_drama_director_id BIGINT UNSIGNED NULL,
  target_drama_company_id BIGINT UNSIGNED NULL,
  target_drama_tag_id BIGINT UNSIGNED NULL,
  target_drama_platform_id BIGINT UNSIGNED NULL,
  target_snapshot_id BIGINT UNSIGNED NULL,
  target_snapshot_revision_id BIGINT UNSIGNED NULL,
  target_import_job_id BIGINT UNSIGNED NULL,
  target_data_quality_issue_id BIGINT UNSIGNED NULL,
  operation_type VARCHAR(64) NOT NULL,
  result_status VARCHAR(16) NOT NULL,
  summary VARCHAR(1000) NOT NULL,
  request_id VARCHAR(64) NULL,
  occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (operation_log_id),
  CONSTRAINT fk_operation_logs_actor_user FOREIGN KEY (actor_user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_user FOREIGN KEY (target_user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_drama FOREIGN KEY (target_drama_id) REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_actor FOREIGN KEY (target_actor_id) REFERENCES actors (actor_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_director FOREIGN KEY (target_director_id) REFERENCES directors (director_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_company FOREIGN KEY (target_company_id) REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_platform FOREIGN KEY (target_platform_id) REFERENCES platforms (platform_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_tag FOREIGN KEY (target_tag_id) REFERENCES tags (tag_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_drama_actor FOREIGN KEY (target_drama_actor_id) REFERENCES drama_actors (drama_actor_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_drama_director FOREIGN KEY (target_drama_director_id) REFERENCES drama_directors (drama_director_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_drama_company FOREIGN KEY (target_drama_company_id) REFERENCES drama_companies (drama_company_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_drama_tag FOREIGN KEY (target_drama_tag_id) REFERENCES drama_tags (drama_tag_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_drama_platform FOREIGN KEY (target_drama_platform_id) REFERENCES drama_platforms (drama_platform_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_snapshot FOREIGN KEY (target_snapshot_id) REFERENCES drama_metric_snapshots (snapshot_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_revision FOREIGN KEY (target_snapshot_revision_id) REFERENCES drama_metric_snapshot_revisions (snapshot_revision_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_import_job FOREIGN KEY (target_import_job_id) REFERENCES import_jobs (import_job_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_operation_logs_target_quality_issue FOREIGN KEY (target_data_quality_issue_id) REFERENCES data_quality_issues (data_quality_issue_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_operation_logs_result CHECK (result_status IN ('SUCCESS', 'FAILURE')),
  CONSTRAINT chk_operation_logs_type CHECK (CHAR_LENGTH(TRIM(operation_type)) > 0),
  CONSTRAINT chk_operation_logs_summary CHECK (CHAR_LENGTH(TRIM(summary)) > 0),
  CONSTRAINT chk_operation_logs_one_target CHECK (
    (target_user_id IS NOT NULL) + (target_drama_id IS NOT NULL)
    + (target_actor_id IS NOT NULL) + (target_director_id IS NOT NULL)
    + (target_company_id IS NOT NULL) + (target_platform_id IS NOT NULL)
    + (target_tag_id IS NOT NULL) + (target_drama_actor_id IS NOT NULL)
    + (target_drama_director_id IS NOT NULL) + (target_drama_company_id IS NOT NULL)
    + (target_drama_tag_id IS NOT NULL) + (target_drama_platform_id IS NOT NULL)
    + (target_snapshot_id IS NOT NULL) + (target_snapshot_revision_id IS NOT NULL)
    + (target_import_job_id IS NOT NULL) + (target_data_quality_issue_id IS NOT NULL) = 1
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DELIMITER $$
CREATE TRIGGER trg_operation_logs_no_update
BEFORE UPDATE ON operation_logs
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Operation logs are append-only';
END$$
CREATE TRIGGER trg_operation_logs_no_delete
BEFORE DELETE ON operation_logs
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Operation logs cannot be deleted';
END$$
DELIMITER ;
