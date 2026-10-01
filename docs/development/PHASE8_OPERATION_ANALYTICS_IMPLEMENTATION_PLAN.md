# Phase 8 Short Drama Operation Analytics Center Implementation Plan

> 状态：实现前规划冻结候选。本文不包含代码实现，不授权创建 Migration、修改 ORM 或修改 Phase 1–7 业务模块。

## 1. 规划目标与边界

Phase 8 是运营分析与复盘层，属于 Read Model / Analytics Layer。它在请求期间读取已有事实，执行确定性、可解释、版本化的统计规则，并返回临时 DTO。

V1 实现范围：

- Operation Effectiveness Analysis；
- Lifecycle Classification；
- Benchmark Comparison；
- Availability Protocol；
- 三个只读 API；
- Operation Analytics Dashboard。

V1 不产生新的业务事实，不持久化分析结果，不修改 Score、Prediction、Anomaly、Action、Explanation 或 Drama Profile。

禁止：

- LLM、AI Agent、机器学习和推荐；
- 因果推断；
- 调用 ScoreService、PredictionService、AnomalyService、OperationActionService、DramaProfileService 或 ExplanationService；
- 创建 V014 Migration 或新增分析结果表；
- 让 Router、Provider、Repository 或 Frontend 执行分析公式。

## 2. 最终依赖结构

Architecture Review 已明确读取和计算必须分离，因此实现结构不是“Provider 调用 Rule，再调用 Repository”的串行关系，而是由 Service 分别编排 Provider 与 Rule：

```text
Operation Analytics Dashboard
              ↓
Operation Analytics API
              ↓
OperationAnalyticsService
       ┌──────┴────────┐
       ↓               ↓
Analysis Providers   Pure Rule Components
       ↓
OperationAnalyticsRepository
       ↓
Existing ORM / Tables
```

依赖规则：

- API 只依赖 Service；
- Service 依赖 Provider、Rule、Validator 和 Contracts；
- Provider 依赖只读 Repository 和 Contracts；
- Rule 只依赖 Contracts、`Decimal` 和标准库；
- Repository 可以依赖 ORM 和 SQLAlchemy；
- Contracts 不依赖 ORM、Repository、Service、Session 或 FastAPI；
- Frontend 只依赖 API Client 与 TypeScript 类型。

## 3. 规划文件结构

### 3.1 Backend

```text
backend/
├── repositories/
│   ├── operation_analytics_repository.py
│   └── __init__.py                         # 仅导出新 Repository
├── services/
│   └── operation_analytics/
│       ├── __init__.py
│       ├── contracts.py
│       ├── providers.py
│       ├── service.py
│       ├── validators.py
│       └── rules/
│           ├── __init__.py
│           ├── action_effect.py
│           ├── lifecycle.py
│           ├── benchmark.py
│           └── revision.py
├── schemas/
│   ├── operation_analytics.py
│   └── __init__.py                         # 仅导出新 Schema
├── routers/
│   ├── operation_analytics.py
│   ├── dependencies.py                     # 仅组装只读依赖
│   └── __init__.py                         # 注册静态路由优先
└── tests/
    ├── test_operation_analytics_contracts.py
    ├── test_operation_analytics_rules.py
    ├── test_operation_analytics_repository.py
    ├── test_operation_analytics_providers.py
    ├── test_operation_analytics_service.py
    └── test_operation_analytics_api.py
```

### 3.2 Frontend

```text
frontend/src/
├── api/operationAnalytics.ts
├── types/operationAnalytics.ts
├── views/operationAnalytics/OperationAnalytics.vue
├── router/index.ts                         # 增加只读页面路由
└── views/Dashboard.vue                     # 增加入口
```

### 3.3 文档

后续每个独立实现阶段新增一份对应开发文档，最终新增 Phase 8 Module Summary。不得在某一阶段预先提交后续阶段的空文件。

## 4. 文件职责

| 文件 | 单一职责 | 禁止内容 |
|---|---|---|
| `contracts.py` | 内部枚举、输入/输出 DTO、协议 | ORM、SQLAlchemy、FastAPI、查询 |
| `rules/action_effect.py` | 前后窗口指标纯计算 | 数据访问、因果判断 |
| `rules/lifecycle.py` | 生命周期纯规则分类 | ORM、机器学习、当前时间 |
| `rules/benchmark.py` | 组统计纯计算 | 自动组选择、排名和推荐 |
| `rules/revision.py` | canonical input 与 SHA-256 revision | 数据库写入、随机值 |
| `providers.py` | Repository 结果到输入 DTO 的映射 | 公式、分类、Service 调用 |
| `validators.py` | 请求间不变量与 DTO 组合校验 | 查询、分析计算、权限 |
| `service.py` | 冻结 as-of、编排 Provider/Rule、组装响应 | SQL、ORM、写事务 |
| `operation_analytics_repository.py` | 只读 SQLAlchemy 查询与投影 | 分析规则、commit、rollback |
| `schemas/operation_analytics.py` | HTTP Schema 和参数枚举 | ORM、业务计算 |
| `routers/operation_analytics.py` | 认证、参数接收、Service 调用、响应转换 | Repository、Provider、Rule、Session |

## 5. Contracts 设计

Contracts 使用 `dataclass(frozen=True)`、`Enum`、`Decimal`、`date` 和带时区 `datetime`。集合字段优先使用 tuple，防止 Rule 调用期间输入被修改。

### 5.1 枚举

#### AvailabilityStatus

```text
AVAILABLE
PARTIAL
INSUFFICIENT
NOT_AVAILABLE
```

#### AvailabilityReason

```text
NOT_CALCULATED
INSUFFICIENT_HISTORY
INCOMPLETE_BEFORE_WINDOW
INCOMPLETE_AFTER_WINDOW
INCOMPARABLE_SCOPE
MISSING_METRIC
ZERO_BASELINE
OVERLAPPING_ACTIONS
MIXED_SOURCE_VERSIONS
INVALID_CUMULATIVE_SEQUENCE
NOT_COMPLETED
GLOBAL_ACTION_UNSUPPORTED
NOT_AVAILABLE
```

#### LifecycleStage

```text
LAUNCH
GROWTH
STABLE
DECLINE
ARCHIVED
```

#### MetricDirection

```text
INCREASED
UNCHANGED
DECREASED
UNAVAILABLE
```

#### OperationMetricType

```text
VIEWS_CHANGE
ENGAGEMENT_CHANGE
GROWTH_RATE_CHANGE
ANOMALY_COUNT_CHANGE
```

#### BenchmarkMetricType

```text
PLAY_INCREMENT_TOTAL
MEAN_DAILY_PLAY_INCREMENT
ENGAGEMENT_RATE
ANOMALY_FREQUENCY
LIFECYCLE_STATE
```

### 5.2 通用 DTO

#### AnalysisAvailability

字段：

- `status: AvailabilityStatus`；
- `reasons: tuple[AvailabilityReason, ...]`。

约束：reasons 去重并保持枚举顺序；AVAILABLE 时 reasons 必须为空；数据不足不能通过数值 0 表达。

#### AnalysisWindow

字段：

- `start_date: date`；
- `end_date: date`；
- `day_count: int`。

约束：日期闭区间长度必须等于 `day_count`。

#### DailyCumulativePoint

字段：

- `business_date`；
- `platform_id`；
- `snapshot_revision_id`；
- `play_count`；
- `like_count`；
- `comment_count`；
- `favorite_count`；
- `share_count`。

所有计数使用非负整数或明确的 null；Rule 对缺失值返回 Availability，不补 0。

#### AnalysisVersionInfo

字段：

- `rule_version`；
- `source_versions`；
- `analysis_revision`；
- `analysis_as_of`。

### 5.3 Action Effect Contracts

#### OperationEffectivenessInput

- `action_id`；
- `drama_id`；
- `anchor_time`；
- `before_window`；
- `after_window`；
- 两个窗口的 `DailyCumulativePoint`；
- 两个窗口的 Anomaly identity/version；
- `overlapping_action_ids`；
- Provider 发现的 Availability。

#### MetricChange

- `metric_type`；
- `before_value: Decimal | int | None`；
- `after_value: Decimal | int | None`；
- `absolute_change: Decimal | int | None`；
- `relative_change: Decimal | None`；
- `direction`；
- `unit`；
- `availability`。

#### OperationEffectivenessResult

- `action_id`；
- `drama_id`；
- `action_type: None`（TBD-P8-02 在 V1 中不推断）；
- `anchor_time`；
- `before_window`；
- `after_window`；
- `metric_changes`；
- `overlapping_action_ids`；
- `availability`；
- `action_effect_rule_version`；
- `analysis_revision`；
- `analysis_as_of`；
- 固定非因果 `disclaimer`。

禁止字段：`causal_result`、`success`、`effective`、`contribution`。

### 5.4 Lifecycle Contracts

#### LifecycleInput

- `drama_id`；
- `drama_status`；
- `release_time`；
- 连续 15 个累计播放量日点；
- `analysis_as_of`；
- 输入 revision IDs。

#### LifecycleEvidence

- `previous_window`；
- `current_window`；
- `previous_average`；
- `current_average`；
- `window_change_rate`。

#### LifecycleResult

- `drama_id`；
- `lifecycle_stage: LifecycleStage | None`；
- `evidence: LifecycleEvidence | None`；
- `rule_version = "Lifecycle Rules V1.0"`；
- `analysis_revision`；
- `evaluated_as_of`；
- `availability`。

历史不足或 release time 无效时 stage 必须为 null，不默认 STABLE。

### 5.5 Benchmark Contracts

#### BenchmarkInput

- `drama_ids`（去重后 2–20）；
- `platform_id`；
- 固定 30 日窗口；
- 每个 Drama 的连续 31 个累计日点；
- 每个 Drama 的窗口异常记录；
- 相同 `analysis_as_of`；
- 输入 revision IDs 与来源版本。

#### BenchmarkMetric

- `metric_type`；
- `value: Decimal | str | None`；
- `group_median: Decimal | None`；
- `unit`；
- `availability`。

#### BenchmarkMemberResult

- `drama_id`；
- `metrics`；
- `availability`。

#### BenchmarkResult

- `target_drama_id: None`（V1 是显式组比较，不设隐含主目标）；
- `comparison_scope`，包含 `drama_ids` 和 `platform_id`；
- `window`；
- `members`；
- `availability`；
- `benchmark_version = "Benchmark Comparison V1.0"`；
- `lifecycle_rule_version`；
- `analysis_revision`；
- `analysis_as_of`。

禁止字段：rank、winner、best、recommendation、value_score。

## 6. Rule Components 规划

所有 Rule Component：

- 构造后无 Session/Repository；
- 不读取当前时间；
- 不修改输入；
- 使用 `Decimal`；
- 相同输入必须产生相同输出；
- 不生成营销、因果或推荐文案。

### 6.1 ActionEffectCalculator

文件：`rules/action_effect.py`

接口：

```text
calculate(input: OperationEffectivenessInput) -> OperationEffectivenessResult
```

职责：

1. 校验两个固定 7 日窗口；
2. 按平台对累计日点相邻差分；
3. 聚合同一固定平台集合；
4. 计算 views、engagement、growth-rate 和 anomaly-count 变化；
5. 生成方向与指标级 Availability；
6. 将重叠行动提升为顶层 PARTIAL；
7. 输出固定 disclaimer。

冻结边界：Anchor Day 不参与窗口；负增量无效；Before 分母 0 时 relative 为 null；不输出综合成功等级。

### 6.2 LifecycleClassifier

文件：`rules/lifecycle.py`

采用 Architecture Review 冻结名称 `LifecycleClassifier`，不使用会暗示 Provider 执行规则的 `LifecycleProvider`。

接口：

```text
classify(input: LifecycleInput) -> LifecycleResult
```

优先级：

```text
ARCHIVED > LAUNCH > 输入有效性 > GROWTH/DECLINE/STABLE
```

规则：INACTIVE 为 ARCHIVED；release 后 0–14 个完整业务日为 LAUNCH；其他需连续 15 日点；两个 7 日增量均值变化率 `>= +0.10` 为 GROWTH，`<= -0.10` 为 DECLINE，其余 STABLE。前窗为 0、后窗大于 0是 GROWTH；两窗均为 0是 STABLE。

release time 缺失、晚于 as-of 或累计序列无效时不分类。

### 6.3 BenchmarkCalculator

文件：`rules/benchmark.py`

接口：

```text
compare(input: BenchmarkInput) -> BenchmarkResult
```

职责：

1. 校验显式 2–20 Drama、单平台和同一滚动 30 日窗口；
2. 为每个成员计算固定五项指标；
3. 对每个数值指标仅使用可比成员计算 median；
4. 少于 2 个可比成员时返回 INCOMPARABLE_SCOPE；
5. 缺失成员保留但不补 0、不进入 median；
6. 不排序价值、不产生排名或推荐。

生命周期指标通过 Service 预先调用同一个 `LifecycleClassifier` 获得，再作为已分类输入传入 Benchmark；BenchmarkCalculator 不复制生命周期规则。

### 6.4 AnalysisRevisionBuilder

文件：`rules/revision.py`

接口：

```text
build(identity: AnalysisRevisionInput) -> str
```

使用排序键 canonical JSON、UTF-8 和 SHA-256。输入包含分析类型、实体 IDs、参数、analysis_as_of、snapshot revision IDs、来源结果 IDs/版本和规则版本；列表按稳定 ID 排序。输出格式固定为 `sha256:<hex>`。

### 6.5 Validators

文件：`validators.py`

只校验跨 DTO 的编排不变量：正整数 ID、时区感知 as-of、窗口日期关系、Benchmark 去重数量、单平台、版本常量和 Provider DTO 类型。参数形状由 Pydantic Schema 校验，数学规则由 Rule Component 校验，数据库存在性由 Provider/Repository 处理。

## 7. Repository 规划

### 7.1 OperationAnalyticsRepository

文件：`backend/repositories/operation_analytics_repository.py`

该 Repository 是 Phase 8 专用只读查询边界，不修改已有业务 Repository 的行为。

建议查询接口：

```text
list_completed_action_records(..., offset, limit)
count_completed_action_records(...)
get_action_history_as_of(action_id, analysis_as_of)
list_overlapping_completed_actions(drama_id, window_start, window_end, exclude_action_id)
list_metric_revision_records(drama_ids, platform_id?, start_time, end_time, analysis_as_of)
get_lifecycle_drama_record(drama_id, analysis_as_of)
list_anomaly_records(drama_ids, start_time, end_time, analysis_as_of)
```

要求：

- 使用 SQLAlchemy ORM/Core 表达式，不使用原生 SQL；
- 返回不可变查询投影 record，不向 Provider 暴露 ORM entity；
- 所有历史查询执行 `changed_at <= analysis_as_of`；
- 同一 snapshot 槽位选择截止时点最高 revision，VOID 排除；
- 批量读取 Drama 和窗口，禁止逐 Drama/逐 Action N+1；
- 不 commit、不 rollback、不 flush、不创建 Session；
- 不包含差分、均值、中位数或生命周期规则。

## 8. Provider 规划

文件：`providers.py`

定义 Protocol：

```text
OperationEffectivenessInputProvider
LifecycleInputProvider
BenchmarkInputProvider
```

具体实现可继续命名：

- `OperationEffectivenessProvider`；
- `LifecycleInputProvider`；
- `BenchmarkProvider`。

### 8.1 OperationEffectivenessProvider

输入过滤条件和 `analysis_as_of`，调用 Repository 批量取得行动、完成事件、重叠行动、窗口指标和异常记录，输出 `OperationEffectivenessInput` 及 Page metadata。

Provider 只确定数据是否存在和窗口是否完整；不计算 metric changes。

### 8.2 LifecycleInputProvider

读取 Drama status、平台上线时间/首映日期和连续 15 日点，输出 `LifecycleInput`。它不调用 `LifecycleClassifier`，不返回 LifecycleStage。

### 8.3 BenchmarkProvider

批量读取显式 Drama 组在指定平台的连续 31 日点和窗口异常，输出 `BenchmarkInput`。它不计算 median、不调用 LifecycleClassifier、不判断“最佳”。

### 8.4 数据缺失与异常

- 可预期缺失转换为输入 Availability；
- 技术性 Repository 异常不得吞掉或伪装为业务数据不足；
- 单个成员缺失不阻止返回其他 Benchmark 成员；
- 整个数据源不可访问时异常传播到现有 ErrorResponse；
- Provider 不写 OperationLog，因为 V1 是只读查询。

## 9. Service 规划

文件：`service.py`

### 9.1 依赖注入

`OperationAnalyticsService` 构造函数注入三个 Provider、三个 Calculator/Classifier、`AnalysisRevisionBuilder`、Validator 和 Clock Protocol。生产 Clock 只在 Service 请求入口生成一次 UTC as-of；Rule 不读取当前时间。

### 9.2 接口

```text
get_operation_effectiveness(filters) -> Page[OperationEffectivenessResult]
get_lifecycle(drama_id, analysis_as_of=None) -> LifecycleResult
get_benchmark(drama_ids, platform_id, analysis_as_of=None) -> BenchmarkResult
```

### 9.3 编排流程

#### Action Effect

```text
validate filters
  → freeze analysis_as_of
  → provider batch input
  → ActionEffectCalculator per input
  → AnalysisRevisionBuilder
  → stable Page result
```

#### Lifecycle

```text
validate drama_id/as_of
  → provider input
  → LifecycleClassifier
  → AnalysisRevisionBuilder
  → LifecycleResult
```

#### Benchmark

```text
validate IDs/platform/as_of
  → provider batch input
  → LifecycleClassifier for comparable members
  → BenchmarkCalculator
  → AnalysisRevisionBuilder
  → BenchmarkResult
```

### 9.4 Service 边界

Service 不执行 SQL、不导入 ORM、不复制公式、不保存结果、不 commit/rollback、不写 OperationLog、不调用其他业务 Service。

“异常隔离”仅适用于结构化的成员缺失：通过 Availability 保留其他成员。不可预期的 Provider/Repository 技术异常使用现有异常体系返回 500，不得静默转成 0 或成功空结果。

## 10. API Schema 规划

文件：`backend/schemas/operation_analytics.py`

使用项目现有 `SchemaModel`、`ResponseModel[T]`、`PageResponse[T]` 和 `ErrorResponse`。

### 10.1 Schema 枚举

API 层定义与 Contracts 同值的：AvailabilityStatusSchema、AvailabilityReasonSchema、LifecycleStageSchema、MetricDirectionSchema、OperationMetricTypeSchema、BenchmarkMetricTypeSchema。转换必须显式，不在 Router 中散落字符串。

### 10.2 Response Schema

- `AnalysisAvailabilitySchema`；
- `AnalysisWindowSchema`；
- `MetricChangeSchema`；
- `OperationEffectivenessResponse`；
- `LifecycleEvidenceSchema`；
- `LifecycleResponse`；
- `BenchmarkMetricSchema`；
- `BenchmarkMemberSchema`；
- `BenchmarkResponse`。

所有响应包含 `analysis_as_of`、规则版本和 `analysis_revision`。Action Effect 还必须包含固定 disclaimer。

禁止 API 字段：causal_result、success、effectiveness_score、rank、winner、recommendation。

## 11. API 与 Router 规划

文件：`backend/routers/operation_analytics.py`

为了同时提供 `/operations/...` 和 `/dramas/...`，Router 不设置单一业务 prefix，直接定义完整子路径，再由现有 `/api/v1` 聚合 Router 注册。

### 11.1 Action Effectiveness

```http
GET /api/v1/operations/effectiveness
```

参数：

- `action_id: int | None`，`ge=1`；
- `drama_id: int | None`，`ge=1`；
- `status: COMPLETED | None`；
- `analysis_as_of: datetime | None`；
- `page: int = 1`，`ge=1`；
- `page_size: int = 20`，`ge=1, le=100`。

返回：`ResponseModel[PageResponse[OperationEffectivenessResponse]]`。排序 `anchor_time DESC, action_id DESC`。V1 不接收 `window_days`。

### 11.2 Lifecycle

```http
GET /api/v1/dramas/{drama_id}/lifecycle
```

参数：正整数 drama_id、可选 analysis_as_of。不存在为 404；历史不足为 200 + Availability。返回 `ResponseModel[LifecycleResponse]`。

### 11.3 Benchmark

```http
GET /api/v1/dramas/benchmark
```

参数：重复 query 参数形式的 `drama_ids`，去重后 2–20；必填正整数 `platform_id`；可选 `analysis_as_of`。显式组有上限，V1 不分页。返回 `ResponseModel[BenchmarkResponse]`。

### 11.4 注册与权限

- 三个接口允许 USER 和 ADMINISTRATOR，匿名 401；
- 全部为 GET，不注册 POST/PUT/PATCH/DELETE；
- `/dramas/benchmark` 必须在所有 `/dramas/{drama_id}` 路由前注册；
- `routers/__init__.py` 中 operation analytics router 必须先于 drama profile 和 dramas router include；
- Router 只依赖 `OperationAnalyticsServiceDependency`；
- dependency factory 用同一个请求级 Session 构造只读 Repository 与 Providers；
- 不创建或调用业务 Service。

### 11.5 错误模型

- 无效参数与范围：422；
- Action/Drama 不存在：404；
- 合法数据不足：200 + Availability；
- 不可恢复的数据访问失败：现有统一 500；
- 不新增错误格式。

## 12. Frontend 规划

页面路径建议：`/operation-analytics`。

页面分为：

1. Operation Effectiveness：分页、Drama/Action 筛选、固定窗口与非因果提示；
2. Lifecycle Overview：单 Drama 查询、阶段、证据、规则版本；
3. Benchmark Analysis：2–20 Drama、多选、单平台、30 日指标与中位数。

Frontend 只显示 API 结果，不执行差分、比率、中位数、生命周期或 Availability 推导。不得添加 AI 建议、最佳短剧、排名或自动运营方案。

若使用 ECharts，仅展示 API 返回的数值；必须实现 resize 和 dispose。无必要时不强制使用图表。

## 13. 测试规划

### 13.1 Contracts

- 所有枚举值完整；
- DTO 正常和 Optional 构造；
- frozen/不可变语义；
- Availability 合法组合；
- 禁止因果、排名字段；
- contracts 无 ORM、Repository、Session、FastAPI 依赖。

### 13.2 Rule Components

#### Action Effect

- 两个完整 7 日窗口；
- Anchor Day 排除；
- 四项公式；
- Decimal 精度；
- 零基线；
- 指标缺失；
- 日期缺口；
- 累计回退；
- 重叠行动 PARTIAL；
- 输出无因果语义；
- 相同输入输出一致。

#### Lifecycle

- ARCHIVED 和 LAUNCH 优先级；
- 15 日点生成双 7 日窗口；
- `+10%`、`-10%` 边界；
- 前窗 0/后窗正值；
- 双零；
- 历史不足；
- release time 缺失、未来时间；
- 日期缺口、累计回退；
- 版本固定且无机器学习依赖。

#### Benchmark

- 2 和 20 成员边界；
- 少于 2 个可比成员；
- 固定 30 日/31 点；
- 五项指标；
- median 奇偶样本；
- 缺失成员不补 0且不进入 median；
- 混合版本 PARTIAL；
- 不产生排名或推荐。

#### Revision

- canonical key/list 顺序；
- 相同输入 hash 相同；
- revision ID、参数、规则版本或 as-of 改变时 hash 改变；
- 输出格式固定。

### 13.3 Repository

- as-of revision 选择；
- VOID 排除；
- 每日最后有效点；
- Action 完成事件稳定排序；
- 重叠 Action 查询；
- 15/31 日窗口批量读取；
- Anomaly 时间和版本过滤；
- 无 N+1；
- 不 commit/rollback/flush/sessionmaker；
- 不包含规则计算。

### 13.4 Providers

- Repository record 到输入 DTO 映射；
- Before/After 日期范围；
- release time 选择；
- Benchmark 单平台批量映射；
- 缺失状态；
- 不调用任何 Service；
- 不调用 Rule Component；
- 不返回 ORM、不管理事务。

### 13.5 Service

- 三个正常编排流程；
- 每个请求只冻结一次 as-of；
- Provider 与 Rule 调用参数正确；
- Benchmark 复用 LifecycleClassifier；
- 分页 metadata 保留；
- 单成员缺失隔离；
- 技术异常不伪装为数据不足；
- Service 不访问 ORM/SQL/Session；
- 不调用已有业务 Service；
- 不执行 commit/rollback。

### 13.6 API

- 三条 GET 路径与无写路径；
- JWT Bearer；
- USER/ADMIN 成功、匿名 401；
- 正整数、分页、2–20 IDs 和必填 platform 校验；
- analysis_as_of 传递；
- 404、422、500 与 200 Availability；
- ResponseModel、PageResponse、ErrorResponse；
- `/dramas/benchmark` 静态路径优先；
- Router 不访问 Repository/ORM/Provider/Rule。

### 13.7 Frontend

- TypeScript 类型与 API 契约一致；
- loading、empty、partial、insufficient、error、success；
- null 与真实 0 的展示差异；
- 非因果提示；
- 无前端公式；
- `npm exec vue-tsc -- --noEmit`；
- `npm run build`；
- 无新增依赖和 lock 修改。

## 14. 实施顺序与独立提交

### Step 1：Contracts

实现 contracts、包导出、Contracts 测试和开发文档。冻结 DTO、枚举、版本常量。不得包含 Rule、Repository 或 API。

建议提交：

```text
feat(phase8): add operation analytics contracts
```

### Step 2：Rule Components

实现 ActionEffectCalculator、LifecycleClassifier、BenchmarkCalculator、AnalysisRevisionBuilder、纯规则测试和文档。

建议提交：

```text
feat(phase8): add operation analytics rules
```

### Step 3：Read Repository 与 Providers

实现只读 OperationAnalyticsRepository、三个 Providers、导出、测试和文档。不得实现 Service。

建议提交：

```text
feat(phase8): add operation analytics providers
```

### Step 4：Service

实现 Validator、OperationAnalyticsService、依赖边界测试和文档。不得实现 Router。

建议提交：

```text
feat(phase8): add operation analytics service
```

### Step 5：API Schema

实现 Pydantic Schema 与 Schema 测试，冻结 HTTP 输出字段，不注册路径。

建议提交：

```text
feat(phase8): add operation analytics schemas
```

### Step 6：Router 与 Dependency

实现三条只读 GET、依赖组装、OpenAPI/权限/边界测试和文档。确保静态 benchmark 路径优先。

建议提交：

```text
feat(phase8): add operation analytics api
```

### Step 7：Dashboard

实现 TypeScript 类型、API Client、页面、路由、Dashboard 入口、构建验证和文档。

建议提交：

```text
feat(phase8): add operation analytics dashboard
```

### Step 8：Module Summary

汇总架构、公式、版本、API、测试、限制和提交历史，只提交归档文档。

建议提交：

```text
docs(phase8): add operation analytics module summary
```

每一步必须精确暂存，禁止 `git add .`，并确认不夹带现有 Backend、Frontend、backup、`.reasonix` 或其他未完成修改。

## 15. 数据库确认

Phase 8 V1 不创建 V014，不修改 V001–V013，不新增：

- `operation_effectiveness_results`；
- `operation_outcomes`；
- `lifecycle_snapshots`；
- `benchmark_snapshots`；
- `benchmark_results`；
- cache 表。

所有分析结果只存在于请求响应。若未来需要历史报告、周报/月报、固化结果或物化性能优化，必须重新进行 Database Design 和 Migration Review。

## 16. Implementation 准入清单

开始 Step 1 前必须由 Implementation Plan Review 确认：

- 文件结构和依赖方向通过；
- Contracts 字段、枚举和 null/0 语义通过；
- Rule 类名、公式、窗口、阈值和版本通过；
- `LifecycleInputProvider` 不执行分类；
- Repository 查询方法和批量策略通过；
- Service 三个接口通过；
- API 参数、响应、权限和路由顺序通过；
- TBD-P8-01、TBD-P8-02 继续作为 V1 排除项；
- 不创建 Migration、不修改 ORM、不持久化分析结果。

未经 Implementation Plan Review 批准，不得创建上述代码文件。
