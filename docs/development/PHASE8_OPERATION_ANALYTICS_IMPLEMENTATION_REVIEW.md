# Phase 8 Short Drama Operation Analytics Center Implementation Plan Review

> 审查对象：`PHASE8_OPERATION_ANALYTICS_IMPLEMENTATION_PLAN.md`
>
> 准入目标：判断是否允许进入 Phase 8 Contracts Implementation。
>
> 本文不授权 Migration、ORM、Repository、Rule、Service、API 或 Frontend 实现。

## 1. Review 结论

Implementation Plan 已将 Design V2 和 Architecture Review 的冻结要求落实到文件结构、Contracts、纯规则、只读 Repository、Providers、Service、API Schema、测试矩阵和独立提交顺序。

审查结论：**Option A——允许进入 Phase 8 Contracts Implementation。**

该准入仅授权下一阶段实现 Contracts、Contracts 单元测试和对应开发文档。Rule Components、Repository、Providers、Service、API 和 Frontend 仍需按计划逐阶段获得单独任务后实施。

## 2. 总体架构审查

Implementation Plan 对建议架构作出了必要的边界澄清。正确调用关系不是 Provider 依次调用 Rule 和 Repository，而是：

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
Read Repository
       ↓
Existing ORM / Tables
```

该结构保证：

- Provider 只准备数据；
- Rule Component 只计算；
- Service 负责二者编排；
- Repository 只执行只读查询；
- API 和 Frontend 不承载分析逻辑。

`OperationAnalyticsService` 被明确禁止调用 ScoreService、PredictionService、AnomalyService、OperationActionService、DramaProfileService 和 ExplanationService。依赖方向单向，不形成跨业务 Service 循环。

此项通过。

## 3. Contracts 设计审查

### 3.1 Availability 协议

状态已冻结：

```text
AVAILABLE
PARTIAL
INSUFFICIENT
NOT_AVAILABLE
```

原因码覆盖无历史、前后窗口不足、指标缺失、不可比较、零基线、重叠行动、混合版本、无效累计序列、Action 未完成、全局 Action 不支持和技术不可用。

业务状态不依赖 null 表达：

- 状态和原因由 `AnalysisAvailability` 明确返回；
- 缺失数值使用 null，但同时必须有 Availability；
- 合法真实零值可以在 AVAILABLE 状态下返回 0；
- 数据不足不得伪造为 0。

该协议可明确表达数据不足、无历史、不可计算和不可用。此项通过。

### 3.2 OperationEffectivenessResult

已规划字段：

- `action_id`；
- `drama_id`；
- `anchor_time`；
- `before_window`；
- `after_window`；
- `metric_changes`；
- `overlapping_action_ids`；
- `availability`；
- 规则版本、`analysis_revision`、`analysis_as_of` 和非因果免责声明。

明确禁止 `causal_result`、`success`、`effective` 和 `contribution`。V1 的 `action_type` 固定为空，不从文本推断。

此项通过。

### 3.3 LifecycleResult

已规划：

- `drama_id`；
- `lifecycle_stage`；
- `evidence`；
- `rule_version`；
- `analysis_revision`；
- `evaluated_as_of`；
- `availability`。

历史不足或 release time 无效时 stage 为 null，但业务原因由 Availability 明确表达，不默认 STABLE。

此项通过。

### 3.4 BenchmarkResult

已规划比较范围、窗口、成员指标、组中位数、Availability、版本和 as-of。明确禁止 rank、winner、best、recommendation 和 value score。

`target_drama_id` 在 V1 为 null，因为比较对象是显式集合而非单一目标；Contracts 实现时可直接省略该字段，避免产生虚假的目标语义。该建议不改变 Design V2 业务范围，不阻塞 Contracts 实现。

Contracts 总体设计通过。

## 4. Rule Components 审查

### 4.1 ActionEffectCalculator

冻结：

```text
T0 = Action 第一次进入 COMPLETED 的历史事件时间
Before = T0 前 7 个完整业务日
After  = T0 后 7 个完整业务日
```

组件负责四项固定指标、方向和指标级 Availability，不判断 Action 是否成功或有效。Anchor Day 排除，窗口不可由客户端修改，负累计增量不能截断为 0。

此项通过。

### 4.2 LifecycleClassifier

阶段冻结为：

```text
LAUNCH / GROWTH / STABLE / DECLINE / ARCHIVED
```

规则采用连续 15 个累计日点、前后两个 7 日增量窗口、±10% 阈值和明确优先级。版本固定为 `Lifecycle Rules V1.0`，不使用机器学习。

计划使用 `LifecycleClassifier`，而不是让 `LifecycleInputProvider` 执行分类，符合 Architecture Review。

此项通过。

### 4.3 BenchmarkCalculator

比较范围冻结为：

- 同一 `platform_id`；
- 显式 2–20 个 Drama；
- 滚动 30 个完整自然业务日；
- 连续 31 个累计点产生 30 个增量；
- 至少 2 个可比成员才能产生组统计。

组件只计算固定指标和中位数，不排序价值、不推荐、不判断“最佳短剧”。

此项通过。

### 4.4 Rule 公共边界

所有 Rule Component 均规划为确定性纯计算：不访问 ORM、Repository、Session、网络或当前时间；相同输入产生相同输出；使用 Decimal；不修改输入。

此项通过。

## 5. AnalysisRevisionBuilder 审查

`AnalysisRevisionBuilder` 的职责是基于 canonical JSON 生成稳定的 `sha256:<hex>` 输入身份摘要。摘要覆盖分析类型、实体 IDs、请求参数、已冻结的 `analysis_as_of`、snapshot revision IDs、来源结果 IDs/版本和规则版本。

必须明确：

- 它**不构造或选择** `analysis_as_of`；
- 它不读取当前时间；
- 它不查询数据库；
- 它不计算业务指标；
- 它不保存或修改数据。

`analysis_as_of` 由 `OperationAnalyticsService` 在请求入口通过注入的 Clock 冻结一次，再传给 Provider、Rule 和 RevisionBuilder。这样才能保证一次请求中的历史读取一致性。

Implementation Plan 已符合该边界。此项通过。

## 6. Provider 设计审查

三个 Provider 已冻结：

1. `OperationEffectivenessProvider`；
2. `LifecycleInputProvider`；
3. `BenchmarkProvider`。

统一职责：调用只读 Repository、批量取得输入、识别结构化数据缺失、映射 Contracts DTO。

统一禁止：

- 返回 ORM entity；
- 调用任何 Service；
- 调用 Rule Component；
- 执行差分、均值、中位数或生命周期分类；
- 写数据库或管理事务。

特别确认：`LifecycleInputProvider` 只返回 `LifecycleInput`，不返回 LifecycleStage；分类由 Service 调用 `LifecycleClassifier` 完成。

Provider 设计通过。

## 7. Repository 设计审查

`OperationAnalyticsRepository` 被规划为 Phase 8 专用只读查询边界，支持：

- Action 与完成事件查询；
- 重叠 Action 查询；
- `analysis_as_of` 过滤；
- snapshot revision 选择；
- VOID 排除；
- 时间窗口查询；
- Drama、指标和 Anomaly 的批量投影；
- 稳定分页与计数。

Repository 不计算 Action Effect、Lifecycle 或 Benchmark，不调用 Rule，不 commit、rollback、flush 或创建 Session。返回不可变投影 record，避免 ORM 泄漏到 Provider。

查询计划要求按 Drama/Action 批量读取并测试 N+1，满足只读聚合层需要。此项通过。

## 8. Service 设计审查

`OperationAnalyticsService` 规划接口：

```text
get_operation_effectiveness(...)
get_lifecycle(...)
get_benchmark(...)
```

职责：

- 校验参数和跨 DTO 不变量；
- 请求入口冻结一次 `analysis_as_of`；
- 调用 Provider 准备输入；
- 调用 Rule Component；
- 调用 RevisionBuilder；
- 组装 Availability、版本和响应 DTO；
- 保留分页元数据。

禁止 ORM、SQL、Session、数据保存、写事务、OperationLog 和已有业务 Service 调用。

计划还区分了业务缺失和技术失败：业务缺失使用 Availability；不可预期的 Repository/Provider 技术异常进入现有错误体系，不能伪装为成功空结果。

Service 设计通过。

## 9. API 规划审查

### 9.1 路由范围

```http
GET /api/v1/operations/effectiveness
GET /api/v1/dramas/{drama_id}/lifecycle
GET /api/v1/dramas/benchmark
```

全部 JWT 保护，USER 与 ADMINISTRATOR 可读，匿名返回 401。V1 不注册 POST、PUT、PATCH 或 DELETE。

### 9.2 参数与分页

- Effectiveness 支持 Action/Drama 过滤、as-of、page 和 1–100 page size；固定 7 日窗口；
- Lifecycle 使用正整数 drama ID 和可选 as-of；
- Benchmark 使用去重后 2–20 个 drama IDs、必填 platform ID 和可选 as-of；显式小集合不分页。

### 9.3 返回与路由顺序

统一使用 `ResponseModel[T]`、`PageResponse[T]` 和 `ErrorResponse`。合法数据不足返回 200 + Availability，不存在返回 404，参数错误返回 422。

`/dramas/benchmark` 必须在任何 `/dramas/{drama_id}` 动态路由之前注册。Router 只调用 `OperationAnalyticsServiceDependency`。

API 规划通过。

## 10. 测试计划审查

测试矩阵覆盖：

### Contracts

- DTO 和枚举；
- Optional、不可变性；
- Availability 合法组合；
- 禁止因果和排名字段；
- 无 ORM/FastAPI 依赖。

### Rules

- Action 前后窗口、四项公式、零基线、缺口、累计回退和重叠 Action；
- Lifecycle 优先级、双窗口、±10% 边界、零值、历史不足和 release time 异常；
- Benchmark 2/20 边界、30 日窗口、中位数、不可比较和混合版本；
- Revision hash 的稳定性和变化敏感性。

### Repository 与 Providers

- as-of revision、VOID、每日最后有效点、批量查询和 N+1；
- DTO 映射、数据缺失、无 Service/Rule 调用、无 ORM 输出和无事务管理。

### Service 与 API

- Provider/Rule 编排、一次 as-of、Availability、异常边界；
- JWT 权限、参数、Schema、错误模型、静态路径优先和只读路由；
- 源码边界检查。

### Frontend

- loading、empty、partial、insufficient、error、success；
- null 与真实 0；
- 非因果提示；
- TypeScript 与生产构建；
- 无前端计算。

测试计划完整，具备实施可验证性。

## 11. 数据库影响确认

Phase 8 V1 继续采用实时 Read Model：

- 不创建 V014 Migration；
- 不修改 V001–V013；
- 不新增 Action Effect 表；
- 不新增 Lifecycle Snapshot 表；
- 不新增 Benchmark Snapshot/Result 表；
- 不新增 cache 表；
- 不修改现有 ORM。

如果未来需要历史报告、周报/月报、固化分析结果或物化性能优化，必须重新进入 Database Design 与 Migration Review。

数据库影响结论：**无数据库变更。**

## 12. TBD 审查

### TBD-P8-01：Drama category

V1 排除 category 自动分组、同类剧自动 Benchmark 和文本/标签推断。未来需先建立标准化 Category 数据模型和治理规则。

### TBD-P8-02：Action 结构不足

V1 排除 promotion 等语义类型分析、实际活动周期分析和文本推断。只使用现有 action ID、Drama 关联、完成历史事件和结构化来源证据。

两个 TBD 已变成明确的 V1 排除项，不阻塞 Contracts Implementation。Contracts 不得为它们预留未经批准的任意字符串扩展口。

## 13. 冻结内容

进入 Contracts Implementation 后不得自行改变：

1. Contracts 枚举、DTO 分层和 null/0 语义；
2. Action T0、两个 7 日窗口、四项指标和非因果字段；
3. Lifecycle 五阶段、双 7 日窗口、±10% 阈值和规则版本；
4. Benchmark 单平台、显式 2–20 Drama、滚动 30 日和无排名原则；
5. RevisionBuilder 只构建摘要，Service 冻结 as-of；
6. Provider 只读数据准备、Rule 纯计算；
7. Repository 的 as-of/revision/批量读取能力；
8. Service 不访问 ORM/SQL、不调用业务 Service；
9. 三条只读 GET API、JWT 权限和统一响应模型；
10. V1 不新增 Migration、不保存分析结果；
11. TBD-P8-01、TBD-P8-02 继续排除。

## 14. Contracts Implementation 准入范围

下一阶段只允许新增：

```text
backend/services/operation_analytics/__init__.py
backend/services/operation_analytics/contracts.py
backend/tests/test_operation_analytics_contracts.py
docs/development/PHASE8_OPERATION_ANALYTICS_CONTRACTS.md
```

Contracts 阶段禁止：

- Repository、Provider、Rule、Service、Schema、Router 或 Frontend；
- ORM/SQLAlchemy/FastAPI 依赖；
- Migration 或数据库变更；
- 计算公式实现；
- 修改 Phase 1–7 模块。

## 15. 最终准入判断

Implementation Plan 与 Design V2、Architecture Review 保持一致，职责边界、文件结构、规则版本、API 范围和测试顺序均可执行。

最终判断：**允许进入 Phase 8 Contracts Implementation。**

该授权仅适用于第 14 节列出的 Contracts 文件范围。完成并独立审查后，方可进入 Rule Components 阶段。
