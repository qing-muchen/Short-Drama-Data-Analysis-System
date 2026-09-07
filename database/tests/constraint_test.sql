-- TASK-P3-06R constraint test suite (write-only in this Task; do not execute here)
-- Prerequisite: run 001_create_database.sql and DDL 002..007, or migrations V001..V006.
-- The test uses a transaction and rolls business data back. Results are kept in a
-- temporary MEMORY table so expected failures can be reported after the rollback.

USE short_drama_analysis;
SET time_zone = '+00:00';

DROP TEMPORARY TABLE IF EXISTS constraint_test_results;
CREATE TEMPORARY TABLE constraint_test_results (
  test_name VARCHAR(128) NOT NULL,
  expected_result VARCHAR(32) NOT NULL,
  actual_result VARCHAR(32) NOT NULL,
  result VARCHAR(8) NOT NULL
) ENGINE=MEMORY;

DROP PROCEDURE IF EXISTS assert_sql_fails;
DELIMITER $$
CREATE PROCEDURE assert_sql_fails(IN p_test_name VARCHAR(128), IN p_sql LONGTEXT)
BEGIN
  DECLARE v_failed BOOLEAN DEFAULT FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_failed = TRUE;
    SET @constraint_test_sql = p_sql;
    PREPARE constraint_test_stmt FROM @constraint_test_sql;
    IF NOT v_failed THEN
      EXECUTE constraint_test_stmt;
    END IF;
    IF NOT v_failed THEN
      DEALLOCATE PREPARE constraint_test_stmt;
    END IF;
  END;

  INSERT INTO constraint_test_results
    (test_name, expected_result, actual_result, result)
  VALUES
    (p_test_name, 'REJECTED', IF(v_failed, 'REJECTED', 'ACCEPTED'), IF(v_failed, 'PASS', 'FAIL'));
END$$
DELIMITER ;

START TRANSACTION;

-- Deterministic fixture rows. Values are reserved for this test transaction only.
INSERT INTO users (username, password_hash, display_name, role_code, status)
VALUES ('__constraint_admin__', '$test_hash_only$', 'Constraint Admin', 'ADMINISTRATOR', 'ACTIVE');
SET @test_user_id = LAST_INSERT_ID();

INSERT INTO dramas (drama_code, drama_name, status)
VALUES ('__CONSTRAINT_DRAMA__', 'Constraint Drama', 'SERIALIZING');
SET @test_drama_id = LAST_INSERT_ID();

INSERT INTO actors (actor_name) VALUES ('Constraint Actor');
SET @test_actor_id = LAST_INSERT_ID();
INSERT INTO directors (director_name) VALUES ('Constraint Director');
SET @test_director_id = LAST_INSERT_ID();
INSERT INTO companies (company_name) VALUES ('Constraint Company');
SET @test_company_id = LAST_INSERT_ID();
INSERT INTO platforms (platform_name) VALUES ('__constraint_platform__');
SET @test_platform_id = LAST_INSERT_ID();
INSERT INTO platforms (platform_name) VALUES ('__constraint_platform_2__');
SET @test_platform_2_id = LAST_INSERT_ID();
INSERT INTO tags (tag_name) VALUES ('__constraint_tag__');
SET @test_tag_id = LAST_INSERT_ID();

INSERT INTO drama_actors (drama_id, actor_id, role_name, role_type, billing_order)
VALUES (@test_drama_id, @test_actor_id, 'Test Role', 'LEAD', 1);
INSERT INTO drama_directors (drama_id, director_id)
VALUES (@test_drama_id, @test_director_id);
INSERT INTO drama_companies (drama_id, company_id, relation_type)
VALUES (@test_drama_id, @test_company_id, 'PRODUCTION');
INSERT INTO drama_tags (drama_id, tag_id)
VALUES (@test_drama_id, @test_tag_id);
INSERT INTO drama_platforms (drama_id, platform_id, platform_drama_code, online_at, status)
VALUES (@test_drama_id, @test_platform_id, '__EXT_1__', UTC_TIMESTAMP(6), 'ONLINE');
SET @test_drama_platform_id = LAST_INSERT_ID();
INSERT INTO drama_platforms (drama_id, platform_id, platform_drama_code, online_at, status)
VALUES (@test_drama_id, @test_platform_2_id, '__EXT_2__', UTC_TIMESTAMP(6), 'ONLINE');
SET @test_drama_platform_2_id = LAST_INSERT_ID();

INSERT INTO import_jobs (
  initiated_by_user_id, import_type, status, original_filename, file_format,
  total_rows, valid_rows, error_rows, imported_rows
) VALUES (
  @test_user_id, 'SNAPSHOT', 'COMPLETED_WITH_ERRORS', '__constraint__.csv', 'CSV',
  2, 1, 1, 1
);
SET @test_import_job_id = LAST_INSERT_ID();
INSERT INTO import_errors (import_job_id, row_number, error_code, error_message)
VALUES (@test_import_job_id, 2, 'TEST_ERROR', 'Constraint test error');

INSERT INTO drama_metric_snapshots (
  drama_platform_id, snapshot_time, source_import_job_id
) VALUES (
  @test_drama_platform_id, '2026-01-01 00:00:00.000000', @test_import_job_id
);
SET @test_snapshot_id = LAST_INSERT_ID();

INSERT INTO drama_metric_snapshot_revisions (
  snapshot_id, version_no, previous_revision_id, revision_action,
  play_count, like_count, comment_count, favorite_count, share_count,
  ranking, changed_by_user_id
) VALUES (
  @test_snapshot_id, 1, NULL, 'INITIAL',
  100, 10, 2, 3, 1, 5, @test_user_id
);
SET @test_revision_1_id = LAST_INSERT_ID();
UPDATE drama_metric_snapshots
SET current_revision_id = @test_revision_1_id
WHERE snapshot_id = @test_snapshot_id;

-- UNIQUE constraints.
CALL assert_sql_fails('UNIQUE users.username',
  'INSERT INTO users (username, password_hash) VALUES (''__constraint_admin__'', ''$other_hash$'')');
CALL assert_sql_fails('UNIQUE dramas.drama_code',
  'INSERT INTO dramas (drama_code, drama_name) VALUES (''__CONSTRAINT_DRAMA__'', ''Duplicate'')');
CALL assert_sql_fails('UNIQUE platforms.platform_name',
  'INSERT INTO platforms (platform_name) VALUES (''__constraint_platform__'')');
CALL assert_sql_fails('UNIQUE drama_actors pair', CONCAT(
  'INSERT INTO drama_actors (drama_id, actor_id) VALUES (', @test_drama_id, ',', @test_actor_id, ')'));
CALL assert_sql_fails('UNIQUE drama_companies triple', CONCAT(
  'INSERT INTO drama_companies (drama_id, company_id, relation_type) VALUES (',
  @test_drama_id, ',', @test_company_id, ',''PRODUCTION'')'));
CALL assert_sql_fails('UNIQUE drama_tags pair', CONCAT(
  'INSERT INTO drama_tags (drama_id, tag_id) VALUES (', @test_drama_id, ',', @test_tag_id, ')'));
CALL assert_sql_fails('UNIQUE drama_platforms pair', CONCAT(
  'INSERT INTO drama_platforms (drama_id, platform_id) VALUES (', @test_drama_id, ',', @test_platform_id, ')'));

-- CHECK constraints for statuses and value dictionaries.
CALL assert_sql_fails('CHECK users status',
  'INSERT INTO users (username, password_hash, status) VALUES (''__invalid_user__'', ''$hash$'', ''INVALID'')');
CALL assert_sql_fails('CHECK dramas status',
  'INSERT INTO dramas (drama_code, drama_name, status) VALUES (''__INVALID_DRAMA__'', ''Invalid'', ''UNKNOWN'')');
CALL assert_sql_fails('CHECK drama_platforms status', CONCAT(
  'UPDATE drama_platforms SET status = ''INVALID'' WHERE drama_platform_id = ', @test_drama_platform_id));
CALL assert_sql_fails('CHECK snapshot revision action', CONCAT(
  'INSERT INTO drama_metric_snapshot_revisions (snapshot_id, version_no, previous_revision_id, revision_action, play_count, change_reason, changed_by_user_id) VALUES (',
  @test_snapshot_id, ',2,', @test_revision_1_id, ',''INVALID'',100,''invalid action'',', @test_user_id, ')'));
CALL assert_sql_fails('CHECK import_jobs status', CONCAT(
  'UPDATE import_jobs SET status = ''INVALID'' WHERE import_job_id = ', @test_import_job_id));

-- Snapshot observation-slot and revision constraints.
CALL assert_sql_fails('Snapshot duplicate observation slot', CONCAT(
  'INSERT INTO drama_metric_snapshots (drama_platform_id, snapshot_time) VALUES (',
  @test_drama_platform_id, ',''2026-01-01 00:00:00.000000'')'));
CALL assert_sql_fails('Snapshot duplicate version number', CONCAT(
  'INSERT INTO drama_metric_snapshot_revisions (snapshot_id, version_no, revision_action, play_count, changed_by_user_id) VALUES (',
  @test_snapshot_id, ',1,''INITIAL'',101,', @test_user_id, ')'));

-- A revision from one slot cannot become current for another slot.
INSERT INTO drama_metric_snapshots (drama_platform_id, snapshot_time)
VALUES (@test_drama_platform_2_id, '2026-01-01 00:00:00.000000');
SET @test_snapshot_2_id = LAST_INSERT_ID();
CALL assert_sql_fails('Snapshot current revision belongs to same slot', CONCAT(
  'UPDATE drama_metric_snapshots SET current_revision_id = ', @test_revision_1_id,
  ' WHERE snapshot_id = ', @test_snapshot_2_id));

-- CORRECTION is append-only and becomes the sole current revision.
INSERT INTO drama_metric_snapshot_revisions (
  snapshot_id, version_no, previous_revision_id, revision_action,
  play_count, like_count, comment_count, favorite_count, share_count,
  ranking, change_reason, changed_by_user_id
) VALUES (
  @test_snapshot_id, 2, @test_revision_1_id, 'CORRECTION',
  110, 11, 2, 3, 1, 4, 'Correct test metrics', @test_user_id
);
SET @test_revision_2_id = LAST_INSERT_ID();
UPDATE drama_metric_snapshots
SET current_revision_id = @test_revision_2_id
WHERE snapshot_id = @test_snapshot_id;
INSERT INTO constraint_test_results
SELECT 'Snapshot correction allowed', 'ACCEPTED',
       IF(COUNT(*) = 1, 'ACCEPTED', 'NOT_CURRENT'),
       IF(COUNT(*) = 1, 'PASS', 'FAIL')
FROM drama_metric_snapshots
WHERE snapshot_id = @test_snapshot_id
  AND current_revision_id = @test_revision_2_id;

-- VOID is retained as a revision event; the slot has no current valid revision.
INSERT INTO drama_metric_snapshot_revisions (
  snapshot_id, version_no, previous_revision_id, revision_action,
  change_reason, changed_by_user_id
) VALUES (
  @test_snapshot_id, 3, @test_revision_2_id, 'VOID',
  'Void test observation', @test_user_id
);
SET @test_revision_3_id = LAST_INSERT_ID();
UPDATE drama_metric_snapshots
SET current_revision_id = NULL
WHERE snapshot_id = @test_snapshot_id;
INSERT INTO constraint_test_results
SELECT 'Snapshot VOID allowed', 'ACCEPTED',
       IF(current_revision_id IS NULL, 'ACCEPTED', 'STILL_CURRENT'),
       IF(current_revision_id IS NULL, 'PASS', 'FAIL')
FROM drama_metric_snapshots
WHERE snapshot_id = @test_snapshot_id;
CALL assert_sql_fails('Snapshot revision delete restricted', CONCAT(
  'DELETE FROM drama_metric_snapshot_revisions WHERE snapshot_revision_id = ', @test_revision_3_id));

-- DataQualityIssue must have exactly one real target.
CALL assert_sql_fails('Quality target cannot be empty', CONCAT(
  'INSERT INTO data_quality_issues (issue_type,severity,status,source,rule_code,evidence_summary,first_detected_at,last_detected_at) VALUES (''OTHER'',''INFO'',''OPEN'',''BUSINESS_RULE'',''TEST'',''No target'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))'));
CALL assert_sql_fails('Quality cannot have two targets', CONCAT(
  'INSERT INTO data_quality_issues (target_drama_id,target_snapshot_revision_id,issue_type,severity,status,source,rule_code,evidence_summary,first_detected_at,last_detected_at) VALUES (',
  @test_drama_id, ',', @test_revision_1_id, ',''OTHER'',''INFO'',''OPEN'',''BUSINESS_RULE'',''TEST'',''Two targets'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))'));
CALL assert_sql_fails('CHECK quality status', CONCAT(
  'INSERT INTO data_quality_issues (target_drama_id,issue_type,severity,status,source,rule_code,evidence_summary,first_detected_at,last_detected_at) VALUES (',
  @test_drama_id, ',''OTHER'',''INFO'',''INVALID'',''BUSINESS_RULE'',''TEST'',''Invalid status'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))'));
CALL assert_sql_fails('CHECK quality severity', CONCAT(
  'INSERT INTO data_quality_issues (target_drama_id,issue_type,severity,status,source,rule_code,evidence_summary,first_detected_at,last_detected_at) VALUES (',
  @test_drama_id, ',''OTHER'',''INVALID'',''OPEN'',''BUSINESS_RULE'',''TEST'',''Invalid severity'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))'));
INSERT INTO data_quality_issues (
  target_snapshot_revision_id, issue_type, severity, status, source,
  rule_code, evidence_summary, first_detected_at, last_detected_at
) VALUES (
  @test_revision_1_id, 'OTHER', 'INFO', 'OPEN', 'BUSINESS_RULE',
  'TEST_SINGLE_TARGET', 'One target', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6)
);
SET @test_quality_issue_id = LAST_INSERT_ID();
INSERT INTO constraint_test_results VALUES
  ('Quality single target allowed', 'ACCEPTED', 'ACCEPTED', 'PASS');

-- OperationLog requires an operator and exactly one target.
CALL assert_sql_fails('OperationLog requires operator', CONCAT(
  'INSERT INTO operation_logs (actor_user_id,target_drama_id,operation_type,result_status,summary) VALUES (NULL,',
  @test_drama_id, ',''TEST'',''SUCCESS'',''Missing operator'')'));
CALL assert_sql_fails('OperationLog requires target', CONCAT(
  'INSERT INTO operation_logs (actor_user_id,operation_type,result_status,summary) VALUES (',
  @test_user_id, ',''TEST'',''SUCCESS'',''Missing target'')'));
CALL assert_sql_fails('OperationLog allows one target only', CONCAT(
  'INSERT INTO operation_logs (actor_user_id,target_drama_id,target_platform_id,operation_type,result_status,summary) VALUES (',
  @test_user_id, ',', @test_drama_id, ',', @test_platform_id, ',''TEST'',''SUCCESS'',''Two targets'')'));
INSERT INTO operation_logs (
  actor_user_id, target_data_quality_issue_id, operation_type, result_status, summary
) VALUES (
  @test_user_id, @test_quality_issue_id, 'QUALITY_ISSUE_CREATED', 'SUCCESS',
  'Constraint test audit event without credentials'
);
INSERT INTO constraint_test_results VALUES
  ('OperationLog one operator and target', 'ACCEPTED', 'ACCEPTED', 'PASS');

-- Real foreign keys and RESTRICT delete behavior.
CALL assert_sql_fails('FK rejects orphan relation',
  'INSERT INTO drama_actors (drama_id, actor_id) VALUES (999999999999,999999999999)');
CALL assert_sql_fails('RESTRICT platform referenced by DramaPlatform', CONCAT(
  'DELETE FROM platforms WHERE platform_id = ', @test_platform_id));
CALL assert_sql_fails('RESTRICT DramaPlatform referenced by Snapshot', CONCAT(
  'DELETE FROM drama_platforms WHERE drama_platform_id = ', @test_drama_platform_id));
CALL assert_sql_fails('RESTRICT Drama referenced by relations', CONCAT(
  'DELETE FROM dramas WHERE drama_id = ', @test_drama_id));
CALL assert_sql_fails('RESTRICT ImportJob referenced by ImportError', CONCAT(
  'DELETE FROM import_jobs WHERE import_job_id = ', @test_import_job_id));

ROLLBACK;

SELECT test_name, expected_result, actual_result, result
FROM constraint_test_results
ORDER BY test_name;

SELECT
  COUNT(*) AS total_tests,
  SUM(result = 'PASS') AS passed_tests,
  SUM(result = 'FAIL') AS failed_tests
FROM constraint_test_results;

DROP PROCEDURE assert_sql_fails;
