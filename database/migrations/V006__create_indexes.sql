-- Migration V006: query-supporting indexes
USE short_drama_analysis;

CREATE INDEX idx_users_status ON users (status);
CREATE INDEX idx_dramas_status_premiere ON dramas (status, premiere_date);
CREATE INDEX idx_dramas_name ON dramas (drama_name);
CREATE INDEX idx_actors_name_status ON actors (actor_name, status);
CREATE INDEX idx_directors_name_status ON directors (director_name, status);
CREATE INDEX idx_companies_name_status ON companies (company_name, status);
CREATE INDEX idx_platforms_status ON platforms (status);
CREATE INDEX idx_tags_status ON tags (status);

CREATE INDEX idx_drama_actors_actor_status ON drama_actors (actor_id, relation_status);
CREATE INDEX idx_drama_directors_director_status ON drama_directors (director_id, relation_status);
CREATE INDEX idx_drama_companies_company_type_status ON drama_companies (company_id, relation_type, relation_status);
CREATE INDEX idx_drama_tags_tag_status ON drama_tags (tag_id, relation_status);
CREATE INDEX idx_drama_platforms_platform_status_online ON drama_platforms (platform_id, status, online_at);
CREATE INDEX idx_drama_platforms_drama_status ON drama_platforms (drama_id, status);

CREATE INDEX idx_snapshots_source_import ON drama_metric_snapshots (source_import_job_id);
CREATE INDEX idx_snapshot_revisions_changed_at ON drama_metric_snapshot_revisions (snapshot_id, changed_at);
CREATE INDEX idx_snapshot_revisions_user_changed ON drama_metric_snapshot_revisions (changed_by_user_id, changed_at);
CREATE INDEX idx_import_jobs_status_created ON import_jobs (status, created_at);
CREATE INDEX idx_import_jobs_user_created ON import_jobs (initiated_by_user_id, created_at);
CREATE INDEX idx_import_jobs_file_hash ON import_jobs (file_hash);
CREATE INDEX idx_import_errors_job_row ON import_errors (import_job_id, source_row_number);
CREATE INDEX idx_import_errors_job_code ON import_errors (import_job_id, error_code);

CREATE INDEX idx_quality_status_severity_detected ON data_quality_issues (status, severity, last_detected_at);
CREATE INDEX idx_quality_revision_type_status ON data_quality_issues (target_snapshot_revision_id, issue_type, status);
CREATE INDEX idx_quality_platform_type_status ON data_quality_issues (target_drama_platform_id, issue_type, status);
CREATE INDEX idx_quality_drama_type_status ON data_quality_issues (target_drama_id, issue_type, status);
CREATE INDEX idx_quality_handler_time ON data_quality_issues (handled_by_user_id, handled_at);

CREATE INDEX idx_operation_actor_time ON operation_logs (actor_user_id, occurred_at);
CREATE INDEX idx_operation_type_time ON operation_logs (operation_type, occurred_at);
CREATE INDEX idx_operation_request ON operation_logs (request_id);
CREATE INDEX idx_operation_target_user_time ON operation_logs (target_user_id, occurred_at);
CREATE INDEX idx_operation_target_drama_time ON operation_logs (target_drama_id, occurred_at);
CREATE INDEX idx_operation_target_actor_time ON operation_logs (target_actor_id, occurred_at);
CREATE INDEX idx_operation_target_director_time ON operation_logs (target_director_id, occurred_at);
CREATE INDEX idx_operation_target_company_time ON operation_logs (target_company_id, occurred_at);
CREATE INDEX idx_operation_target_platform_time ON operation_logs (target_platform_id, occurred_at);
CREATE INDEX idx_operation_target_tag_time ON operation_logs (target_tag_id, occurred_at);
CREATE INDEX idx_operation_target_drama_actor_time ON operation_logs (target_drama_actor_id, occurred_at);
CREATE INDEX idx_operation_target_drama_director_time ON operation_logs (target_drama_director_id, occurred_at);
CREATE INDEX idx_operation_target_drama_company_time ON operation_logs (target_drama_company_id, occurred_at);
CREATE INDEX idx_operation_target_drama_tag_time ON operation_logs (target_drama_tag_id, occurred_at);
CREATE INDEX idx_operation_target_drama_platform_time ON operation_logs (target_drama_platform_id, occurred_at);
CREATE INDEX idx_operation_target_snapshot_time ON operation_logs (target_snapshot_id, occurred_at);
CREATE INDEX idx_operation_target_revision_time ON operation_logs (target_snapshot_revision_id, occurred_at);
CREATE INDEX idx_operation_target_import_time ON operation_logs (target_import_job_id, occurred_at);
CREATE INDEX idx_operation_target_quality_time ON operation_logs (target_data_quality_issue_id, occurred_at);
