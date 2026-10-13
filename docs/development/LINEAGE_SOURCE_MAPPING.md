# Explanation / Lineage 来源映射候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.1 |
| 适用软件版本 | V1.0 maintenance baseline |
| Git 基线 | `0bd34f44d2f0e8065c22cdc423cf50d1373b8e9a` |
| 设计状态 | **STATUS: PROPOSED — USER APPROVAL REQUIRED** |

## 1. 设计约束

V1 来源类型限定为 `METRIC/SNAPSHOT/RULE/PREDICTION_INPUT/ANOMALY_EVIDENCE`，关系限定为 `DERIVED_FROM/USES_METRIC/USES_RULE/USES_WINDOW`；弱引用必须由 Service/只读 Provider 校验存在性和版本（`PHASE6_DATA_LINEAGE_DESIGN_V2.md:116-136,163-178,208`；V013 `:46-81`）。Explanation 是结果时快照，不能用解释文本替代来源记录。

当前 Handler 行为不是可接受的生产映射：Metric 用 `score_id` 伪装 `METRIC` 且 evidence 只有维度名（metric handler `:23-47,70-77`）；Trend evidence 为空并默认把 `prediction_id` 当输入 ID（trend handler `:22-52`）；Anomaly 用 `anomaly_id` 自指来源（anomaly handler `:31-62`）。测试只证明这些组件当前行为（`test_explanation_handlers.py:41-91`），不构成业务批准。

## 2. 三类冻结候选映射（EX-03）

| Explanation | 目标结果 | 目标版本 | 来源类型 → 实际表/主键 | 关系 | as-of 与 Evidence |
|---|---|---|---|---|---|
| METRIC → SCORE | `drama_scores.score_id` | `algorithm_version` + `analysis_as_of`；rule_set=`N/A` | `SNAPSHOT` → 每个实际参与计算的 `drama_metric_snapshot_revisions.snapshot_revision_id` | `USES_METRIC` | 所有 source `changed_at <= score.analysis_as_of`，且是相应 slot 在截点下选中的非 VOID 修订；detail 保存四维分、冻结权重、positive/weak 推导及 source revision IDs 的受控摘要 |
| TREND → PREDICTION | `prediction_results.prediction_id` | Moving Average version + `analysis_as_of`；rule_set=`N/A` | `PREDICTION_INPUT` → 8 日连续窗口中实际使用的每个 `drama_metric_snapshot_revisions.snapshot_revision_id` | `USES_WINDOW` | 精确 8 个 observation dates、平台选择、累计播放值摘要、window=8、target date；所有修订不晚于 as-of |
| ANOMALY → ANOMALY | `data_anomaly_records.anomaly_id` | anomaly algorithm + `analysis_as_of`；rule_set=`N/A` | `ANOMALY_EVIDENCE` → 规则实际使用窗口的每个 `drama_metric_snapshot_revisions.snapshot_revision_id` | `DERIVED_FROM` | anomaly type/severity/metric、baseline/actual/deviation（适用时）、threshold 与窗口摘要；来源集合必须与检测输入一致 |

这里的 `PREDICTION_INPUT`、`ANOMALY_EVIDENCE` 是逻辑来源类型；其 `source_id` 明确映射到 snapshot revision PK。`METRIC` 暂不用于运行时来源，因为仓库没有独立、可用数字 PK 指向“派生指标”记录；`metric_dependencies` 只有算法依赖定义，不能冒充一次计算的输入事实。Score 采用 `SNAPSHOT` 是 V013 已允许的类型，不需伪造 ID。

## 3. 来源校验规则（EX-04）

每条 Lineage 在写入前必须满足：

1. 目标结果存在、其 PK/algorithm/as-of 与请求完全一致，且在推荐方案中不可变。
2. 来源 revision 存在、属于目标 drama（及适用平台/slot）、`changed_at <= analysis_as_of`。
3. 按 `(snapshot_id, changed_at, revision_id)` 选择截点下最新可见修订；可见最新为 VOID 时，该 slot 不得作为有效输入，也不得回退。
4. 来源的 observation time 在算法窗口内；Prediction 必须覆盖精确连续八日和实际共同平台条件。
5. 同一来源多次出现去重；多来源均各写一条 lineage；排序只影响确定性内容，不影响集合 identity。
6. 来源不存在/失效/越过 as-of/版本不一致：不生成部分 Explanation；在推荐单事务中整个命令回滚。
7. 目标已重算：不可变旧目标仍存在则旧 lineage 保留；新目标生成新 Explanation/Lineage。若旧目标已被历史 replace 删除，查询标记 `TARGET_MISSING`，不得迁移到新 PK。

## 4. Explanation 内容完整性

| 类型 | 必填业务结果 | 必填 evidence | 不得生成的情况 |
|---|---|---|---|
| METRIC | score PK、四维分、总分/等级、算法/as-of | 四维实际值与权重、positive/weak 确定性推导、至少一个有效 revision source | 只有维度名称、无值/权重/来源；目标不存在 |
| TREND | prediction PK、trend direction、target date、window=8、算法/as-of | 八日日期和值摘要、实际 source revisions、连续性和单调条件已满足 | evidence 空；历史不足；来源包含 VOID/越界修订 |
| ANOMALY | anomaly PK/type/severity/metric、算法/as-of | threshold、evidence summary、参与检测的 source revisions；适用时 baseline/actual/deviation | 自指 anomaly PK 作为唯一来源；阈值/证据空 |

共同必填：非空 summary、受控 detail envelope、algorithm/rule-set 版本（不适用用明确 `N/A`）、analysis_as_of、至少一个真实来源。解释文本可选扩展不得替代结构化证据。信息不足时返回稳定的 `EXPLANATION_EVIDENCE_INCOMPLETE`；来源暂时不可见才允许安全重试，契约性缺字段不得无限重试。

## 5. Schema 与兼容性

- 上述来源映射本身无需 V013 变更；其弱引用语义必须在 Provider 映射表和测试中冻结。
- 当前前端 query/display 可继续读取；detail 增加字段属于向后兼容，但不能无限复制原始 snapshot。
- 若用户要求数据库 FK 强制多态来源，现结构不能表达，需新关联模型，属于 **BREAKING CHANGE — APPROVAL REQUIRED**；本候选不推荐。

## 6. 未解决问题与需批准决策

- Score 当前聚合对象没有携带全部实际输入 revision IDs；B2 必须调整内部结果契约，具体 DTO 尚待 EX-03 批准后冻结。
- Anomaly 各检测类型是否都能暴露完整窗口 revision IDs 需在 B2 逐规则验证；无法证明来源集合时不得生成解释。
- 同一 as-of 的纠错重算身份仍受 EX-02 阻塞；不得把新结果 PK 自动迁移到旧解释。

最后审查结论：**三类来源均应落到真实 snapshot revision；当前 Handler 的自指/空 evidence 不满足完整 Lineage。**
