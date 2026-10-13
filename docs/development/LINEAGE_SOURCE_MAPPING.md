# Explanation / Lineage 来源映射最终候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.2 |
| Git 基线 | `15b161c09f78b804c42802bc76108613e77d9508` |
| 状态 | **PROPOSED — APPROVAL REQUIRED** |
| 依据 | Phase 6 Design V2、V013、实际 Score/Prediction/Anomaly DTO 与 Data Governance source validator |

## 1. 对 B1 映射的校正

B1 正确要求来源落到实际 revision，但直接把 revision ID 放入 `source_id` 与现有实现冲突：Data Governance 已将 `SNAPSHOT.source_id` 校验为 `drama_metric_snapshots.snapshot_id`。最终推荐由后续 Migration 新增 `source_revision_id`：

```text
source_type = SNAPSHOT
source_id = drama_metric_snapshots.snapshot_id
source_revision_id = drama_metric_snapshot_revisions.snapshot_revision_id
```

三类解释的指标输入均使用真实 SNAPSHOT 来源，业务角色由 Explanation 类型和 relationship 区分；Score 的 lifecycle 还需要真实 DRAMA/DRAMA_PLATFORM 主数据来源。V015 因此还需扩展允许的 source type。新流程不再用结果 PK 自指 `METRIC/PREDICTION_INPUT/ANOMALY_EVIDENCE`；旧逻辑类型保留供 legacy 数据读取。

## 2. 最终候选映射 EX-04

| 类型 | 目标 | 完整来源集合 | 关系 / 必填 detail | 当前可实现性 |
|---|---|---|---|---|
| METRIC→SCORE | 不可变 `drama_scores.score_id` | heat/raw、growth windows、engagement实际读取的全部 snapshot/revision 对；lifecycle 使用 `dramas.drama_id`（premiere_date）或实际决定最早 online_at 的 `drama_platforms.drama_platform_id` | Snapshot=`USES_METRIC`；主数据=`DERIVED_FROM`；四维分、权重、positive/weak、algorithm/as-of、source count及 current-state limitation | SnapshotPoint 有 IDs，但 MetricResult/_EligibleCandidate 丢失；V013 又无 DRAMA/DRAMA_PLATFORM source type，需内部 DTO + V015 |
| TREND→PREDICTION | 不可变 `prediction_results.prediction_id` | 最终被共同平台交集选中的连续8日×全部平台 snapshot/revision 对；不是“至少8条”，而是精确完整输入集合 | `USES_WINDOW`；8日日期、聚合累计值、共同平台、target date、window=8 | Observation 有 revision_id，但转为 points 时丢失；需让 prepare 同时返回 evidence |
| ANOMALY→ANOMALY | `data_anomaly_records.anomaly_id` | 当前实现所有异常均依赖连续9日、每日全部参与聚合平台的 revision 对；按 finding 保存其实际集合 | `DERIVED_FROM`；类型、metric、8历史/当前值、threshold、baseline/actual/deviation、algorithm/as-of | Observation 有 revision_id，但日聚合丢失；需携带 evidence map |

## 3. Anomaly 类型逐项校验

| anomaly_type | 实际算法输入 | 完整 revision 集合 | 不能生成的情况 |
|---|---|---|---|
| `PLAY_COUNT_GROWTH_ANOMALY` | 9日 play counts → 8 increments；前7 increments baseline、最后1 current | 9日全部参与平台 revisions | 任一日/平台来源集合丢失、VOID、质量 ERROR、非连续 |
| `PLAY_COUNT_DROP_ANOMALY` | 同上，方向相反 | 同上 | 同上 |
| `ENGAGEMENT_RATE_ANOMALY` | 9日 engagement rates；前8 baseline、最后1 current；含最低播放门槛 | 9日所有播放及互动字段贡献 revisions | 字段缺失、门槛 NOT_APPLICABLE、来源不全 |
| `DATA_SPIKE_ANOMALY` | PLAY_COUNT 或 ENGAGEMENT_RATE 的前8值 baseline + current | 对应 metric 的9日完整 revisions；engagement 仍需播放门槛证据 | metric/门槛/source set 不完整 |

虽然当前四类都用9日窗口，契约按 anomaly type 保存实际集合；未来新增类型不得自动套用9日。

## 4. 完整性与校验

“至少一个来源”只适用于证明记录格式，不足以证明业务输入完整。提交条件是**完整来源集合**：

1. 每个 source snapshot/revision 都存在，revision 属于 snapshot及目标 drama/platform。
2. `changed_at <= analysis_as_of`，且是该 slot 截点下最新可见 revision；VOID 不得作为有效输入或回退。
3. 来源日期/平台集合与算法实际窗口一致；数量由实际依赖决定，而非固定最小1。
4. source set 规范排序、去重；同一来源可被多个 Explanation 引用，一个 Explanation 可引用多个来源。
5. DB 唯一约束防重复 snapshot relationship；Service 校验 revision 归属和集合完整性。
6. 来源失效/不存在/版本不一致：新生成失败并按 EX-01 回滚；已有 legacy 查询返回 `NOT_AVAILABLE`/原因，不删除历史。
7. 只有同一不可变目标 identity、相同内容和相同来源集合才幂等返回；不同集合冲突或显式创建新 result revision。

## 5. Evidence 内容要求

- Score：四维分及权重、输入版本、每个分量对应来源集合摘要；只有维度名称不完整。
- Prediction：8日日期和值、共同平台、所有 source revisions；空 evidence 或单 revision 不完整。
- Anomaly：类型/metric/severity/阈值/baseline/current/deviation及类型对应完整9日来源；目标 anomaly_id 自指不完整。
- `NOT_AVAILABLE` 用于查询旧结果没有可证明完整来源；对新成功写请求不允许以 NOT_AVAILABLE 代替 Explanation，必须失败回滚。
- 重新生成仅允许原记录不存在且完整来源仍可验证，或新 result revision；不得覆盖已有 snapshot。

## 6. 兼容性与审批

- 需要 V015 候选新增 nullable `source_revision_id`，并将 source type CHECK 扩展 `DRAMA/DRAMA_PLATFORM`；旧行保留 NULL。
- Handler、Validator、Workflow 和 Data Governance source validation 需调整；公开 Explanation 查询只增加可选字段，可向后兼容。
- 如果用户拒绝 Schema 变化，唯一安全降级是 snapshot-level lineage + detail 中保存受控 revision IDs；该方案数据库不可直接索引/校验 exact revision，不推荐。

**EX-04 候选批准文本：**批准三类新 Explanation 统一以 snapshot_id + source_revision_id 记录完整实际输入集合；按上述类型校验；Evidence 不完整则新生成失败，legacy 查询返回 NOT_AVAILABLE；禁止结果自指和空 Evidence。

最后结论：**PROPOSED；映射可实现，但依赖 V015 和内部 Evidence DTO。**
