# Phase 8 Short Drama Operation Analytics Center Design Proposal

## 1. Phase 8 定位

Phase 8 建设 Short Drama Operation Analytics Center（短剧运营分析中心），用于基于已有分析结果，对短剧运营表现、运营行动前后变化和生命周期状态进行统计分析与复盘。

Phase 8 是企业级只读分析层，不是 AI 系统、大模型应用、智能助手、机器学习平台或自动策略系统。V1 不引入 LLM、AI Agent、自动决策模型或推荐算法。

本阶段核心目标是把“分析结果”和“运营执行记录”连接成可追溯的复盘视图，但不宣称运营动作与指标变化之间存在因果关系。

## 2. 与 Phase 1–7 的关系

Phase 1–7 已提供：

- 数据采集、导入和质量治理；
- 综合评分与短剧表现评价；
- 趋势预测；
- 异常检测；
- 运营行动及处理历史；
- 解释和数据血缘；
- Drama 360° 聚合画像。

Phase 8 只消费上述模块产生的既有事实，不修改 Score、Quality、Prediction、Anomaly、Action、Explanation 或 Drama Profile 结果，不重新执行评分、预测或异常检测。

依赖方向必须保持单向：

```text
Phase 3–7 Existing Results
              ↓
Operation Analytics Providers
              ↓
OperationAnalyticsService
              ↓
Read-only API / Dashboard
```

## 3. 核心子模块设计

### 3.1 Operation Effectiveness Analysis

#### 目标

描述运营行动发生前后指标如何变化，用于复盘行动执行过程和后续表现。

#### 分析窗口

```text
Before Window → Operation Action → After Window
```

V1 建议默认行动前后各 7 个完整日点，并允许 API 在受控范围内选择窗口长度。分析时间以行动完成或指定事件时间为锚点。

#### 输入

- `operation_actions`；
- `operation_action_history`；
- `prediction_results`；
- revision-aware 历史运营指标。

#### 输出

- 行动 ID、短剧 ID 和行动状态；
- 前后窗口及数据完整性；
- 行动前指标摘要；
- 行动后指标摘要；
- 绝对变化和相对变化；
- 描述性效果状态；
- 来源版本和 `analysis_as_of`。

效果状态只描述观测结果，例如 `IMPROVED`、`UNCHANGED`、`DECLINED`、`INSUFFICIENT_DATA`，不得表达“行动导致增长”。页面和 API 必须展示“前后变化不等于因果关系”的说明。

### 3.2 Drama Lifecycle Analysis

#### 目标

以可解释规则描述短剧当前生命周期阶段及阶段变化依据。

#### V1 阶段

```text
LAUNCH → GROWTH → STABLE → DECLINE → ARCHIVED
```

#### 规则原则

- 使用明确的连续增长天数、增长率变化、累计播放趋势和运营状态；
- 使用确定性规则，不使用机器学习分类；
- 规则必须有 `lifecycle_rule_version`；
- 输出规则证据、输入时间范围和 `analysis_as_of`；
- 历史数据不足时返回 `INSUFFICIENT_HISTORY`，不强行分类。

生命周期分析是描述性规则模型，不等同于收益、成功概率或市场价值预测。

### 3.3 Drama Benchmark Analysis

#### 目标

支持同口径短剧之间的横向统计比较。

#### 比较维度

- 播放规模；
- 增长速度；
- 互动表现；
- 异常频率；
- 生命周期阶段；
- 数据质量状态。

#### 边界

Benchmark 只返回原始值、标准化展示值、分位位置或组内差异，不生成“最佳短剧”“投资价值”或主观推荐。对比组必须由明确过滤条件形成，不能静默混用不同时间、平台或版本口径。

## 4. 数据来源与追溯

### Operation Effectiveness

- 行动事实：`operation_actions`；
- 行动事件：`operation_action_history`；
- 历史指标：`drama_metric_snapshots` 与 revision；
- 趋势参考：`prediction_results`。

### Lifecycle

- 历史累计播放量及 revision；
- `prediction_results`；
- `drama_scores`；
- Drama 发布与运营状态。

### Benchmark

- `dramas` 与分类信息；
- `drama_scores`；
- `data_quality_scores`；
- `prediction_results`；
- `data_anomaly_records`；
- Drama Profile DTO。

所有读取必须保留：

- `analysis_as_of`；
- `algorithm_version`；
- `rule_set_version`；
- `lifecycle_rule_version`（生命周期适用）；
- 输入窗口起止时间；
- revision 截止规则。

历史分析必须使用 `changed_at <= analysis_as_of` 的当时有效 revision，禁止未来修订污染历史复盘。

## 5. 数据库影响分析

Phase 8 V1 优先采用实时 Read Model，不新增业务表，不创建 V014 Migration。

理由：

1. 三类分析均可由现有事实表与只读 Repository 聚合得到；
2. V1 主要用于当前查询与复盘展示，不要求持久化新的分析事实；
3. 避免保存 action effect、lifecycle stage 或 benchmark snapshot 后产生版本同步问题；
4. `analysis_as_of`、输入窗口和版本信息可随 API 结果返回，保持可追溯性。

若未来需要长期保存已发布的复盘报告、生命周期历史快照或大规模 Benchmark 物化结果，应单独评审 V014，不能在 V1 中提前引入。

## 6. Service 架构

建议结构：

```text
backend/services/operation_analytics/
├── contracts.py
├── providers.py
├── lifecycle_rules.py
└── service.py
```

调用链：

```text
Operation Analytics Dashboard
              ↓
Operation Analytics API
              ↓
OperationAnalyticsService
              ↓
Analysis Providers
              ↓
Existing Repositories
```

`OperationAnalyticsService` 负责参数校验、Provider 编排、口径一致性检查和响应聚合。它禁止调用 ScoreService、PredictionService、AnomalyService、OperationActionService 或 DramaProfileService。

Provider 只读取单一数据域并返回 DTO，不写数据库、不管理事务、不返回 ORM 对象。生命周期规则应放在独立的纯规则模块中，不放入 Router、Repository 或前端。

## 7. API 规划

### 7.1 运营行动效果

```text
GET /api/v1/operations/effectiveness
```

参数建议：

- `drama_id`（可选）；
- `action_id`（可选）；
- `status`（可选）；
- `analysis_as_of`（可选）；
- `window_days`（默认 7，限制 3–30）；
- `page`、`page_size`。

返回分页行动效果摘要，USER 与 ADMINISTRATOR 均可查看。

### 7.2 生命周期分析

```text
GET /api/v1/dramas/{drama_id}/lifecycle
```

参数建议：`analysis_as_of`。返回阶段、规则版本、证据、输入窗口和可用状态。不存在 Drama 返回 404，历史不足返回正常响应中的明确状态。

### 7.3 短剧对比分析

```text
GET /api/v1/dramas/benchmark
```

参数建议：

- `drama_ids`（限制数量，例如 2–20）；
- `platform_id`、`tag_id`（可选分组条件）；
- `analysis_as_of`；
- `page`、`page_size`（使用筛选组时）。

返回统一口径的比较维度和版本信息，不返回价值排名或自动推荐。

三个接口均为 GET，只读且使用 JWT；V1 不提供 POST、PUT、PATCH。

## 8. Dashboard 规划

新增 Operation Analytics Dashboard，包含：

### Action Effectiveness

- 行动数量与完成状态；
- 前后窗口指标变化；
- 数据完整性；
- 非因果免责声明。

### Lifecycle Overview

- 生命周期阶段分布；
- 单剧当前阶段；
- 阶段变化证据和规则版本。

### Benchmark Analysis

- 多短剧横向指标表；
- 趋势对比图；
- 对比口径和分析时间。

前端只展示 API 结果，不计算生命周期、效果状态、标准化指标或比较结论。页面禁止 AI 建议卡片和自动运营方案。

## 9. 测试规划

### Contracts 与规则

- DTO 与枚举完整性；
- 生命周期阶段边界；
- 数据不足；
- 相同输入输出确定性；
- 版本字段传递。

### Providers

- revision-aware 历史读取；
- action 前后窗口；
- latest available 版本选择；
- 无数据与部分数据；
- 不调用业务 Service。

### Service

- 完整行动复盘；
- 无法形成前后窗口；
- 生命周期正常/历史不足；
- Benchmark 口径一致性；
- 单 Provider 异常隔离；
- 不写数据库。

### API

- USER/ADMINISTRATOR 权限；
- 参数范围与分页；
- Response Schema；
- 404 和缺失状态；
- 仅注册 GET。

### Frontend

- loading、empty、error、success；
- 部分模块不可用；
- 对比筛选；
- 非因果提示；
- TypeScript 与生产构建。

## 10. 风险分析

### 因果误判风险

行动后的变化不能证明由行动导致。API 字段和页面文案必须使用“行动前后变化”“观测结果”，禁止“贡献”“导致”“提升来源”等因果措辞。

### 数据不足风险

窗口缺失、行动时间过近或 revision 不完整时返回 `INSUFFICIENT_HISTORY`/`INCOMPLETE_WINDOW`，不生成零值或伪结果。

### 指标口径风险

不同模块的时间、平台聚合和版本可能不同。响应必须附带输入窗口、`analysis_as_of` 和版本；Benchmark 必须验证比较口径一致。

### 复杂度风险

V1 使用简单统计和确定性规则，禁止复杂机器学习模型、自动推荐和因果推断。

### 性能风险

行动窗口和 Benchmark 可能产生多次历史查询。Provider 应使用批量查询和预加载，避免 N+1；V1 不在没有性能证据时引入缓存或物化视图。

## 11. 实施路线

建议分阶段实施：

1. Architecture Review：冻结 V1 子模块范围、指标口径和非因果语义；
2. Design V2：冻结 DTO、状态枚举、生命周期规则和 API；
3. Contracts 与纯生命周期规则；
4. Analysis Providers；
5. `OperationAnalyticsService`；
6. 只读 API 与测试；
7. Operation Analytics Dashboard；
8. 模块总结和性能基线归档。

进入实现前必须再次确认：V1 不需要 V014 Migration，不持久化新的分析结果，不修改 Phase 1–7 业务模块。

## 12. Proposal 结论

Phase 8 与已有模块互补：已有模块回答“当前表现、异常、预测和行动”，Operation Analytics Center 进一步提供可追溯的行动前后复盘、生命周期描述和同口径横向比较。

该方向不重复已有分析能力，且能形成“分析—执行—复盘”的运营闭环。当前仅完成 Design Proposal，下一步必须进入 Architecture Review，审查通过前不进入数据库或代码实现。
