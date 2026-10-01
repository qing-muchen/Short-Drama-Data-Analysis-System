# Phase 6 V013 Migration Final Architecture Review

## 1. Review结论

V013 的数据库范围和架构边界与 Design V2 一致，可以进入数据库实现阶段，但必须按本审查文档冻结唯一约束、受控 JSON、弱关联和数据保留策略后再编写 SQL。

最终判断：**允许进入 V013 Migration 实现阶段。**

本结论不授权 ORM、Service、API 或 Dashboard 同步实现；后续仍应按 Migration → ORM → Repository → Service → API 的顺序推进。

## 2. 数据库范围审查

V013 仅新增三张表：

1. `analysis_explanations`
2. `analysis_lineage_records`
3. `metric_dependencies`

V013 不修改 V001-V012，不修改 `drama_scores`、`data_quality_scores`、`prediction_results`、`data_anomaly_records`、`operation_actions` 或任何既有业务表。三表使用现有 InnoDB、utf8mb4、UTC 时间、BIGINT UNSIGNED 主键规范。

## 3. `analysis_explanations`审查

### 3.1 字段和枚举

字段冻结为：

`explanation_id`、`entity_type`、`entity_id`、`module_type`、`summary`、`detail`、`algorithm_version`、`rule_set_version`、`analysis_as_of`、`created_at`、`updated_at`。

`entity_type` 枚举冻结为：

```text
SCORE, QUALITY, PREDICTION, ANOMALY, ACTION
```

`module_type` 使用相同的模块集合，表示解释来源模块。`entity_id` 为 NOT NULL 的 BIGINT UNSIGNED 弱关联 ID，不建立跨模块外键。

### 3.2 重复保存风险

通过以下边界避免重复保存业务结果：

- 不保存短剧名称、平台名称和完整业务对象；
- 不复制 Score、Quality、Prediction、Anomaly 或 Action 的全部字段；
- `summary` 只保存解释结论，`detail` 只保存受控的小型证据结构；
- 具体输入来源由 `analysis_lineage_records` 记录，不嵌入完整 snapshot。

因此该表是解释快照，不是新的业务事实表。

### 3.3 `detail` JSON审查

`detail` 必须符合固定顶层结构：`reason`、`inputs`、`rules`、`versions`、`evidence`。各模块通过 Schema 限制扩展字段：Score 可保存 contributors 和 metric_changes，Anomaly 可保存 threshold、baseline、evidence，Quality 可保存 failed_rules 和 dimensions。

该结构满足：

- 可解释：保存用户可读原因和关键证据；
- 可追溯：保存版本和分析截点，来源由 lineage 关联；
- 可扩展：通过受控模块 Schema 增加字段，不允许任意 JSON。

数据库可使用 JSON 类型或 TEXT 配合 Service Schema 校验；V1 必须由应用层完成结构校验，不能把任意 JSON 直接写入数据库。

### 3.4 唯一约束

提议的：

```text
(entity_type, entity_id, algorithm_version, analysis_as_of)
```

不足以区分不同 `module_type`，也无法完整区分质量规则集版本。V1 推荐冻结为：

```text
(entity_type, entity_id, module_type, analysis_as_of,
 algorithm_version, rule_set_version)
```

其中版本字段必须使用一致的非 NULL 哨兵值或等价规范化策略，避免 MySQL UNIQUE 对 NULL 允许多条重复记录。不同算法版本、规则集版本或历史截点允许并存，旧解释不被覆盖。

## 4. `analysis_lineage_records`审查

字段冻结为：

`lineage_id`、`target_type`、`target_id`、`source_type`、`source_id`、`relationship_type`、`analysis_as_of`、`created_at`。

允许的 `target_type`：

```text
EXPLANATION, SCORE, QUALITY, PREDICTION, ANOMALY, ACTION
```

允许的 `source_type`：

```text
METRIC, SNAPSHOT, RULE, PREDICTION_INPUT, ANOMALY_EVIDENCE
```

所有核心 ID 和类型字段 NOT NULL，采用弱关联 ID，不建立 Explanation → Score、Quality、Prediction、Anomaly 或 Action 的跨模块 Foreign Key。这样可以避免多态外键、跨模块循环依赖和后续 Migration 互相锁定。

### 4.1 唯一性

以下唯一约束合理：

```text
(target_type, target_id, source_type, source_id,
 relationship_type, analysis_as_of)
```

同一来源可以被多个目标解释引用；唯一约束只阻止同一目标、来源、关系和分析截点重复写入。若实现中 lineage 还保存算法或规则集版本，则应将对应规范化版本纳入唯一键，否则不同版本可能错误合并。

## 5. `metric_dependencies`审查

该表作为静态配置表合理，不应在运行时按每次分析动态生成。字段冻结为：

`dependency_id`、`parent_metric`、`child_metric`、`module_type`、`algorithm_version`、`created_at`。

V1 不强制增加 version hash、status 或 active 字段：

- `algorithm_version` 已能区分依赖图版本；
- 当前依赖配置规模小，可通过版本新增和停用记录管理；
- 过早增加状态会扩大 API、权限和 Migration 复杂度。

如果实现确实需要停用依赖，允许增加 `enabled`，但必须保持默认启用和明确索引；不得在 V1 引入复杂发布工作流。配置写入时应校验无自依赖和循环依赖。

## 6. Foreign Key审查

V013 不建立以下跨业务外键：

- Explanation → Score；
- Explanation → Quality；
- Explanation → Prediction；
- Explanation → Anomaly；
- Explanation → Action。

原因是这些对象属于不同模块和不同版本演进节奏，强外键会造成循环依赖和删除/迁移耦合。来源存在性、来源类型和版本一致性由 Explanation Service 的只读 Provider 校验，数据库通过 CHECK、NOT NULL、UNIQUE 和索引保证结构约束。

V1 不需要创建者字段，因此不强制 User FK。未来若增加人工解释创建者，可增加 `created_by_user_id` → `users.user_id` 的 RESTRICT 外键，但不能借此建立业务模块外键。

## 7. 索引审查

### Explanations

- `(entity_type, entity_id, analysis_as_of)`：详情和历史解释查询；
- `(module_type, analysis_as_of)`：按模块和时间检索；
- `created_at` 可用于归档和管理查询。

### Lineage

- `(target_type, target_id, analysis_as_of)`：按目标查询来源；
- `(source_type, source_id)`：按来源反查影响的解释；
- `created_at` 可作为归档辅助字段。

### Dependencies

- `(parent_metric, algorithm_version)`：查询某指标的下游依赖；
- `(child_metric, algorithm_version)`：反向查询上游指标；
- 若增加 `enabled`，将其加入配置查询索引。

索引覆盖详情、模块、时间、目标、来源和指标查询场景，不修改已有模块索引。

## 8. 数据规模和保留策略

Explanation 数量约随分析结果批次增长；Lineage 数量还会随指标依赖和输入窗口增长，可能高于业务结果表；Dependency 数量较小，仅保存静态版本配置。

V1 采用永久可追溯、可归档策略：

- 不使用无审计 TTL 删除；
- `detail` 只保存受控摘要，禁止完整输入快照；
- 使用唯一约束防止重算重复写入；
- 保留 `created_at` 索引和 `analysis_as_of` 索引，支持按月归档；
- 归档必须可恢复，不能改变历史 ID 和版本含义。

V1 不增加归档字段；通过时间字段和独立归档流程管理。容量监控、分区和压缩可在后续阶段评估。

## 9. ORM设计审查

ORM 只建立三表内部关系（如 Explanation 内部的结构化 detail 不映射为跨表对象，Lineage 和 Dependency 按自身实体映射）。禁止建立跨业务模块 relationship，也不修改 Drama、Score、Quality、Prediction、Anomaly 和 Operation Action ORM。

## 10. API影响审查

V013 对应 API 仍为只读规划：

- `GET /api/v1/explanations/{entity_type}/{id}`；
- `GET /api/v1/lineage/{entity_type}/{id}`；
- `GET /api/v1/metrics/{metric_name}/dependencies`。

建议支持分页、`analysis_as_of` 时间过滤、模块/来源过滤和稳定排序。默认返回最新解释，历史版本通过显式参数查询。不修改已有 Score、Quality、Prediction、Anomaly、Operation Action API。

## 11. Dashboard影响审查

V1 采用嵌入已有详情页：Score、Quality、Prediction、Anomaly、Action 分别增加“查看依据/来源”入口。不新增复杂独立 Dashboard，不让前端重新计算指标、解释或血缘关系。

## 12. 必须冻结项

进入 SQL 实现前必须冻结：

1. `entity_type`、`module_type`、`target_type`、`source_type` 枚举；
2. `detail` 顶层 JSON 和模块 Schema；
3. Explanation 唯一键包含 `module_type` 和版本字段；
4. Lineage 唯一键和版本字段是否纳入；
5. 版本字段的非 NULL 哨兵策略；
6. 三表索引和 `created_at` 归档索引；
7. 弱关联存在性由 Service 校验，数据库不建跨模块 FK；
8. 永久保留、可恢复归档和容量监控策略。

## 13. V013 Migration准入判断

上述范围、字段、弱关联、索引和保留边界已满足 Design V2 的架构要求。完成必须冻结项后，V013 可以进入数据库 Migration 实现阶段。

最终结论：**允许进入 V013 Migration；本审查阶段不创建 SQL、不修改 ORM 或业务代码。**

## 14. 当前Git状态

本阶段仅新增本审查文档，未执行 `git add` 或 `git commit`；工作区其他修改保持原状。
