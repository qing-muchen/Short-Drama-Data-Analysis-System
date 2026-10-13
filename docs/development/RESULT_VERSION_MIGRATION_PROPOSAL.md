# 结果版本与 Lineage Revision Migration 候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.1 |
| Git 基线 | `15b161c09f78b804c42802bc76108613e77d9508` |
| 状态 | **PROPOSED — APPROVAL REQUIRED** |
| 风险 | **BREAKING CHANGE — HIGH-RISK DDL** |

本文件是结构设计，不是可执行 SQL。不得修改 V001–V013；候选后续迁移应使用新的连续版本并在 B2-E 单独实现、审查和演练。

## 1. 候选变更

### V014：不可变 Score / Prediction 版本

`drama_scores` 与 `prediction_results`：

1. 新增 `result_revision INT UNSIGNED NOT NULL DEFAULT 1`。
2. 新增 nullable `supersedes_result_id` 自引用 FK，`ON DELETE RESTRICT/ON UPDATE RESTRICT`。
3. 新增 nullable `input_fingerprint CHAR(64)`、`result_fingerprint CHAR(64)`；CHECK 为 NULL 或长度64。
4. 删除旧唯一约束并创建包含 `analysis_as_of,result_revision` 的新唯一约束，列集合见 Identity 文档。
5. 新增 current 查询索引：Score `(drama_id,score_date,algorithm_version,scope_type,scope_id,analysis_as_of DESC,result_revision DESC)`；Prediction `(drama_id,metric_type,target_date,algorithm_version,analysis_as_of DESC,result_revision DESC)`。
6. 新增 `supersedes_result_id` 索引；不删除任何行、不改变 PK。

已有行自动为 revision 1；fingerprint 保持 NULL 并标识 legacy，不能凭空重建输入来源。

### V015：Lineage 精确修订来源

B1 曾建议把 revision ID 直接放入 `source_id`。实际 Data Governance 已把 `SNAPSHOT.source_id` 映射为 `drama_metric_snapshots.snapshot_id`（repository `:407-437`），直接替换会造成同一枚举双重语义。

推荐对 `analysis_lineage_records` 新增：

- `source_revision_id BIGINT UNSIGNED NULL`；FK 到 `drama_metric_snapshot_revisions.snapshot_revision_id`，RESTRICT。
- 索引 `(source_revision_id)`。
- 保留 `source_type/source_id`：真实 snapshot 输入统一写 `source_type=SNAPSHOT`、`source_id=snapshot_id`、`source_revision_id=精确revision_id`；关系类型区分 Score/Prediction/Anomaly 用途。
- 用新 CHECK 取代 V013 的 source type CHECK，并加入 `DRAMA`、`DRAMA_PLATFORM`，分别映射 `dramas.drama_id` 与 `drama_platforms.drama_platform_id`，用于 Score lifecycle 的真实主数据来源；这两类 `source_revision_id` 必须 NULL。
- 旧 lineage 保持 NULL，查询显示 legacy evidence completeness=`NOT_AVAILABLE`，不得猜测补值。

现有 lineage 唯一约束可保留：同一 explanation、snapshot、relationship、as-of 只应选择一个 revision。Service 另校验 revision 属于 source snapshot。`analysis_explanations` 无需结构变化，其 entity_id 将引用不可变结果 PK。

## 2. 查询迁移

- Score/Prediction current/history Repository 必须先适配新排序，再启用 append 写入。
- Reporting、Profile、Dashboard 使用 current 子查询；按明确 PK/as-of 的历史消费者不切换 latest。
- Data Governance 的 lineage source existence 增加 revision FK/归属/as-of/VOID 校验；不再把 PREDICTION_INPUT/ANOMALY_EVIDENCE 的 source_id 猜成其他表。
- 不需要兼容视图；过渡期使用 feature flag：Migration 完成但 append/Workflow 未启用时，旧写逻辑必须被禁止，避免 delete 破坏新历史。

## 3. 演练与部署顺序

1. 用户批准 EX-02/03/04/05。
2. 完整 `short_drama_analysis` 备份，包含结构、数据、索引、触发器/对象；独立临时库恢复验证。
3. 只读预检：重复候选新 identity、非法 as-of、孤儿 PK、表行数、磁盘空间、长事务和外键。
4. 在恢复副本执行 V014/V015；比较 DDL、PK、行数、关键查询和 explain plan。
5. 运行旧读接口兼容测试、新 current/history/Reporting 测试、并发修订测试。
6. 安排写入维护窗口；停止相关 Score/Prediction/Explanation 写入，确认无并发 DDL。
7. 正式执行并立即验证；再部署与 Schema 匹配的代码。不得先启用 append 代码。
8. 保存迁移日志、校验结果和恢复点；不改验收库，除非另有明确授权。

## 4. 失败恢复

MySQL DDL 可能隐式提交，不能依赖 rollback。失败时停止应用写入并核实已完成的 DDL 步骤：

- 若只新增 nullable/default 字段和索引，优先完成同一迁移到已验证目标状态，不做盲目反向 DDL。
- 若唯一约束切换失败，保持写入关闭，从经验证备份恢复到独立库，校验后按运维切换/恢复流程替换目标；不得清空或重建原库来“重试”。
- 任何反向删除新字段/约束都可能丢失新版本数据，必须有用户再次授权。
- 代码部署失败时保留向后兼容 Schema，回退到只读或明确支持新 Schema 的旧代码；旧 delete+insert 写路径不得恢复。

## 5. 风险

- 删除/重建唯一索引会持有 metadata lock；大表虽当前结果行少，仍需维护窗口。
- 自 FK、索引和 append history 增加存储及写时成本。
- Reporting 若漏掉 current 过滤会重复计数。
- V014/V015 不回填 fingerprint/revision lineage；旧记录只能保持可识别的 legacy 不完整状态。

**EX-05 候选批准文本：**批准以两个独立新 Migration 实施上述 additive/versioned 变更；要求备份恢复验证、隔离演练、写维护窗口、逐步校验和失败时备份恢复；禁止修改 V001–V013 和破坏性历史回填。

最后结论：**PROPOSED；未生成或执行 SQL。**
