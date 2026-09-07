# Database Validation Report

## 1. Report metadata

| Item | Result |
| --- | --- |
| Task | TASK-P3-07 Database Initialization Verification |
| Validation time | 2026-09-07 20:05:58 +08:00 |
| Overall status | **FAILED — BLOCKING DDL ISSUE** |
| Repository commit under test | `ec9c8beb816db5199cc0af547a1aeceb41f42e9b` |
| Execution model | Isolated temporary MySQL instance; temporary data removed after shutdown |
| Schema under test | `short_drama_analysis` created from an empty instance |

## 2. Environment

| Check | Actual result | Status |
| --- | --- | --- |
| MySQL Server | MySQL Community Server 8.0.45, Win64 x86_64 | PASS |
| Minimum version | Required >= 8.0; actual 8.0.45 | PASS |
| Default storage engine | InnoDB | PASS |
| Server character set | utf8mb4 | PASS |
| Server collation | utf8mb4_0900_ai_ci | PASS |
| Test isolation | Local named pipe and dedicated temporary data directory | PASS |

The temporary server was not a project or user database. It was shut down successfully and its validated task-specific temporary directory was removed after evidence collection.

## 3. Empty-database initialization and Migration results

Before execution, `information_schema.schemata` confirmed that `short_drama_analysis` did not exist.

| Step | File | Exit code | Elapsed | Result |
| --- | --- | ---: | ---: | --- |
| Database bootstrap | `database/ddl/001_create_database.sql` | 0 | 226 ms | PASS |
| V001 | `V001__create_core_tables.sql` | 0 | 152 ms | PASS |
| V002 | `V002__create_relation_tables.sql` | 0 | 163 ms | PASS |
| V003 | `V003__create_snapshot_tables.sql` | 0 | 151 ms | PASS |
| V004 | `V004__create_import_quality_tables.sql` | 1 | 76 ms | **FAIL** |
| V005 | `V005__create_operation_log.sql` | — | — | NOT RUN: blocked by V004 |
| V006 | `V006__create_indexes.sql` | — | — | NOT RUN: blocked by V004 |

MySQL returned error 1064 at V004 line 31 while parsing the `import_errors` definition near `row_number BIGINT UNSIGNED NULL`. Because MySQL DDL commits table creation independently, the successful tables before the failing statement remained present for evidence collection; they were removed with the temporary instance afterward.

## 4. Partial physical state at failure

| Validation | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Base tables | 18 | 15 | FAIL |
| BIGINT UNSIGNED AUTO_INCREMENT primary keys | 18 | 15 created before failure | INCOMPLETE |
| Foreign keys | 39 | 16 created before failure | INCOMPLETE |
| CHECK constraints | 58 | 40 created before failure | INCOMPLETE |

Tables present at the failure point:

```text
actors
companies
directors
drama_actors
drama_companies
drama_directors
drama_metric_snapshot_revisions
drama_metric_snapshots
drama_platforms
drama_tags
dramas
import_jobs
platforms
tags
users
```

Tables not reached or not created:

```text
import_errors
data_quality_issues
operation_logs
```

## 5. Constraint and model verification

| Area | Result | Evidence / reason |
| --- | --- | --- |
| Foreign-key delete tests | NOT RUN | Full schema initialization failed before the constraint suite |
| Business UNIQUE tests | NOT RUN | Full schema initialization failed before the constraint suite |
| Status CHECK tests | NOT RUN | Full schema initialization failed before the constraint suite |
| Snapshot INITIAL/CORRECTION/VOID | NOT RUN | V003 installed successfully, but end-to-end suite was not run against an incomplete schema |
| Single current Snapshot revision | NOT RUN | End-to-end suite blocked by V004 |
| Historical revision retention | NOT RUN | End-to-end suite blocked by V004 |
| DataQualityIssue exactly-one target | NOT RUN | `data_quality_issues` was not created |
| OperationLog operator and target | NOT RUN | `operation_logs` was not created |
| Query-supporting indexes | NOT RUN | V006 was not reached |
| Physical 3NF consistency | INCOMPLETE | No deviation observed in V001–V003, but all 18 tables were not initialized |

`database/tests/constraint_test.sql` was therefore not executed. Reporting its expected assertions as PASS would be false evidence.

## 6. Database Validation Issue

### DBVAL-P3-07-001 — unquoted MySQL reserved identifier blocks V004

| Item | Detail |
| --- | --- |
| Severity | Blocking |
| Affected files | `database/migrations/V004__create_import_quality_tables.sql`; mirrored DDL `database/ddl/005_create_import_quality_tables.sql` |
| Affected object | `import_errors.row_number` |
| Actual error | MySQL 1064 syntax error near `row_number BIGINT UNSIGNED NULL` |
| Cause | `ROW_NUMBER` is a reserved keyword in MySQL 8.0 and is used without identifier quoting |
| Design impact | None established; the field semantics and 3NF design are unchanged |
| Required follow-up | An authorized DDL repair Task must either quote the existing identifier consistently or approve a non-reserved physical name, mirror the fix in DDL and V004, then rerun TASK-P3-07 from an empty database |

No DDL, Schema, business rule, E-R model, or 3NF conclusion was modified during this validation Task.

## 7. Conclusion

Database initialization verification is **FAILED**. V001–V003 and the environment checks passed, but V004 prevented complete initialization. TASK-P3-07 cannot be marked Completed, and Phase 3 Final Review must not begin until DBVAL-P3-07-001 is repaired and the full Migration plus constraint suite passes on a new empty database.
