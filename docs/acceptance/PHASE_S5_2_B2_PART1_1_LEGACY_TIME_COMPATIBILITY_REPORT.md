# Phase S5.2-B2 Part 1.1-F Legacy Time Compatibility Report

**Status:** LEGACY TIME COMPATIBILITY VERIFIED — DEVELOPMENT DEPLOYMENT PENDING APPROVAL

**GitHub status:** GITHUB PUSH PENDING USER APPROVAL

**Review date:** 2026-10-14 (Asia/Shanghai)

**Starting Git baseline:** `b9a99dbe11386b2782884c7dd0077f82658dff26`

**Compatibility implementation commit:** `51d9cfb` (`fix(data-quality): normalize legacy revision timestamps`)

**Target development database:** `short_drama_analysis` (read-only throughout this phase)

## 1. Outcome and safety boundary

The old Revision population can be classified without rewriting historical rows. The
implemented policy is explicitly scoped to one audited database and one immutable ID
cutover, and validates the old population's count and raw timestamp range before any
Evidence query. A mismatch fails closed instead of silently applying an eight-hour
conversion to unknown data.

This phase did **not** run Seed APPLY, persist a quality score, backfill or update a
historical timestamp in `short_drama_analysis`. It did not write to
`short_drama_acceptance_v1`, modify V001-V013, execute V014/V015, or change the
`v1.0.0` tag.

## 2. Verified baseline

| Item | Verified value |
|---|---|
| Initial branch / HEAD | `main` / `b9a99dbe11386b2782884c7dd0077f82658dff26` |
| Initial origin/main | `b9a99dbe11386b2782884c7dd0077f82658dff26` |
| Initial ahead / behind | 0 / 0 |
| `v1.0.0` peeled commit | `0e350381d1fd7a16eaa9da5cf9bb92c24285c7de` |
| Development dramas | 131 |
| Development snapshots / revisions | 64,255 / 64,255 |
| Development DQ rules / results / scores | 0 / 0 / 0 |
| Development operation logs | 17 |
| Audit actor | `user_id=1`, `ACTIVE`, `ADMINISTRATOR` (read-only recheck) |
| Acceptance dramas / snapshots / revisions | 5 / 235 / 235 (read-only recheck) |

## 3. Revision identity and source audit

The development Revision table contained 64,255 rows with IDs 1 through 64,255,
64,255 distinct IDs, no gaps, and `AUTO_INCREMENT=64256`. Every row was version 1,
action `INITIAL`; there were no historical `CORRECTION` or `VOID` rows.

Every Revision and Snapshot was traceable through a persisted import source:

| Import job | Revision ID range | Revision count |
|---|---:|---:|
| 2 | 1-47,450 | 47,450 |
| 3 | 47,451-64,123 | 16,673 |
| 25 | 64,124-64,255 | 132 |

For all 64,255 rows, `changed_at - import_jobs.started_at` was approximately
480.03-482.30 minutes. Together with the `DATETIME(6)` schema and invariant reads
under `+00:00` and `+08:00` sessions, this proves that the existing raw `changed_at`
values are Asia/Shanghai wall-clock values, not MySQL `TIMESTAMP` conversions.

Import metadata is strong audit evidence for the existing population, but it cannot
classify a future UTC `CORRECTION` or `VOID` written against an old Snapshot. Snapshot
age and import ownership were therefore rejected as runtime classifiers.

## 4. Classification decision

Three strategies were assessed:

| Strategy | Decision | Reason |
|---|---|---|
| Import Batch/source metadata | Evidence only | Cannot distinguish a future UTC Revision on an old Snapshot. |
| Audited ID cutover | Implemented, database-scoped | Existing population is contiguous and future auto IDs start above 64,255. New rows are classified per Revision, not per Snapshot. |
| Explicit per-row time metadata | Deferred | Strongest long-term model, but requires an unapproved Migration and historical metadata initialization. |

The cutover is **not** a universal hard-coded constant. Deployment must provide one
complete configuration bundle: database name, maximum legacy Revision ID, expected
legacy row count, and expected minimum/maximum raw `changed_at`. Partial configuration
is rejected during settings validation. A database-name or fingerprint mismatch raises
`LegacyRevisionClassificationError` before Evidence calculation.

The audited development candidate is:

- database: `short_drama_analysis`;
- legacy maximum ID: 64,255;
- expected count at or below cutover: 64,255;
- expected minimum raw `changed_at`: `2026-09-08 21:36:34.682889`;
- expected maximum raw `changed_at`: `2026-09-09 19:41:11.712205`.

Activating this bundle in the development runtime remains part of the separately
approved deployment procedure; it was not added to the secret `.env` in this phase.

## 5. Normalization and query semantics

`backend/repositories/data_quality_evidence_repository.py` now centralizes the two
semantics:

- `LEGACY_SHANGHAI_WALL_CLOCK`: attach `Asia/Shanghai`, convert to UTC, then return a
  UTC-naive value while preserving microseconds;
- `UTC_NAIVE`: keep the persisted value unchanged.

The historical dates are in 2026 and resolve to UTC+08:00 under the IANA
`Asia/Shanghai` zone. The implementation intentionally uses `zoneinfo` rather than a
general fixed eight-hour subtraction.

SQL visibility uses two bounded predicates so legacy rows are not discarded before
normalization:

- legacy ID range: raw `changed_at <= analysis_as_of` expressed as Shanghai wall time;
- post-cutover range: raw `changed_at <= analysis_as_of` in UTC-naive form.

The application normalizes every returned value, defensively reapplies
`normalized_changed_at <= analysis_as_of`, then orders by
`(normalized_changed_at, snapshot_revision_id)`. Equal timestamps therefore have a
stable ID tie-break. Rows remain grouped by their real Snapshot ID and Evidence keeps
the real Revision ID.

The latest visible Revision is selected before validity interpretation. If it is
`VOID`, the Snapshot remains void and the code does not fall back to an older valid
Revision. Version-chain validation still sees the complete visible chain.

`EXPLAIN` on the restored production-shaped database showed indexed access through
the eligible feed relation, Snapshot unique index, and Revision unique index. The
query is bounded by eligible feed IDs and does not perform an unbounded Revision table
scan. Three full compatibility loads took 2.4062, 2.8674 and 2.7580 seconds.

## 6. Mixed old/new chains

Unit and real MySQL integration tests cover an old Snapshot followed by new UTC
`CORRECTION` and `VOID` rows. Because classification belongs to each Revision ID:

- the legacy INITIAL row is converted from Shanghai wall time;
- later UTC rows retain their UTC value;
- normalized ordering selects the actual latest visible row;
- a later visible VOID remains selected and prevents fallback;
- `previous_revision_id` and version numbers are unchanged;
- an exact `analysis_as_of` boundary is inclusive;
- a row after `analysis_as_of` is excluded.

The same tests cover ID gaps, database/fingerprint mismatch, absent Revisions,
incomplete chains, wrong Snapshot ownership, no eligible feed, missing natural days,
duplicate Evidence prevention, and current-master limitation reporting.

## 7. The 44 previously invisible Revisions

For the approved seven-day window, there were 4,698 Snapshot slots. Raw UTC-naive
comparison selected 4,654; compatibility comparison selected all 4,698. The recovered
set is exactly 44 Revisions across 22 eligible feeds.

Their raw Shanghai wall-clock range is
`2026-09-09 19:41:11.670933` through `2026-09-09 19:41:11.712205`; normalized UTC is
`2026-09-09 11:41:11.670933` through `2026-09-09 11:41:11.712205`. Every recovered row
belongs to the audited legacy population and falls before the approved
`analysis_as_of=2026-09-09 15:59:59.999999Z`. No additional row was incorrectly added.

The drama 6 sample had one eligible feed, 22 relevant window Snapshot slots, and 22
selected Revisions; it remains a fully evidenced manual-check sample.

## 8. Isolated full-data calculation

The verified deployment candidate parameters were used unchanged:

- `valid_from`: `2026-09-08 16:00:00` UTC-naive;
- `score_date`: `2026-09-09`;
- seven-day window: `2026-09-02` through `2026-09-08`, Asia/Shanghai;
- `analysis_as_of`: `2026-09-09 15:59:59.999999` UTC-naive;
- scope: `ALL/0`;
- rules: approved C4/A1/K2/T1 definitions and weights.

| Rule | Result | Evidence |
|---|---:|---|
| C4 play-count coverage | 82.22 | 1,295 / 1,575, 280 failures |
| A1 cumulative nonnegative | 100.00 | 23,490 / 23,490 |
| K2 Revision chain valid | 100.00 | 4,698 / 4,698 |
| T1 Snapshot freshness | 69.60 | 143 / 225 meet threshold, 82 failures |
| Quality Score V2.0 | 90.11 / S | weighted `rule_score` calculation |
| Quality Score V1.0 | 55.00 / C | preserved binary historical semantics |

These values were computed by the production Service and evaluators against the
restored real-data copy; they are not hard-coded test expectations. Differences from
the earlier raw-time result are explained by the recovered visibility and consequent
Evidence denominator changes, not by threshold or formula changes.

## 9. Isolated deployment rehearsal

The backup was restored into an independently named schema. The rehearsal produced:

| Table | Delta |
|---|---:|
| `data_quality_rules` | +4 |
| `data_quality_rule_results` | +8 |
| `data_quality_scores` | +2 |
| `operation_logs` | +3 |

Seed CHECK made no write. First APPLY inserted four rules; repeated APPLY was a no-op
with four unchanged rules. A deliberate same-ID/version content conflict aborted and
rolled back. V2 and V1 coexisted; repeated V2 returned the same score ID. An injected
operation-log failure rolled back the attempted results, score and log together.

All stage-only schemas were removed after verification. Their exact names were
checked against the guarded `short_drama_s5_2_b2_part1_` prefix and protected database
deny-list before deletion.

## 10. Regression evidence

| Check | Result |
|---|---|
| Backend full pytest | 741 passed, 2 skipped (743 collected) |
| Opt-in mixed legacy/UTC MySQL test | 1 passed separately |
| Opt-in full Data Quality MySQL workflow | 1 passed separately |
| Python compileall | passed |
| Frontend `vue-tsc --noEmit` | passed as part of build |
| Frontend production build | passed; existing large-chunk warning only |

The two full-suite skips are precisely the opt-in MySQL tests that require guarded
database URLs; both were executed separately and passed. An initial pytest invocation
from `backend/` exposed two existing tests that assume repository-root CWD. The full
suite was rerun from the documented repository root rather than skipping those tests,
and all non-opt-in tests passed.

## 11. Data integrity and backup

The retained backup file was rechecked locally:

- size: 13,204,229 bytes;
- SHA-256: `A0F574573B6EB10615D4BEFD26CF99E2E66F56F4BBA96762CF49A148BFA6D4FB`;
- restore: successful into an independent schema;
- restored business counts: 131 dramas, 64,255 snapshots, 64,255 Revisions.

The backup is ignored by Git and was not staged. Development counts after this phase
remain 131 / 64,255 / 64,255 and 0 / 0 / 0 DQ rules/results/scores. Acceptance data
was not modified.

## 12. Code changes

- `backend/config/settings.py`: complete-bundle validation for the database-specific
  cutover and fingerprint.
- `backend/repositories/data_quality_evidence_repository.py`: policy validation,
  SQL visibility split, centralized normalization, normalized ordering, and Evidence
  provenance fields.
- `backend/routers/dependencies.py`: request-scoped policy composition.
- `backend/.env.example`: non-secret, disabled deployment placeholders.
- targeted unit and guarded MySQL integration tests.

No rule threshold, severity, weight, Quality Score formula, public API schema, or
historical database field was changed.

## 13. GitHub security status

The implementation was committed locally as `51d9cfb`, followed by the acceptance
documentation commit. A fresh `git fetch --no-tags origin main` left `origin/main` at
the starting baseline and produced no divergence: local ahead 2, behind 0 before the
final audit-note commit. The origin fetch and push URLs both identify the expected
public GitHub repository, and the current branch is `main`.

All eight newly introduced Blob objects were scanned, including complete contents
rather than only the working-tree diff. They total 91,044 bytes, are all text, and
contain no private key, GitHub/OpenAI/AWS/Slack token, JWT, SQL dump signature,
non-example `.env`, backup, database file, Windows user path, or new binary object.
The one author email used by the new commits matches the already-published repository
author identity. Changed paths are limited to the Evidence compatibility code, its
configuration/dependency composition, tests, `.env.example`, and this report.

Local `v1.0.0` still peels to
`0e350381d1fd7a16eaa9da5cf9bb92c24285c7de`. The remote currently has no
`v1.0.0` tag; this phase did not create or push one. The worktree was clean after the
local commits and no force operation, rebase, reset, Release creation, or `git push`
was performed. The new commits satisfy the technical conditions for a normal
fast-forward main push, but this task explicitly retains the user approval gate.

## 14. Deployment recommendation and remaining gates

The compatibility mechanism is ready for controlled development deployment. The next
authorized deployment should:

1. fetch and revalidate Git state;
2. recheck the development fingerprint and active administrator;
3. validate the retained backup and isolated restore;
4. configure the complete five-field legacy policy bundle;
5. run Seed CHECK and inspect its exact plan;
6. only after explicit user approval, run Seed APPLY and the single V2/V1 scoring
   pair for the approved date/scope;
7. compare exact table deltas and execute API/browser acceptance.

Still not authorized: development Seed APPLY, development score persistence, bulk
historical backfill, V014/V015, Explanation/Lineage work, and GitHub push.

The ID-cutover solution depends on the audited legacy range being immutable. Any
change inside ID 1-64,255, database restore under a different schema name, or
fingerprint mismatch is a hard stop. A future schema-level per-Revision time-semantics
marker remains the preferred long-term alternative if a new Migration is approved.

**Final phase state:** LEGACY TIME COMPATIBILITY VERIFIED — DEVELOPMENT DEPLOYMENT PENDING APPROVAL

**Remote synchronization state:** GITHUB PUSH PENDING USER APPROVAL
