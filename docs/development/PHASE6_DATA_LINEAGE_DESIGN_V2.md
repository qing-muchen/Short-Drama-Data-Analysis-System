# Phase 6 Data Lineage & Analysis Explanation Center Design V2

## 1. Design V2目标

Phase 6 建设 Analysis Explanation & Data Lineage Center，为已有 Score、Quality、Prediction、Anomaly 和 Operation Action 提供统一的解释快照、输入追踪和指标依赖查询。

本模块：

- 解释已有分析结果；
- 追踪分析输入来源；
- 保存指标依赖关系；
- 支持按历史分析时间和版本进行可解释查询。

本模块不重新计算 Score、Quality、Prediction 或 Anomaly Detection，不创建 Operation Action，不修改原有业务结果。

依赖方向固定为：

```text
Score / Quality / Prediction / Anomaly / Operation Action
                             ↓ 只读消费
                    Explanation Center
```

Explanation Center 禁止调用任何已有业务 Service，已有模块也不得反向调用 Explanation Service，避免循环依赖。

## 2. Explanation生成策略

候选方案：

- A：实时生成。查询时重新组织解释，数据可能随源记录修订或代码变化而变化，历史重现性较弱。
- B：分析计算完成时生成并保存。解释与结果共享同一分析截点和版本，查询稳定，适合审计。
- C：按需生成并缓存。初次查询成本低，但缓存失效、版本变化和并发一致性更复杂。

V1 冻结选择 **B：分析结果产生时生成 Explanation Snapshot**。解释作为结果生成流程的一部分保存，查询只读取已保存快照，不在 GET 请求中重新执行分析算法。后续显式刷新解释时生成新版本记录，不静默覆盖历史快照。

## 3. 数据模型

### 3.1 `analysis_explanations`

用途：保存面向用户的解释快照，而不是复制业务结果。

字段：

| 字段 | 设计 |
|---|---|
| `explanation_id` | BIGINT UNSIGNED PK AUTO_INCREMENT |
| `entity_type` | NOT NULL，SCORE、QUALITY、PREDICTION、ANOMALY、ACTION |
| `entity_id` | BIGINT UNSIGNED NOT NULL，逻辑关联实体 |
| `module_type` | NOT NULL，对应 SCORE、QUALITY、PREDICTION、ANOMALY、ACTION |
| `summary` | NOT NULL，用户可读的简短解释 |
| `detail` | NOT NULL，受控 JSON 结构 |
| `algorithm_version` | 可空；非人工分析时保存算法版本 |
| `rule_set_version` | 可空；质量解释时保存规则集版本 |
| `analysis_as_of` | NOT NULL，分析截点 |
| `created_at` / `updated_at` | NOT NULL，UTC时间 |

建议唯一性：

```text
(entity_type, entity_id, module_type, analysis_as_of,
 algorithm_version, rule_set_version)
```

版本字段为空时，Service 必须将其规范化为固定哨兵值或使用一致的唯一性策略，避免 MySQL UNIQUE 对 NULL 的特殊行为造成重复快照。

### 3.2 `detail` JSON结构

禁止任意 JSON。V1 统一顶层结构：

```json
{
  "reason": "解释结论",
  "inputs": [],
  "rules": [],
  "versions": {},
  "evidence": []
}
```

各模块允许的扩展字段受 Schema 约束：

Score：

```json
{
  "metric_changes": [],
  "contributors": [],
  "version": "Composite Score V1.0"
}
```

Anomaly：

```json
{
  "threshold": "abs(z_score) >= 2",
  "baseline": "7-day mean and standard deviation",
  "evidence": "current growth deviated from baseline"
}
```

Quality：

```json
{
  "failed_rules": [],
  "dimensions": [],
  "rule_set_version": "QUALITY_RULE_SET_V1"
}
```

Prediction 的 `inputs` 可保存 8 日窗口的日期和值摘要；Action 的 `evidence` 保存来源快照摘要。任何 detail 都不得复制完整业务结果表或无限制保存原始 snapshot。

### 3.3 `analysis_lineage_records`

用途：保存“结果 ← 来源”的关系，使用弱关联，不建立跨模块多态外键。

字段：

- `lineage_id`：BIGINT UNSIGNED PK AUTO_INCREMENT；
- `target_type`：EXPLANATION、SCORE、QUALITY、PREDICTION、ANOMALY、ACTION；
- `target_id`：NOT NULL，逻辑目标 ID；
- `source_type`：METRIC、SNAPSHOT、RULE、PREDICTION_INPUT、ANOMALY_EVIDENCE；
- `source_id`：NOT NULL，逻辑来源 ID；
- `relationship_type`：NOT NULL，如 DERIVED_FROM、USES_METRIC、USES_RULE、USES_WINDOW；
- `analysis_as_of`：NOT NULL；
- `created_at`：NOT NULL。

V1 唯一性冻结为：

```text
(target_type, target_id, source_type, source_id,
 relationship_type, analysis_as_of)
```

同一个来源可以被多个解释引用；唯一约束只禁止同一目标在同一截点重复建立完全相同的关系。不同目标、关系类型、分析截点或版本可以产生独立记录。

如版本差异会导致同一关系需要并存，应将 `algorithm_version` 和 `rule_set_version` 纳入唯一键，并按统一哨兵值处理 NULL。

### 3.4 `metric_dependencies`

用途：保存静态、版本化的指标依赖图。

字段：

- `dependency_id`：BIGINT UNSIGNED PK；
- `parent_metric`：上层指标；
- `child_metric`：依赖指标或输入事实；
- `module_type`：所属分析模块；
- `algorithm_version`：依赖关系适用的算法版本；
- `created_at` / `updated_at`；
- 可选 `enabled`：是否启用。

依赖图不是运行时生成的。静态配置能被解释生成、API和文档复用，并且可以版本化审计；运行时某次结果实际使用了哪些 snapshot，仍由 lineage 表记录。V1 禁止在线编辑和循环依赖，配置发布时执行 DAG 校验。

## 4. 版本策略

V1 保留两个独立版本维度：

- `algorithm_version`：Score、Prediction、Anomaly 等算法版本；
- `rule_set_version`：Data Quality 规则集版本。

解释和血缘记录同时保存 `analysis_as_of`，历史数据必须遵循原模块的 revision 截止规则。版本变化时新增解释和血缘记录，不覆盖旧记录。

V1 不引入 `model_registry`。当前系统没有训练模型发布、参数管理和模型生命周期需求，增加注册中心会扩大迁移、权限和运维范围。未来需要模型元数据时另行设计独立模块。

## 5. NULL策略

核心关联字段统一 NOT NULL：

- `analysis_explanations.entity_id` NOT NULL；
- `analysis_lineage_records.target_id` NOT NULL；
- `analysis_lineage_records.source_id` NOT NULL；
- `entity_type`、`module_type`、`source_type`、`relationship_type` NOT NULL。

V1 不允许用大量 NULL 表达全局实体。如果未来需要全局解释，使用明确的 `entity_type + entity_id` 约定（例如固定系统实体 ID），并在 CHECK 和文档中冻结，不将同一字段混合为“单剧 ID或全局 NULL”。

版本字段可为空的场景仅限于人工说明或不适用的规则集；写入层必须规范化版本值，确保唯一性和历史查询稳定。

## 6. 数据保留策略

数据规模估计：

- Explanation 数量约等于已生成分析结果批次乘以模块数量；
- Lineage 数量会随输入窗口和依赖点增长，可能显著高于业务结果表；
- Dependency 数量较小，属于静态配置。

V1 策略：

1. Explanation 和 Lineage 永久保留可追溯记录，不使用无审计的 TTL 删除。
2. detail 只保存受控摘要，禁止完整输入快照，控制单条记录大小。
3. 通过唯一约束避免重复写入，按 `analysis_as_of` 和模块建立查询索引。
4. 建立容量监控和按月归档方案；归档必须可恢复，不改变历史 ID。
5. Dependency 只保存当前和必要历史版本，不按每次运行复制。

后续可以独立增加归档表、内容哈希或压缩策略，但不能静默合并不同版本的解释。

## 7. V013规划

V013 只新增：

- `analysis_explanations`；
- `analysis_lineage_records`；
- `metric_dependencies`。

不修改 V001-V012，不修改已有业务表。三表使用项目统一的 InnoDB、utf8mb4、UTC 时间和 BIGINT UNSIGNED 主键规范。

V1 不建立跨模块外键。来源存在性、类型合法性、版本一致性由 Explanation Service 和只读 Provider 校验；数据库负责字段 CHECK、唯一约束和索引。

建议索引：

- explanations：`(entity_type, entity_id, analysis_as_of)`、`(module_type, created_at)`；
- lineage：`(target_type, target_id, analysis_as_of)`、`(source_type, source_id)`；
- dependencies：`(parent_metric, algorithm_version, enabled)`、`(child_metric, algorithm_version)`。

## 8. API规划（仅设计）

统一前缀 `/api/v1`：

### `GET /explanations/{entity_type}/{id}`

默认返回最新解释快照，支持：

- `page`、`page_size`：历史解释分页；
- `analysis_as_of`：时间截点过滤；
- `module_type`；
- `algorithm_version`、`rule_set_version`。

### `GET /lineage/{entity_type}/{id}`

返回目标的来源关系，支持 `source_type`、`relationship_type`、`analysis_as_of` 和分页。默认按分析截点倒序、ID倒序稳定排序。

### `GET /metrics/{metric_name}/dependencies`

查询静态依赖图，支持 `algorithm_version`、`module_type`、`enabled` 和递归深度上限。V1 不开放客户端写入解释、血缘或依赖配置。

查询接口面向登录用户；未来如需手工刷新解释，应由管理员或内部 Service 触发独立命令，不让普通 GET 隐式计算。

## 9. Dashboard规划

V1 推荐嵌入已有详情页，不建设独立复杂 Dashboard：

- Score详情：评分依据、四维贡献、版本；
- Quality详情：失败规则、维度和规则集版本；
- Prediction详情：8日输入窗口、analysis_as_of 和算法版本；
- Anomaly详情：基线、阈值、偏差、证据和版本；
- Action详情：来源模块、来源记录和证据快照。

前端只展示 API 返回的解释和 lineage，不重新计算评分、预测、异常或质量分，不自行推导状态和来源关系。

## 10. 测试规划

### Database / ORM

- V001-V013 空库按顺序迁移；
- 三表字段、CHECK、UNIQUE、INDEX 和时间字段验证；
- `entity_id`、`source_id` NOT NULL 和类型约束；
- 同一来源被多个目标引用时允许，不同版本历史并存时不冲突。

### Repository

- 最新解释和历史解释分页；
- lineage 目标、来源、关系类型和时间过滤；
- dependency 版本和启用状态查询；
- 重复解释/血缘唯一约束；
- 不创建 Session、不 commit、不重新计算。

### Service

- 分析结果生成时保存解释快照；
- 版本、rule_set_version、analysis_as_of 正确传递；
- 源记录不存在、版本不一致或 detail 不符合 Schema 时整体回滚；
- 不调用 ScoreService、PredictionService、AnomalyService 或 DataQualityService。

### API / Frontend

- 登录权限、404、参数校验、分页和统一响应；
- 历史解释一致性和 lineage 完整性；
- 详情页入口映射正确；
- 前端不包含模型、规则或依赖图计算逻辑。

## 11. 风险与限制

- V1 仍采用弱关联，来源存在性不能由数据库外键完全保证，必须加强 Service 校验和测试。
- 解释快照可能与源结果生成失败不同步，因此需要同一事务或明确的补偿重试策略。
- 受控 JSON Schema 需要随模块演进维护，禁止通过任意字段绕过版本治理。
- 血缘记录可能膨胀，必须依靠窗口摘要、唯一约束、索引、监控和归档控制。
- 不引入事件驱动和 model registry，保留给未来独立阶段。

## 12. V013准入结论

Design V2 已冻结主要边界，可以进入 V013 Migration 前的实现准备。但在真正执行 Migration 前，必须再次确认 SQL 层的 NULL 哨兵策略、detail JSON 校验方式、唯一键版本字段和归档索引设计。

最终判断：**有条件允许进入 V013 Migration 评审，不直接执行 Migration。**

## 13. 当前Git状态

本阶段仅新增本设计文档，不执行 `git add` 或 `git commit`。工作区其他修改保持原状。
