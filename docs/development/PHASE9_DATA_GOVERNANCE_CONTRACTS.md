# Phase 9 Data Governance Contracts

## 1. Contracts 定位

Phase 9.1 建立 Data Governance / Quality Monitoring Layer 的纯数据协议。Contracts 只描述后续 Provider、Rule、Service 与 API adapter 之间交换的数据，不查询数据、不计算质量状态、不持久化结果。

实现文件：

- `backend/services/data_governance/contracts.py`；
- `backend/services/data_governance/__init__.py`。

所有 DTO 使用 `@dataclass(frozen=True, slots=True)`，所有集合使用 tuple 表达不可变输入。Contracts 不使用 Pydantic，也不包含 ORM Model。

## 2. Enum 协议

### 2.1 QualityStatus

- `HEALTHY`：已完成评估，未发现质量问题；
- `WARNING`：已完成或部分完成评估，存在警告；
- `FAILED`：已完成评估，发现明确质量失败；
- `NOT_AVAILABLE`：无法形成质量结论。

QualityStatus 表示评估结论，不等同于输入可用性。

### 2.2 AvailabilityStatus

- `AVAILABLE`：计划输入完整；
- `PARTIAL`：部分输入缺失；
- `INSUFFICIENT`：历史长度或样本不足；
- `NOT_AVAILABLE`：无法获得评估输入。

### 2.3 AvailabilityReason

V1 支持：

- `NO_DATA`；
- `MISSING_SOURCE`；
- `INSUFFICIENT_HISTORY`；
- `MISSING_REQUIRED_FIELD`；
- `INCOMPLETE_TIME_SERIES`；
- `UNRESOLVED_RELATION`；
- `REVISION_NOT_VISIBLE`；
- `UNSUPPORTED_SCOPE`；
- `EVALUATION_FAILED`；
- `NOT_AVAILABLE`。

`DataQualityAvailability` 强制：AVAILABLE 不携带 reason，其他状态至少携带一个 reason；reason 不得重复并按 Enum 顺序保存。

### 2.4 QualityIssueType

- `FRESHNESS`；
- `COMPLETENESS`；
- `CONSISTENCY`。

### 2.5 GovernanceScope

Phase 9 V1 只定义 `SYSTEM`。Contracts 不提供 USER、TEAM 或 CUSTOM scope。

## 3. DTO 结构

### 3.1 通用 DTO

`DataQualityAvailability`：

- status；
- reasons；
- message。

`EvidenceItem`：

- issue_type；
- check_code；
- entity_type；
- entity_id；
- observed_value；
- expected_condition；
- source_type；
- source_reference_ids；
- message。

Evidence 只允许 JSON-safe scalar 或 scalar tuple，不接受 dict、list、ORM 或完整业务对象。`entity_id=None` 仅允许用于 SYSTEM 汇总 Evidence。

### 3.2 Rule Input DTO

`FreshnessRuleInput`：

- entity identity；
- latest_timestamp；
- current_timestamp；
- 24 小时 threshold；
- 72 小时 failure_threshold。

允许 `latest_timestamp=None` 表示没有可见数据；Contracts 不把缺失转换为零延迟。

`CompletenessRuleInput`：

- expected_fields / available_fields；
- metric_coverage；
- entity identity；
- expected_dates / available_dates；
- platform relationship 与 play_count 可用事实。

DTO 保留缺失日期和真实零值语义，不补日期、不补零。

`ConsistencyCheckInput`：描述一项预加载的一致性事实。`consistent=None` 表示当前弱引用无法解析。

`ConsistencyRuleInput`：

- relationship_checks；
- revision_checks；
- as_of_timestamp。

Input DTO 只验证数据形状，不执行 HEALTHY/WARNING/FAILED 判断。

### 3.3 Result DTO

`FreshnessResult`：

- status；
- availability；
- delay_seconds；
- evidence；
- analysis_as_of；
- rule_version；
- summary。

`delay_seconds=0` 表示真实零延迟；`None` 表示无法计算。负数可保留未来时间事实，判断由后续 FreshnessRule 完成。

`CompletenessResult`：

- status；
- availability；
- coverage_ratio；
- missing_items；
- evidence；
- analysis_as_of；
- rule_version；
- summary。

coverage_ratio 使用 Decimal，范围为 0–1；`None` 表示不能计算。

`ConsistencyResult`：

- status；
- availability；
- issue_count；
- evidence；
- analysis_as_of；
- rule_version；
- summary。

issue_count 必须等于 Evidence 数量。所有非 HEALTHY Result 必须携带 Evidence；`NOT_AVAILABLE + AVAILABLE` 被拒绝。

`DataGovernanceResponse`：

- analysis_as_of；
- scope；
- availability；
- freshness；
- completeness；
- consistency；
- rule_set_version。

Response 强制 timezone-aware 截点和 `GovernanceScope.SYSTEM`。QualityStatus 与 Availability 保持正交，例如 `FAILED + AVAILABLE` 是合法状态。

## 4. 规则版本字段

Contracts 提供以下默认版本常量：

- `Freshness Rules V1.0`；
- `Completeness Rules V1.0`；
- `Consistency Rules V1.0`；
- `Governance Rule Set V1.0`。

本层只保存和传递版本，不选择、注册或管理规则版本。

## 5. 字段设计与边界校验

- 所有分析时间必须带时区；
- entity integer ID 必须为正数，string ID 不得为空；
- tuple 字段拒绝可变 list；
- field、metric 和 source ID 不得重复；
- 日期 tuple 必须去重并按升序排列；
- Availability reason 明确区分缺失、历史不足、未解析和评估失败；
- 不使用 `None` 或数值 0 代替 Availability；
- 不包含评分、自动修复、推荐或业务写入字段。

## 6. 依赖限制

`contracts.py` 只导入 Python 标准库：

- dataclasses；
- datetime；
- decimal；
- enum；
- typing。

明确禁止依赖：

- SQLAlchemy；
- ORM Model；
- Repository；
- Session / Database；
- Service；
- FastAPI / Schema / Router；
- Frontend。

包 `__init__.py` 只导出 Contracts，不提前导出 Rule、Provider 或 Service。

## 7. 测试结果

执行命令：

```text
backend/.venv/Scripts/python.exe -m pytest -q backend/tests/test_data_governance_contracts.py
```

结果：

```text
13 passed
```

覆盖：

- Enum 合法值和非法值；
- Availability 默认值与组合约束；
- frozen DTO；
- Evidence 最小结构与完整对象拦截；
- 三类 Rule Input 边界；
- Result 默认版本、真实零值和数值范围；
- 完整 SYSTEM Response；
- Contracts AST 依赖边界；
- 包导出不包含后续层。

本阶段未实现 Rules、Repository、Providers、Service、API 或 Frontend。
