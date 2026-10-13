# DQ Rules 1.0 候选发布规格

| 项目 | 值 |
|---|---|
| 文档版本 | 0.1 |
| 适用软件基线 | `0bd34f44d2f0e8065c22cdc423cf50d1373b8e9a` |
| 设计状态 | **STATUS: PROPOSED — USER APPROVAL REQUIRED** |
| 规则集标识 | `DQ Rules 1.0`（候选；尚未发布） |

## 1. 证据边界

本清单只展开 `PHASE2_DATA_QUALITY_DESIGN_V2.md:396-480` 已列出的四维检查方向。该设计没有给出生产 `rule_code`、逐规则权重、严重程度、完整配置、所有阈值或分母，因此下表中的 `C-* / A-* / K-* / T-*` 仅是本审查文档的候选引用号，不是可写入数据库的 Rule ID。

实现和测试不能补足业务批准：

- V009/ORM 只冻结字段和约束，允许 `PASS_RATE`、`BUCKET_AVERAGE`、`INFO/WARNING/ERROR` 和规则生命周期，不定义生产规则内容（`database/migrations/V009__create_data_quality_tables.sql`；`backend/models/data_quality.py:23-119`）。
- `test_data_quality_service.py:60-141` 的四条规则和 `MagicMock` evaluator 是编排夹具；`database/tests/constraint_test.sql:112-165` 是约束夹具，均不是生产规则。
- 开发库只读实测：规则 0、ACTIVE 规则 0、规则结果 0、评分 0。因此没有已发布规则可继承。

## 2. 规则集公共契约

| 字段 | 候选契约 | 状态/依据 |
|---|---|---|
| 维度及总权重 | Completeness 30%、Accuracy 30%、Consistency 25%、Timeliness 15% | EVIDENCE VERIFIED；Design V2 `:396-456` |
| 单规则身份 | 稳定 `rule_code` + 不可变 `rule_version` | EVIDENCE VERIFIED；Design V2 `:294-324` |
| 生命周期 | `DRAFT/ACTIVE/INACTIVE`；ACTIVE 或已使用版本不得原地改变语义 | EVIDENCE VERIFIED；Design V2 `:141-163` |
| APPLIED 规则分 | `PASS_RATE = 100 × passed/applicable`；Timeliness 可用 `BUCKET_AVERAGE` | EVIDENCE VERIFIED；Design V2 `:363-379` |
| N/A | 仅当规则对当前数据域真正不适用；缺失必需数据必须 FAIL，不能用 N/A 绕过 | EVIDENCE VERIFIED；Design V2 `:379` |
| severity | 只决定治理优先级，不二次乘入扣分 | EVIDENCE VERIFIED；Design V2 `:480` |
| ERROR 阻断 | 现有设计没有规定 ERROR 自动阻断整次评分 | **UNRESOLVED**；需 DQ-01 批准 |
| 规则启用 | 一个可评分发布必须覆盖四个维度；任一维度无 APPLIED 规则则不持久化总分 | EVIDENCE VERIFIED；Design V2 `:391-393, 508-515` |
| 防重复 | 每条规则必须冻结对象、窗口、分母、主证据、去重键及是否产生持续 issue | EVIDENCE VERIFIED；Design V2 `:469-480` |

## 3. 候选规则清单

`字段/条件` 中未出现于原设计的精确字段名不作推断；`UNRESOLVED` 表示不可直接实现。

| 引用号 | Rule ID / 名称 | 维度、目标 | 输入与权威 Evidence | 字段、判断与阈值 | 缺失/异常/N/A | 计分 | severity / 权重 / 阻断 | 设计依据与结论 |
|---|---|---|---|---|---|---|---|---|
| C-01 | Rule ID **UNRESOLVED**；短剧必填主数据 | COMPLETENESS / DRAMA | `dramas`；主键 `drama_id` | 必填字段集合、分母和字段级阈值 **UNRESOLVED** | 必填缺失 FAIL；非法值归 C-01 还是 A-04 **UNRESOLVED** | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:400-402`；不可实现 |
| C-02 | Rule ID **UNRESOLVED**；ONLINE 发布关系上线时间 | COMPLETENESS / RELEASE | `drama_platforms`；关系主键 | `status=ONLINE` 时 `online_at` 必须存在；时间范围另由 A-03/A-04 判定 | 缺失 FAIL；非 ONLINE 是否 N/A **UNRESOLVED** | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:403`；需批准分母 |
| C-03 | Rule ID **UNRESOLVED**；快照当前修订完整性 | COMPLETENESS / SNAPSHOT | `drama_metric_snapshots` + revisions；`snapshot_id/current_revision_id` | current 指针存在且归属同一 snapshot；与 K-02 的边界 **UNRESOLVED** | 缺失 current FAIL | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:404,422-423`；需去重边界 |
| C-04 | Rule ID **UNRESOLVED**；有效修订必要运营指标 | COMPLETENESS / SNAPSHOT | `drama_metric_snapshot_revisions`；`snapshot_revision_id` | 非 VOID 修订所需指标集合 **UNRESOLVED** | 必需指标缺失 FAIL；VOID 不作为有效事实，但分母口径 **UNRESOLVED** | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:405`；不可实现 |
| C-05 | Rule ID **UNRESOLVED**；Import 已处理行覆盖 | COMPLETENESS / IMPORT_JOB | `import_jobs`、`import_errors`；job/error 主键 | processed/total 的权威字段、完成状态、窗口、合格阈值 **UNRESOLVED** | 无导入任务是否 N/A **UNRESOLVED** | PASS_RATE 候选 | 全部 **UNRESOLVED** | Design V2 `:406,471-480`；不可实现 |
| A-01 | Rule ID **UNRESOLVED**；累计指标非负 | ACCURACY / SNAPSHOT | 有效 snapshot revision；`snapshot_revision_id` | 累计指标集合 **UNRESOLVED**；值 `>=0` | 必需值缺失 FAIL；非数值应由导入还是本规则负责 **UNRESOLVED** | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:410-412`；需字段集合 |
| A-02 | Rule ID **UNRESOLVED**；排名正值或空 | ACCURACY / SNAPSHOT | 有效 snapshot revision | 排名字段集合 **UNRESOLVED**；`NULL or >0` | NULL 合法；非整数/零/负数 FAIL | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:413`；需字段集合 |
| A-03 | Rule ID **UNRESOLVED**；快照时间范围 | ACCURACY / SNAPSHOT | snapshot + revision + AnalysisContext | “允许范围”、未来容差、时区和窗口 **UNRESOLVED** | 缺失时间 FAIL | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:414`；不可实现 |
| A-04 | Rule ID **UNRESOLVED**；日期/数值/枚举可解析 | ACCURACY / IMPORT_JOB | import job/error；必要时业务表 | 字段集合、错误码集合、分母和窗口 **UNRESOLVED** | 解析失败 FAIL；已被导入拒绝行是否计入 **UNRESOLVED** | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:415-416`；需防重复规则 |
| A-05 | Rule ID **UNRESOLVED**；Import 负值/时间/类型/字段错误 | ACCURACY / IMPORT_JOB | `import_errors` | 错误码集合、窗口、同 A-04 去重键 **UNRESOLVED** | 无导入是否 N/A **UNRESOLVED** | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:416,480`；与 A-04 可能重复 |
| K-01 | Rule ID **UNRESOLVED**；快照业务键唯一 | CONSISTENCY / SNAPSHOT | `drama_metric_snapshots` | 业务键由现有唯一约束提供，但评分分母/历史冲突窗口 **UNRESOLVED** | 冲突 FAIL；无快照是否 N/A **UNRESOLVED** | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:422`；需冻结业务键 |
| K-02 | Rule ID **UNRESOLVED**；revision 链及 current 归属 | CONSISTENCY / SNAPSHOT | snapshot + revisions；revision/current/previous IDs | 链连续、版本号、前驱和 current 归属；精确规则可沿用 schema 约束但评分分母 **UNRESOLVED** | 孤儿/断链 FAIL | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:423`；需与 C-03 去重 |
| K-03 | Rule ID **UNRESOLVED**；累计指标无不合理回退 | CONSISTENCY / SNAPSHOT | 同业务序列的有效 revisions | 指标集合、可接受回退阈值、修订/跨日语义 **UNRESOLVED** | 缺连续比较对是否 N/A **UNRESOLVED** | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:424`；不可实现 |
| K-04 | Rule ID **UNRESOLVED**；发布状态与上线时间一致 | CONSISTENCY / RELEASE | `drama_platforms` | 状态—时间真值表 **UNRESOLVED** | 缺失按 C-02 还是本规则 FAIL **UNRESOLVED** | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:425`；需真值表和去重 |
| K-05 | Rule ID **UNRESOLVED**；短剧/平台/发布关系引用有效 | CONSISTENCY / RELEASE | `dramas`、`platforms`、`drama_platforms` | 现有 FK 可作事实；是否只查违反项及分母 **UNRESOLVED** | 孤儿引用 FAIL | PASS_RATE | 全部 **UNRESOLVED** | Design V2 `:426`；需分母 |
| T-01 | Rule ID **UNRESOLVED**；最新有效快照及时性 | TIMELINESS / SNAPSHOT | snapshot + as-of 有效 revision；`snapshot_revision_id` | 年龄/期望间隔：`<=1→100, <=2→80, <=3→60, <=7→40, >7→20, 无有效快照→0`；期望间隔来源及 `pass_threshold` **UNRESOLVED** | 无有效快照是 APPLIED 0 分，不是 N/A | BUCKET_AVERAGE | 全部 **UNRESOLVED** | Design V2 `:428-439`；阈值部分有依据，仍不可发布 |

## 4. 发布结论

现有设计足以冻结维度、通用评分语义和候选检查方向，但不足以形成可执行的生产 Seed。16 个候选方向均缺至少一个关键定义；其中只有 T-01 的分段得分有明确数值。**DQ-01 的可批准文本必须同时补齐生产 rule_code/name、逐规则权重、severity、分母、窗口、主证据、去重键、配置与 evaluator key；否则 DQ Rules 1.0 不得激活。**

## 5. 未解决问题与需批准决策

1. 是否批准以上 16 个方向全部进入首个规则集，还是缩减为一个仍覆盖四维的最小集合。
2. 每条规则的生产身份、权重、severity、阻断性和完整配置。
3. A-04/A-05、C-03/K-02、C-02/K-04 的去重边界。
4. T-01 的期望更新间隔来源和 `pass_threshold`。

最后审查结论：**PROPOSED；当前没有任何可直接初始化的生产规则。**
