# Phase 10 ReportingService

## 1. Service定位

`ReportingService` 是 Analysis Reporting & Export Center 的只读应用编排层。它连接已冻结的 Contracts、Schema Registry、Policies 和 Report Providers，形成以下请求链路：

```text
Request
    ↓
Filter Validation
    ↓
Snapshot Resolution
    ↓
Provider Selection
    ↓
Schema-bound ReportRow
    ↓
ReportResponse / ReportExportPreparation
```

Service不访问ORM、SQL、Session或Repository，不管理事务，不调用已有业务Service，不生成新指标或业务事实，也不直接生成CSV/XLSX文件。

## 2. 依赖注入

`ReportingService`通过构造器注入：

- `ReportSchemaRegistry`：报告目录、列、格式和Snapshot语义；
- `ReportProviderRegistry`：六类报告Provider选择；
- `ReportFilterPolicy`：Filter allowlist、类型与默认值校验；
- `ExportLimitPolicy`：导出行数、确认和硬限制决策；
- `Clock`：未显式提供截点时生成一次UTC时间。

Service内部不创建上述依赖，也不创建任何数据库对象。

## 3. 公共接口

### 3.1 get_catalog

`get_catalog()`直接返回Schema Registry中显式注册且顺序稳定的六种`ReportSchema`：

1. `DRAMA_CATALOG`；
2. `SCORE_RESULTS`；
3. `DATA_QUALITY_RESULTS`；
4. `PREDICTION_RESULTS`；
5. `ANOMALY_RECORDS`；
6. `OPERATION_ACTIONS`。

Catalog不访问Provider或Clock，不动态发现字段，不暴露表名、ORM或SQL。

### 3.2 preview_report

Preview流程：

1. 校验`offset >= 0`以及`1 <= limit <= 100`；
2. 从Registry取得对应Schema；
3. 使用Filter Policy校验并规范化Filter；
4. 冻结一个UTC `analysis_as_of`；
5. 构造immutable `ReportRequest`和`AnalysisSnapshot`；
6. 从Provider Registry选择对应Provider；
7. 使用同一个Request执行`count()`和`list_rows()`；
8. 使用Registry列、标题、版本和Snapshot语义组装`ReportResponse`。

Service不重新排列、增加或删除Provider生成的列。`ReportResponse`契约继续验证每个`ReportRow`与Schema列顺序完全一致。

### 3.3 prepare_export

`prepare_export()`只准备Serializer所需的结构化输入，不调用Serializer、不创建文件：

- Schema-bound `ReportResponse`；
- 对应`ReportSchema`；
- Registry声明的`ExportDescriptor`；
- `ExportLimitPolicy`产生的`ExportDecision`。

Service先执行Count和Limit Policy。需要用户确认、空结果或超过硬限制时不读取全部行；只有Decision为`ALLOW`时才读取报告行。后续API/传输层负责解释确认协议并将准备结果交给Serializer。

## 4. Snapshot策略

### 4.1 未提供analysis_as_of

Service调用注入Clock一次，将返回值规范化为timezone-aware UTC。同一个值用于：

- `ReportRequest.analysis_as_of`；
- `AnalysisSnapshot.requested_at`；
- `AnalysisSnapshot.analysis_as_of`；
- Provider Count与Rows查询。

Service不会在同一请求中多次读取当前时间。

### 4.2 显式提供analysis_as_of

Service不调用Clock，将输入规范化为UTC并用于完整请求链。naive datetime会被拒绝。

在V1中，显式截点请求的`requested_at`与`analysis_as_of`使用同一规范化值，从而不引入第二次隐式时间读取。报告的真实历史能力仍由Schema中的`SnapshotSemantics`明确表达。

## 5. Availability策略

Service输出Contracts冻结的五种状态：

| 状态 | Service处理 |
| --- | --- |
| `AVAILABLE` | Provider成功且存在数据；或导出等待显式确认 |
| `PARTIAL` | Provider通过`ReportAvailabilityError`明确上报部分可用状态 |
| `EMPTY` | 查询成功但Count为0，reason为`NO_MATCHING_DATA` |
| `INSUFFICIENT` | Provider明确上报数据不足，Service原样保留 |
| `NOT_AVAILABLE` | 未分类Provider异常、来源不可用或导出超过硬限制 |

Service不使用`None`、空body或伪造零值行表达业务状态。

`ReportAvailabilityError`是编排层的结构化失败协议。Provider可携带已冻结的`ReportAvailability`，Service不重新解释`PARTIAL`或`INSUFFICIENT`。未知异常统一映射为：

```text
status = NOT_AVAILABLE
reason = MISSING_SOURCE
```

## 6. Provider编排与异常隔离

Preview和Export均只通过`ReportProviderRegistry`选择Provider，Service不知道也不导入具体Repository。

Provider调用异常会：

1. 使用logger记录完整异常；
2. 转换为结构化Availability；
3. 返回空Rows而不是伪造数据；
4. 不影响后续其他Report Type请求。

Service不执行跨报告聚合，因此一个来源失败不会污染其他五类Provider。

## 7. Schema组装

所有下列信息均来自`ReportSchemaRegistry`：

- Report名称与说明；
- `schema_version`；
- Columns及其顺序；
- Snapshot Semantics；
- supported formats；
- Export Descriptor。

Service不自行定义Column、Format、MIME、扩展名或文件名模板。

## 8. Export限制与Descriptor

导出准备复用Phase 10.2 `ExportLimitPolicy`：

- 空报告：`EMPTY`，不读取Rows；
- 需要确认：保留`AVAILABLE`与准确total rows，同时返回`REQUIRE_CONFIRMATION` Decision；
- 超过格式硬限制：`NOT_AVAILABLE / LIMIT_EXCEEDED`；
- 允许导出：读取与Count相同Request下的全部Rows。

Descriptor从Schema的显式`export_descriptors`按`ExportFormat`精确选择。Service不生成路径、不保存文件、不调用CSV/XLSX Serializer。

## 9. 架构边界

自动化测试确认`service.py`：

- 不导入ORM Model、SQLAlchemy、Repository、Router、FastAPI或Serializer；
- 不导入Score、Prediction、Anomaly、Operation Action、Drama Profile、Data Governance等业务Service；
- 不执行`commit`、`rollback`、`flush`、`query`或`execute`；
- 仅通过Provider、Registry、Policy和Contracts工作。

## 10. 测试记录

Service专项测试覆盖：

- Catalog稳定顺序；
- 六类Provider Preview编排；
- Filter规范化；
- Clock单次调用；
- 显式截点不调用Clock并规范化UTC；
- Schema与Rows映射；
- `AVAILABLE`、`PARTIAL`、`EMPTY`、`INSUFFICIENT`、`NOT_AVAILABLE`；
- Provider Count/Rows异常隔离；
- CSV/XLSX Descriptor选择；
- 导出确认与硬限制；
- Preview分页边界；
- 架构依赖与写操作禁令。

执行：

```text
python -m pytest tests/test_reporting_service.py -q
```

结果：`24 passed`。

Phase 10.1–10.4完整回归：`92 passed`。

Python `compileall`：通过。

## 11. 下一阶段边界

下一阶段可进入Phase 10.5 Reporting API，实现JWT保护的Catalog、Preview和Export GET接口、API Schema转换及Dependency组装。Router只能调用`ReportingService`，不得访问Repository、Provider、ORM或Serializer内部实现；Frontend仍需等待单独授权。
