# Score / Prediction 结果身份与历史最终候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.2 |
| Git 基线 | `15b161c09f78b804c42802bc76108613e77d9508` |
| 状态 | **PROPOSED — APPROVAL REQUIRED** |

## 1. 现状与身份层次

当前 Score 唯一键为 `(drama_id, score_date, algorithm_version, scope_type, scope_id)`；Prediction 为 `(drama_id, metric_type, target_date, algorithm_version)`。两者 replace 均 delete+insert，`analysis_as_of` 不在唯一键，物理 PK 改变。Explanation 使用结果 PK 作 entity_id，弱引用会悬空。

候选身份定义：

- 业务序列身份：Score=`drama+score_date+algorithm+scope`；Prediction=`drama+metric+target_date+algorithm`。
- 分析版本身份：业务序列 + `analysis_as_of`。
- 纠错版本身份：分析版本 + `result_revision`。
- 物理身份：不可变 `score_id` / `prediction_id`。
- 输入身份：规范化 AnalysisContext、算法/参数、排序后的 snapshot/revision IDs 计算 `input_fingerprint`。
- 内容身份：持久化业务结果规范化后计算 `result_fingerprint`。

## 2. 方案比较

| 方案 | 历史/Lineage | 幂等与纠错 | Schema/查询 | 风险/结论 |
|---|---|---|---|---|
| A 稳定逻辑身份、原行 UPDATE | PK稳定但旧解释指向新内容，历史事实被覆盖 | 同 identity 易更新；无法证明旧值 | 最小变化 | 不满足永久历史，不推荐 |
| B 不可变版本 INSERT | 每个解释指向永存 PK；来源精确 | 相同内容幂等；纠错可用 revision | 新字段/唯一键；latest需显式 | **推荐** |
| C 保持 delete+insert并同步失效/迁移 | 可把新引用同步到新 PK | 会重写旧解释含义；失败补偿复杂 | 少量结果表变化，Explanation维护复杂 | 不推荐；违反历史语义 |
| D 独立 result-run 映射表 | 最强通用运行身份 | 可容纳所有模块 | 新表/抽象/迁移最多 | 当前仅两表，无必要，暂不推荐 |

## 3. 推荐 EX-02：不可变版本

新增候选字段到 `drama_scores` 与 `prediction_results`：

| 字段 | 类型/语义 |
|---|---|
| `result_revision` | `INT UNSIGNED NOT NULL DEFAULT 1`；同一分析版本内递增 |
| `supersedes_result_id` | nullable self FK，指向被合法纠错替代的上一版本，`ON DELETE RESTRICT` |
| `input_fingerprint` | nullable `CHAR(64)`；旧行可空，新写必须由 Service 提供 |
| `result_fingerprint` | nullable `CHAR(64)`；旧行可空，新写必须提供 |

唯一键候选：

- Score：`(drama_id, score_date, algorithm_version, scope_type, scope_id, analysis_as_of, result_revision)`。
- Prediction：`(drama_id, metric_type, target_date, algorithm_version, analysis_as_of, result_revision)`。

不增加可变 `is_current`：current 由每个业务序列最大 `(analysis_as_of, result_revision, PK)` 决定，避免并发下维护多个 current 标志。旧行迁移为 revision 1、fingerprint NULL、无 supersedes。

## 4. 同一 analysis_as_of 纠错方案（EX-03）

| 方案 | 行为 | 优点 | 风险 |
|---|---|---|---|
| A 严格不可变冲突 | 同完整 identity 相同内容返回原行；不同内容 409，要求提升 algorithm/context/as-of | 最简单；无修订链 | 合法源数据纠错后无法在同 cutoff 重算 |
| B 显式 result revision | 相同 fingerprint返回原行；不同输入/内容必须带显式 `correction_reason`，插入 revision+1并链接 supersedes | 保存纠错前后事实；适合 revision 数据模型 | 新字段/查询/并发控制和 UI说明 |

推荐 B，但纠错只能由管理员显式命令触发；普通重复请求遇到不同内容仍 409，不自动创建 revision。创建时锁定同分析身份的版本集合或使用唯一冲突重试，revision=`max+1`。旧结果、旧 Explanation 永久可查；新 Explanation 只引用新结果 PK。current 选择新 revision；Reporting 默认 current，审计/历史可查看全部并显示 supersedes 链。

如果用户拒绝 B，则退回 A，不得折中为覆盖旧行。

## 5. 输入来源与 AnalysisContext

- Score 当前 `MetricResult` 只保留聚合值，不保存完整 revision IDs；B2 必须扩展内部 `_EligibleCandidate`/calculation evidence DTO，不改变公开评分算法。
- Prediction 的 Observation 有 revision_id，但 `_prepare_points` 输出聚合点时丢失来源集合；需同时返回 immutable prepared evidence。
- Anomaly Observation 有 revision_id，但按日聚合后丢失；需为每个 finding 携带其九日窗口全部平台 revision 集合。
- fingerprint 必须包含实际 revision IDs、algorithm version、时间窗口/范围、scope、as-of 和影响结果的配置；不得包含不稳定的 JSON 顺序或数据库自动 PK。

## 6. 查询与 API 兼容

- 现有 current API 响应可保持字段兼容，并按上述 latest 规则只返回一行。
- history 默认每个业务序列只返回每个分析版本的 current revision；管理员审计可请求 `include_superseded=true`。新增响应字段可选返回 revision/supersedes/fingerprint摘要。
- Reporting 必须使用窗口函数或子查询选 current，禁止因多版本重复统计。
- Drama Profile 只取 current；Operation Analytics 按其 source as-of/PK 读取指定不可变版本，不自动换成 latest。
- 不重算、不回填已有业务结果；Migration 只保留并标记 legacy revision 1。

## 7. 风险与批准文本

这是 **BREAKING CHANGE — APPROVAL REQUIRED**：Repository 从 replace 变为 append/idempotent；唯一键和查询改变；结果数量会增长。算法、权重、预测条件不变。

**EX-02/EX-03 候选批准文本：**批准不可变结果、显式 result_revision、supersedes 链和 fingerprints；普通重复请求相同内容幂等、不同内容冲突；只有管理员显式纠错可创建 revision+1；旧结果及解释永久保留；current 按 as-of/revision 选择。

最后结论：**PROPOSED；方案完整但必须通过新 Migration 与用户授权后实施。**
