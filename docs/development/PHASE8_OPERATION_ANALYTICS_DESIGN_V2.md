# Phase 8 Short Drama Operation Analytics Center Design V2

> 状态：Implementation 前冻结设计候选。本文只定义只读分析契约，不创建 Migration、不新增业务表、不修改 Phase 1–7 的业务事实。

## 1. Scope

Phase 8 Operation Analytics Center 是建立在现有事实和分析结果之上的 Read Model / Analytics Layer。V1 在请求期间读取可追溯输入，执行确定性规则并返回结果：

```text
Existing Data
    ↓
Provider
    ↓
Pure Rule Component
    ↓
OperationAnalyticsService
    ↓
Read-only API Response
```

V1 包含四项能力：

1. **Action Effect Analysis**：描述一个已完成运营行动前后固定窗口内的指标变化；
2. **Lifecycle Classification**：使用版本化规则描述 Drama 当前生命周期阶段；
3. **Benchmark Comparison**：在同平台、同时间窗口和显式指定的比较组内进行统计比较；
4. **Availability Protocol**：统一表达完整、部分、数据不足和不可用状态。

V1 只支持同步、只读、按请求计算。结果不落库，不形成新的业务事实，不修改任何来源记录。

### 1.1 V1 支持范围

- 基于 `analysis_as_of` 的历史可见性读取；
- 使用 `changed_at <= analysis_as_of` 的 snapshot revision；
- 固定 7 日行动前后窗口；
- 固定五阶段生命周期规则；
- 固定 30 日 Benchmark 窗口；
- 显式 Drama ID 比较组，规模为 2–20；
- 规则和响应版本标识；
- USER 与 ADMINISTRATOR 的只读查询。

### 1.2 V1 不支持范围

- 持久化分析结果、缓存或物化视图；
- 自定义行动分析窗口；
- 自动选择“相似 Drama”；
- 按类别自动形成 Benchmark 组；
- 生命周期历史快照；
- 对行动效果作因果归因；
- 自动生成行动、策略或推荐。

## 2. Non-goals

Phase 8 V1 明确不进行：

- 因果推断；
- 未来收益、投资价值或成功概率预测；
- LLM、AI Agent、机器学习分类或推荐；
- 自动运营决策或自动行动生成；
- Score、Quality、Prediction、Anomaly 的重新计算；
- 对 Action、Explanation 或 Drama Profile 的修改；
- “最佳短剧”等价值判断；
- 分析结果快照持久化。

禁止创建 `analysis_effects`、`operation_outcomes`、`lifecycle_snapshots`、`benchmark_results` 或 operation analytics cache 表。Phase 8 V1 不需要 V014 Migration。

## 3. Domain Model

本节定义 Phase 8 的输入 DTO 语义，不修改现有 ORM。

### 3.1 Drama

`AnalyticsDrama` 是分析输入中的 Drama 摘要：

| 字段 | 类型 | 来源与规则 |
|---|---|---|
| `drama_id` | positive integer | `dramas.drama_id` |
| `platform_id` | positive integer / null | Action 分析由被纳入窗口的平台集合给出；Benchmark V1 为请求必填的单个平台 |
| `category` | string / null | **[TBD-P8-01]** 当前模型没有规范化 category；V1 不得从标签或名称推断 |
| `release_time` | datetime / null | 平台分析取对应 `drama_platforms.online_at`；跨平台 Lifecycle 取最早非空 `online_at`，均为空时使用 `dramas.premiere_date` 当日 00:00（业务时区） |
| `status` | enum | `dramas.status`，只用于显式 `INACTIVE` 判断 |

所有业务日按 `Asia/Shanghai` 划分，数据库时间在边界层转换为 UTC 查询条件。响应时间使用带时区 ISO 8601。

### 3.2 Action

一次可分析 Action 是一条满足以下条件的 `operation_actions` 记录：

- `drama_id` 非空；
- 存在第一次进入 `COMPLETED` 的历史事件；
- 在 `analysis_as_of` 时该完成事件已经可见；
- 能构建固定的 Before 和 After 窗口。

逻辑输入结构：

| 字段 | 定义 |
|---|---|
| `action_id` | `operation_actions.action_id` |
| `drama_id` | 行动关联 Drama；全局行动不参与 V1 行动效果分析 |
| `action_type` | **[TBD-P8-02]** 当前 Action 表没有结构化类型；V1 不得从 `title` 或 `description` 推断 promotion/recommendation/campaign/release_event |
| `anchor_time` | 第一次进入 `COMPLETED` 的有效历史事件时间 |
| `duration` | `anchor_time - operation_actions.created_at`，只描述记录生命周期，不代表活动实际持续时间 |
| `metadata` | action 状态、priority、source types 与不可变 evidence 摘要；不得包含推断类别 |

#### 什么算一次 Action

每个唯一 `action_id` 算一次 Action。COMMENT、ASSIGN 和普通 STATUS_CHANGE 事件不是独立 Action。`CANCELLED`、`OPEN`、`IN_PROGRESS` 行动不产生完成后效果结果，返回明确 Availability。

#### 多 Action 重叠

若同一 Drama 的另一个 Action 的 `anchor_time` 落入当前 Action 的 Before 或 After 窗口，当前结果仍可返回，但 Availability 为 `PARTIAL`，原因包含 `OVERLAPPING_ACTIONS`，并返回重叠 `action_id`。不得扣除、分摊或归因重叠 Action 的影响。

## 4. Action Effect Analysis

版本常量：

```text
action_effect_rule_version = "Action Effect Analysis V1.0"
```

### 4.1 Action Definition

V1 只分析上节定义的、与单个 Drama 关联且已完成的 Action。

Proposal 中的 `promotion`、`recommendation`、`campaign`、`release_event` 尚无可靠结构化数据源，因此不作为 V1 可筛选类型。不得用文本分类补齐。若未来增加结构化 action type，必须先更新 Design 与数据契约。

### 4.2 Anchor

冻结：

```text
T0 = 第一次使 Action 进入 COMPLETED 的历史事件 created_at
```

选择完成时间而非 Action 创建时间，是因为现有模型能审计完成事件，但没有独立的活动开始时间。若同时存在 `CLOSE` 和 `STATUS_CHANGE -> COMPLETED`，取时间最早、`history_id` 最小的完成事件；后续重复事件不改变 T0。

`T0` 所在业务日是 Anchor Day，不进入 Before 或 After，避免把部分日混入完整日均值。

### 4.3 Analysis Window

V1 窗口固定，不接受客户端覆盖：

```text
Before Window = T0 业务日前第 7 日至前第 1 日（7 个完整业务日）
After Window  = T0 业务日后第 1 日至后第 7 日（7 个完整业务日）
```

要求：

- 两个窗口均必须有连续日点；
- 不插值，不以 0 填补缺失日期；
- `analysis_as_of` 必须不早于 After Window 最后一天结束时刻；
- 相同的可比平台集合贯穿两个窗口；
- 每个平台每天取截止 `analysis_as_of` 可见的最后有效累计观测；
- VOID revision 排除，未来 revision 不可见；
- 任一侧窗口不完整时不计算该侧派生指标。

### 4.4 Metrics

所有累计计数先按同平台相邻日末值做差，再跨固定平台集合求和。累计值回退属于无效输入，不把负增量截断为 0。

#### A. `views_change`

```text
before_views = sum(7 个 Before 日播放增量)
after_views  = sum(7 个 After 日播放增量)
absolute_change = after_views - before_views
relative_change = absolute_change / before_views
```

- 数据源：snapshot revision 的 `play_count`；
- `before_views = 0` 时 `relative_change = null`，原因增加 `ZERO_BASELINE`；
- `absolute_change` 仍可返回。

#### B. `engagement_change`

单日互动增量：

```text
interaction_increment
  = like_increment + comment_increment
  + favorite_increment + share_increment
```

窗口互动率：

```text
engagement_rate = sum(interaction_increment) / sum(play_increment)
engagement_change = after_engagement_rate - before_engagement_rate
```

- 数据源：snapshot revision 的五个累计指标；
- 任一窗口播放增量为 0，或互动指标缺失时，该指标为 null，并返回固定原因；
- 不使用累计互动总量直接除累计播放总量。

#### C. `growth_rate_change`

```text
before_daily_average = before_views / 7
after_daily_average  = after_views / 7
growth_rate_change
  = (after_daily_average - before_daily_average) / before_daily_average
```

- 数据源：与 `views_change` 相同；
- Before 均值为 0 时返回 null 和 `ZERO_BASELINE`；
- 字段表示前后窗口日均播放增量的相对变化，不表示行动“带来”的增长率。

#### D. `anomaly_count_change`

```text
before_anomaly_count = count(anomaly analysis_as_of date in Before Window)
after_anomaly_count  = count(anomaly analysis_as_of date in After Window)
anomaly_count_change = after_anomaly_count - before_anomaly_count
```

- 数据源：`data_anomaly_records`；
- 只统计同一 `drama_id`，不按当前状态排除已处置异常；
- 响应必须携带所纳入的 `algorithm_version` 集合；混合版本时 Availability 为 `PARTIAL`、原因包含 `MIXED_SOURCE_VERSIONS`。

#### 描述性结论

V1 不输出 `IMPROVED`、`SUCCESSFUL` 或 `EFFECTIVE` 等综合效果等级。每项指标只输出 `INCREASED`、`UNCHANGED`、`DECREASED` 或 `UNAVAILABLE`。这些方向由数值符号直接映射，不代表因果或价值判断。

### 4.5 Output Schema

```json
{
  "action_id": 1001,
  "drama_id": 88,
  "action_type": null,
  "anchor_time": "2026-09-10T09:30:00+08:00",
  "window": {
    "before_start": "2026-09-03",
    "before_end": "2026-09-09",
    "after_start": "2026-09-11",
    "after_end": "2026-09-17",
    "window_days": 7
  },
  "metrics": [],
  "availability": {
    "status": "AVAILABLE",
    "reasons": []
  },
  "overlapping_action_ids": [],
  "action_effect_rule_version": "Action Effect Analysis V1.0",
  "analysis_revision": "sha256:<digest>",
  "analysis_as_of": "2026-09-18T00:00:00Z",
  "disclaimer": "Observed post-action metric movement does not establish causation."
}
```

`metrics` 的每一项固定包含 `metric_type`、`before_value`、`after_value`、`absolute_change`、`relative_change`、`direction`、`unit` 和自身 Availability。

## 5. Lifecycle Classification

### 5.1 State Definition

V1 沿用 Architecture Review 的五阶段集合：

| 状态 | 含义 | 判断依据 |
|---|---|---|
| `LAUNCH` | 上线初期，历史仍处于冷启动窗口 | 距 `release_time` 0–14 个完整业务日 |
| `GROWTH` | 最近窗口日均播放增量显著高于前一窗口 | 两个连续 7 日窗口比较 |
| `STABLE` | 最近窗口与前一窗口变化处于稳定带 | 两个连续 7 日窗口比较 |
| `DECLINE` | 最近窗口日均播放增量显著低于前一窗口 | 两个连续 7 日窗口比较 |
| `ARCHIVED` | Drama 已被业务系统明确停用 | `dramas.status = INACTIVE` |

`ARCHIVED` 只由显式业务状态产生，不根据低播放量自动推断。V1 不使用 `NEW/GROWING/MATURE/DECLINING/DORMANT` 的另一套枚举，避免双重协议。

### 5.2 Classification Rules

版本：

```text
lifecycle_rule_version = "Lifecycle Rules V1.0"
```

输入：

- `drama_id`；
- `release_time`；
- Drama status；
- 截止 `analysis_as_of` 的连续 15 个累计播放量日末点；
- 由 15 点产生的连续 14 个日增量。

窗口：

```text
previous_average = mean(较早 7 个日增量)
current_average  = mean(最近 7 个日增量)
```

确定性规则：

1. status 为 `INACTIVE`：`ARCHIVED`；
2. 非 INACTIVE 且距 release_time 不超过 14 个完整业务日：`LAUNCH`；
3. 其余情况必须具有连续 15 个累计日点，否则 `INSUFFICIENT`；
4. `previous_average = 0` 且 `current_average > 0`：`GROWTH`；
5. `previous_average = 0` 且 `current_average = 0`：`STABLE`；
6. `previous_average > 0` 时计算：

```text
window_change_rate
  = (current_average - previous_average) / previous_average
```

- `window_change_rate >= 0.10`：`GROWTH`；
- `window_change_rate <= -0.10`：`DECLINE`；
- 其他：`STABLE`。

任何累计播放量回退、负数、非有限数值或日期缺口均不分类，返回 `INSUFFICIENT` 或 `NOT_AVAILABLE` 及对应原因；不得修补数据。

### 5.3 Priority

规则优先级固定：

```text
ARCHIVED > LAUNCH > 输入有效性 > GROWTH/DECLINE/STABLE
```

`GROWTH` 与 `DECLINE` 的阈值区间互斥，不会同时命中。边界值 `+0.10` 属于 GROWTH，`-0.10` 属于 DECLINE。其他值属于 STABLE。

### 5.4 Lifecycle Output

响应至少包含：`drama_id`、`state`、`evidence`、两个窗口、`window_change_rate`、Availability、`lifecycle_rule_version`、`analysis_revision` 和 `analysis_as_of`。历史不足时 `state = null`，不得返回默认 STABLE。

## 6. Benchmark Design

### 6.1 Comparison Group

V1 只支持调用方显式提供 2–20 个不同的 `drama_id`，同时必须提供一个 `platform_id`。所有 Drama 必须：

- 在该平台存在 release relation；
- 在同一窗口有可比较数据；
- 使用相同 `analysis_as_of` 和 revision 规则。

V1 不自动按 category、tag 或全库平均形成比较组。当前 Drama 没有规范化 category，故 category cohort 属于 **[TBD-P8-01]**。全库平均被禁止，因为平台、上线时间和数据覆盖不可比。

### 6.2 Benchmark Time

版本：

```text
benchmark_version = "Benchmark Comparison V1.0"
```

V1 使用截至 `analysis_as_of` 前一完整业务日结束的固定 30 日窗口，需要连续 31 个累计日末点生成 30 个日增量。请求不允许改为 7/90 日。

比较基于同一自然日期窗口，而不是各自上线后的相对天数。尚未上线或覆盖不足的 Drama 保留在响应中，但 Availability 为 `INSUFFICIENT`，不进入组统计。

### 6.3 Benchmark Metrics

| 指标 | 定义 | 数据源 |
|---|---|---|
| `play_increment_total` | 30 个 `play_count` 日增量之和 | snapshot revisions |
| `mean_daily_play_increment` | `play_increment_total / 30` | snapshot revisions |
| `engagement_rate` | 30 日互动增量总和 / 30 日播放增量总和 | snapshot revisions |
| `anomaly_frequency` | 窗口内同 Drama 异常记录数 / 30 | anomaly records |
| `lifecycle_state` | 使用 `Lifecycle Rules V1.0` 在相同 `analysis_as_of` 的分类 | lifecycle pure rule |

数据质量分数当前为 `ALL / 0` 全局作用域，不能作为 Drama 间比较指标。若未来增加 Drama 级质量结果，需要另行评审，当前不得把全局质量分复制到每个 Drama。

每个数值指标返回各 Drama 原始值以及可比成员的组 `median`。V1 不返回综合分、权重、名次、赢家、推荐或“优于/劣于”的价值标签。少于 2 个可比成员时组统计不可用，原因 `INCOMPARABLE_SCOPE`。

### 6.4 Benchmark Output

响应包含：比较组、`platform_id`、固定窗口、指标定义、成员值、组中位数、成员 Availability、来源版本集合、`benchmark_version`、`lifecycle_rule_version`、`analysis_revision` 和 `analysis_as_of`。

## 7. Availability Protocol

所有顶层分析和单项指标均使用：

```json
{
  "status": "AVAILABLE",
  "reasons": []
}
```

### 7.1 Status

| 状态 | 含义 |
|---|---|
| `AVAILABLE` | 所有必需输入完整且结果可比较 |
| `PARTIAL` | 核心结果可返回，但存在重叠行动、个别可选指标缺失或来源版本混合 |
| `INSUFFICIENT` | 必需历史长度或完整窗口不足，不能产生核心结论 |
| `NOT_AVAILABLE` | 输入无效、来源不可访问或请求范围不可比较 |

### 7.2 Reason Codes

V1 固定原因：

- `NOT_CALCULATED`；
- `INSUFFICIENT_HISTORY`；
- `INCOMPLETE_BEFORE_WINDOW`；
- `INCOMPLETE_AFTER_WINDOW`；
- `INCOMPARABLE_SCOPE`；
- `MISSING_METRIC`；
- `ZERO_BASELINE`；
- `OVERLAPPING_ACTIONS`；
- `MIXED_SOURCE_VERSIONS`；
- `INVALID_CUMULATIVE_SEQUENCE`；
- `NOT_COMPLETED`；
- `GLOBAL_ACTION_UNSUPPORTED`；
- `NOT_AVAILABLE`。

规则：

- 数据不足时数值字段为 null，不返回 0；
- 合法的真实零值必须在 `AVAILABLE` 状态下返回 0；
- `reasons` 去重并按枚举定义顺序输出；
- PARTIAL 不得伪装为 AVAILABLE；
- Provider 技术异常映射为 NOT_AVAILABLE，但日志不得泄露到响应。

## 8. Revision Model

### 8.1 `analysis_as_of`

`analysis_as_of` 是本次分析可见数据的硬截止时间：

- snapshot observation 不晚于该时间；
- snapshot revision 必须满足 `changed_at <= analysis_as_of`；
- 每个 snapshot 槽位选择截止时点可见的最高 `version_no`；
- 截止时点选择到 VOID revision 时排除该槽位；
- Prediction、Anomaly、Score 等结果不得选择分析时间晚于该截止点的记录；
- API 未传入时，由 Service 在请求开始时确定一次 UTC 当前时间，并在整个请求复用。

### 8.2 Rule Versions

V1 固定：

- `action_effect_rule_version = "Action Effect Analysis V1.0"`；
- `lifecycle_rule_version = "Lifecycle Rules V1.0"`；
- `benchmark_version = "Benchmark Comparison V1.0"`。

阈值、窗口、指标公式或分类优先级发生语义变化时必须升级对应版本，不得静默修改。

### 8.3 `analysis_revision`

V1 不存储 revision，响应中的 `analysis_revision` 是本次输入身份摘要：

```text
analysis_revision = "sha256:" + SHA-256(canonical JSON)
```

Canonical JSON 按键排序、UTF-8 编码，至少包含：分析类型、实体 ID、请求参数、`analysis_as_of`、使用的 snapshot revision IDs、来源结果 IDs 与版本、规则版本。列表按稳定主键升序排列。

相同输入和规则产生相同 revision；任何输入 revision、来源结果、参数或规则版本变化都会产生不同 revision。该值用于响应追踪和测试，不代表数据库记录，也不保证跨规则版本相等。

## 9. Architecture Boundary

### 9.1 Provider

Provider 只负责批量读取和映射：

- `OperationEffectivenessProvider`：读取 Action、完成事件、重叠 Action 和前后窗口原始输入；
- `LifecycleInputProvider`：读取 Drama、release time 和 15 日累计点；
- `BenchmarkProvider`：批量读取显式比较组的 31 日点、异常和版本信息。

Provider 不执行指标公式、生命周期分类、综合判断或写入；不调用任何业务 Service；不向上返回 ORM；不 commit/rollback。

### 9.2 Rule Component

纯规则组件：

- `ActionEffectCalculator`；
- `LifecycleClassifier`；
- `BenchmarkCalculator`；
- `AnalysisRevisionBuilder`。

它们只接收 DTO 并返回 DTO，不访问数据库、Repository、Session、网络或当前时间。相同输入必须产生相同输出。

### 9.3 Service

`OperationAnalyticsService` 负责：

- 参数和范围校验；
- 在请求开始时冻结 `analysis_as_of`；
- 调用 Provider；
- 调用对应纯规则组件；
- 校验版本和比较口径；
- 组装 Availability、revision 和响应。

Service 不调用 ScoreService、PredictionService、AnomalyService、OperationActionService、DramaProfileService 或 ExplanationService；不写数据库，不管理写事务，不修改来源数据。

### 9.4 Router 与 Frontend

Router 只做认证、参数解析、Service 调用和 `ResponseModel[T]` 转换。Frontend 只展示 API 结果。两者均不得计算指标、分类生命周期或推导 Availability。

## 10. API Contract

所有接口使用 `/api/v1`、JWT Bearer、现有 `ResponseModel[T]` 和 `ErrorResponse`。USER 与 ADMINISTRATOR 均可读取；匿名为 401。V1 无写接口。

### 10.1 Action Effectiveness

```http
GET /api/v1/operations/effectiveness
```

查询参数：

- `action_id: int | null`，正整数；
- `drama_id: int | null`，正整数；
- `status: COMPLETED | null`，V1 仅接受 COMPLETED；
- `analysis_as_of: datetime | null`；
- `page: int = 1`，最小 1；
- `page_size: int = 20`，范围 1–100。

`action_id` 指定时忽略分页但仍返回单项分页结构。V1 不暴露 `window_days`，窗口固定为 7。响应为 `ResponseModel[PageResponse[ActionEffectResponse]]`，按 `anchor_time DESC, action_id DESC` 稳定排序。

### 10.2 Lifecycle

```http
GET /api/v1/dramas/{drama_id}/lifecycle
```

- 路径 `drama_id` 为正整数；
- 可选 `analysis_as_of`；
- Drama 不存在返回 404；
- 历史不足返回 HTTP 200，并在 Availability 中表达。

响应为 `ResponseModel[LifecycleResponse]`。

### 10.3 Benchmark

```http
GET /api/v1/dramas/benchmark
```

查询参数：

- `drama_ids: list[int]`，必填、去重后 2–20；
- `platform_id: int`，必填、正整数；
- `analysis_as_of: datetime | null`。

比较组已明确受限，因此 V1 不分页。响应为 `ResponseModel[BenchmarkResponse]`，成员按请求中去重后的 drama ID 顺序返回。静态 `/benchmark` 必须在 `/{drama_id}` 动态路由之前注册。

### 10.4 API 错误边界

- 参数格式、范围和重复后成员不足：422；
- Drama/Action 不存在：404；
- 合法但数据不足：200 + Availability；
- Provider 不可用：200 + NOT_AVAILABLE（单项）或现有统一 500（整个数据源不可访问且无法形成响应）；
- 禁止新增错误格式。

## 11. Implementation Constraints

进入实现前必须满足：

1. Design V2 Architecture Review 通过；
2. Contracts DTO、枚举和 Availability Schema 冻结；
3. 三个 API Contract 冻结；
4. 三个规则版本及其公式、窗口和边界冻结；
5. `[TBD]` 被明确接受为 V1 排除项，或通过新的已批准设计消除；
6. 确认不创建 V014、不修改 V001–V013；
7. 确认所有 Repository 查询支持 as-of revision 与批量读取，若缺失只允许新增只读 Repository 方法；
8. 建立非因果措辞的 Schema、API 和 Frontend 测试；
9. 建立源码边界测试，禁止 Service-to-Service、Rule-to-Database 和 Frontend 计算。

建议实现顺序：

1. Contracts 与 Availability；
2. 三个纯规则组件和单元测试；
3. 只读 Providers；
4. `OperationAnalyticsService`；
5. Schema、Dependency 与只读 API；
6. Operation Analytics Dashboard；
7. 模块总结与性能基线。

## 12. 数据库与保留策略

Phase 8 V1 的分析结果只存在于请求响应中：

- 不保存 Action effect；
- 不保存 Lifecycle state；
- 不保存 Benchmark result；
- 不保存 `analysis_revision`；
- 不新增 cache 表。

来源事实继续由 Phase 1–7 的现有表负责。若未来需要发布型复盘报告、生命周期历史或性能物化，必须单独发起 Design、Migration Review 和新版本契约，不能复用本 V1 的临时结果作为持久化事实。

## 13. 冻结结论与 TBD

本文冻结 Phase 8 V1 的只读架构、固定窗口、公式、生命周期规则、Benchmark 范围、Availability、版本和 API 形态。

尚未解决项：

- **[TBD-P8-01] Drama category**：当前没有规范化 category 字段；V1 Benchmark 不支持 category 自动分组。
- **[TBD-P8-02] Action semantic type**：当前没有结构化 `action_type`、实际开始时间或活动持续时间；V1 不支持 promotion/recommendation/campaign/release_event 类型筛选，也不从文本推断。

以上 TBD 不阻止实现已经冻结的 V1 范围，但任何试图加入 category cohort 或语义 Action 类型的实现都必须先补充事实模型与设计审查。
