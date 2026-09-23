# Phase 9 Data Governance Repository and Providers

## 1. 层级定位

Phase 9.3 建立 Data Governance 的只读数据准备链：

```text
Existing Tables
      ↓
DataGovernanceRepository
      ↓
Freshness / Completeness / Consistency Providers
      ↓
Phase 9 Rule Input DTO
```

Repository 只查询并返回 frozen projection；Provider 只做 projection 到 Contracts Input DTO 的映射。本阶段不调用 Quality Rule，不实现 Service、API 或 Frontend，也不修改 Database、Migration 或 ORM。

## 2. DataGovernanceRepository

文件：`backend/repositories/data_governance_repository.py`。

Repository 接收外部 Session，但不创建 Session，不拥有事务，不调用 commit、rollback 或 flush。所有公开查询只执行 SELECT。

### 2.1 Immutable projections

定义以下 `@dataclass(frozen=True, slots=True)` 投影：

- `FreshnessReadRecord`；
- `CompletenessTargetRecord`；
- `MetricCoverageReadRecord`；
- `ActionSourceReadRecord`；
- `ActionStatusReadRecord`；
- `LineageReadRecord`；
- `RevisionReadRecord`。

Repository 不返回 ORM Model，也不生成 QualityStatus、Availability、coverage ratio 或 Evidence。

### 2.2 Freshness 查询

`list_freshness_records(analysis_as_of)`：

- 查找 SERIALIZING/COMPLETED Drama；
- 只包含 ONLINE drama-platform 和 ACTIVE Platform；
- 对每个 Snapshot observation slot 选择截点前最大 `version_no`；
- 最新 Revision 为 VOID 时排除该 slot，不回退旧 Revision；
- 对每个 feed 返回最新可见 `snapshot_time`；
- 使用 outer join 保留没有可见 Snapshot 的 feed，时间返回 None。

Repository 不计算 delay，也不判断 HEALTHY/WARNING/FAILED。

### 2.3 Completeness 查询

`list_completeness_targets(analysis_as_of)` 返回：

- Drama identity fields；
- 当前符合条件的 drama-platform identity；
- ACTIVE Platform identity；
- 无有效关系时保留 Drama 并返回空 relation projection。

`list_metric_coverage_records(...)` 返回七日窗口内：

- observation slot；
- 截点前最大 Revision；
- snapshot time；
- revision action/version；
- play_count；
- changed_at。

该查询同样在选中最大版本后过滤 VOID，不回退历史版本。Repository 不计算覆盖率、不补日期、不补零。

### 2.4 Consistency 查询

`list_action_source_records(analysis_as_of)`：

- 返回 ANOMALY / QUALITY / SCORE / MANUAL logical reference；
- 返回目标存在性事实；
- 不决定警告或失败等级。

`list_action_status_records(analysis_as_of)`：

- 返回 Action 当前状态；
- 返回截点前最新带 `new_status` 的 History event。

`list_lineage_records(analysis_as_of)`：

- 返回 Explanation target 存在性和 as-of 匹配事实；
- 对 SNAPSHOT / RULE / ANOMALY_EVIDENCE 返回 source 存在性和可见性；
- METRIC / PREDICTION_INPUT 返回不可解析事实，不猜测目标表。

`list_revision_records(analysis_as_of)`：

- 选择截点前最大 Revision；
- 返回 action、version、previous revision identity；
- 保留最新 VOID，供 ConsistencyRule 检查合法 Revision chain。

## 3. as-of 与 Revision 策略

所有版本化查询遵守：

```text
revision.changed_at <= analysis_as_of
```

并按每个 `snapshot_id` 选择最大 `version_no`。查询不读取 `current_revision_id`，避免当前状态污染历史截点。

不同用途的 VOID 语义：

- Freshness / Completeness：选择最大 Revision 后过滤 VOID，slot 不可见，不回退旧版本；
- Consistency：保留最大 VOID Revision，用于验证 action/version/previous chain。

Snapshot 时间和 lineage `analysis_as_of` 也受请求截点限制。SQL DATETIME 参数在 Repository 边界规范化为 UTC timezone-naive 值，以匹配当前 Schema；Provider 对外继续使用 timezone-aware UTC datetime。

非版本化 Drama、Platform、Action 等 mutable row 使用保守过滤：`created_at <= cutoff` 且 `updated_at <= cutoff`。无法证明历史状态的记录不会被声明为历史事实。

## 4. FreshnessProvider

文件：`backend/services/data_governance/providers.py`。

`FreshnessProvider.get_rule_inputs(analysis_as_of)`：

- 调用 `list_freshness_records`；
- 每个 feed 映射为一个 `FreshnessRuleInput`；
- `drama_platform_id` 作为 entity identity；
- 将数据库 naive UTC timestamp 转为 aware UTC；
- 保留 `latest_timestamp=None`，不转换为零延迟。

Provider 不计算 delay，不比较 24/72 小时阈值，不调用 FreshnessRule。

## 5. CompletenessProvider

`CompletenessProvider.get_rule_inputs(analysis_as_of)`：

- 获取 Drama/platform target projection；
- 以 `Asia/Shanghai` 为业务时区；
- 排除截点所在的未完成本地日期；
- 构造此前七个完整自然业务日；
- 批量读取所有有效 drama-platform 的 metric coverage；
- 将 snapshot UTC 时间映射到业务日期；
- 构造 fields、metric coverage、expected/available dates、relation 和 play_count 输入事实。

每个有效 drama-platform 返回一个 `CompletenessRuleInput`；没有有效关系的 Drama 仍返回 DRAMA-level Input，并显式标记 relation/play_count 不可用。

Provider 不计算 coverage ratio，不决定 HEALTHY/WARNING/FAILED，不插值、不补日期。

## 6. ConsistencyProvider

`ConsistencyProvider.get_rule_input(analysis_as_of)` 构造一个 SYSTEM-level `ConsistencyRuleInput`。

Relationship checks：

- Action source reference；
- Action current status 与最新 status event；
- Lineage target existence；
- Lineage target as-of；
- Lineage source existence；
- Lineage source as-of visibility。

Revision checks：

- version 1 必须为 INITIAL 且无 previous revision；
- version > 1 必须为 CORRECTION/VOID；
- previous revision 必须属于同一 snapshot；
- previous version 必须是当前 version - 1。

Provider 只将原始事实映射为 `consistent=True/False/None`；Quality Rule 决定 WARNING、FAILED 和 Availability。对于未冻结 identity 的弱引用，Provider 保留 None，不猜测目标表。

## 7. Provider 边界

Providers：

- 依赖 Repository Protocol 和 Phase 9 Contracts；
- 返回 `FreshnessRuleInput`、`CompletenessRuleInput`、`ConsistencyRuleInput`；
- 不导入 SQLAlchemy 或 ORM；
- 不调用 Rule、Service 或 API；
- 不执行 SQL；
- 不调用 commit、rollback 或 flush；
- 不返回 ORM Model。

## 8. 测试结果

### 8.1 Repository tests

覆盖：

- Freshness 最新可见时间与无数据 projection；
- Completeness field/relation projection；
- metric 时间窗口；
- as-of 最大 Revision；
- VOID 过滤且不读取 current revision；
- Action weak reference；
- Action status history；
- Lineage target/source/as-of；
- Revision chain 投影保留 VOID；
- frozen projection；
- read-only 和依赖边界。

SQL 测试使用 MySQL dialect 编译实际 SQLAlchemy statement，并验证 cutoff、max(version_no)、VOID 和时间窗口条件。

### 8.2 Provider tests

覆盖：

- Freshness projection 映射和 None 保留；
- Completeness 七个完整业务日、UTC/Asia-Shanghai 日期转换；
- 缺失 relation / metric 输入；
- Action、Lineage、Revision consistency mapping；
- unsupported weak reference 保留 None；
- 输出为 Contracts DTO；
- 无 Rule、Service、ORM 依赖。

### 8.3 Commands and results

```text
backend/.venv/Scripts/python.exe -m pytest -q \
  backend/tests/test_data_governance_repository.py \
  backend/tests/test_data_governance_providers.py
```

结果：`18 passed`。

```text
backend/.venv/Scripts/python.exe -m pytest -q \
  backend/tests/test_data_governance_contracts.py \
  backend/tests/test_data_governance_rules.py \
  backend/tests/test_data_governance_repository.py \
  backend/tests/test_data_governance_providers.py
```

Phase 9.1–9.3 回归结果：`48 passed`。

```text
backend/.venv/Scripts/python.exe -m compileall -q \
  backend/repositories/data_governance_repository.py \
  backend/services/data_governance/providers.py \
  backend/tests/test_data_governance_repository.py \
  backend/tests/test_data_governance_providers.py
```

结果：passed。

本阶段未实现 DataGovernanceService、API、Frontend，未修改 Database、Migration 或 ORM。
