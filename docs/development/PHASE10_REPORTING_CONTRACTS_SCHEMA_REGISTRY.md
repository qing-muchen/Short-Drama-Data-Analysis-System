# Phase 10 Reporting Contracts + Schema Registry

## 1. Scope

本阶段补齐 Analysis Reporting & Export Center 的纯数据契约与显式 Schema Registry，为 Policies、Serializers、Repository、Providers 和后续 Service 提供稳定类型基础。

本阶段不包含数据查询、ORM、Session、Repository、Provider、ReportingService、API、Frontend、文件生成或业务计算。不新增 Migration、报告表、Snapshot表、File表、Cache表或Audit表。

## 2. File Structure

```text
backend/services/reporting/
├── __init__.py
├── contracts.py
└── registry/
    ├── __init__.py
    ├── schemas.py
    └── registry.py

backend/tests/
├── test_reporting_contracts.py
└── test_reporting_schema_registry.py
```

## 3. ReportType

V1 使用闭合 `ReportType` Enum，仅包含：

1. `DRAMA_CATALOG`；
2. `SCORE_RESULTS`；
3. `DATA_QUALITY_RESULTS`；
4. `PREDICTION_RESULTS`；
5. `ANOMALY_RECORDS`；
6. `OPERATION_ACTIONS`。

每个 Report Type 在 `ReportSchema` 中明确：

- identifier；
- name；
- description；
- schema version；
- ordered columns；
- allowed filters；
- supported formats；
- Snapshot Semantics；
- fixed sheet name；
- Export Descriptor。

未知 Report Type 不允许动态注册或自动发现。

## 4. Enums

- `ReportType`；
- `ExportFormat`：CSV、XLSX；
- `ReportAvailabilityStatus`：AVAILABLE、PARTIAL、EMPTY、INSUFFICIENT、NOT_AVAILABLE；
- `ReportAvailabilityReason`；
- `SnapshotSemantics`：AS_OF_RECONSTRUCTED、CURRENT_STATE_AT_REQUEST；
- `ReportColumnType`：STRING、INTEGER、DECIMAL、BOOLEAN、DATE、DATETIME；
- `FilterValueType`：STRING、INTEGER、DATETIME、ENUM。

Enum保持闭合，不接受实现阶段自定义字符串扩展。

## 5. Availability Protocol

`ReportAvailability`字段：

- `status`；
- immutable `reasons`；
- optional nonblank `message`。

约束：

- AVAILABLE不得携带reason；
- PARTIAL、EMPTY、INSUFFICIENT、NOT_AVAILABLE必须携带至少一个reason；
- reason不得重复，必须按Enum顺序稳定排列；
- 不使用`None`表达业务状态。

EMPTY用于查询成功但没有匹配行；INSUFFICIENT用于来源数据不足；NOT_AVAILABLE用于当前条件无法形成报告。

## 6. Snapshot Semantics

`AnalysisSnapshot`字段：

- `requested_at`；
- `analysis_as_of`；
- `timezone`；
- `semantics`。

规则：

- 两个时间必须timezone-aware；
- V1 timezone固定为UTC；
- `analysis_as_of <= requested_at`；
- Contracts不调用当前时间，调用方必须显式提供；
- Snapshot Semantics必须明确历史重建能力。

能力矩阵：

| Report | Semantics |
| --- | --- |
| Drama Catalog | CURRENT_STATE_AT_REQUEST |
| Score Results | AS_OF_RECONSTRUCTED |
| Data Quality Results | AS_OF_RECONSTRUCTED |
| Prediction Results | AS_OF_RECONSTRUCTED |
| Anomaly Records | CURRENT_STATE_AT_REQUEST |
| Operation Actions | CURRENT_STATE_AT_REQUEST |

## 7. Request Contracts

`ReportFilter`只允许结构化标量：nonblank string、positive/validated integer由Policy进一步约束、aware datetime。禁止SQL、Query对象或ORM对象。

`ReportRequest`字段：

- `report_type`；
- sorted immutable `filters`；
- aware `analysis_as_of`；
- optional `export_format`。

重复或非稳定顺序Filter在契约边界被拒绝。Request不生成默认时间。

## 8. Response Contracts

### 8.1 ReportColumn

字段：

- `name`；
- `display_name`；
- `data_type`；
- `nullable`；
- optional `format`。

为兼容Phase 10.2 Serializer，同时提供只读属性：

- `key -> name`；
- `title -> display_name`；
- `column_type -> data_type`。

### 8.2 ReportRow

`ReportRow`是frozen、slots、只读Mapping。内部保存有序唯一键值tuple，仅允许：

- string；
- integer；
- Decimal；
- boolean；
- date；
- aware datetime；
- None。

不允许float、任意dict、完整业务对象或ORM对象。

### 8.3 Metadata and Response

`ReportMetadata`包含Report Type、title、description、Schema Version、Snapshot、total rows和source versions。

`ReportResponse`包含Metadata、ordered Columns、preview Rows和Availability。每行key和顺序必须与Columns精确一致，返回行数不能超过Metadata total rows。

## 9. ExportDescriptor

`ExportDescriptor`只描述传输格式：

- `format`；
- `mime_type`；
- `extension`；
- `filename_template`。

禁止包含文件路径。扩展名必须是安全后缀，filename template不得包含路径分隔符且必须以对应扩展名结尾。

CSV MIME：`text/csv; charset=utf-8`。

XLSX MIME：`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`。

## 10. ReportSchema

`ReportSchema`是每种报告的完整结构定义：

- Report Type、名称、说明、版本；
- ordered unique Columns；
- sorted unique Filter Definitions；
- supported Formats；
- Snapshot Semantics；
- safe XLSX sheet name；
- matching Export Descriptors。

Schema不查询数据、不转换Row、不进行业务判断。

## 11. Explicit Schema Registry

`ReportSchemaRegistry`在构造时接收显式Schema tuple，建立只读`MappingProxyType`。它提供：

- `get_schema(report_type)`；
- `get_filter_definitions(report_type)`；
- `list_schemas()`；
- `len(registry)`。

重复Report Type、未知Report Type或非ReportSchema输入均失败。

`create_default_registry()`每次创建独立只读Registry，不提供全局可变单例，也不提供运行时`register()`。`DEFAULT_REPORT_SCHEMAS`是六个frozen Schema组成的immutable tuple。

禁止数据库扫描、ORM反射、动态import、目录扫描或plugin discovery。

## 12. Six V1 Schemas

### 12.1 Drama Catalog

输出主数据展示字段、平台和标签展示值；允许drama、platform、status和tag Filter。当前主数据无法历史重建。

### 12.2 Score Results

输出持久化Score identity、scope、四维分数、总分、等级、截点和算法版本；允许drama、时间和算法版本Filter。

### 12.3 Data Quality Results

输出Phase 2持久化Quality Score、维度分数、评估数量、开放问题数量和版本信息；不展开source watermark JSON或Rule Evidence。

### 12.4 Prediction Results

输出持久化Prediction identity、metric、日期、预测值、截点和算法版本；不重新预测。

### 12.5 Anomaly Records

输出异常类型、严重度、请求时当前状态、检测时间、版本和最小Evidence字段；状态明确标记为Current State语义。

### 12.6 Operation Actions

输出Action事实、请求时当前状态以及source/history数量；不把当前字段描述为历史快照。

## 13. Phase 10.2 Compatibility

兼容性通过真实集成测试验证：

- `ReportSchemaRegistry.get_filter_definitions()`满足`ReportFilterPolicy`的Registry Protocol；
- `FilterDefinition`满足Filter Definition Protocol；
- `ReportSchema.columns/sheet_name`满足CSV/XLSX Schema Protocol；
- `ReportColumn.key/title/column_type/nullable`满足Serializer列接口；
- `ReportRow`实现Mapping，可直接传给Serializer；
- Column顺序、nullable和类型由Registry决定，Serializer不推断。

真实Drama Catalog Schema和ReportRow分别完成CSV与XLSX生成测试。

## 14. Architecture Boundaries

Contracts和Registry不导入：

- SQLAlchemy或ORM Model；
- Session或Database；
- Repository、Provider、Service；
- FastAPI或API Schema；
- Serializer实现或文件系统。

代码不包含query、execute、commit、rollback或flush，不创建文件，不读取当前时间。

## 15. Tests

新增测试覆盖：

- 六种闭合Report Type与其他Enum；
- frozen DTO、默认值、时间/类型/顺序边界；
- Availability与Snapshot规则；
- Mapping Row和Response一致性；
- Export Descriptor无路径；
- 六个显式Schema、版本、列顺序、格式、Filter与Snapshot矩阵；
- Duplicate/Unknown Registry失败；
- 无全局可变Registry；
- 与Filter Policy、CSV Serializer、XLSX Serializer真实兼容；
- 无数据层、应用层或写事务依赖。

Phase 10.1 + Phase 10.2回归结果：

```text
49 passed
```

验证命令：

```text
backend/.venv/Scripts/python.exe -m pytest \
  tests/test_reporting_contracts.py \
  tests/test_reporting_schema_registry.py \
  tests/test_reporting_policies.py \
  tests/test_reporting_serializers.py \
  -q -W error::pytest.PytestUnraisableExceptionWarning
```

## 16. Next Boundary

Contracts与Schema Registry已形成Phase 10类型闭环。下一阶段可实现Repository + Providers，但仍不得实现ReportingService、API或Frontend；数据读取层必须返回与本Schema精确一致的immutable projection/ReportRow。
