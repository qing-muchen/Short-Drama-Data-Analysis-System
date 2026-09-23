# Phase 10 Reporting Repository + Providers

## 1. 阶段定位

本阶段实现 Analysis Reporting & Export Center 的只读数据读取与映射层，将已有持久化事实转换为 Phase 10 Schema Registry 约束下的 immutable `ReportRow`。

实现链路：

```text
Existing Tables
    ↓
ReportingRepository
    ↓
Immutable Projection
    ↓
Report Providers
    ↓
Schema-bound ReportRow
```

本阶段不包含 ReportingService、API、Frontend、Serializer 调用或文件导出；不创建 Migration，不修改 ORM，不写数据库，也不产生新指标、新评分、新预测、推荐或 AI 内容。

## 2. 文件结构

- `backend/repositories/reporting_repository.py`：六类报告的只读查询与 immutable projection；
- `backend/services/reporting/providers/report_providers.py`：projection 到 `ReportRow` 的显式映射；
- `backend/services/reporting/providers/__init__.py`：Provider 公共导出；
- `backend/tests/test_reporting_repository.py`：Repository 查询、截点、版本、NULL 与边界测试；
- `backend/tests/test_reporting_providers.py`：六类 Provider、Registry 和架构边界测试。

## 3. ReportingRepository

`ReportingRepository` 由调用方注入 SQLAlchemy `Session`，但不创建 Session、不管理事务。它为每种 Report Type 提供成对的 `count_*` 与 `list_*` 方法，并让 Count 与 Rows 复用相同 statement builder，避免筛选口径漂移。

Repository 只负责：

- 构造只读查询；
- 应用允许的结构化 Filter；
- 应用 `analysis_as_of` 截点；
- 保留已持久化版本；
- 使用稳定排序与唯一 ID tie-breaker；
- 分页读取；
- 返回 frozen、slots projection。

Repository 不负责格式化、报告状态判断、业务计算、序列化或事务控制。它不调用 Rule、Policy、Serializer、Provider 或 Service，不执行 `commit`、`rollback`、`flush`。

### 3.1 Immutable Projections

实现六种 frozen、slots projection：

1. `DramaCatalogProjection`；
2. `ScoreResultsProjection`；
3. `DataQualityResultsProjection`；
4. `PredictionResultsProjection`；
5. `AnomalyRecordsProjection`；
6. `OperationActionsProjection`。

Projection 仅包含 Registry Schema 所声明的报告字段，不暴露 ORM Model、SQLAlchemy Row 或 Session。

## 4. 六类报告查询

### 4.1 DRAMA_CATALOG

读取当前 Drama 主数据，并以相关子查询聚合有效平台与标签展示值。支持 `drama_id`、`platform_id`、`status`、`tag_id` Filter，按 `drama_id` 稳定排序。

该来源没有完整 temporal history，属于 `CURRENT_STATE_AT_REQUEST`；`analysis_as_of` 仅作为请求快照说明，不伪装历史重建能力。

### 4.2 SCORE_RESULTS

读取已保存的 Score 结果，应用 `analysis_as_of <= cutoff`，支持 Drama、算法版本与时间范围 Filter。保留 cutoff 前全部持久化 identity/version，禁止重新评分或以当前版本覆盖历史结果。

稳定排序为 `analysis_as_of, score_date, score_id`。

### 4.3 DATA_QUALITY_RESULTS

读取 Phase 2 已保存的 Data Quality Score，不调用 Phase 9 Data Governance。应用 `analysis_as_of <= cutoff`，支持算法版本、规则集版本与时间范围 Filter；每个持久化唯一 identity 保持独立行。

稳定排序为 `analysis_as_of, score_date, quality_score_id`。

### 4.4 PREDICTION_RESULTS

读取已保存 Prediction 结果，应用 `analysis_as_of <= cutoff`，保留不同 algorithm version，禁止重新预测或补齐历史。

稳定排序为 `analysis_as_of, target_date, prediction_id`。

### 4.5 ANOMALY_RECORDS

读取 `detected_at <= cutoff` 的异常事实，支持 Drama、算法版本、严重度、当前状态与时间范围 Filter。异常状态是请求时当前值，因此属于 `CURRENT_STATE_AT_REQUEST`，不声称能够恢复历史状态。

稳定排序为 `detected_at, anomaly_id`。

### 4.6 OPERATION_ACTIONS

读取 `created_at <= cutoff` 的运营行动。Action 当前字段不做历史恢复；source/history count 仅统计 cutoff 前已存在的关联记录。支持 Drama、当前状态与时间范围 Filter。

稳定排序为 `created_at, action_id`。

## 5. Snapshot、as-of 与 Revision

Repository 接收 `ReportRequest` 内已经冻结的 timezone-aware `analysis_as_of`，统一转换为 UTC 数据库比较值。Repository 不读取系统当前时间，也不调用 `now()`。

V1 截点能力遵循冻结矩阵：

| Report | Snapshot 语义 | 截点/版本规则 |
| --- | --- | --- |
| Drama Catalog | Current State | 当前主数据，不承诺历史恢复 |
| Score Results | As-of Reconstructed | `analysis_as_of <= cutoff`，保留全部持久化版本 |
| Data Quality Results | As-of Reconstructed | `analysis_as_of <= cutoff`，不跨 algorithm/rule set/hash 折叠 |
| Prediction Results | As-of Reconstructed | `analysis_as_of <= cutoff`，保留不同算法版本 |
| Anomaly Records | Current State | `detected_at <= cutoff`，status 为当前值 |
| Operation Actions | Current State | `created_at <= cutoff`，Action 字段为当前值 |

“保留版本”表示报告明细忠实呈现 cutoff 前的持久化事实；Repository 不替用户挑选“最佳”版本，也不以最新版本覆盖历史记录。

## 6. Report Providers

实现六个显式 Provider：

- `DramaCatalogReportProvider`；
- `ScoreResultsReportProvider`；
- `DataQualityResultsReportProvider`；
- `PredictionResultsReportProvider`；
- `AnomalyRecordsReportProvider`；
- `OperationActionsReportProvider`。

每个 Provider：

- 绑定且只服务一个 `ReportType`；
- 将 Count 直接委托给对应 Repository 方法；
- 将分页 projection 映射为 immutable `ReportRow`；
- 不执行 SQL；
- 不访问 ORM；
- 不调用 Service、API、Policy 或 Serializer；
- 不产生业务计算或写操作。

`ReportProviderRegistry` 使用只读 `MappingProxyType` 进行显式注册。重复 Report Type 会被拒绝；`create_default_provider_registry()` 固定组装且仅组装 V1 六类 Provider，不使用动态扫描。

## 7. Schema Registry映射

Provider 构造时从 `ReportSchemaRegistry` 获取其固定 `ReportSchema`。生成每一行时：

1. 按 `schema.columns` 原始顺序读取列名；
2. 从 projection 读取完全同名字段；
3. 按相同顺序构造 `ReportRow`；
4. 由 `ReportRow` 契约验证标量类型与 aware datetime。

Provider 不允许自行添加、删除、重排或发现字段。Schema 变更必须先修改并版本化 Registry，而不是在 Provider 中隐式兼容。

数据库返回的 naive datetime 被解释为数据库 UTC 并转换为 timezone-aware UTC；已有 aware datetime 规范化为 UTC。该处理只解决传输类型契约，不改变业务时间含义。

## 8. NULL语义

Repository projection 与 Provider 均原样保留数据库 `NULL`：

- 不转换为 `0`；
- 不转换为 `false`；
- 不转换为空字符串；
- 不生成字符串 `NULL`。

只有 Registry 中声明 `nullable=True` 的字段允许出现 `None`。CSV/XLSX 的最终 NULL 表示仍由 Phase 10.2 Serializer 按冻结策略处理。

## 9. 架构边界

自动化边界测试检查：

- Repository 不导入 Rule、Service、Provider、API 或 Serializer；
- Provider 不导入 ORM Model、Session、Service、API 或 Serializer；
- 两层均不调用 `commit`、`rollback`、`flush`；
- Provider 返回 `ReportRow` 而非 `dict` 或 ORM；
- Repository 返回不可变 projection；
- 不新增 Migration、表或 ORM 变更。

## 10. 测试记录

执行命令：

```text
python -m pytest tests/test_reporting_repository.py tests/test_reporting_providers.py -q
```

结果：`19 passed`。

Phase 10.1–10.3 回归：

```text
python -m pytest tests/test_reporting_contracts.py tests/test_reporting_schema_registry.py tests/test_reporting_policies.py tests/test_reporting_serializers.py tests/test_reporting_repository.py tests/test_reporting_providers.py -q -W error::pytest.PytestUnraisableExceptionWarning
```

结果：`68 passed`。

编译检查：

```text
python -m compileall -q repositories/reporting_repository.py services/reporting/providers tests/test_reporting_repository.py tests/test_reporting_providers.py
```

结果：通过。

## 11. 下一阶段边界

下一阶段可进入 Phase 10.4 ReportingService Implementation，由 Service 注入 Schema Registry、Provider Registry、Policy、Serializer 与 Clock，负责编排 Catalog、Preview 和 Export。未经授权不得实现 API 或 Frontend，Service 仍不得访问 ORM、SQL 或写事务。
