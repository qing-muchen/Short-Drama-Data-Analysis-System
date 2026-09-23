# Phase 8 OperationAnalyticsService

## 1. Service 定位

`OperationAnalyticsService` 是 Phase 8 的只读 Application Service / Orchestration
Layer。它连接已经冻结的 Provider、Rule Component、Contracts 和
`AnalysisRevisionBuilder`：

```text
API（后续阶段）
  ↓
OperationAnalyticsService
  ├─ freeze analysis_as_of
  ├─ validate request invariants
  ├─ call Provider
  ├─ call Rule Component
  └─ attach analysis_revision
```

Service 不访问 ORM、Session 或 SQL，不创建数据库事务，不修改现有分析结果，也不调用
Score、Prediction、Anomaly、Operation Action 或 Drama Profile Service。

## 2. 依赖注入

构造器显式注入：

- `OperationEffectivenessProvider`；
- `LifecycleInputProvider`；
- `BenchmarkProvider`；
- `ActionEffectCalculator`；
- `LifecycleClassifier`；
- `BenchmarkCalculator`；
- `AnalysisRevisionBuilder`；
- `Clock`。

Service 不自行创建 Provider、Rule、Repository 或全局单例。生产环境可使用
`SystemClock`，测试使用固定 Clock。

## 3. `analysis_as_of` 冻结

每个公开方法在入口只冻结一次 `analysis_as_of`：

1. 请求明确提供时，校验其为带时区 `datetime`；
2. 未提供时，只调用一次注入的 `Clock.now()`；
3. 将截点规范化为带时区 UTC；
4. 将同一实例值传给所有相关 Provider、Rule 输出和 RevisionBuilder。

`AnalysisRevisionBuilder` 不读取当前时间，也不选择分析截点，只对 Service 已冻结的输入
身份生成 `sha256:<hex>`。

## 4. Operation Effectiveness 流程

接口：

```text
get_operation_effectiveness(
  action_id?, drama_id?, analysis_as_of?, page=1, page_size=20
) -> OperationEffectivenessResultPage
```

流程：

```text
validate filters/page
  → freeze analysis_as_of
  → OperationEffectivenessProvider.get_inputs
  → ActionEffectCalculator.calculate per input
  → AnalysisRevisionBuilder.build per result
  → aggregate page Availability
```

返回页保留 `page`、`page_size`、`total`、不可变结果集合、页级 Availability 和冻结截点。
Service 不计算指标变化，也不输出行动成功、失败或因果结论。

Action revision 覆盖：行动/短剧 ID、Before/After 窗口、快照 revision IDs、异常版本和
Action Effect 规则版本。

## 5. Lifecycle 流程

接口：

```text
get_lifecycle(drama_id, analysis_as_of?) -> LifecycleResult
```

流程：

```text
validate drama_id
  → freeze analysis_as_of
  → LifecycleInputProvider.get_input
  → LifecycleClassifier.classify
  → AnalysisRevisionBuilder.build
  → LifecycleResult
```

Lifecycle revision 覆盖 Drama ID、状态、release time、连续快照 revision IDs 和
Lifecycle Rule 版本。Service 不判断生命周期阶段。

Provider 无法提供输入或 Provider/Rule 发生隔离故障时，返回阶段为空且 Availability 为
`NOT_AVAILABLE` 的结构化结果，不使用 `None` 表达对外业务状态。

## 6. Benchmark 流程

接口：

```text
get_benchmark(drama_ids, platform_id, analysis_as_of?) -> BenchmarkResult
```

流程：

```text
validate/deduplicate 2–20 drama IDs and platform ID
  → freeze analysis_as_of
  → BenchmarkProvider.get_input
  → LifecycleInputProvider + LifecycleClassifier per member
  → BenchmarkCalculator.compare
  → AnalysisRevisionBuilder.build
  → BenchmarkResult
```

逐成员 Lifecycle 补充符合冻结 Implementation Plan：Benchmark 的生命周期指标来自同一
规则组件，不由 Benchmark Provider 或 Service 自行判断。单个成员的 Lifecycle 读取或
分类失败时，仅将该成员标记为 `NOT_AVAILABLE`；其他成员仍进入 Benchmark Rule。若剩余
可比较成员不足两个，Rule 返回 `INSUFFICIENT / INCOMPARABLE_SCOPE`。

Benchmark revision 覆盖显式 Drama 集合、平台、固定30日窗口、快照 revision IDs、异常
算法版本、Benchmark 版本与 Lifecycle Rule 版本。

## 7. Availability 策略

Service 保留 Provider 与 Rule 已生成的原因，不将数据不足转换为零：

- 正常分析：`AVAILABLE`；
- 部分指标或成员不可用：`PARTIAL`；
- 历史不足或不可比较：`INSUFFICIENT`，原因包括
  `INSUFFICIENT_HISTORY`、`INCOMPARABLE_SCOPE` 等；
- Provider/Rule 隔离故障：`NOT_AVAILABLE / NOT_AVAILABLE`；
- 尚未形成依赖分析结果：由 Rule 保留 `NOT_CALCULATED` 原因。

Action 结果页会根据所有成员 Availability 聚合页级状态；空查询结果是合法的
`AVAILABLE` 空页。

## 8. 异常隔离

本阶段按照明确的结构化降级协议处理单次分析调用：

- Action Provider 失败：返回 `NOT_AVAILABLE` 空页；
- 单个 Action Rule 失败：仅该 Action 返回 `NOT_AVAILABLE`，保留 action/drama 身份；
- Lifecycle Provider/Rule 失败：返回 `NOT_AVAILABLE` LifecycleResult；
- Benchmark Provider/Rule 失败：返回相同请求 scope 和窗口的
  `NOT_AVAILABLE` BenchmarkResult；
- Benchmark 单个成员 Lifecycle 失败：仅隔离该成员。

所有被隔离的技术异常均通过标准 Python logger 记录堆栈，不会被当作正常的零值数据。
三个公开分析方法没有共享可变状态，因此一个请求的失败不会污染其他分析请求。

RevisionBuilder 或 Clock 无法工作时不降级：缺失稳定截点或 revision 身份会破坏结果
可追溯性，应由上层统一错误体系处理。

## 9. 参数校验

Service 校验：

- ID 必须为非布尔正整数；
- Action page 必须大于等于1；
- page size 必须为1–100；
- Benchmark 去重后必须包含2–20个 Drama ID；
- `analysis_as_of` 必须为带时区 datetime。

违反约束时抛出现有 `ValidationException`。指标数学边界继续由 Rule Component 负责。

## 10. 事务与依赖边界

Service 不包含：

- `commit`、`rollback`、`flush`；
- SQLAlchemy、Session、ORM Model 或 Repository 查询；
- 业务结果写入或 OperationLog；
- 其他业务 Service 调用；
- LLM、网络调用或非确定性业务规则。

## 11. 测试记录

### 11.1 Service 定向测试

```text
python -m pytest -q tests/test_operation_analytics_service.py

13 passed
```

覆盖：

- 三条完整编排流程；
- Clock 单次冻结和显式 as-of 复用；
- 稳定 analysis revision；
- Provider/Rule 异常隔离；
- Benchmark 单成员隔离；
- Availability 保留与聚合；
- 参数校验；
- ORM、Session、事务和业务 Service 依赖边界。

### 11.2 Phase 8 回归测试

```text
python -m pytest -q \
  tests/test_operation_analytics_service.py \
  tests/test_operation_analytics_repository.py \
  tests/test_operation_analytics_providers.py \
  tests/test_operation_analytics_rules.py \
  tests/test_operation_analytics_contracts.py

51 passed
```

### 11.3 全量测试说明

全量 `pytest -q` 使用工作区内独立 `--basetemp` 执行。本阶段没有新增失败；测试仍保留
6项既有 Phase 7 路由发现、源码边界和测试路径失败。本阶段未修改这些范围外文件。
