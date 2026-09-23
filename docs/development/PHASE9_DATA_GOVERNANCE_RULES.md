# Phase 9 Data Governance Quality Rules

## 1. Rule Components 定位

Phase 9.2 在已冻结 Contracts 之上实现三个确定性质量规则：

- `FreshnessRule`；
- `CompletenessRule`；
- `ConsistencyRule`。

数据流固定为：

```text
Input DTO → Rule.evaluate() → Result DTO
```

Rule 只执行纯判断，不读取数据库、不访问 ORM、不调用 Repository、Provider、Service 或 API，不修改任何数据，也不进行自动修复。

## 2. 文件结构

```text
backend/services/data_governance/rules/
├── __init__.py
├── freshness.py
├── completeness.py
└── consistency.py
```

Rule 仅从 `services.data_governance.rules` 导出。Phase 9.1 顶层 Contracts 包导出保持不变，没有提前引入 Repository 或 Service。

## 3. FreshnessRule

### 3.1 输入与输出

输入：`FreshnessRuleInput`。

输出：`FreshnessResult`。

Rule 使用调用方提供的 `latest_timestamp`、`current_timestamp`、24 小时 warning threshold 和 72 小时 failure threshold，不读取当前系统时间。

### 3.2 判断规则

| 条件 | QualityStatus | Availability |
| --- | --- | --- |
| `0 <= delay <= 24h` | HEALTHY | AVAILABLE |
| `24h < delay <= 72h` | WARNING | AVAILABLE |
| `delay > 72h` | FAILED | AVAILABLE |
| 无 latest timestamp | NOT_AVAILABLE | NOT_AVAILABLE / NO_DATA |
| latest timestamp 晚于 cutoff | FAILED | AVAILABLE |

边界为闭区间：正好 24 小时仍为 HEALTHY，正好 72 小时仍为 WARNING。

### 3.3 Evidence

非 HEALTHY 结果生成一项 Evidence：

- `NO_VISIBLE_DATA`；
- `FUTURE_TIMESTAMP`；
- `DATA_DELAYED`；
- `DATA_STALE`。

Evidence 只保存 ISO timestamp、delay seconds 和阈值，不保存 Snapshot 或业务对象。

## 4. CompletenessRule

### 4.1 输入与输出

输入：`CompletenessRuleInput`。

输出：`CompletenessResult`。

检查范围：

1. expected fields 与 available fields；
2. metric coverage；
3. expected dates 与 available dates；
4. platform relationship；
5. required play_count availability。

### 4.2 Coverage ratio

每个字段、metric、日期、平台关系和 play_count 检查各占一个布尔检查单元：

```text
coverage_ratio = passed_check_count / total_check_count
```

使用 Decimal 输出。真实 0 与缺失保持不同：全部检查失败时 ratio 为 0；没有任何字段、metric 或日期范围时 ratio 为 None，并返回 NOT_AVAILABLE / NO_DATA。

### 4.3 状态规则

- 全部通过：HEALTHY；
- 非关键字段、非必要 metric 或日期部分缺失：WARNING；
- `drama_id`、`drama_code`、`drama_name`、`status` 缺失：FAILED；
- 平台关系缺失：FAILED；
- play_count 不可用：FAILED；
- 无可评估范围：NOT_AVAILABLE。

缺失项使用稳定顺序并去重。Rule 不补字段、不补日期、不插值、不把缺失变成 0。

### 4.4 Evidence

按检查类别生成最小 Evidence：

- `MISSING_REQUIRED_FIELDS`；
- `INCOMPLETE_METRIC_COVERAGE`；
- `INCOMPLETE_TIME_SERIES`；
- `MISSING_PLATFORM_RELATIONSHIP`；
- `PLAY_COUNT_UNAVAILABLE`；
- `NO_COMPLETENESS_SCOPE`。

## 5. ConsistencyRule

### 5.1 输入与输出

输入：`ConsistencyRuleInput`，包含已加载的 relationship checks、revision checks 和固定 `as_of_timestamp`。

输出：`ConsistencyResult`。

Repository/Provider 将来负责准备事实；Rule 不解析数据库引用，也不修改 Revision。

### 5.2 状态规则

- 所有检查 consistent=True：HEALTHY / AVAILABLE；
- relationship check 为 False：WARNING / AVAILABLE；
- revision check 为 False：FAILED / AVAILABLE；
- check code 表示 AS_OF 冲突且为 False：FAILED / AVAILABLE；
- weak reference 无法解析（consistent=None）：WARNING / PARTIAL / UNRESOLVED_RELATION；
- 无任何检查：NOT_AVAILABLE / NO_DATA。

若同一输入同时包含 unresolved 和明确 revision/as-of failure，QualityStatus 保留 FAILED，Availability 保留 PARTIAL，分别表达结论严重度和输入完整度。

### 5.3 Evidence

每个 False 或 None check 生成一项 Evidence。无法解析的 check code 增加 `_UNRESOLVED` 后缀，不猜测目标表。`issue_count` 始终等于 Evidence 数量。

## 6. Rule 版本策略

三个 Rule 均公开只读类属性 `rule_set_version`：

- Freshness：`Freshness Rules V1.0`；
- Completeness：`Completeness Rules V1.0`；
- Consistency：`Consistency Rules V1.0`。

`evaluate()` 将该值写入 Result DTO 的 `rule_version`。本阶段不实现版本注册、动态选择或数据库持久化。阈值和判断规则发生变化时必须提升版本，不能在相同版本下静默改变语义。

## 7. 确定性与禁止边界

实现满足：

- 相同 Input DTO 产生相同 Result DTO；
- 不使用 random、当前时间、网络或外部服务；
- 不导入 SQLAlchemy、ORM、Repository、Provider、Service、Router；
- 不调用 commit、rollback、flush、query 或 execute；
- 不写数据库；
- 不自动刷新、补数、修复关系或 Revision；
- 不生成评分、推荐或新的业务事实。

## 8. 测试与验证

Rule 专项测试覆盖：

- Freshness 正常、24h/72h 边界、超阈值、无时间和未来时间；
- Completeness 全量、部分缺失、关键缺失、空范围、0/1 coverage；
- Consistency 全部一致、关联问题、Revision 冲突、as-of 冲突、弱引用未解析和空范围；
- 三个 Rule 的版本字段；
- 相同输入结果一致；
- AST 依赖和事务写入边界。

执行：

```text
backend/.venv/Scripts/python.exe -m pytest -q backend/tests/test_data_governance_rules.py
backend/.venv/Scripts/python.exe -m pytest -q \
  backend/tests/test_data_governance_rules.py \
  backend/tests/test_data_governance_contracts.py
backend/.venv/Scripts/python.exe -m compileall -q \
  backend/services/data_governance/rules \
  backend/tests/test_data_governance_rules.py
```

结果：

- Rule 专项：17 passed；
- Contracts + Rules 回归：30 passed；
- Python compileall：passed。

本阶段未实现 Repository、Providers、Service、API 或 Frontend。
