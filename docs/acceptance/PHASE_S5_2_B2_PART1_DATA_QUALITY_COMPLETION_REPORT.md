# Phase S5.2-B2 Part 1 — Data Quality Production Completion Report

| Item | Result |
|---|---|
| Report version | 1.0 |
| Review time | 2026-10-13 (Asia/Shanghai) |
| Starting Git baseline | `4fcae807e3af0017f4f28003f75109697a6782d9` |
| Code commit | `b0111f35fb4130fbed8715233b259cce9dc5f8c2` |
| Branch | `main` |
| Release baseline | annotated tag `v1.0.0` still peels to `0e350381d1fd7a16eaa9da5cf9bb92c24285c7de` |
| Phase status | **IMPLEMENTATION AND ISOLATED VERIFICATION COMPLETED — DEVELOPMENT DEPLOYMENT NOT PERFORMED** |

## 1. Scope and safety result

This phase implemented only the user-approved DQ-01 through DQ-04 scope:

- four reviewed production rules C4/A1/K2/T1;
- deterministic Evidence Repository and production evaluator registry;
- explicit, idempotent Seed check/apply workflow;
- Quality Score V1.0/V2.0 coexistence;
- version-safe `replace_scope_scores()` behavior;
- Service/API/frontend version-specific workflow;
- isolated MySQL, automated API/unit, and real browser verification.

No Explanation/Lineage pipeline, V014/V015, historical backfill, additional quality rule, or unrelated algorithm was implemented. V001-V013, `PROJECT_MASTER.md`, and `v1.0.0` were not modified.

All database writes were restricted to `short_drama_s5_2_b2_part1_20261013`. The isolated database was schema-cloned with 31 tables and zero copied business rows, populated only with controlled test data, and removed after verification (`information_schema` remaining count = 0).

## 2. Approved rules implemented

| Rule | Dimension | Scope and calculation | Threshold | Severity / weight / blocking |
|---|---|---|---:|---|
| `DQ_C_PLAY_COUNT_COVERAGE` | COMPLETENESS | Eligible Feed × seven complete Shanghai calendar days; covered feed/day requires a selected non-VOID revision with non-null `play_count`; score = covered/expected × 100 | 100 | ERROR / 1.000000 / no |
| `DQ_A_CUMULATIVE_NONNEGATIVE` | ACCURACY | In the same eligible seven-day window, each present cumulative metric value must be nonnegative; optional null interaction fields are excluded and missing `play_count` is already charged by C4 | 100 | ERROR / 1.000000 / no |
| `DQ_K_REVISION_CHAIN_VALID` | CONSISTENCY | For each related window Snapshot, validate every revision visible at `analysis_as_of`, including VOID: version sequence, INITIAL root, same-Snapshot predecessor chain | 100 | ERROR / 1.000000 / no |
| `DQ_T_SNAPSHOT_FRESHNESS` | TIMELINESS | For each Eligible Feed, use the latest valid Snapshot visible at `analysis_as_of`, without a seven-day restriction; bucket scores are 100/80/60/40/20, missing valid Snapshot = 0 | 80 | WARNING / 1.000000 / no |

Eligible Feed is exactly:

```text
Drama.status in {SERIALIZING, COMPLETED}
AND Platform.status = ACTIVE
AND DramaPlatform.status = ONLINE
```

The seven-day interval is `[score_date - 7 days 00:00, score_date 00:00)` in `Asia/Shanghai`, converted to UTC-naive MySQL boundaries. Feed identities and all query results use stable ordering and deduplication.

## 3. Evidence, as-of, VOID, and missing-data behavior

The Evidence Repository performs persistence access only; evaluators remain deterministic and have no database access or persistence side effects.

- Eligible Feed uses current master-data status. Every saved score records `replay_capability=LIMITED_CURRENT_MASTER`; the API/front end does not claim strict historical master-data reproduction.
- Revisions are visible when `changed_at <= analysis_as_of`.
- Selection is deterministic by maximum `(changed_at, snapshot_revision_id)` per Snapshot.
- A selected VOID revision invalidates that Snapshot and never falls back to an older revision of the same Snapshot.
- K2 receives the complete visible chain, including VOID revisions.
- T1 may use an earlier different Snapshot for the same feed after a later Snapshot is currently VOID; it never resurrects the older revision of that VOID Snapshot.
- Missing feed/day or missing required `play_count` lowers C4; missing valid T1 Snapshot scores 0. No interpolation, forward fill, or fabricated Evidence is used.
- A genuinely non-applicable rule returns `NOT_APPLICABLE`. If no Eligible Feed exists, all rules are non-applicable and the Service raises `INSUFFICIENT_QUALITY_DATA` without persisting a score.
- Any dimension without an APPLIED rule, zero effective denominator, invalid configuration, unknown evaluator, or Evidence/transaction failure stops the calculation and rolls back.

Supported historical replay is limited to retained Snapshot/Revision facts. Drama, Platform, and DramaPlatform are not full bitemporal master data, so historical scope replay remains explicitly limited.

## 4. V1/V2 compatibility and repository defect repair

### V1.0

V1 keeps its historical binary meaning: within each dimension, PASS weights count as 100 and FAIL weights as 0. No V1 formula, dimension weight, grade boundary, or rounding behavior was changed.

### V2.0

V2 uses only APPLIED rule scores:

```text
dimension_score = Σ(weight × rule_score) / Σ(APPLIED weight)
total_score = 0.30*C + 0.30*A + 0.25*K + 0.15*T
```

Inputs are finite Decimal values, rule scores are in `[0, 100]`, weights are in `(0, 1]`, and dimension/total results use `ROUND_HALF_UP` to two decimal places. Existing grade boundaries are retained.

### Version isolation repair

Root cause: the previous `replace_scope_scores()` delete predicate omitted `algorithm_version` and `rule_set_hash`. Recomputing one algorithm could delete the other algorithm's result for the same date/rule set/scope.

Repair:

- replacement now uses the full persisted identity: date + algorithm version + rule-set version + rule-set hash + scope type + scope ID;
- the Service first performs an exact-identity lookup and returns the existing result for an identical repeat request;
- current/history queries explicitly filter algorithm version;
- API and TypeScript contracts accept V1 or V2;
- the frontend defaults to the approved current combination (V2), offers an explicit V1 selector, and never mixes versions in one trend.

No DQ schema migration was required because the existing V009 unique constraint already includes the algorithm version and rule-set hash.

## 5. Seed mechanism

`backend/app/seed_data_quality_rules.py` provides an explicit command; application startup never inserts rules.

Safety properties:

- exact `--expected-database` guard;
- mandatory explicit `--valid-from`;
- default CHECK mode is read-only;
- APPLY requires an existing administrator ID;
- stable identity is `(rule_code, rule_version)`;
- missing rules are inserted atomically with an operation-log audit event;
- an exact second run is a no-op;
- the same identity with different reviewed content is a hard conflict, never a silent update;
- failures roll back the rule rows and audit event together.

The development database Seed was deliberately not executed. The production-effective `valid_from` timestamp was not specified in the approval and affects rule applicability, so it remains an explicit deployment approval item.

## 6. API and frontend behavior

The following existing endpoints remain in use and now support precise algorithm selection:

- `POST /api/v1/data-quality/calculate` accepts `algorithm_version` (V2 default); administrator-only authorization remains enforced by the backend.
- `GET /api/v1/data-quality/score` accepts an optional algorithm version (V2 default).
- `GET /api/v1/data-quality/history` accepts an optional algorithm version and returns only that version.
- `GET /api/v1/data-quality/rules` exposes currently effective active rules even before the first score exists.

The frontend adds a V1/V2 selector, version-specific loading and trend queries, a precise `INSUFFICIENT_QUALITY_DATA` message, and the visible `LIMITED_CURRENT_MASTER` historical warning. It does not recalculate scores or grades in JavaScript.

## 7. Isolated MySQL evidence

The guarded integration test refuses any database name outside the prefix `short_drama_s5_2_b2_part1_` and explicitly denies the development, acceptance, and existing test databases.

Observed result on a schema-only 31-table clone:

| Check | Actual result |
|---|---|
| Seed first/second APPLY | 4 inserted / 0 inserted, 4 unchanged |
| Eligible Feed filter | 1 included; draft/inactive feed excluded |
| Seven-day window | 7 deterministic Snapshot slots |
| Future correction | revision after as-of not visible |
| VOID selection | latest VOID selected then Snapshot excluded; no same-Snapshot fallback |
| V2 calculation | C=100, A=100, K=100, T=80, total=97.00, grade S |
| V1 compatibility | four PASS dimensions, total=100.00, grade S |
| Persistence | 2 scores and 8 rule results coexist |
| Repeat V2 request | same `quality_score_id`, no rewrite |
| History/current query | V1 and V2 independently selectable |
| Forced audit failure | whole new score transaction rolled back; score count remained 2 |

## 8. Browser verification

Automated real-browser verification used the isolated backend and actual API data. It passed at 1920×1080 and 1366×768, verified no horizontal overflow at 1366, displayed all four real rules and the limitation warning, and switched from V2 (97.00) to V1 (100.00).

- [1920×1080 V2 evidence](evidence/phase_s5_2_b2_part1/data-quality-v2-1920x1080.png)
- [1366×768 V2 evidence](evidence/phase_s5_2_b2_part1/data-quality-v2-1366x768.png)

This is Agent browser verification, not user acceptance.

## 9. Regression results

| Validation | Result |
|---|---|
| Backend full pytest | **724 passed, 1 skipped**, 2 dependency deprecation warnings, 20.46s |
| Skipped test | opt-in MySQL integration test; run separately and passed 1/1 |
| Targeted architecture/Seed/repository | 36 passed |
| Python compileall | passed |
| Frontend `vue-tsc --noEmit` | passed as part of build |
| Frontend production build | passed; only pre-existing large-chunk warning |
| Browser verification | passed at both requested resolutions plus V1/V2 switching |
| `git diff --check` before commit | passed |

The first full pytest invocation exposed a real Service-layer ORM import in the new Seed code; persistence was moved into repositories and the architecture test then passed. The remaining initial errors were Windows/Python 3.12 pytest `tmp_path` ACL behavior. A one-process test launcher ignored only the `mkdir(0700)` mode argument; no test source or expectation was changed, and the resulting full suite passed.

## 10. Protected database verification

Read-only counts after all tests:

| Database | Tables | Dramas | Snapshots | Revisions | DQ rules | DQ results | DQ scores |
|---|---:|---:|---:|---:|---:|---:|---:|
| `short_drama_analysis` | 31 | 131 | 64,255 | 64,255 | 0 | 0 | 0 |
| `short_drama_acceptance_v1` | 31 | 5 | 235 | 235 | 1 | 1 | 1 |

No write was made to either protected database. The existing `short_drama_analysis_test` database was not targeted. No backup, credentials, temporary browser profile, or isolated database was added to Git.

## 11. Files and commits

The code commit changes only the authorized backend analytics/repository/service/router/schema, frontend Data Quality API/types/view, explicit Seed CLI, test support, and targeted tests:

```text
b0111f35fb4130fbed8715233b259cce9dc5f8c2
feat(data-quality): complete production scoring workflow
```

This report and its two screenshots are intentionally delivered in a separate documentation commit.

## 12. Remaining approvals and stop conditions

### APPROVAL REQUIRED before development deployment

1. Approve the exact UTC-naive `valid_from` timestamp for DQ Rules 1.0.
2. Approve the existing administrator ID to record as Seed actor (the report must not contain credentials).
3. Explicitly authorize CHECK/APPLY against `short_drama_analysis` after a fresh backup/read-only preflight.
4. After Seed, explicitly authorize any first persistent V1/V2 calculation in the development database.

### Known limitations

- Historical eligibility uses current master state and is marked `LIMITED_CURRENT_MASTER`.
- The remaining 12 candidate rules are not implemented.
- V1 and V2 results must not be compared as if they used the same scoring semantics.
- User manual acceptance has not occurred.

### Hard stop

Do not deploy, initialize development/acceptance rules, backfill scores, implement Explanation/Lineage, execute V014/V015, or enter B2 Part 2 / S5.2-C without a separate user authorization.

## 13. Conclusion

The authorized Phase S5.2-B2 Part 1 implementation is complete and reproducibly verified in isolation. It is ready for user review of the code and evidence, but it has **not** been deployed to the development database and is **not** a declaration of production readiness or user acceptance.
