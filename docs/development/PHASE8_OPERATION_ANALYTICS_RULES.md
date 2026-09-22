# Phase 8 Operation Analytics Rule Components

## 1. 定位

Rule Components 是 Phase 8 的确定性纯计算层。它们只接收 Contracts DTO、返回 Contracts DTO，不查询或保存数据，不访问 ORM、Repository、Session、API、网络、LLM 或外部模型。

相同输入必须产生相同输出。所有比率使用 `Decimal`，不读取当前时间。

## 2. 文件结构

```text
backend/services/operation_analytics/rules/
├── __init__.py
├── action_effect.py
├── lifecycle.py
├── benchmark.py
└── revision.py
```

## 3. ActionEffectCalculator

输入：`OperationEffectivenessInput`。输出：`OperationEffectivenessResult`。

冻结规则：

- T0 已由输入明确提供，Calculator 不读取创建时间、更新时间或当前时间；
- Before 为 T0 前 7 个完整业务日；
- After 为 T0 后 7 个完整业务日；
- 每个平台需要窗口开始日前一日基线及窗口内 7 个累计点；
- 累计值先按平台差分，再跨相同平台集合聚合；
- 不插值、不补 0；累计值回退返回无效序列。

计算四项指标：

- 播放增量变化；
- 互动率变化；
- 日均播放增量变化；
- 异常数量变化。

方向使用 `INCREASED`、`DECREASED`、`UNCHANGED`、`UNAVAILABLE`。结果只描述完成时间前后变化，不输出 success、effectiveness score、因果结果或推荐。

## 4. LifecycleClassifier

输入：`LifecycleInput`。输出：`LifecycleResult`。

规则版本：`Lifecycle Rules V1.0`。

优先级：

```text
ARCHIVED > LAUNCH > 输入有效性 > GROWTH/DECLINE/STABLE
```

- Drama status 为 INACTIVE：ARCHIVED；
- release time 后 0–14 个完整业务日：LAUNCH；
- 其他情况需要连续 15 个累计日点；
- 14 个日增量分为前后两个 7 日窗口；
- 变化率 `>= +10%`：GROWTH；
- 变化率 `<= -10%`：DECLINE；
- 其他：STABLE；
- 前窗为 0、后窗大于 0：GROWTH；
- 双零：STABLE。

release time 缺失/晚于 as-of、日期缺口和累计回退均不会被强行分类。组件不输出预测概率或置信度。

## 5. BenchmarkCalculator

输入：`BenchmarkInput`。输出：`BenchmarkResult`。

规则版本：`Benchmark Comparison V1.0`。

- 同一平台；
- 显式 2–20 个 Drama；
- 滚动 30 个完整自然业务日；
- 每个可比成员需要连续 31 个累计点；
- 至少两个可比成员才能形成组统计；
- 计算播放增量总和、日均增量、互动率、异常频率和生命周期状态；
- 数值指标提供组中位数；
- 缺失成员不补 0、不进入中位数。

组件不输出 rank、winner、best drama、recommendation 或价值判断。

## 6. AnalysisRevisionBuilder

输入：`AnalysisRevisionInput`。输出：`sha256:<hex>`。

Builder 对已冻结的 as-of、实体、参数、snapshot revision、来源版本和规则版本生成 canonical JSON SHA-256。它不创建 `analysis_as_of`、不选择 revision、不访问数据库、不保存结果。

## 7. Availability 与边界

- 数据完整：AVAILABLE；
- 可返回核心结果但可选指标缺失、行动重叠或版本混合：PARTIAL；
- 历史或窗口不足：INSUFFICIENT；
- 序列无效或范围不可比较：NOT_AVAILABLE。

真实零值保留为 0；缺失值为 `None` 并携带明确 Availability。

## 8. 测试记录

测试覆盖 Action 正常增长/下降/稳定、空窗口、日期边界、重叠行动；Lifecycle 五阶段、±10% 边界、历史缺口和累计回退；Benchmark 2/20 成员、不可比较组、30 日窗口和中位数；Revision 稳定性；以及无数据库、Repository、Service、Session 或网络依赖。

执行：

```text
backend/.venv/Scripts/python.exe -m pytest \
  tests/test_operation_analytics_rules.py \
  tests/test_operation_analytics_contracts.py
```

结果：`24 passed in 0.79s`。
