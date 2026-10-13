# DQ Rules 1.0 最终候选提案

| 项目 | 值 |
|---|---|
| 文档版本 | 0.2 |
| 适用基线 | `15b161c09f78b804c42802bc76108613e77d9508` |
| 状态 | **PROPOSED — APPROVAL REQUIRED** |
| 设计依据 | Phase 2 Design V2 `:363-480,506-517`；V009；Snapshot/Relation ORM；Phase 9 只读 Evidence 设计 |

本文收敛 B1 的 16 个方向，但不把提案值冒充原始冻结设计。`VERIFIED` 表示仓库已有依据；`PROPOSED` 表示推荐参数；`UNRESOLVED` 表示不得实现。

## 1. 候选全集：身份与发布控制

下列 Rule ID 均是候选稳定业务键；原设计没有给出 ID。权重是维度内权重。

| Ref | 候选 Rule ID / 名称 | 维度 / 对象 | severity / weight / block | version | 发布建议 |
|---|---|---|---|---|---|
| C1 | `DQ_C_DRAMA_REQUIRED_FIELDS` / 短剧必填字段 | COMPLETENESS / DRAMA | UNRESOLVED / UNRESOLVED / 否（PROPOSED） | 1.0 | 延后 |
| C2 | `DQ_C_ONLINE_AT_PRESENT` / 在线关系上线时间 | COMPLETENESS / DRAMA_PLATFORM | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| C3 | `DQ_C_CURRENT_REVISION_PRESENT` / 当前修订完整性 | COMPLETENESS / SNAPSHOT | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| C4 | `DQ_C_PLAY_COUNT_COVERAGE` / 七日播放量覆盖 | COMPLETENESS / SNAPSHOT | ERROR / 1.000000 / 否（均 PROPOSED） | 1.0 | **首批** |
| C5 | `DQ_C_IMPORT_PROCESSED_COVERAGE` / 导入处理覆盖 | COMPLETENESS / IMPORT_JOB | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| A1 | `DQ_A_CUMULATIVE_NONNEGATIVE` / 累计指标非负 | ACCURACY / SNAPSHOT | ERROR / 1.000000 / 否（均 PROPOSED） | 1.0 | **首批** |
| A2 | `DQ_A_RANK_POSITIVE_OR_NULL` / 排名正值或空 | ACCURACY / SNAPSHOT | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| A3 | `DQ_A_SNAPSHOT_TIME_RANGE` / 快照时间范围 | ACCURACY / SNAPSHOT | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| A4 | `DQ_A_PARSEABILITY` / 字段可解析 | ACCURACY / IMPORT_JOB | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| A5 | `DQ_A_IMPORT_ERROR_RATE` / 导入错误率 | ACCURACY / IMPORT_JOB | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| K1 | `DQ_K_SNAPSHOT_KEY_UNIQUE` / 快照业务键唯一 | CONSISTENCY / SNAPSHOT | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| K2 | `DQ_K_REVISION_CHAIN_VALID` / 修订链一致 | CONSISTENCY / SNAPSHOT | ERROR / 1.000000 / 否（均 PROPOSED） | 1.0 | **首批** |
| K3 | `DQ_K_CUMULATIVE_MONOTONIC` / 累计指标合理单调 | CONSISTENCY / SNAPSHOT | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| K4 | `DQ_K_RELEASE_STATUS_TIME` / 发布状态时间一致 | CONSISTENCY / DRAMA_PLATFORM | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| K5 | `DQ_K_REFERENCE_INTEGRITY` / 业务引用完整 | CONSISTENCY / DRAMA_PLATFORM | UNRESOLVED / UNRESOLVED / 否 | 1.0 | 延后 |
| T1 | `DQ_T_SNAPSHOT_FRESHNESS` / 最新快照及时性 | TIMELINESS / SNAPSHOT | WARNING / 1.000000 / 否（均 PROPOSED） | 1.0 | **首批** |

阻断含义：规则 FAIL 参与评分但不单独中止整次计算；配置错误、Evidence 不一致、Evaluator 异常或任一维度无 APPLIED 规则才中止。Design V2 只证明 severity 用于治理优先级、不二次乘分（`:480`），故 ERROR 不自动阻断仍需批准。

## 2. 16 条计算与 Evidence 规格

通用规则：as-of 选择每个 snapshot slot 中 `changed_at <= cutoff` 的最大 `(changed_at, snapshot_revision_id)`；最新为 VOID 时 slot 无有效事实且不回退。必需数据缺失为 FAIL，业务域真正不适用才 N/A。APPLIED PASS_RATE 为 `100×passed/applicable`；状态 PASS 当且仅当规则分达到各规则 pass threshold。

| Ref | Evidence / 字段 / 窗口 | 判定、分子/分母、阈值 | 去重；缺失/VOID；PASS/FAIL/N/A | Repository / 冲突 / 审批项 |
|---|---|---|---|
| C1 | `dramas`; ID/code/name/status；current-state | 每个目标 drama 必填字段均合法；pass/目标 drama；字段集合阈值 100% | `drama_id` 去重；必填缺失 FAIL；无目标 N/A | 可复用 governance projection；历史非双时态；字段集/对象范围需批 |
| C2 | `drama_platforms`; status/online_at；current-state | ONLINE/OFFLINE 关系须有 online_at；pass/适用关系；100% | 关系 PK；缺失 FAIL；PLANNED N/A；VOID 不适用 | 现有 Repository 可扩展；对象范围/severity/weight需批 |
| C3 | snapshots/revisions；current_revision_id；as-of | 当前日：指针存在且属于同 slot；历史日不能以当前指针证明 | snapshot_id；缺失 FAIL；VOID 仍可作为 current 指针但无有效 metric | 需新 Evidence 查询；历史语义冲突，**UNRESOLVED** |
| C4 | active+ONLINE feed、snapshot、revision.play_count；截至 score_date 前 7 个完整业务日（PROPOSED） | 每 feed×day 为 expected slot；存在最新非 VOID 且 play_count 非空即 pass；`passed/expected×100`；threshold=100 | feed+date；缺 slot/VOID/play_count NULL 均 FAIL；无 eligible feed N/A | 可复用 governance 查询；7日、scope、severity/weight需批 |
| C5 | import_jobs/errors；批准窗口 | processed/declared rows；完成状态、字段及 threshold **UNRESOLVED** | job+row；缺计数 FAIL 或 N/A 未定；VOID 不适用 | Import Repository 可扩展；不可实现 |
| A1 | C4 窗口内最新有效 revisions；play_count及非空累计互动字段 | 每个存在的数值字段 `>=0`；pass/存在值；threshold=100 | revision_id+field；NULL 可选互动字段排除，play_count 缺失由 C4 负责；VOID 排除；无值 N/A | 现有 unsigned/check 已防多数异常；字段集/severity/weight需批 |
| A2 | revision.ranking；C4 窗口 | `ranking IS NULL OR ranking>0`；pass/revisions；100% | revision_id；NULL PASS；VOID 排除；无 revision N/A | Schema 已约束；窗口/severity/weight需批 |
| A3 | snapshot_time/changed_at/as-of | 允许未来容差、业务时区、最早边界 **UNRESOLVED** | snapshot_id；时间缺失 FAIL；VOID 不改变时间事实 | 需 Evidence；阈值未定，不可实现 |
| A4 | import_errors + staged/raw row；批准窗口 | 日期/数值/枚举解析错误码集合与分母 **UNRESOLVED** | job+row+field+error_code；缺原始行语义未定 | 现有导入记录不足以证明全部成功字段；不可实现 |
| A5 | import_jobs/errors；批准窗口 | `1-errors/processed` 或 error rows/declared rows，方向和 threshold **UNRESOLVED** | job+row；与 A4 按 error_code 去重；无任务 N/A 未定 | 与 A4 重复风险；不可实现 |
| K1 | snapshot `(drama_platform_id,snapshot_time)` | 每业务键最多一个 slot；pass/keys；100% | 业务键；重复 FAIL；无 slot N/A | DB unique 已约束；是否值得评分/权重需批 |
| K2 | 每 snapshot 的可见 revision chain；截至 as-of，全链 | version 从1连续；INITIAL 无 previous；后续 previous 指向同 slot前一版；每 slot pass/slots；threshold=100 | snapshot_id；断链/多头 FAIL；最新 VOID 合法且不回退；无 slot N/A | 需批量 chain projection；severity/weight及扫描范围需批 |
| K3 | 同 feed 连续有效 revisions；累计指标 | “不合理回退”的允许阈值/纠错语义 **UNRESOLVED** | feed+date+field；缺比较对 N/A；VOID slot 不回退 | 不能以 `>= previous` 代替未批准规则；不可实现 |
| K4 | relation status/online_at | PLANNED 可空；ONLINE/OFFLINE 必须有时间（现有 CHECK）；pass/relations；100% | relation PK；缺失 FAIL；无关系 N/A | current-state only；历史和权重需批 |
| K5 | drama/platform/relation FK | 引用记录存在且符合批准状态；pass/relations；100% | relation PK；孤儿 FAIL；无范围 N/A | FK 已防多数异常；状态语义/权重需批 |
| T1 | 每 active+ONLINE feed 最新可见非 VOID snapshot_time；as-of | age/24h：`<=1→100, <=2→80, <=3→60, <=7→40, >7→20, 无数据→0`；rule_score=对象 bucket 平均；pass_threshold=80（PROPOSED） | feed PK；同 slot修订选择；无有效 snapshot APPLIED 0，不是 N/A；无 eligible feed N/A | bucket值 VERIFIED；24h/80/severity/weight需批 |

## 3. 首批发布策略比较

| 维度 | A：一次发布16条 | B：四维最小规则集 |
|---|---|---|
| 设计成熟度 | 12条仍缺阈值/分母/边界，不可安全实现 | 4条可形成具体提案，仍需参数批准 |
| 业务覆盖 | 广，但会把猜测固化为业务规则 | 每维至少一条，符合 Design V2 “每维有 APPLIED”要求 `:391-393` |
| Evidence/实现/测试 | Import、主数据、revision、关系多域同时上线 | 聚焦 revision-aware snapshot facts；批量查询可控 |
| 历史可比性 | 首次版本复杂，后续修正规则概率高 | `DQ Rules 1.0` 稳定；扩展必须发布新 rule-set version |
| 风险 | 高；重复扣分和历史主数据重放不确定 | 中；范围有限但语义清楚、可验证 |

推荐方案 B，首批为 C4/A1/K2/T1。它不是为了凑数：四条分别覆盖数据可用性、值域准确性、修订链一致性和更新时效，且都能追溯到真实 revision。延后其余 12 条，直到其 UNRESOLVED 项获批。

## 4. 发布与历史边界

- 首批规则集：`DQ Rules 1.0`；每条 `rule_version=1.0`；计算算法推荐 `Quality Score V2.0`。
- 新增/移除规则、改权重或配置必须发布新的 rule-set version；候选建议后续 `DQ Rules 1.1`，版本命名仍需批准。
- 历史 as-of：snapshot/revision 可按截点重放；active/ONLINE scope 来自非完整双时态主数据，只能记录 `LIMITED_CURRENT_MASTER` watermark，不能宣称严格历史复现。
- 同一历史 score identity 已存在时默认返回已有结果，不用当前主数据静默重算覆盖。

## 5. 待审批参数

**DQ-01 必须逐项批准：**首批四条、7日窗口、eligible feed 定义、C4/A1/K2/T1 的 threshold、severity、weight、非阻断语义、24h expected interval、T1 pass threshold=80，以及延后12条。任一项未批，不得 Seed 或实现 evaluator。

最后结论：**PROPOSED；四维最小首批规则集已具备可审查规格，但尚未 APPROVED。**
