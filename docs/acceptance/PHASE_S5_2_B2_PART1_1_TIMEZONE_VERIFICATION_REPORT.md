# Phase S5.2-B2 Part 1.1 Timezone Verification Report

**Status:** TIMEZONE VERIFIED — DEVELOPMENT DEPLOYMENT PENDING APPROVAL

**Review date:** 2026-10-13 (Asia/Shanghai)

**Software baseline before this work:** `f459800c171e8d9333d80d856cd0da8b6218f22c`

**Timezone fix commit:** `6df96b7` (`fix(database): initialize mysql sessions in utc`)

**Target development database:** `short_drama_analysis` (read-only during this phase)

## 1. Scope and safety result

This phase verified the historical timestamp semantics, fixed future MySQL connection
sessions, restored a full development backup into isolated databases, and rehearsed
the approved four-rule Data Quality workflow. It did **not** run Seed APPLY, persist a
quality score, update a historical timestamp, or backfill data in
`short_drama_analysis`. It did not write to `short_drama_acceptance_v1`.

The formal Data Quality deployment remains blocked until the user approves a
production implementation/configuration for the verified legacy timestamp read
policy. `SET time_zone = '+00:00'` fixes future server-generated values but does not
reinterpret existing `DATETIME(6)` values.

## 2. Git and database baseline

| Item | Verified value |
|---|---|
| Branch | `main` |
| Initial HEAD | `f459800c171e8d9333d80d856cd0da8b6218f22c` |
| `v1.0.0` peeled commit | `0e350381d1fd7a16eaa9da5cf9bb92c24285c7de` |
| Origin | expected GitHub repository (credentials not embedded) |
| Remote divergence after fetch | remote ahead 0, local ahead 113 before this phase's commits |
| Development tables | 31 |
| Dramas / snapshots / revisions | 131 / 64,255 / 64,255 |
| DQ rules / rule results / scores | 0 / 0 / 0 before and after this phase |
| Existing operation logs | 17 before and after this phase |
| Administrator audit identity | `user_id=1`, `ADMINISTRATOR`, `ACTIVE` (rechecked read-only) |

The acceptance database remained at 5 dramas, 235 snapshots, 235 revisions, one DQ
rule result and one DQ score. No acceptance-database write was performed.

## 3. Timestamp schema and root cause

Schema inspection against `information_schema.columns` and the ORM established:

| Field | MySQL type | ORM type | Write source |
|---|---|---|---|
| `drama_metric_snapshots.snapshot_time` | `DATETIME(6)` | MySQL `DATETIME(6)` | application converts business time to UTC-naive |
| `drama_metric_snapshot_revisions.changed_at` | `DATETIME(6)` | MySQL `DATETIME(6)` | `CURRENT_TIMESTAMP(6)` default |
| `operation_logs.occurred_at` | `DATETIME(6)` | MySQL `DATETIME(6)` | `CURRENT_TIMESTAMP(6)` default |
| `import_jobs.started_at/finished_at` | `DATETIME(6)` | MySQL `DATETIME(6)` | explicit application UTC-naive values |
| `import_jobs.created_at/updated_at` | `DATETIME(6)` | mixin `DATETIME(6)` | MySQL timestamp defaults |

The server had `@@global.time_zone=SYSTEM`, `@@session.time_zone=SYSTEM`, and
`NOW() - UTC_TIMESTAMP() = 480 minutes`. The schema contract in `PROJECT_MASTER.md`
requires UTC-naive `DATETIME(6)` values and a UTC connection session, but the runtime
engine did not initialize the session timezone.

For all 64,255 INITIAL revisions joined to their source import job:

- `changed_at - started_at` minimum: 480.0333 minutes;
- average: 480.9934 minutes;
- maximum: 482.3000 minutes.

For eight import-linked operation logs, the same range was 480.0000 to 482.3000
minutes. This is consistent with server-local Asia/Shanghai wall-clock defaults being
stored literally while application timestamps were UTC-naive.

Reading the same revision in `+00:00` and `+08:00` sessions returned the identical
`changed_at` value. Only `NOW()` changed. Therefore the historical discrepancy is not
`TIMESTAMP` session conversion; it is a `DATETIME` value written under a non-UTC
session.

## 4. Code correction

`backend/database/engine.py` now attaches a SQLAlchemy physical-connection listener
that executes:

```sql
SET time_zone = '+00:00'
```

The listener runs for every new pooled MySQL DBAPI connection and always closes its
cursor. It does not run for non-MySQL engines. No migration or historical update is
included.

Verification:

- unit tests cover the statement and cursor cleanup on success/failure;
- a live connection returned `@@session.time_zone = '+00:00'` and exact equality of
  `NOW(6)` and `UTC_TIMESTAMP(6)`;
- after `engine.dispose()`, a newly-created pooled connection returned the same result;
- isolated Seed/audit rows created after the fix used UTC wall-clock values.

## 5. The 44 invisible revisions

For score date 2026-09-09, the approved Shanghai window maps to UTC-naive
`[2026-09-01 16:00:00, 2026-09-08 16:00:00)`. The as-of cutoff is
`2026-09-09 15:59:59.999999` UTC-naive.

The window contains 4,698 snapshot slots. Under the raw historical values, 4,654 had
a visible revision and 44 did not. The 44 rows:

- belong to 22 Eligible Feeds;
- came from the same source import execution;
- have raw `changed_at` values from `2026-09-09 19:41:11.670933` through
  `2026-09-09 19:41:11.712205`;
- are 481.3147 to 481.3154 minutes after their explicit UTC `started_at`;
- all become visible when the verified legacy Shanghai wall-clock value is interpreted
  as UTC by subtracting eight hours.

No historical row was updated. A read-only compatibility rehearsal used the immutable
watermark `snapshot_revision_id <= 64255` and an `-08:00` interpretation. New revisions
must remain unshifted after the UTC connection fix. This watermark policy was validated
against the restored data but is not yet wired into the production repository; doing
so requires the next explicit deployment approval.

## 6. Recalculated scores

The approved rule parameters, weights, severities, thresholds, Eligible Feed logic,
window, VOID behavior, and calculators were unchanged.

| Result | Raw historical read | Verified legacy-time interpretation | Change |
|---|---:|---:|---:|
| C4 | 79.43 (1,251 / 1,575) | 82.22 (1,295 / 1,575) | +2.79; 44 feed-days became evidenced |
| A1 | 100.00 (23,270 / 23,270) | 100.00 (23,490 / 23,490) | score unchanged; 220 metric values added |
| K2 | 99.06 (4,654 / 4,698) | 100.00 (4,698 / 4,698) | 44 complete chains became visible |
| T1 | 61.78 (121 / 225 feeds at threshold) | 69.60 (143 / 225) | 22 feeds gained their actual latest revision |
| Quality Score V2.0 | 87.86 / A | 90.11 / S | changed because V2 aggregates rule scores |
| Quality Score V1.0 | 30.00 / C | 55.00 / C | K2 changed from binary FAIL to PASS |

The improved scores are a consequence of the verified timestamp interpretation, not
a threshold adjustment, interpolation, zero-fill, selected favorable as-of, or data
mutation. Results retain `LIMITED_CURRENT_MASTER` because eligible master-data status
is current-state, not a fully historical bitemporal replay.

## 7. `valid_from`, `score_date`, and as-of

The current repository activates rules with
`valid_from <= analysis_as_of`; it does not directly compare `score_date` with
`valid_from`.

For the proposed `valid_from = 2026-09-08 16:00:00` UTC-naive:

- at `2026-09-08 15:59:59.999999`, zero rules are active;
- at `2026-09-08 16:00:00`, all four are active;
- the service maps historical score date 2026-09-08 to
  `2026-09-08 15:59:59.999999`, and 2026-09-09 to
  `2026-09-09 15:59:59.999999`.

Thus 2026-09-09 is the first verified acceptance date for this proposed activation
timestamp. This does not add a separate score-date lower-bound contract and does not
authorize broader historical calculation.

## 8. Backup and recovery verification

The full development database was backed up with a consistent single transaction,
structure, data, indexes/constraints, triggers, routines and events as applicable.

| Item | Result |
|---|---|
| Backup file | `backup_phase_s5_2_b2_part1_1_short_drama_analysis_20261013_222311.sql` (Git-ignored) |
| Size | 13,204,229 bytes |
| SHA-256 | `A0F574573B6EB10615D4BEFD26CF99E2E66F56F4BBA96762CF49A148BFA6D4FB` |
| Dump exit status | 0 |
| Restore exit status / stderr | 0 / 0 bytes |
| Restored table count | 31 |
| Per-table row counts | identical for every table |
| Schema metrics | 238 constraints, 289 index-column rows, 4 triggers, 0 events, 0 routines; identical |

No source database was overwritten, deleted, or rebuilt.
After verification, the three explicitly named temporary restore/rehearsal/integration
databases created by this phase were removed and their absence was rechecked. The
verified SQL backup was retained.

## 9. Isolated deployment rehearsal

The rehearsal restored the verified dump and used the exact proposed parameters:

- four `DQ Rules 1.0` rules;
- `valid_from=2026-09-08T16:00:00` UTC-naive;
- score date 2026-09-09;
- as-of `2026-09-09T15:59:59.999999Z`;
- global `ALL/0` scope;
- administrator `user_id=1`;
- Quality Score V2.0 and V1.0 once each.

Results:

- CHECK before apply: no writes;
- APPLY: 4 inserts, configuration hash
  `2be36e9c28fa2763e1b5b244f6b5b1a89ef6bd59a57f0116f4882180e607d9d5`;
- CHECK after apply and repeated APPLY: four unchanged, zero inserts;
- deliberate `DQ_C_PLAY_COUNT_COVERAGE@1.0` weight conflict: detected and rolled back;
- V2 and V1 persisted with 8 total rule results and separate score IDs;
- repeated V2 returned the original V2 ID (idempotent);
- forced audit-log failure left all score/result counts unchanged;
- isolated counts changed from rules/results/scores/logs `0/0/0/17` to
  `4/8/2/20` exactly.

The expected formal development write, if the legacy read policy and deployment are
later approved, is therefore exactly +4 rules, +8 rule results, +2 scores and +3
operation logs. Current auto-increment candidates are rules 1, results 1, scores 1 and
operation logs 18; final IDs must still be rechecked immediately before deployment.

## 10. Regression results

| Check | Result |
|---|---|
| Targeted UTC engine tests | 2 passed |
| Backend full pytest | 726 passed, 1 skipped, 2 deprecation warnings |
| Skipped real-MySQL DQ integration, run separately | 1 passed |
| Python `compileall` | passed |
| Frontend `vue-tsc --noEmit` | passed |
| Frontend production build | passed; existing large-chunk warning only |
| Development DB integrity recheck | 131 / 64,255 / 64,255 retained; DQ remains 0/0/0 |

Two preliminary pytest attempts were invalid because the existing Windows pytest temp
root denied access. The authoritative run used a fresh explicit temp directory and
passed. No assertion was removed or weakened.

## 11. GitHub safety audit

After `git fetch origin --prune`, the branch had no remote-only commit and was 113
commits ahead before this phase. The complete pending range was audited, including
deleted paths and 88,784 textual patch lines.

- no committed `.env`, dump, backup, private key, GitHub/OpenAI/AWS token or JWT was
  found;
- database URL matches in examples use uppercase placeholders only;
- the only deleted path in the pending range was a Python service file;
- **blocking finding:** historical commit `989c3e6` contains a local Windows user path
  in `docs/acceptance/BUILD_VERIFICATION.md` (reported here as
  `C:\Users\<redacted>\...`). This category was explicitly prohibited by the push
  requirements.

Consequently, no `git push` was performed. The repository history was not rewritten,
no force push was attempted, and `v1.0.0` was not changed. A user-approved remediation
decision is required before GitHub synchronization.

## 12. Remaining approval gates

1. Approve or revise the non-mutating legacy read policy: only immutable revisions at
   or below the verified transition watermark (`snapshot_revision_id <= 64255`) are
   interpreted as Asia/Shanghai wall-clock and normalized by `-08:00`; later revisions
   remain UTC-naive.
2. After that policy is implemented and retested, explicitly approve Seed APPLY and
   the two limited score writes to `short_drama_analysis`.
3. Recheck administrator 1 and all source/target counts immediately before write.
4. Decide how to remediate the local-path disclosure in the unpushed historical commit
   before any GitHub push. No history rewrite should occur without explicit approval.
5. Browser acceptance against the development database remains pending because the
   development Seed and scores were intentionally not deployed.

No work on Explanation/Lineage, V014/V015, historical backfill, Dashboard redesign, or
copyright finalization was performed.
