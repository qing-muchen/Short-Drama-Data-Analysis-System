# Database Validation Report

## 1. Report metadata

| Item | Result |
| --- | --- |
| Task | TASK-P3-07 Retry — Database Initialization Verification |
| Validation time | 2026-09-07 20:33:42 +08:00 |
| Overall status | **PASS — DATABASE VALIDATION COMPLETED** |
| Repository commit under test | `74869450216a82eb9e9a539e1a657689fb727d11` |
| Execution model | Isolated temporary MySQL instance; temporary data removed after shutdown |
| Temporary schema | `short_drama_analysis`, created from an empty isolated instance |

## 2. Environment and isolation

| Check | Actual result | Status |
| --- | --- | --- |
| MySQL Server | MySQL Community Server 8.0.45, Win64 x86_64 | PASS |
| Minimum version | Required >= 8.0; actual 8.0.45 | PASS |
| Default storage engine | InnoDB | PASS |
| Server character set | utf8mb4 | PASS |
| Server collation | utf8mb4_0900_ai_ci | PASS |
| Empty-instance precondition | `short_drama_analysis` did not exist before bootstrap | PASS |
| Test isolation | Dedicated temporary data directory and local Named Pipe | PASS |
| Cleanup | Server shutdown exit 0; validated temporary directory removed | PASS |

No existing project or user database was connected to or modified.

## 3. Database bootstrap and Migration execution

The database entry file was executed first, followed strictly by V001 through V006.

| Step | File | Exit code | Elapsed | Result |
| --- | --- | ---: | ---: | --- |
| Database bootstrap | `database/ddl/001_create_database.sql` | 0 | 43 ms | PASS |
| V001 | `V001__create_core_tables.sql` | 0 | 145 ms | PASS |
| V002 | `V002__create_relation_tables.sql` | 0 | 143 ms | PASS |
| V003 | `V003__create_snapshot_tables.sql` | 0 | 137 ms | PASS |
| V004 | `V004__create_import_quality_tables.sql` | 0 | 140 ms | PASS |
| V005 | `V005__create_operation_log.sql` | 0 | 95 ms | PASS |
| V006 | `V006__create_indexes.sql` | 0 | 664 ms | PASS |

DBVAL-P3-07-001 is no longer reproducible: `import_errors.source_row_number` was accepted by MySQL 8.0.45 and V004 completed successfully.

## 4. Physical structure verification

| Validation | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Base tables | 18 | 18 | PASS |
| BIGINT UNSIGNED AUTO_INCREMENT primary keys | 18 | 18 | PASS |
| Foreign keys | 39 | 39 | PASS |
| Foreign keys using RESTRICT | 39 | 39 | PASS |
| CHECK constraints | 58 | 58 | PASS |

Tables created:

```text
actors
companies
data_quality_issues
directors
drama_actors
drama_companies
drama_directors
drama_metric_snapshot_revisions
drama_metric_snapshots
drama_platforms
drama_tags
dramas
import_errors
import_jobs
operation_logs
platforms
tags
users
```

The physical plural table names match MySQL Schema Design V1. No denormalized analysis fields were introduced, so the implementation remains consistent with the completed 3NF design review.

## 5. Constraint suite result

`database/tests/constraint_test.sql` executed successfully in 68 ms.

| Result | Count |
| --- | ---: |
| Total tests | 32 |
| Passed | 32 |
| Failed | 0 |

The transaction-scoped fixture was rolled back successfully. Follow-up queries found zero persisted fixture users and zero persisted fixture dramas.

### 5.1 UNIQUE and relationship uniqueness

All seven duplicate attempts were rejected as expected:

- `users.username`;
- `dramas.drama_code`;
- `platforms.platform_name`;
- Drama–Actor pair;
- Drama–Company–relation type triple;
- Drama–Tag pair;
- Drama–Platform pair.

### 5.2 CHECK constraints

All seven tested invalid values were rejected as expected, covering User status, Drama status, DramaPlatform status, Snapshot revision action, ImportJob status, DataQualityIssue status and quality severity.

The Snapshot status semantics are physically represented by the frozen observation-slot/current-revision model and the `INITIAL/CORRECTION/VOID` revision action constraint.

### 5.3 Foreign keys and RESTRICT behavior

- An orphan DramaActor relation was rejected.
- Deleting a Platform referenced by DramaPlatform was rejected.
- Deleting a DramaPlatform referenced by Snapshot was rejected.
- Deleting a Drama referenced by relationship tables was rejected.
- Deleting an ImportJob referenced by ImportError was rejected.

The information-schema catalog independently confirmed all 39 foreign keys and all 39 `RESTRICT` delete rules.

## 6. Snapshot model verification

| Scenario | Actual result | Status |
| --- | --- | --- |
| Create observation slot | Accepted | PASS |
| Create INITIAL revision and set current pointer | Accepted | PASS |
| Append CORRECTION and move current pointer | Accepted; exactly one current pointer | PASS |
| Append VOID and clear current pointer | Accepted | PASS |
| Duplicate observation slot | Rejected | PASS |
| Duplicate revision version | Rejected | PASS |
| Use a revision as current for another slot | Rejected | PASS |
| Delete historical revision | Rejected | PASS |

The stable observation-slot plus immutable revision model preserves history and enforces the frozen current-revision relationship.

## 7. DataQualityIssue verification

| Scenario | Actual result | Status |
| --- | --- | --- |
| No target | Rejected | PASS |
| More than one target | Rejected | PASS |
| Exactly one Snapshot Revision target | Accepted | PASS |

The mutually exclusive real-FK target model behaves as designed.

## 8. OperationLog verification

| Scenario | Actual result | Status |
| --- | --- | --- |
| Missing operator | Rejected | PASS |
| Missing target | Rejected | PASS |
| More than one target | Rejected | PASS |
| One operator and one target | Accepted | PASS |

The test audit summary contained no password, Token or Secret content.

## 9. Index verification

| Query area | Frozen physical index columns | Result |
| --- | --- | --- |
| Snapshot as-of | `drama_metric_snapshots(drama_platform_id, snapshot_time)` | PASS |
| Quality list | `data_quality_issues(status, severity, last_detected_at)` | PASS |
| Import jobs | `import_jobs(status, created_at)` | PASS |
| Operation audit | `operation_logs(actor_user_id, occurred_at)` | PASS |

The Quality and Operation column names above are the physical names frozen in MySQL Schema Design V1; they correspond to the task's logical quality-created-time and operator-created-time query requirements.

## 10. Issues and conclusion

- DBVAL-P3-07-001: **Closed by successful retry verification**.
- New blocking validation issues: none.
- Database bootstrap, all six Migrations, structure checks and all 32 constraint tests passed on MySQL 8.0.45.
- Phase 3 remains in progress. This Task does not authorize Phase 4 or backend development.
