# Phase S5.1 Development Database Recovery Report

## 1. Executive summary

- Execution date: 2026-10-12 (Asia/Shanghai).
- Target database: `short_drama_analysis` only.
- Protected databases: `short_drama_acceptance_v1`, `short_drama_analysis_test`, and all unrelated schemas were not modified.
- Git baseline at task start: branch `main`, HEAD `0e350381d1fd7a16eaa9da5cf9bb92c24285c7de`, tag `v1.0.0` at the same commit, clean worktree.
- Recovery result: the development database was upgraded from 19 to 31 tables by applying the unchanged V008-V013 SQL migrations in order.
- Structural result: after recovery, the development and acceptance databases have the same 31-table structure. No differences were found in columns, primary keys, foreign keys, indexes, unique constraints, or CHECK constraints.
- Data preservation result: the existing 131 dramas, 64,255 snapshot slots, 64,255 snapshot revisions, and all other pre-existing business rows were preserved.
- Prediction result: the missing-table HTTP 500 is resolved. Drama 25 can be calculated, persisted, queried, charted, and recalculated. Drama 120 has only six observations and correctly returns `INSUFFICIENT_HISTORY` rather than an internal error.
- Source repair: one independent MySQL compatibility defect in the Data Quality history query was fixed in commit `f822f53182f91909c910b5b8bc2f9255c9ff4605`.

## 2. Root causes and actual evidence

### 2.1 Prediction HTTP 500

Before repair, authenticated requests produced:

| Request | Actual result |
| --- | --- |
| `GET /api/v1/predictions/120` | HTTP 500, `PERSISTENCE_ERROR` |
| `GET /api/v1/predictions/120/history?limit=100` | HTTP 500, `PERSISTENCE_ERROR` |
| `POST /api/v1/predictions/calculate` with `{"drama_id":120}` | HTTP 400, `INSUFFICIENT_HISTORY` |

The real registered calculate route is `POST /api/v1/predictions/calculate` with a JSON body. `/calculate/120` is not the implemented route.

The reproduced Repository traceback ended with:

```text
pymysql.err.ProgrammingError: (1146,
  "Table 'short_drama_analysis.prediction_results' doesn't exist")

sqlalchemy.exc.ProgrammingError: ...
[SQL: SELECT ... FROM prediction_results ...]
```

Therefore the GET failures were conclusively caused by the absent `prediction_results` table. The calculate request for drama 120 did not reach result persistence because the Service correctly identified insufficient history.

### 2.2 Data Quality history HTTP 500

After the missing tables were available in the rehearsal database, `GET /api/v1/data-quality/history` exposed an independent code defect:

```text
pymysql.err.NotSupportedError: (1235,
  "This version of MySQL doesn't yet support 'LIMIT & IN/ALL/ANY/SOME subquery'")
```

`DataQualityScoreRepository.list_history()` generated an `IN (SELECT ... LIMIT ...)` query. It was minimally changed to wrap the limited query in a named derived table before the outer `IN` selection. The API subsequently returned HTTP 200 with an empty history. The change does not alter scoring rules, ordering, version filters, limits, or the HTTP contract.

## 3. Pre-repair audit

### 3.1 Git and release state

- Start branch: `main`.
- Start HEAD: `0e350381d1fd7a16eaa9da5cf9bb92c24285c7de`.
- `v1.0.0` resolved to the same frozen commit.
- Start worktree: clean.
- No tag or historical commit was rewritten.

### 3.2 Runtime configuration

- `backend/.env` selected `short_drama_analysis` through `DATABASE_URL`.
- MySQL connection and version were verified (`8.0.45`).
- Credential values were not printed or added to this report.
- `backend/.env` and the backup file remain ignored by Git.

### 3.3 Migration history mechanism

- There is no migration history table or formal SQL migration runner.
- `backend/alembic/versions` contains no business revision.
- Alembic has not adopted the SQL baseline.
- Actual migration state therefore had to be established by schema inspection, not inferred from filenames or table counts.

### 3.4 Development versus acceptance database

The 19 tables common to both databases had identical inspected structures. Development had no extra tables. The following 12 tables were completely absent, not partially present:

| Migration | Missing tables |
| --- | --- |
| V008 | `drama_scores` |
| V009 | `data_quality_rules`, `data_quality_scores`, `data_quality_rule_results` |
| V010 | `prediction_results` |
| V011 | `data_anomaly_records` |
| V012 | `operation_actions`, `operation_action_sources`, `operation_action_history` |
| V013 | `analysis_explanations`, `analysis_lineage_records`, `metric_dependencies` |

No existing-but-incomplete table, missing column, missing shared-table index/constraint, or extra development table was found. V001-V007 prerequisites, including `import_batches` and the V007 columns/constraints on `import_jobs`, were present and structurally identical to the acceptance database.

### 3.5 Key initial row counts

| Table | Initial count |
| --- | ---: |
| `dramas` | 131 |
| `drama_metric_snapshots` | 64,255 |
| `drama_metric_snapshot_revisions` | 64,255 |
| `drama_platforms` | 260 |
| `drama_actors` | 792 |
| `drama_directors` | 110 |
| `drama_companies` | 251 |
| `drama_tags` | 341 |
| `import_batches` | 9 |
| `import_jobs` | 29 |
| `import_errors` | 37 |
| `operation_logs` | 9 |

### 3.6 Process deviation before the formal backup

The initial authenticated traceback reproduction included a calculate request for drama 120. Although the request returned `INSUFFICIENT_HISTORY` and did not create a prediction, the existing Service intentionally appended one successful skip audit record to `operation_logs`. This changed `operation_logs` from 9 to 10 before the formal dump. No business/master/snapshot row or schema object changed. This is a deviation from the requested “no writes before backup” sequence and is recorded rather than hidden. The append-only trigger correctly prevents deleting that audit record. The formal backup contains the 10-log state.

## 4. Migration SQL audit

All V001-V013 files were read and hashed before execution. Every file contains a fixed `USE short_drama_analysis` statement and is therefore target-specific.

- No migration contains `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`, `DELETE FROM`, business-data `UPDATE`, or table rename.
- V003 creates snapshot tables and immutable-history triggers, then adds the current-revision composite foreign key to `drama_metric_snapshots`.
- V004 creates import/quality governance tables, then adds `source_import_job_id` foreign-key support to `drama_metric_snapshots`.
- V006 contains only index creation.
- V007 creates `import_batches` and adds batch columns, constraints, and indexes to `import_jobs`.
- V008-V013 only create the 12 missing tables, their indexes, and constraints. They do not alter any existing development table.
- V009 and V012 contain intentional `ON DELETE CASCADE` rules from parent derived/action records to their owned child rows; they do not execute a delete during migration.
- The migrations are non-idempotent. Re-executing an already applied file would fail and was not attempted.

SHA-256 values for the applied files:

| File | SHA-256 |
| --- | --- |
| V008 | `1F2A88CBBE3ED50052375A225426AE58AB1D7C23A7CB525960205CA77FFCFAB1` |
| V009 | `F7CD28503B26C5D6A3BAEC395C8F5C6049EB32C4B4B0DAEC36EE4833E3EFAB51` |
| V010 | `8EC0E441F015E2ACF3B3D95495BA9EF058881B5E3CBCBB38C9FA1969A919E36E` |
| V011 | `D851897785B3B9A264E28EFA5A209548CE2B52223D29CA4E7E95A4FDC820E253` |
| V012 | `FE496D1FBA10B671D5D84D6AC9DEDBEB4FF9D9969A7764C6C74CC95FCDAA5645` |
| V013 | `98A36AA8FCEC0785C55AFEDFBB8136316A889E9BD39E3CBB044699E1AF14216E` |

Historical migration files were not edited.

## 5. Backup and restore verification

- Backup file: `backup_phase_s5_1_short_drama_analysis_20261012_161955.sql`.
- Location: repository root; ignored by `backup*.sql` and not committed.
- Created: 2026-10-12 16:19:55 +08:00.
- Size: 13,158,524 bytes.
- SHA-256: `B2A1E2ED1E0ACF363426233AECC296A2C05CFB8ED232ACFDF51893AB9A7FB9FA`.
- Dump options included `--single-transaction`, `--quick`, `--routines`, `--triggers`, `--events`, `--hex-blob`, `--set-gtid-purged=OFF`, `--no-tablespaces`, and `--databases short_drama_analysis`.
- Active database connections were inspected before the dump; only sleeping application pool connections and the audit query were present.

The dump was restored to an independently named temporary database. All 19 tables, columns, keys, constraints, indexes, row counts, table checksums, and four immutable-history triggers matched. Both restored and source snapshots produced fingerprint:

```text
4123F396B789FBB8E134F1A381A0BCA712E4199EDDE761EA14A02018BA91D3B8
```

The restore-verification database was removed after validation.

## 6. Isolated migration rehearsal

A second temporary database was restored from the verified backup. The fixed `USE short_drama_analysis` text was replaced only in the in-memory input stream so the unchanged migration files targeted the temporary schema.

Execution order and result:

1. V008 — PASS
2. V009 — PASS
3. V010 — PASS
4. V011 — PASS
5. V012 — PASS
6. V013 — PASS

The rehearsal database then contained the same 31-table structure as `short_drama_acceptance_v1`, with no structural differences. Existing row counts were preserved and all newly created tables were empty before functional tests. The rehearsal database was deleted after testing.

## 7. Development database changes

After a final preflight confirmed the exact target and the exact 12-table missing set, the original V008-V013 files were executed against `short_drama_analysis` in order. All six commands succeeded.

Immediately after migration:

- 31 tables existed.
- Development and acceptance table sets matched.
- Structural differences: none.
- Four original triggers were preserved.
- Inspected development totals: 31 primary keys, 52 foreign keys, 111 reflected indexes, 29 unique constraints, and 126 CHECK constraints.
- All 12 new tables were empty.
- All original business row counts were unchanged.

## 8. Prediction verification

### 8.1 Schema, ORM, Repository, and algorithm

- `prediction_results` matches V010 and the `PredictionResult` ORM mapping.
- Repository reads, chronological history queries, delete-and-replace persistence, uniqueness, and ordering execute successfully on MySQL.
- Moving Average V1.0 remains unchanged: eight consecutive cumulative daily points produce seven daily increments; their Decimal mean is rounded with `ROUND_HALF_UP` and added to the latest cumulative count.
- Metric remains `PLAY_COUNT`; version remains `Moving Average V1.0`; `analysis_as_of`, revision cutoff, latest visible revision selection, comparable platform intersection, and Decimal persistence were not changed.

Input screening across 131 dramas found:

- 4 dramas with a valid monotonic prediction window (`25`, `27`, `36`, `53`).
- 78 with a cumulative decrease in the selected comparable history (`INVALID_CUMULATIVE_SEQUENCE`, mapped to `INVALID_REVISION`).
- 25 with insufficient history.
- 24 with no history.

No source snapshot was fabricated or changed.

### 8.2 Actual development API results

| Scenario | Result |
| --- | --- |
| Anonymous calculate | 401 |
| Drama 120 latest | 404 `NOT_FOUND` |
| Drama 120 history | 200, empty items |
| Drama 120 calculate | 400 `INSUFFICIENT_HISTORY` |
| Drama 25 calculate | 200, predicted value `711830.00`, target date `2026-09-08` |
| Drama 25 latest | 200 |
| Drama 25 history | 200, one item |
| Drama 25 repeat calculate | 200; replacement retained one history item |

The replacement receives a new auto-increment ID while the unique identity remains one row. No prediction endpoint returned HTTP 500 after recovery.

## 9. Other module verification

All results below are actual development API results.

| Module | Verification |
| --- | --- |
| Composite Score | Calculate 200; 82 results generated through the Service; ranking 200; level distribution 200; drama 25 detail 200 |
| Data Quality persisted scoring | Rules 200 empty; current score 404; history 200 empty after compatibility fix; calculate 400 because no rules/evaluators are configured |
| Anomaly Detection | Detect 200; 2 findings generated through the Service; statistics/list 200 |
| Operation Action Center | List/statistics 200 with zero actions; no fake action was inserted |
| Explanation / Lineage | Queries 200 with empty items; no fake explanation or lineage record was inserted |
| Drama 360 Profile | Drama 25 profile 200; score and prediction available; quality/explanation correctly reported not calculated/not available |
| Operation Analytics | Effectiveness 200 empty; lifecycle and benchmark 200 with explicit `INSUFFICIENT` reasons |
| Data Governance | Overview/freshness/completeness/consistency all 200; actual statuses returned |
| Reporting | Catalog and prediction/score/anomaly previews 200; CSV and XLSX exports completed after the required 409 confirmation handshake |

Final derived row counts created only through existing APIs/Services:

- `drama_scores`: 82
- `prediction_results`: 1
- `data_anomaly_records`: 2
- `operation_logs`: 16 (audit reproduction and functional calculations)

## 10. Frontend and browser verification

Vite was started and tested with a real headless Microsoft Edge session using an isolated temporary browser profile. Credentials were read locally and were not printed.

- Login through the rendered form succeeded.
- `/predictions?drama_id=25` rendered the title, value `711,830`, algorithm version, one historical target date, and one ECharts canvas.
- Latest and history requests returned 200.
- Clicking “重新预测” sent the real calculate request, received 200, and displayed `预测生成成功：711,830`.
- Drama 120 rendered the two no-data states without an error alert; latest returned 404 and history returned 200 empty.
- The Composite Score page loaded without an error alert and its current-date ranking/distribution requests returned 200. It showed no rows for 2026-10-12 because the verified derived scores were generated for 2026-09-07.

The browser profile and all temporary browser processes were removed after testing.

## 11. Regression tests

| Check | Result |
| --- | --- |
| Targeted Data Quality repository/API/service tests | 42 passed |
| Full Backend pytest collection | 706 tests |
| Full Backend pytest execution | 706/706 passed; 2 third-party deprecation warnings |
| Python `compileall` | PASS |
| Frontend `vue-tsc --noEmit` | PASS |
| Frontend production build | PASS; existing large-chunk warnings only |
| Migration rehearsal | PASS |
| Post-migration schema comparison | PASS, no differences |
| API and browser regression | PASS with the business availability limitations documented above |

On this Windows runtime, pytest's default `0700` temporary-directory mode produced an ACL that even the owner could not traverse, causing 10 fixture setup errors. The complete run used a one-time process-local wrapper that changed only temporary directory creation mode. No test was skipped, deleted, weakened, or edited to hide the environment issue.

## 12. Final data and protected baseline checks

| Table | Before migration | Final | Explanation |
| --- | ---: | ---: | --- |
| `dramas` | 131 | 131 | Preserved |
| `drama_metric_snapshots` | 64,255 | 64,255 | Preserved |
| `drama_metric_snapshot_revisions` | 64,255 | 64,255 | Preserved |
| `drama_platforms` | 260 | 260 | Preserved |
| `drama_actors` | 792 | 792 | Preserved |
| `drama_directors` | 110 | 110 | Preserved |
| `drama_companies` | 251 | 251 | Preserved |
| `drama_tags` | 341 | 341 | Preserved |
| `drama_scores` | absent | 82 | Generated by Score API |
| `prediction_results` | absent | 1 | Generated by Prediction API |
| `data_anomaly_records` | absent | 2 | Generated by Anomaly API |

`short_drama_acceptance_v1` retained its original 31 tables and all initial row counts, including 5 dramas, 235 snapshots, 5 scores, 5 predictions, and 2 anomaly records. No temporary recovery schema remains.

## 13. Git status and commits

- Historical V001-V013 files: unchanged.
- `PROJECT_MASTER.md`, release materials, algorithms, and unrelated features: unchanged.
- Maintenance code commit: `f822f53182f91909c910b5b8bc2f9255c9ff4605` (`fix(data-quality): support MySQL history window query`).
- Backup: ignored, not staged, not committed.
- `v1.0.0`: still points to `0e350381d1fd7a16eaa9da5cf9bb92c24285c7de`.
- This report is committed separately from the code repair.

## 14. Recovery / rollback plan

Because MySQL DDL implicitly commits, rollback must use the verified dump rather than a transaction rollback.

Preferred non-destructive recovery procedure:

1. Stop Backend and all writers.
2. Preserve a forensic dump of the current failed state.
3. Restore the verified backup into a new, explicitly named recovery schema by replacing only the dump's database identifier in a copy or restore stream.
4. Re-run the same structure, trigger, row-count, and checksum comparison used in this task.
5. Change the local `DATABASE_URL` to the verified recovery schema and restart the Backend.
6. Keep the failed original schema untouched until the user authorizes disposal.

Restoring over or dropping `short_drama_analysis` is destructive and requires explicit user approval. The backup should not be removed until the recovery is accepted.

## 15. Remaining limitations and risks

- The project still has no migration execution ledger. Future maintenance should add an approved version-history mechanism without retroactively changing frozen migrations.
- All SQL migrations contain a fixed `USE short_drama_analysis`; operators must verify the target before execution. Rehearsals require a controlled copy/stream substitution.
- Data Quality persisted scoring cannot run until approved quality rules/evaluators are configured. Current 400/404/empty responses correctly distinguish this state from a server error.
- Only four current dramas satisfy the strict monotonic eight-day Prediction input contract. This is a data-quality/availability characteristic, not repaired by inventing source history.
- A real non-administrator account was not available in the development database. Anonymous 401 was exercised live; USER read/admin-write permission behavior remains covered by the passing API tests.
- The pre-backup append-only audit record described in section 3.6 is irreversible by design and is the only process deviation.
- The frontend build retains existing bundle-size warnings; they are unrelated to database recovery.

## 16. Completion classification

### Completed and verified

- Full structural audit, backup, restore validation, isolated rehearsal, V008-V013 development migration, schema comparison, Prediction recovery, dependent-module API regression, browser verification, full automated regression, and protected-baseline checks.

### Completed with limitations

- Data Quality persisted calculation remains unavailable because the database contains no active rule definitions/evaluators.
- Prediction availability is limited by real historical data quality; drama 120 is correctly unavailable while drama 25 is verified successful.
- One audit-log write occurred during traceback reproduction before the formal dump, as documented.

### Not performed

- No migration was applied to the acceptance/test databases.
- No source snapshots, quality rules, operation actions, explanations, or lineage facts were fabricated.
- No release tag, historical commit, frozen business rule, algorithm, migration, or acceptance artifact was changed.

### User confirmation required

- None for continued normal development use.
- Explicit approval would be required before destructive restoration over the current database or deletion of the verified backup.
