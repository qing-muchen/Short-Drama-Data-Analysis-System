# Phase 6 Data Lineage & Analysis Explanation Center Design Proposal

## 1. Phase 6 定位

Phase 6 是面向分析结果的解释与追溯中心，不是新的评分、预测、质量检测或异常检测模型。它回答“结果为什么是这样”和“结果依赖了哪些数据”，帮助用户理解并审计已有分析结果。

核心职责：

1. 保存面向用户的分析结果解释。
2. 追踪分析结果到输入事实、规则或指标的来源关系。
3. 保存算法版本、规则集版本和分析时间点。
4. 管理可查询的指标依赖图。

Phase 6 不重新计算 Score、Quality、Prediction 或 Anomaly，不修改 Operation Action，也不替代 `operation_logs` 的操作审计职责。

## 2. 现有系统缺口

当前系统已经形成：

```text
数据采集 → 指标分析 → 评分 / 质量评价 / 预测 / 异常检测 → 运营处置
```

已有模块能够产生结果，但结果的解释分散在算法代码、规则结果、预测输入窗口、异常证据和行动来源中，缺少统一的用户可读入口：

- Score 用户难以从总分追到 Heat、Growth、Engagement 和 Lifecycle 的贡献。
- Prediction 用户难以查看形成预测的连续累计播放量窗口。
- Anomaly 用户难以统一查看历史基线、阈值和检测版本。
- Quality 用户难以从质量分追到失败规则及规则版本。
- Operation Action 已有来源证据，但缺少跨模块统一的解释入口。

Phase 6 通过解释记录和弱关联血缘记录补足可解释性，而不是复制各模块的业务结果。

## 3. 核心数据模型设计

### 3.1 `analysis_explanations`

用途：保存面向用户的解释摘要和详情。解释是对已有结果的说明，不是新的业务事实。

建议字段：

| 字段 | 说明 |
|---|---|
| `explanation_id` | BIGINT UNSIGNED 主键 |
| `entity_type` | 解释对象类型，如 SCORE、QUALITY、PREDICTION、ANOMALY、ACTION |
| `entity_id` | 对象业务 ID，逻辑引用 |
| `module_type` | 产生结果的模块类型 |
| `summary` | 面向列表和卡片的简短解释 |
| `detail` | 结构化或可读的详细解释文本 |
| `algorithm_version` | 算法、规则或模型版本快照，可为空于纯人工说明 |
| `rule_set_version` | 质量规则集版本，非质量解释时可为空 |
| `analysis_as_of` | 解释所对应的分析截点 |
| `created_at` / `updated_at` | 审计时间 |

V1 建议保留 `algorithm_version`、`rule_set_version` 和 `analysis_as_of`，因为解释必须能够说明当时使用的版本和时间。两种版本字段语义不同，不合并为一个模糊字段。V1 不引入独立 `model_registry`；如未来需要模型元数据、发布状态和参数管理，再通过独立 Migration 建立注册表。

解释表不保存 `drama_name`、完整 snapshot、完整 Score 或完整 Prediction 结果。若解释需要展示数值，应保存必要的解释文本或小型结构化 detail，而非复制源表。

### 3.2 `analysis_lineage_records`

用途：描述一个分析结果与其输入事实、指标、规则或证据之间的关系。

建议字段：

| 字段 | 说明 |
|---|---|
| `lineage_id` | BIGINT UNSIGNED 主键 |
| `target_type` / `target_id` | 结果对象类型和逻辑 ID |
| `source_type` / `source_id` | 输入来源类型和逻辑 ID |
| `relationship_type` | DERIVED_FROM、USES_METRIC、USES_RULE、USES_WINDOW 等 |
| `analysis_as_of` | 血缘关系对应的时间截点 |
| `algorithm_version` / `rule_set_version` | 生成该关系时的版本快照 |
| `evidence_summary` | 可选的简短证据说明 |
| `created_at` | 记录时间 |

V1 采用弱关联：`target_type + target_id` 和 `source_type + source_id` 不建立跨模块多态外键。这样可以连接 `drama_scores`、`data_quality_scores`、`prediction_results`、`data_anomaly_records`、`operation_action_sources` 以及 snapshot/revision，而不把所有模块耦合在同一组外键上。数据库通过 CHECK、唯一约束和索引保证记录格式，来源存在性由写入 Service 校验。

建议唯一性为：`target_type, target_id, source_type, source_id, relationship_type, analysis_as_of, algorithm_version`。同一结果与同一输入在同一分析截点和版本下不重复，但不同版本或历史截点可以并存。

### 3.3 `metric_dependencies`

用途：保存稳定的指标依赖图，而不是某次分析的具体输入记录。

示例：

```text
Total Score ──depends on── Heat Score
Growth Score ──depends on── play_count snapshot
Prediction PLAY_COUNT ──uses── 8-day cumulative window
```

建议字段：

- `dependency_id`
- `parent_metric`
- `child_metric`
- `relationship_type`
- `algorithm_version`
- `description`
- `enabled`
- `created_at` / `updated_at`

`parent_metric` 表示被解释的上层指标，`child_metric` 表示其依赖项。指标依赖是版本化配置，实际某次结果使用了哪些 snapshot，仍由 `analysis_lineage_records` 保存。V1 只支持有限的已确认指标，不实现用户在线编辑依赖图。

## 4. 数据库影响与 V013 规划

如果进入实现，规划新增 V013：

- `analysis_explanations`
- `analysis_lineage_records`
- `metric_dependencies`

V013 只新增上述表，不修改 V001-V012。所有表使用现有 MySQL InnoDB、utf8mb4、UTC 时间、BIGINT UNSIGNED 主键和统一时间字段规范。

建议索引：

- explanations：`(entity_type, entity_id, created_at)`、`(module_type, analysis_as_of)`。
- lineage：`(target_type, target_id, analysis_as_of)`、`(source_type, source_id)`。
- dependencies：`(parent_metric, algorithm_version, enabled)`、`(child_metric, algorithm_version)`。

V1 应保存解释摘要、版本、截点和必要的弱关联证据，不保存完整 snapshot 快照或重复的业务结果。若未来要求不可变审计，可在后续版本引入证据内容哈希，而不是复制全部输入数据。

## 5. 架构依赖

推荐单向依赖：

```text
Score / Quality / Prediction / Anomaly / Operation Action
                         ↓ read-only
                Explanation Center
                         ↓
                 API / Dashboard
```

建议模块划分：

- `ExplanationCalculator`：V1 可选，仅负责把已提供的结果和依赖信息组织成解释文本；不查询数据库。
- `AnalysisExplanationRepository`：保存和查询解释。
- `AnalysisLineageRepository`：保存和查询血缘关系。
- `MetricDependencyRepository`：查询指标依赖图。
- `AnalysisExplanationService`：组合只读结果、版本和血缘，管理解释记录事务。
- Router：只做权限、参数、Service 调用和响应转换。

Explanation Service 可以读取已有 Repository 或只读 Provider，但禁止调用 `ScoreService`、`PredictionService`、`AnomalyService`、`DataQualityService` 或 `OperationActionService` 重新执行计算。已有模块也不反向调用 Explanation Service，避免循环依赖。

## 6. 版本与时间追踪

V1 使用以下规则：

- 分析算法使用 `algorithm_version`，例如 `Composite Score V1.0` 或 `Rule-based Detection V1.0`。
- 质量规则使用 `rule_set_version`，必要时同时记录单条规则版本。
- 解释和血缘必须保存 `analysis_as_of`，避免当前修订覆盖历史解释。
- 对历史结果的解释只引用当时可见的来源：源数据 revision 的有效时间必须不晚于 `analysis_as_of`。

V1 只保存版本快照，不建设通用模型注册中心。版本发生变化时创建新解释/血缘记录，不静默覆盖旧记录。

## 7. API 规划（仅设计）

建议统一前缀 `/api/v1`：

- `GET /explanations/{entity_type}/{id}`：获取某个评分、质量、预测、异常或行动的解释。
- `GET /lineage/{entity_type}/{id}`：获取结果的直接输入和关系类型。
- `GET /metrics/{metric_name}/dependencies`：查询指标依赖图。

查询接口面向登录用户；如未来允许重新生成解释，管理员接口应单独设计。V1 不提供客户端写入任意血缘关系的接口，防止伪造分析来源。

## 8. Dashboard 规划

解释入口应嵌入已有详情页，而不是再建一个脱离业务的列表：

- Score 详情：查看 Heat、Growth、Engagement、Lifecycle、权重和算法版本。
- Prediction 详情：查看 8 日累计播放量窗口、analysis_as_of 和版本。
- Anomaly 详情：查看指标、历史基线、阈值、偏差和检测版本。
- Quality 详情：查看维度、失败规则、规则集版本和结果来源。
- Operation Action 详情：查看来源模块、来源记录和证据快照。

前端只展示 API 返回的解释和血缘，不重新计算评分、预测、异常或质量分，也不根据血缘自行推导业务结论。

## 9. 测试规划

### 数据库与 ORM

- V001-V013 空库迁移顺序。
- 三表字段、CHECK、唯一约束和索引。
- 弱关联对象类型和 ID 的格式校验。
- 历史版本与 analysis_as_of 可并存。

### Repository / Service

- 解释和血缘保存不重复。
- 版本与截点正确传递。
- 查询目标和来源双向索引有效。
- 生成失败时解释、血缘和 OperationLog 整体回滚。
- Service 不调用分析 Service，不触发重新计算。

### API / Frontend

- 登录权限、404、参数校验和统一响应。
- Score、Quality、Prediction、Anomaly、Action 详情入口映射正确。
- 空解释、来源缺失和历史版本场景。
- 前端只消费 API，不包含模型或规则计算。

## 10. 风险与限制

1. **重复存储风险**：解释表不能复制业务结果；只保存摘要、版本、截点和必要证据。
2. **OperationLog 职责冲突**：OperationLog 记录谁做了什么操作；Explanation 记录分析结果为什么这样，二者按用途分离。
3. **快照膨胀风险**：V1 不保存完整输入快照，使用弱关联、摘要和 analysis_as_of；必要时再增加内容哈希或归档策略。
4. **一致性风险**：解释可能滞后于结果。V1 要求解释携带版本和截点，并在查询时明确生成时间。
5. **事件驱动过早引入**：V1 采用显式 Service 编排和按需查询，不引入消息队列或事件总线；当结果量和实时要求明确后再评估事件驱动。
6. **依赖图复杂度**：V1 只登记冻结的核心指标，不支持任意循环依赖和在线编辑。

## 11. 是否允许进入 Review 阶段

设计方向与现有 Score、Quality、Prediction、Anomaly、Operation Action 互补，不新增分析模型，也不反向耦合已有 Service。建议允许进入架构 Review，但在 Review 通过前不得创建 V013、ORM 或 API。

Review 阶段应重点确认：解释生成时机（结果生成时还是按需生成）、`detail` 是否采用 JSON、弱关联来源校验策略、历史解释保留周期以及是否需要证据哈希。
