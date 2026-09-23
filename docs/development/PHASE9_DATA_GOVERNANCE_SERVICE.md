# Phase 9 Data Governance Service

## 1. Service 定位

`DataGovernanceService` 是 Phase 9 的只读应用编排层。它把三个 Provider 准备的事实输入交给对应的确定性 Rule，并把结果组装成统一的 `DataGovernanceResponse`。

该层不查询 ORM、不执行 SQL、不管理 Session，也不写入数据库。它不会调用 Phase 2、Phase 6、Phase 7、Phase 8 或其他业务 Service，不执行质量计算、自动修复、推荐或 AI 推断。

依赖方向固定为：

```text
DataGovernanceService
    ├── FreshnessProvider  ──> FreshnessRule
    ├── CompletenessProvider ──> CompletenessRule
    └── ConsistencyProvider ──> ConsistencyRule
```

Provider 和 Rule 均通过构造器注入。Service 不自行创建 Repository、Provider 或 Rule。

## 2. 对外方法

- `get_overview(analysis_as_of=None)`：执行三个质量维度并返回 SYSTEM scope 的完整治理响应。
- `get_freshness(analysis_as_of=None)`：执行数据新鲜度链路。
- `get_completeness(analysis_as_of=None)`：执行数据完整性链路。
- `get_consistency(analysis_as_of=None)`：执行数据一致性链路。

所有方法均为只读操作。

## 3. analysis_as_of 策略

Service 是分析截点的唯一冻结边界：

- 调用方未传入截点时，Service 对注入的 `Clock` 调用一次 `now()`。
- 调用方显式传入截点时，不读取 Clock。
- 截点必须是 timezone-aware `datetime`；否则抛出 `ValidationException`。
- 合法截点统一转换为 UTC。
- 一次 `get_overview` 请求中的三个 Provider、三个 Rule 结果和最终 Response 使用同一个截点。
- Provider 不生成当前时间，Rule 不读取当前时间。

`SystemClock` 仅提供默认 UTC 时间实现；依赖组装层可注入它，单元测试使用固定 Clock。

## 4. 三条编排流程

### 4.1 Freshness

```text
analysis_as_of
  -> FreshnessProvider.get_rule_inputs
  -> FreshnessRule.evaluate（每个输入一次）
  -> FreshnessResult 聚合
```

Service 不计算数据延迟。多个 Rule 结果聚合时保留最严重的质量状态、最严格的可用性和 Rule 已计算出的最大延迟值。

### 4.2 Completeness

```text
analysis_as_of
  -> CompletenessProvider.get_rule_inputs
  -> CompletenessRule.evaluate（每个输入一次）
  -> CompletenessResult 聚合
```

Service 不计算覆盖率。它仅从 Rule 输出中选择最低的已计算覆盖率，并稳定合并缺失项和 Evidence。

### 4.3 Consistency

```text
analysis_as_of
  -> ConsistencyProvider.get_rule_input
  -> ConsistencyRule.evaluate
  -> ConsistencyResult
```

Service 校验 Provider 使用了统一截点，并为最终 Result 设置同一 `analysis_as_of`。Overview 中 Evidence 按响应上限裁剪；`issue_count` 与返回的 Evidence 数量保持一致。

Provider 返回空集合时，Service 仍构造显式的空范围 Rule Input 并调用 Rule，由 Rule 产生 `NOT_AVAILABLE` 结果；不会用 `None` 表示业务状态。

## 5. Availability 聚合

模块内和 Overview 采用同一确定性策略：

- 全部 `AVAILABLE`：返回 `AVAILABLE`。
- 全部 `INSUFFICIENT`：返回 `INSUFFICIENT`。
- 全部 `NOT_AVAILABLE`：返回 `NOT_AVAILABLE`。
- 可用、部分可用、历史不足或不可用状态混合：返回 `PARTIAL`。

原因按照 `AvailabilityReason` 枚举顺序去重，保证相同输入产生稳定输出。Provider 或 Rule 异常使用 `EVALUATION_FAILED`，不使用空值隐藏失败。

质量状态聚合顺序为 `FAILED`、`WARNING`、`HEALTHY`。只有没有任何可评估结果时才返回 `NOT_AVAILABLE`。Service 只聚合 Rule 已生成的状态，不重新执行质量判断。

## 6. 异常隔离与日志

每个质量模块拥有独立异常边界：

- Provider 或 Rule 异常通过模块级 Logger 记录异常堆栈。
- 失败模块返回带 `EVALUATION_FAILED` Evidence 的显式 `NOT_AVAILABLE` Result。
- 另外两个模块继续执行。
- 单个或多个模块失败但仍有成功模块时，Overview 为 `PARTIAL`。
- 三个模块全部失败时，Overview 为 `NOT_AVAILABLE`。

异常隔离只应用于模块执行。无时区的 `analysis_as_of` 属于请求参数错误，在调用任何 Provider 前直接拒绝。

## 7. 边界确认

Service 中不存在：

- SQLAlchemy、ORM Model、Repository 或 Session 依赖；
- `commit()`、`rollback()`、`flush()` 或数据写入；
- Phase 2 Data Quality、Explanation、Drama Profile、Operation Analytics 等业务 Service 调用；
- AI、自动化修复、推荐或新的业务事实。

## 8. 测试记录

专项测试覆盖：

- Clock 未显式传入截点时只读取一次；
- 显式截点不读取 Clock，并规范化为 UTC；
- 三个 Provider 和三个 Rule 使用同一截点且全部被调用；
- Freshness、Completeness、Consistency 独立查询链路；
- 全成功、单模块失败、多模块失败、全失败和历史不足 Availability；
- Provider 与 Rule 异常的日志记录和隔离；
- 空 Provider 结果仍经过 Rule；
- Service 源码无持久化及其他业务 Service 依赖。

验证命令：

```text
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_data_governance_service.py -q
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_data_governance_contracts.py backend/tests/test_data_governance_rules.py backend/tests/test_data_governance_repository.py backend/tests/test_data_governance_providers.py backend/tests/test_data_governance_service.py -q
backend/.venv/Scripts/python.exe -m compileall backend/services/data_governance backend/tests/test_data_governance_service.py
```

验证结果：专项测试和 Phase 9.1–9.4 回归测试全部通过；编译检查通过。
