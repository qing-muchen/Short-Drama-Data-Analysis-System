# Phase 8 Operation Analytics Module Summary

## 1. Module Overview

Phase 8 建设 Short Drama Operation Analytics Center（短剧运营分析中心），定位为只读运营分析与复盘层。模块连接已有分析结果、历史指标与 Operation Action，提供行动前后指标变化、短剧生命周期和同平台 Benchmark 统计比较。

Phase 8 属于 Read Model / Analytics Layer，不创建新的业务事实，不修改 Score、Prediction、Anomaly、Operation Action、Explanation 或 Drama Profile 结果。V1 不是 AI、自动决策或推荐系统，不包含 LLM、AI Agent、机器学习、自动运营建议或推荐算法。

## 2. Architecture Overview

完整调用链为：

```text
Operation Analytics Dashboard
        ↓
Operation Analytics API
        ↓
OperationAnalyticsService
        ↓
Providers
        ↓
OperationAnalyticsRepository
        ↓
Existing Modules / Existing Tables
```

确定性规则组件由 Service 显式调用：Provider 只准备输入，Rule Component 只进行纯计算。Phase 8 V1 采用实时 Read Model，不建立分析结果表、快照表或缓存表。

依赖方向保持单向。Phase 8 不调用 ScoreService、PredictionService、AnomalyService、OperationActionService 或 DramaProfileService，避免跨模块业务编排耦合和循环依赖。

## 3. Design Principles

### 3.1 Read Only

模块只读取现有 Action、Action History、Drama、历史 Metric Revision 和 Anomaly 数据。Repository 只执行查询，Service、Rule、Provider 和 API 均不写数据库，不执行 `commit`、`rollback` 或 `flush`。

### 3.2 No Causality

Operation Effectiveness 仅描述行动完成时间前后观察到的指标变化。输出包含固定非因果免责声明，不判断“行动导致结果”，也不输出行动成功、失败或效果分数。

### 3.3 No Ranking

Benchmark 只提供同平台显式 Drama 集合的统计比较和组中位数，不生成排名、最佳 Drama、胜者、价值判断或推荐。

### 3.4 No AI

生命周期和统计分析均使用固定、可解释、版本化规则。V1 不包含 AI、LLM、Agent、机器学习分类或推荐算法。

## 4. Contracts Layer

文件：`backend/services/operation_analytics/contracts.py`。

Contracts 使用不可变 `frozen/slots` dataclass 定义模块间稳定协议，不依赖 SQLAlchemy、ORM、Repository、Session、FastAPI 或数据库。

主要 Enum：

- `AvailabilityStatus`；
- `AvailabilityReason`；
- `LifecycleStage`；
- `MetricDirection`；
- `OperationMetricType`；
- `BenchmarkMetricType`。

主要 DTO：

- `AnalysisAvailability`；
- `AnalysisWindow`；
- `DailyCumulativePoint`；
- `OperationEffectivenessInput` / `OperationEffectivenessResult`；
- `LifecycleInput` / `LifecycleResult`；
- `BenchmarkInput` / `BenchmarkResult`；
- `AnalysisRevisionInput`。

Contracts 明确区分真实零值与数据缺失：真实零值保留为 `0`；缺失值使用 `None`，并通过 Availability 描述原因。

## 5. Rule Components

位置：`backend/services/operation_analytics/rules/`。

### 5.1 ActionEffectCalculator

以 Action 首次完成事件时间为 T0，使用 T0 前后各 7 个完整业务日。累计指标先按平台差分，再对相同平台集合聚合，计算：

- 播放增量变化；
- 互动率变化；
- 日均播放增量变化；
- 异常数量变化。

结果仅输出 `INCREASED`、`DECREASED`、`UNCHANGED` 或 `UNAVAILABLE` 等观察状态，不输出因果结论。规则版本为 `Action Effect Analysis V1.0`。

### 5.2 LifecycleClassifier

生命周期固定为：

- `LAUNCH`；
- `GROWTH`；
- `STABLE`；
- `DECLINE`；
- `ARCHIVED`。

规则使用双 7 日窗口和 ±10% 阈值。优先级为 `ARCHIVED > LAUNCH > 输入有效性 > GROWTH/DECLINE/STABLE`。规则版本为 `Lifecycle Rules V1.0`，不输出概率或置信度。

### 5.3 BenchmarkCalculator

规则范围为同一平台、显式 2–20 部 Drama、滚动 30 个完整自然业务日。Calculator 计算播放增量总和、日均增量、互动率、异常频率和生命周期状态，并为数值指标提供组中位数。缺失成员不补零，也不进入中位数统计。规则版本为 `Benchmark Comparison V1.0`。

### 5.4 AnalysisRevisionBuilder

Builder 对冻结后的 `analysis_as_of`、实体、参数、Snapshot Revision、来源版本和规则版本生成 canonical JSON SHA-256 revision。它不创建时间截点、不选择数据库 revision，也不持久化结果。

## 6. Repository Layer

文件：`backend/repositories/operation_analytics_repository.py`。

`OperationAnalyticsRepository` 是独立只读查询层，返回冻结的 dataclass 投影，不向 Provider 暴露 ORM Model。主要能力包括：

- 分页读取已完成 Action；
- 查询指定窗口内的完成 Action；
- 读取最小 Drama 投影；
- 读取历史 Metric Revision；
- 读取 Anomaly ID 与算法版本。

所有历史查询遵守 `analysis_as_of`。Metric Revision 只选择 `changed_at <= analysis_as_of` 的最新有效 `version_no`，历史最新 revision 为 `VOID` 时排除对应 observation slot，不使用当前 `current_revision_id` 污染历史分析。

Action 完成锚点来自 `operation_action_history` 中首个 `COMPLETED` 状态事件；Anomaly 同时受业务窗口和自身 `analysis_as_of` 限制。

## 7. Provider Layer

文件：`backend/services/operation_analytics/providers.py`。

### 7.1 OperationEffectivenessProvider

批量读取 Action、Before/After 指标、异常和重叠行动，构造 `OperationEffectivenessInput`。Provider 不计算指标变化，也不判断 Action 是否有效。

### 7.2 LifecycleInputProvider

读取 Drama 状态、发布时间和连续历史播放指标，构造 `LifecycleInput`。Provider 不判断生命周期阶段。

### 7.3 BenchmarkProvider

读取显式同平台 Drama 集合、30 日指标窗口和异常记录，构造 `BenchmarkInput`。Provider 不计算平均值、中位数、排名或推荐。

三个 Provider 均只返回 Contracts DTO，不返回 ORM，不执行 SQL，不写数据库，也不调用其他业务 Service。SQL 和 revision 选择仅位于 Repository。

## 8. Service Layer

文件：`backend/services/operation_analytics/service.py`。

`OperationAnalyticsService` 负责：

- 参数校验；
- 每次请求只冻结一次 `analysis_as_of`，并规范化为 UTC；
- Provider 与 Rule Component 编排；
- Availability 保留和聚合；
- `analysis_revision` 构造；
- Contracts DTO 组装。

公开接口为：

- `get_operation_effectiveness()`；
- `get_lifecycle()`；
- `get_benchmark()`。

Service 不访问 ORM、Session 或 SQL，不保存数据。Provider 或 Rule 失败时返回结构化 `NOT_AVAILABLE`；单个 Action 或 Benchmark 成员失败仅隔离对应结果，不污染其他分析请求。

## 9. API Layer

Phase 8 提供三个只读接口：

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/operations/effectiveness` | 查询行动前后指标变化 |
| GET | `/api/v1/dramas/{drama_id}/lifecycle` | 查询单剧生命周期 |
| GET | `/api/v1/dramas/benchmark` | 查询同平台统计比较 |

接口统一使用 `ResponseModel[T]` 和既有 `ErrorResponse`，JWT Bearer 保护。`USER` 与 `ADMINISTRATOR` 均可查询，匿名访问返回 401。API 不注册 POST、PUT、PATCH 或 DELETE。

HTTP Pydantic Schema 与内部 Contracts 分离。Router 只接收参数、执行认证、调用 Service 并完成 Schema 转换，不访问 ORM、Repository、Provider、Rule 或 Session。

## 10. Frontend Dashboard

页面：`/operation-analytics`。

前端实现包括：

- Operation Effectiveness 查询、分页、Before/After 窗口和指标变化；
- Lifecycle 阶段、规则版本、分析时间和证据；
- Benchmark 比较范围、30 日窗口、成员指标和组中位数；
- 四种 Availability 状态及固定原因展示；
- 三个模块独立的 loading、empty、error 和 success 状态。

Frontend 复用现有 Axios Client、Token 拦截器和路由认证守卫，仅展示 API 返回结果。页面不计算指标、不判断生命周期、不生成排名或推荐。V1 使用状态标签、摘要卡和表格，不为图形展示额外聚合数据。

## 11. Availability Protocol

Phase 8 使用统一状态协议：

- `AVAILABLE`：输入完整，结果可正常使用；
- `PARTIAL`：核心结果可返回，但部分指标、成员或版本信息缺失；
- `INSUFFICIENT`：历史窗口不足或比较范围不可形成有效分析；
- `NOT_AVAILABLE`：输入无效、数据不可恢复或组件隔离故障。

原因由闭合的 `AvailabilityReason` 表达，例如 `INSUFFICIENT_HISTORY`、`MISSING_METRIC`、`OVERLAPPING_ACTIONS`、`INCOMPARABLE_SCOPE` 和 `NOT_AVAILABLE`。前后端均不使用空值或零值代替业务可用状态。

## 12. Testing Record

### 12.1 Backend

- Contracts：8 项通过，覆盖 Enum、DTO、Availability、窗口、不变性和依赖隔离；
- Rules + Contracts：24 项通过，覆盖 Action 增减/稳定、生命周期五阶段与 ±10% 边界、Benchmark 2/20 成员、30 日窗口和 Revision 稳定性；
- Repository + Providers：14 项定向测试通过，Phase 8.1–8.3 回归 38 项通过；
- Service：13 项定向测试通过，Phase 8.1–8.4 回归 51 项通过；
- API：11 项定向测试通过，Phase 8.1–8.5 回归 55 项通过。

API 测试覆盖路径、GET-only、JWT 权限、Schema 转换、Availability、参数传递、Dependency Override、OpenAPI 和 Router 分层边界。

完整后端测试最终仍有 4 项工作区既有 Phase 7/通用 Router 断言失败；Phase 8 新增测试全部通过，未修改这些范围外问题。

### 12.2 Frontend

执行：

```text
npm exec vue-tsc -- --noEmit
npm run build
```

TypeScript 检查和 Vite 生产构建均通过。Operation Analytics 页面生成独立异步 chunk；未新增依赖、未修改 lockfile。构建的大 chunk warning 为既有非阻塞提示。

## 13. Git History

| Phase | Commit | Message | 内容 |
| --- | --- | --- | --- |
| 8.1 | `d24f48670f8c640dd3acbd2b532db247f3d784fb` | `feat(phase8): add operation analytics contracts` | 冻结 Enum、DTO、Availability、窗口和版本契约 |
| 8.2 | `6e7a6078ce553fd48603f03604a93907bd1ed0b8` | `feat(phase8): add operation analytics rule components` | 实现 Action Effect、Lifecycle、Benchmark 和 Revision 纯规则组件 |
| 8.3 | `ebc611e8df20dc2c6e57c8c8b9e3fa4af468a03a` | `feat(phase8): add operation analytics repositories and providers` | 实现历史只读 Repository、as-of/revision 选择与三个 Provider |
| 8.4 | `ec6970b272bfb9aa31665dfe4bc5790a778bb2de` | `feat(phase8): add operation analytics service` | 实现只读编排、统一截点、Availability 和异常隔离 |
| 8.5 | `51708d9e898c04bb080ec0fd14b600ff742dffb5` | `feat(phase8): add operation analytics api` | 实现 Schema、三条 GET API、JWT 权限和 Dependency 组装 |
| 8.6 | `a5b0b58b9a8ee8e4da68745157c47885e498f605` | `feat(phase8): add operation analytics dashboard` | 实现 API Client、TypeScript 类型、运营分析页面、路由和 Dashboard 入口 |

本归档文档由 Phase 8.7 独立提交。

## 14. Current Limitations

Phase 8 V1 当前限制：

- Operation Action 缺少标准化 Action Type、实际开始时间和持续时间，因此不支持 Action 类型语义或活动周期分析；
- Drama 缺少标准化 category，因此不支持 category 自动分组和同类剧自动 Benchmark；
- 不持久化 Action Effect、Lifecycle 或 Benchmark 分析结果；
- 不保存 Benchmark Snapshot 或 Lifecycle Snapshot；
- 不提供长期分析缓存、历史报表或周报/月报；
- Benchmark 必须由调用方显式提供同平台的 2–20 个 Drama ID。

需要突破上述边界时，必须重新执行架构与数据库设计审查。

## 15. Future Extensions

未来可在独立 Phase 中评估：

- 持久化、可审计的运营复盘报告；
- 标准化 Action Type 与活动时间模型；
- 标准化 Drama category 与标签体系；
- 更多可解释统计维度；
- 更多只读业务 Provider；
- 在实际性能数据支持下引入受控缓存。

未来扩展仍应保持非因果、可解释和版本化原则，不引入自动决策或 AI 推荐。
