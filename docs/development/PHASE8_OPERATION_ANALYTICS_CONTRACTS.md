# Phase 8 Operation Analytics Contracts

## 1. Contracts 定位

`backend/services/operation_analytics/contracts.py` 定义 Phase 8 Read Model 内部使用的 Enum、不可变 DTO 和 Value Object。该模块只表达数据结构和结构不变量，不读取数据、不执行分析公式、不管理事务。

Contracts 不依赖 SQLAlchemy、ORM、Repository、Session、FastAPI 或数据库。

## 2. Availability 协议

Availability 采用状态与原因分离的两层协议：

- `AvailabilityStatus`：`AVAILABLE`、`PARTIAL`、`INSUFFICIENT`、`NOT_AVAILABLE`；
- `AvailabilityReason`：包含 `NOT_CALCULATED`、`INSUFFICIENT_HISTORY`、窗口不足、指标缺失、不可比较、零基线、重叠行动、版本混合等固定原因。

`AVAILABLE` 不允许携带原因；其他状态必须至少携带一个原因。真实零值可以在 AVAILABLE 状态下保留为 0，缺失数值使用 `None` 并同时返回明确 Availability，不能用 0 伪造缺失数据。

## 3. Enum

- `AvailabilityStatus`
- `AvailabilityReason`
- `LifecycleStage`
- `MetricDirection`
- `OperationMetricType`
- `BenchmarkMetricType`

生命周期固定为 `LAUNCH`、`GROWTH`、`STABLE`、`DECLINE`、`ARCHIVED`。Action Effect 指标支持播放量、互动率、增长率和异常数量；Benchmark 指标采用已冻结的五项统计类型。

## 4. 通用 DTO

- `AnalysisAvailability`：业务可用状态与原因；
- `AnalysisWindow`：包含首尾日期和闭区间日数，不包含指标计算；
- `DailyCumulativePoint`：Provider 向纯规则传递的版本化累计日点；
- `AnalysisVersionInfo`：规则、来源版本、revision 与 as-of；
- `AnalysisRevisionInput`：后续 RevisionBuilder 的不可变输入。

时间字段要求时区感知。ID 必须为正整数。所有 DTO 使用 frozen/slots dataclass。

## 5. Action Effect DTO

- `OperationEffectivenessInput`
- `MetricChange`
- `OperationEffectivenessResult`

结果包含 action/drama identity、完成时间锚点、前后窗口、指标变化、Availability、重叠 Action、版本、revision、as-of 和固定非因果免责声明。

V1 不支持结构化 Action Type，因此 `action_type` 只能为 `None`。Contracts 不包含 success、failure、causal result、contribution 或 recommendation 字段。

## 6. Lifecycle DTO

- `LifecycleInput`
- `LifecycleEvidence`
- `LifecycleResult`

结果包含阶段、规则版本、证据、evaluation as-of、Availability 和 revision。AVAILABLE 必须有阶段；历史不足时阶段为 `None` 并由 Availability 表达原因。Contracts 不包含预测概率。

## 7. Benchmark DTO

- `ComparisonScope`
- `BenchmarkMemberInput`
- `BenchmarkInput`
- `BenchmarkMetric`
- `BenchmarkMemberResult`
- `BenchmarkResult`

比较范围限制为同一平台、2–20 个唯一 Drama。结果表达成员指标和组统计，不包含 ranking、winner、best drama、recommendation 或 value score。

## 8. 版本常量

- `Action Effect Analysis V1.0`
- `Lifecycle Rules V1.0`
- `Benchmark Comparison V1.0`

Contracts 只携带版本，不实现版本对应的公式。

## 9. 禁止边界

本阶段未实现：

- ActionEffectCalculator；
- LifecycleClassifier；
- BenchmarkCalculator；
- AnalysisRevisionBuilder；
- Repository、Provider、Service；
- API、Router、Frontend；
- Database、Migration、ORM。

## 10. 测试记录

Contracts 测试覆盖闭合 Enum、Availability 组合、窗口边界、DTO 构造、禁止字段、真实 0/缺失语义、不可变性和依赖隔离。

执行：

```text
backend/.venv/Scripts/python.exe -m pytest tests/test_operation_analytics_contracts.py
```

结果：`8 passed in 0.83s`。
