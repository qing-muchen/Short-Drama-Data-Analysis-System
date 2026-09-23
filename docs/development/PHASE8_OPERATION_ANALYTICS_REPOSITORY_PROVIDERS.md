# Phase 8 Operation Analytics Repository + Providers

## 1. 阶段定位

本阶段连接现有数据表与 Phase 8 规则输入，形成只读链路：

```text
Existing Database Tables
        ↓
OperationAnalyticsRepository
        ↓
Operation Effectiveness / Lifecycle / Benchmark Providers
        ↓
Phase 8 Contracts Input DTO
```

本阶段不实现 Service、API、Frontend，也不保存分析结果。冻结后的分层由后续
`OperationAnalyticsService` 分别调用 Provider 和 Rule Component；Provider 不直接
执行规则，避免将数据准备与确定性计算混合。

## 2. Repository 职责

`OperationAnalyticsRepository` 是独立的只读 Repository，不继承含写操作的通用
`BaseRepository`。它仅持有调用方注入的 `Session` 并执行 `SELECT`。

公开查询包括：

- `list_completed_actions`：分页读取截至分析时间已完成的单剧行动；完成时间来自
  `operation_action_history` 的首个 `COMPLETED` 状态事件，而不是当前时间或行动更新时间。
- `list_completed_actions_in_range`：批量读取指定短剧、时间范围内的完成行动，用于
  识别分析窗口中的重叠行动。
- `list_drama_records`：读取生命周期和同平台 Benchmark 所需的最小 Drama 投影。
- `list_metric_revisions`：读取时间窗口内、在分析截点可见的指标 revision。
- `list_anomalies`：按短剧、时间窗口和分析截点读取异常 ID 与算法版本。

Repository 返回冻结 dataclass 投影，不向 Provider 暴露 ORM Model。Repository 不调用
Calculator 或 Service，也不执行 `commit`、`rollback`、`flush` 或创建 Session。

## 3. `analysis_as_of` 与 revision 策略

### 3.1 指标 revision

每个 `drama_metric_snapshots.snapshot_id` 按以下规则选择历史 revision：

1. 只考虑 `changed_at <= analysis_as_of` 的 revision；
2. 在可见 revision 中选择最大 `version_no`；
3. 如果选中的历史最新 revision 为 `VOID`，该 observation slot 不参与分析；
4. 查询同时要求 `snapshot_time <= analysis_as_of`；
5. 不使用 `current_revision_id`，避免当前 revision 污染历史分析。

该策略保留历史截点语义，不会以当前最新 revision 覆盖过去结果。

### 3.2 Action 与 Anomaly

- Action 的完成锚点必须来自 `operation_action_history.created_at <= analysis_as_of`。
- Anomaly 同时受业务窗口和 `DataAnomalyRecord.analysis_as_of <= analysis_as_of` 约束。

### 3.3 非版本化主数据

`dramas` 与 `drama_platforms` 当前没有历史 revision 表。为避免读取在分析截点之后修改的
当前行，V1 采用保守策略：仅接收 `created_at <= analysis_as_of` 且
`updated_at <= analysis_as_of` 的行。被后续修改而无法可靠还原历史状态的记录不会用于
历史生命周期输入。

## 4. DTO 映射

Provider 将 Repository 投影转换为 `contracts.py` 中已经冻结的 DTO：

- 指标快照转换为 `DailyCumulativePoint`；
- 同一短剧、平台、业务日期存在多个 observation slot 时，选择该业务日最后一个
  `snapshot_time`，并以 `snapshot_id` 作为稳定 tie-breaker；
- MySQL 返回的无时区 UTC 时间按 UTC 解释，再按 `Asia/Shanghai` 转换为业务日期；
- Provider 不返回 ORM，不计算指标变化、生命周期阶段或 Benchmark 统计值。

## 5. OperationEffectivenessProvider

`OperationEffectivenessProvider.get_inputs`：

- 读取已完成行动，使用完成事件时间作为 `T0`；
- Before Window 固定为 `T0` 业务日前 7 个完整日；
- After Window 固定为 `T0` 业务日后 7 个完整日；
- 批量读取所有分页行动所需的指标、异常和重叠行动，避免逐指标查询；
- 为每个可分析的单剧行动构造 `OperationEffectivenessInput`；
- 返回不可变 input page，保留 Repository 的 `page`、`page_size` 和 `total`；
- 保留异常算法版本和重叠行动 ID；
- 不计算 before/after 差异，也不判断行动是否有效或存在因果关系。

全局行动的 `drama_id` 为空，超出 Phase 8 V1 单剧效果分析范围，因此不会构造成违反
Contracts 的输入。

## 6. LifecycleInputProvider

`LifecycleInputProvider.get_input`：

- 读取 Drama 的可证明历史状态和发布时间；
- 读取 `analysis_as_of` 前一个完整业务日结束的连续 15 个累计日点；
- 优先使用平台 `online_at`，缺失时使用 `premiere_date` 的上海业务日零点；
- 构造 `LifecycleInput`，不判断 `LAUNCH/GROWTH/STABLE/DECLINE/ARCHIVED`。

Drama 不存在或其历史状态无法在截点可靠读取时返回 `None`，由后续 Service 负责对外
组装 Availability。

## 7. BenchmarkProvider

`BenchmarkProvider.get_input`：

- 要求显式提供同一平台的 2–20 个 Drama ID；
- 固定读取 `analysis_as_of` 前一个完整业务日结束的滚动 30 日窗口；
- 为累计差分额外读取窗口前一个基准日，共 31 个业务日点；
- 批量读取指标和异常记录，构造 `BenchmarkInput` 与 `BenchmarkMemberInput`；
- 数据缺失的成员使用 `INSUFFICIENT / INSUFFICIENT_HISTORY`，不以零替代缺失；
- `lifecycle_result` 保持为空，后续 Service 可独立调用 Lifecycle Rule 后再组装；
- 不计算平均值、中位数、排名或推荐。

## 8. 架构边界

本阶段明确禁止并通过源码边界测试检查：

- Provider 调用 Score、Prediction、Anomaly、Operation Action、Drama Profile Service；
- Provider 导入 SQLAlchemy、Session 或 ORM Model；
- Provider 执行 SQL 或事务操作；
- Repository 执行分析规则或写操作；
- 任何组件保存 Phase 8 分析结果。

## 9. 测试记录

执行环境：`backend/.venv`，工作目录为 `backend`。

### 9.1 本阶段定向测试

```text
python -m pytest -q \
  tests/test_operation_analytics_repository.py \
  tests/test_operation_analytics_providers.py

14 passed
```

覆盖：

- as-of revision 子查询与 `VOID` 处理；
- 时间窗口和分析截点过滤；
- Action 完成历史锚点；
- 空数据短路；
- Action Effect、Lifecycle、Benchmark DTO 映射；
- Availability 缺失语义；
- Provider/Repository 分层和只读边界。

### 9.2 Phase 8 回归

```text
python -m pytest -q \
  tests/test_operation_analytics_repository.py \
  tests/test_operation_analytics_providers.py \
  tests/test_operation_analytics_rules.py \
  tests/test_operation_analytics_contracts.py

38 passed
```

### 9.3 全量测试说明

全量 `pytest -q` 使用工作区内独立 `--basetemp` 执行，但未全绿。共发现 6 项失败，
均来自本阶段范围外的既有 Phase 7 路由发现、源码边界与测试路径问题。本阶段新增的
Repository/Provider 测试均通过，且未修改上述无关模块。
