# Phase 10 Analysis Reporting & Export Center Implementation Plan

> 状态：Implementation Planning。本文档将已通过的 Architecture Review 转换为文件级实施契约，仅授权后续 Implementation Review；不授权编码。

## 1. Implementation Overview

### 1.1 目标

Phase 10 实现 Analysis Reporting & Export Center，定位为 Reporting / Read Model Layer。模块从已有持久化事实生成 JSON Preview、CSV 和 XLSX，并保留报告 Schema、来源版本、`analysis_as_of` 与 Snapshot Semantics。

V1 只支持六种报告：

1. `DRAMA_CATALOG`；
2. `SCORE_RESULTS`；
3. `DATA_QUALITY_RESULTS`；
4. `PREDICTION_RESULTS`；
5. `ANOMALY_RECORDS`；
6. `OPERATION_ACTIONS`。

### 1.2 边界

V1 不生成新指标、评分、预测、异常、解释、推荐或决策；不调用 Phase 1–9 业务 Service；不导出 Phase 8/9 请求期结果；不导出 Explanation 或 Import Errors；不使用 AI、LLM、Agent 或机器学习。

V1 不创建 Migration，不修改 ORM，不保存报告结果、快照、文件、缓存或审计记录。文件仅存在于单次请求的受控临时资源中。

### 1.3 最终架构

```text
Reporting Frontend
        ↓
Read-only Reporting API
        ↓
ReportingService
        ↓
Report Providers
        ↓
ReportingRepository
        ↓
Existing Tables
```

辅助纯组件：

```text
Contracts ← Report Schema Registry
    ↓
Filter / Export Policies
    ↓
CSV / XLSX Serializers
```

依赖必须单向。Serializer、Policy 和 Registry 不访问数据库；Repository 不引用 Service、Provider、Registry 或 Serializer。

## 2. Directory Structure

计划文件结构：

```text
backend/
├── repositories/
│   └── reporting_repository.py
├── routers/
│   ├── __init__.py
│   ├── dependencies.py
│   └── reporting.py
├── schemas/
│   ├── __init__.py
│   └── reporting.py
├── services/
│   ├── __init__.py
│   └── reporting/
│       ├── __init__.py
│       ├── contracts.py
│       ├── schema_registry.py
│       ├── policies.py
│       ├── providers.py
│       ├── service.py
│       └── serializers/
│           ├── __init__.py
│           ├── csv_serializer.py
│           └── xlsx_serializer.py
└── tests/
    ├── test_reporting_contracts.py
    ├── test_reporting_schema_registry.py
    ├── test_reporting_policies.py
    ├── test_reporting_serializers.py
    ├── test_reporting_repository.py
    ├── test_reporting_providers.py
    ├── test_reporting_service.py
    └── test_reporting_api.py

frontend/src/
├── api/report.ts
├── types/report.ts
├── views/reporting/Reports.vue
├── router/index.ts
└── views/Dashboard.vue

docs/development/
├── PHASE10_ANALYSIS_REPORTING_CONTRACTS.md
├── PHASE10_ANALYSIS_REPORTING_SERIALIZERS.md
├── PHASE10_ANALYSIS_REPORTING_REPOSITORY_PROVIDERS.md
├── PHASE10_ANALYSIS_REPORTING_SERVICE.md
├── PHASE10_ANALYSIS_REPORTING_API.md
├── PHASE10_ANALYSIS_REPORTING_FRONTEND.md
└── PHASE10_ANALYSIS_REPORTING_MODULE_SUMMARY.md
```

不规划 `models/reporting.py`、Migration、任务队列、文件目录或缓存组件。

## 3. Implementation Phases

### 3.1 Phase 10.1 — Contracts + Schema Registry

文件范围：

- `backend/services/reporting/__init__.py`；
- `backend/services/reporting/contracts.py`；
- `backend/services/reporting/schema_registry.py`；
- `backend/tests/test_reporting_contracts.py`；
- `backend/tests/test_reporting_schema_registry.py`；
- `docs/development/PHASE10_ANALYSIS_REPORTING_CONTRACTS.md`。

输入：Architecture Review 冻结的六种 Report Type、Availability、Snapshot Semantics 和版本要求。

输出：纯 Python immutable DTO、闭合 Enum、六类显式 Schema 定义和只读 Registry。

测试：DTO 冻结性、Enum 闭合值、六类 Schema 的列 key 唯一性、顺序稳定性、类型/nullable 完整性、版本存在性、禁止动态扫描和禁止 ORM/FastAPI 依赖。

### 3.2 Phase 10.2 — Policies + Serializers

文件范围：

- `backend/services/reporting/policies.py`；
- `backend/services/reporting/serializers/__init__.py`；
- `backend/services/reporting/serializers/csv_serializer.py`；
- `backend/services/reporting/serializers/xlsx_serializer.py`；
- `backend/tests/test_reporting_policies.py`；
- `backend/tests/test_reporting_serializers.py`；
- `docs/development/PHASE10_ANALYSIS_REPORTING_SERIALIZERS.md`。

输入：规范化 Request DTO、Report Schema、Report Row DTO。

输出：规范化 Filter、导出策略决策、完整生成于请求期临时资源的 CSV/XLSX 描述符。

测试：Filter allowlist、确认协议、行数/字节边界、CSV Injection、NULL、Unicode、CRLF、MIME、XLSX 无公式/宏/外链/隐藏 Sheet，以及成功/失败资源清理。

### 3.3 Phase 10.3 — Repository + Providers

文件范围：

- `backend/repositories/reporting_repository.py`；
- `backend/repositories/__init__.py`（仅必要导出）；
- `backend/services/reporting/providers.py`；
- `backend/services/reporting/__init__.py`（仅必要导出）；
- `backend/tests/test_reporting_repository.py`；
- `backend/tests/test_reporting_providers.py`；
- `docs/development/PHASE10_ANALYSIS_REPORTING_REPOSITORY_PROVIDERS.md`。

输入：规范化 Filter、权限范围、统一 `analysis_as_of`、分页/批次边界。

输出：不可变 projection、准确 Count、稳定批次和 Report Row DTO。

测试：六类查询、Count/Rows 条件一致、as-of、版本选择、稳定排序、空数据、Provider 映射、不返回 ORM、无 commit/rollback/flush、无跨 Service 调用。

### 3.4 Phase 10.4 — ReportingService

文件范围：

- `backend/services/reporting/service.py`；
- `backend/services/reporting/__init__.py`（仅必要导出）；
- `backend/tests/test_reporting_service.py`；
- `docs/development/PHASE10_ANALYSIS_REPORTING_SERVICE.md`。

输入：内部 Catalog / Preview / Export Request DTO、认证上下文、Clock。

输出：Catalog、Report Preview 或完成生成的 Export Descriptor。

测试：Clock 一次、Registry/Provider/Policy/Serializer 编排、确认重计数、异常映射、权限范围不扩大、Snapshot Semantics、禁止 ORM/Session/SQL/写事务和业务 Service。

### 3.5 Phase 10.5 — Reporting API

文件范围：

- `backend/schemas/reporting.py`；
- `backend/schemas/__init__.py`（仅必要导出）；
- `backend/routers/reporting.py`；
- `backend/routers/__init__.py`（路由注册所需最小修改）；
- `backend/routers/dependencies.py`（仅 composition root）；
- `backend/tests/test_reporting_api.py`；
- `docs/development/PHASE10_ANALYSIS_REPORTING_API.md`。

输入：HTTP Query、JWT 用户。

输出：Catalog/Preview JSON 或 CSV/XLSX `StreamingResponse`。

测试：三条 GET 路由、无写方法、401/403/409/422、Schema 转换、MIME/Header、流内容、Dependency Override 和 Router 分层边界。

### 3.6 Phase 10.6 — Reporting Frontend

文件范围：

- `frontend/src/api/report.ts`；
- `frontend/src/types/report.ts`；
- `frontend/src/views/reporting/Reports.vue`；
- `frontend/src/router/index.ts`；
- `frontend/src/views/Dashboard.vue`；
- `docs/development/PHASE10_ANALYSIS_REPORTING_FRONTEND.md`。

输入：Catalog、Preview、Export HTTP Contract。

输出：`/reports` 页面、Dashboard 导航和安全下载交互。

测试：TypeScript、生产构建、Catalog 驱动 Filter、Preview/Export 截点一致、Availability、确认流程、下载错误和文件名清理。不得新增依赖或修改 lockfile。

### 3.7 Phase 10.7 — Module Summary

文件范围仅为：

- `docs/development/PHASE10_ANALYSIS_REPORTING_MODULE_SUMMARY.md`。

输入：10.1–10.6 实际提交、测试和最终边界。

输出：模块定位、架构、Contracts、Registry、Policies、Serializer、数据读取、Service、API、Frontend、测试、Git 历史、限制和后续扩展的归档文档。

不得修改实现代码。

## 4. Contracts Plan

### 4.1 Enums

- `ReportType`：六种且仅六种冻结类型；
- `ExportFormat`：`CSV`、`XLSX`；
- `ReportAvailabilityStatus`：`AVAILABLE`、`PARTIAL`、`EMPTY`、`NOT_AVAILABLE`；
- `ReportAvailabilityReason`：`NO_MATCHING_DATA`、`MISSING_SOURCE`、`UNSUPPORTED_FILTER`、`SOURCE_VERSION_MISMATCH`、`LIMIT_EXCEEDED`、`EXPORT_FAILED`；
- `SnapshotSemantics`：`AS_OF_RECONSTRUCTED`、`CURRENT_STATE_AT_REQUEST`；
- `ReportColumnType`：`STRING`、`INTEGER`、`DECIMAL`、`BOOLEAN`、`DATE`、`DATETIME`。

### 4.2 Request DTO

`ReportFilter` 只包含结构化可选字段：`drama_id`、`platform_id`、`start_time`、`end_time`、`status`、`algorithm_version`、`rule_set_version`、`tag_id`。Registry 按 Report Type 声明子集，不支持的非空字段必须拒绝，不能静默忽略。

`ReportPreviewRequest`：

- `report_type`；
- `filters`；
- `analysis_as_of`；
- `preview_limit`，默认 20、范围 1–100。

`ReportExportRequest`：

- `report_type`；
- `filters`；
- `analysis_as_of`；
- `export_format`；
- `confirmed_row_count`，可选且非负。

### 4.3 Schema / Row DTO

- `ReportColumn`：`key`、`title`、`column_type`、`nullable`；
- `ReportSchema`：`report_type`、`schema_version`、有序 `columns`、允许 Filter、允许 Format、Snapshot Semantics；
- `ReportRow`：与 Schema key 精确对应的不可变标量映射，不允许 ORM、嵌套业务对象、公式或任意 JSON；
- `ReportMetadata`：标题、说明、Report Type、Schema Version、`analysis_as_of`、Snapshot Semantics、Filter 摘要、总行数、来源版本；
- `ReportAvailability`：显式 status、reasons 和 message；
- `ReportPreview`：Metadata、Columns、Rows、Availability；
- `ReportExportDescriptor`：安全文件名、MIME、字节长度、受控 Header、已定位到起始位置且由调用方关闭的请求期资源。

所有 DTO 使用 frozen dataclass/tuple 等纯 Python 不可变结构，不依赖 SQLAlchemy、Session、FastAPI、Pydantic 或 openpyxl。

### 4.4 六类报告数据契约

| Report Type | 数据来源 | V1行结构 | Snapshot | 可用性 |
| --- | --- | --- | --- | --- |
| `DRAMA_CATALOG` | `dramas` 及显式平台/标签关系 | drama id/code/name、状态、首播日期、集数、单集时长、平台/标签展示值 | Current State | 无匹配为 `EMPTY`；关系缺失不伪造值 |
| `SCORE_RESULTS` | `drama_scores` | identity、drama、score date/scope、四维分数、总分、等级、analysis as-of、算法版本 | As-of Reconstructed | 来源缺失为 `EMPTY`；版本异常为 `PARTIAL/NOT_AVAILABLE` |
| `DATA_QUALITY_RESULTS` | `data_quality_scores` | identity/date/scope、四维质量分、总分、等级、评估数、开放问题数、analysis as-of、算法/规则集版本/hash | As-of Reconstructed | 不展开 JSON watermark 或规则 Evidence |
| `PREDICTION_RESULTS` | `prediction_results` | identity、drama、metric、prediction/target date、预测值、analysis as-of、算法版本 | As-of Reconstructed | 不重算预测，不补历史 |
| `ANOMALY_RECORDS` | `data_anomaly_records` | identity、drama、metric/anomaly type、severity、当前 status、detected/analysis time、算法版本、数值 Evidence 摘要 | Current State | 明示 status 为请求时当前状态 |
| `OPERATION_ACTIONS` | `operation_actions`；可投影 source/history 摘要计数 | action/drama、title、priority、当前 status、assignee/creator id、due/created/updated time、source/history count | Current State | 不把当前状态描述成历史快照 |

Registry 在 10.1 冻结精确列 key、标题、类型和 nullable；不得增加 Proposal 已排除的自由 JSON、完整业务对象、Explanation detail 或 Import Error 原文。

## 5. Report Schema Registry Plan

`ReportSchemaRegistry` 是进程内显式只读映射：

- `register(report_schema)` 仅在 composition 时显式使用；
- `get_schema(report_type)` 未注册即失败；
- `list_catalog()` 保持固定顺序；
- 重复注册失败；
- 不进行动态 import、plugin scan 或目录发现。

每类报告独立使用 `<REPORT_TYPE> Schema V1.0`。以下变化必须升版：列 key、顺序、类型、nullable、NULL 语义、Filter 语义、字段来源或 Snapshot Semantics。Catalog、Preview Metadata 与导出 Metadata 必须返回相同版本。

Registry 只声明定义，不查询数据库、不计算指标、不判断业务状态、不扩展权限。

## 6. Policies and Serializers Plan

### 6.1 Filter Policy

`ReportFilterPolicy` 按 Registry allowlist 校验并规范化参数：

- 非支持 Filter 返回 422 `UNSUPPORTED_REPORT_FILTER`；
- 时间范围要求 aware UTC、`start_time <= end_time`；
- Enum 使用来源闭合值；
- 不接受自由 SQL、自由列、自由排序或文本推断；
- Tag 仅在 `DRAMA_CATALOG` 且能复用现有 OR 语义时允许；
- category 不进入 V1；
- 默认排序由每个 Provider 固定，客户端不能覆盖。

### 6.2 Export Limit Policy

版本固定为 `Export Limit Policy V1.0`：

- 有至少一个有效 Filter 且 `total_rows <= 1000`：直接允许；
- 无有效 Filter 或 `total_rows > 1000`：409 `EXPORT_CONFIRMATION_REQUIRED`；
- 重试必须携带与重新 Count 完全一致的 `confirmed_row_count`；不一致继续 409；
- CSV 硬上限 10,000 行；XLSX 硬上限 5,000 行；超过返回 422 `EXPORT_LIMIT_EXCEEDED`；
- 两种格式生成后文件硬上限均为 25 MiB；超过返回 422 `EXPORT_SIZE_LIMIT_EXCEEDED`；
- 请求期 `SpooledTemporaryFile` 内存阈值为 5 MiB，超过阈值转入操作系统临时存储；
- Preview 不使用确认协议；Export 零行返回 409 `EMPTY_REPORT`。

确认不能绕过行数或文件大小硬上限。文件大小只能在完整生成后确认，因此 Header 发送前必须完成大小检查。

### 6.3 CSV Serializer

- 使用标准 CSV writer；
- UTF-8 with BOM；
- CRLF；
- Schema 决定 Header 顺序；
- NULL 输出空单元格，不转成 0、false 或 `NULL`；
- V1 不允许有业务意义的空字符串；
- 字符串忽略前导空白后以 `=`, `+`, `-`, `@` 开头时，在原字符串前添加单引号；
- 不剥离原值、不进行类型推断；
- 控制字符、逗号、引号、换行和中文进入安全测试矩阵。

MIME 固定为 `text/csv; charset=utf-8`，扩展名 `.csv`。

### 6.4 XLSX Serializer

- 使用项目现有 `openpyxl`，不得新增依赖；
- write-only Workbook 写入请求期临时资源；
- 固定 Data Sheet，可选固定 Metadata Sheet；
- 不写 formula、macro、external link 或 hidden sheet；
- 文本使用与 CSV 相同的危险前缀保护；
- UTC datetime 写 ISO 8601 文本；
- NULL 写空单元格；
- Sheet 名只来自 Registry 常量。

MIME 固定为 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`，扩展名 `.xlsx`。

### 6.5 临时资源与 Streaming

Serializer 必须在 API 发送 Header 前完成生成、大小验证、flush 和 rewind。Service 返回 Descriptor 后，Router 使用 `StreamingResponse` 分块读取。正常完成、生成失败、客户端断开均必须关闭资源。

响应开始前的错误转换为统一 `ErrorResponse`；响应开始后的网络错误只终止连接，不尝试追加 JSON，也不保留半成品。

## 7. Repository and Providers Plan

### 7.1 Repository接口

`ReportingRepository` 接收已规范化的具体 Query Spec，而不是自由 `report_type`/列名字符串。为六类来源提供对应 `count_*` 和 `iter_*` 方法；Count 和 Rows 必须复用同一条件构造器。

共同要求：

- 查询不晚于统一 `analysis_as_of` 的可证明历史事实；
- 当前状态来源明确标记 Current State；
- stable order 必须含唯一 ID 作为最后 tie-breaker；
- 批次读取，不执行逐行关系查询；
- 返回 frozen projection，不返回 ORM；
- 不 commit、rollback、flush，不调用 Policy/Service/Serializer。

### 7.2 as-of与版本规则

| Report | 截点/版本选择 | 稳定排序 |
| --- | --- | --- |
| Drama | 请求时当前记录；不声称历史重建 | `drama_id` |
| Score | `analysis_as_of <= cutoff`；保留所有不同 identity/version 的已保存结果 | `analysis_as_of, score_date, score_id` |
| Data Quality | `analysis_as_of <= cutoff`；同日不跨 algorithm/rule set/hash 折叠，每个持久化唯一 identity 一行 | `analysis_as_of, score_date, quality_score_id` |
| Prediction | `analysis_as_of <= cutoff`；保留不同 algorithm version | `analysis_as_of, target_date, prediction_id` |
| Anomaly | `detected_at <= cutoff`；status 为请求时当前值 | `detected_at, anomaly_id` |
| Action | `created_at <= cutoff`；当前字段不做历史恢复 | `created_at, action_id` |

“保留所有版本”避免以当前最新版本覆盖历史结果。V1 报告是结果明细，不替用户选择“最佳”版本。

### 7.3 Providers

显式 Provider Registry 注册：

- `DramaCatalogReportProvider`；
- `ScoreResultsReportProvider`；
- `DataQualityResultsReportProvider`；
- `PredictionResultsReportProvider`；
- `AnomalyRecordsReportProvider`；
- `OperationActionsReportProvider`。

每个 Provider 提供 `count(request_context)` 与 `iter_rows(request_context)`，把 Repository projection 映射为严格符合 Registry Schema 的 Report Row，并传播来源版本和 Availability。Provider 不执行 SQL、不调用 Serializer、Policy、Rule 或业务 Service，不修改 NULL，不返回 ORM。

## 8. ReportingService Plan

`ReportingService` 使用构造器注入 Clock、Schema Registry、Provider Registry、Filter Policy、Export Limit Policy 和 Serializer Registry；不得内部实例化数据库依赖。

方法：

- `get_catalog(auth_context)`；
- `preview_report(request, auth_context)`；
- `export_report(request, auth_context)`。

编排顺序：

1. 从认证上下文建立权限范围；
2. 解析 Registry Schema；
3. 规范化 Filter；
4. 显式 `analysis_as_of` 转 UTC，未提供时 Clock 只调用一次；
5. 选择 Provider 并 Count；
6. Preview 读取最多 `preview_limit` 行；Export 执行 Limit Policy；
7. Provider 生成 Row DTO；
8. 对 Row/Schema 做结构校验；
9. Serializer 完整生成临时文件；
10. 检查字节上限并返回 DTO/Descriptor。

Catalog、Preview 和 Export 使用同一权限策略。`USER` 与 `ADMINISTRATOR` 可访问相同六类、但仅限其现有查询范围；管理员不能绕过限制。匿名在 API 层返回 401。

Service 不访问 ORM、Session 或 SQL，不写数据库，不调用已有业务 Service。单一报告来源失败不得降级为伪数据；在 Header 前转换为明确错误或 `NOT_AVAILABLE`。

## 9. Snapshot and as-of Plan

### 9.1 截点策略

- 未提供 `analysis_as_of`：Service 调用 Clock 一次并冻结 UTC 时间；
- 显式提供：必须 timezone-aware，转换为 UTC，不调用 Clock；
- Count、Rows、Metadata、安全文件名和 Header 使用同一值；
- Preview 返回的截点由 Frontend 原样传给 Export。

### 9.2 能力矩阵

| Report Type | Snapshot Semantics | 实现约束 |
| --- | --- | --- |
| Drama Catalog | `CURRENT_STATE_AT_REQUEST` | 截点只标记请求，不承诺历史状态 |
| Score Results | `AS_OF_RECONSTRUCTED` | 读取 cutoff 前已保存结果，不重算 |
| Data Quality Results | `AS_OF_RECONSTRUCTED` | 按 persisted identity 保留同日多版本 |
| Prediction Results | `AS_OF_RECONSTRUCTED` | 读取 cutoff 前已保存预测，不重算 |
| Anomaly Records | `CURRENT_STATE_AT_REQUEST` | 检测时间受 cutoff 限制，status 仍是当前状态 |
| Operation Actions | `CURRENT_STATE_AT_REQUEST` | 创建时间受 cutoff 限制，不重建当前字段历史 |

Preview 与 Export 之间，Current State 来源可能变化；`confirmed_row_count` 不是 Snapshot token。API 和页面必须展示该语义。

## 10. API Plan

### 10.1 Catalog

```http
GET /api/v1/reports/catalog
```

JWT 保护。返回当前用户可用的六类报告、Format、Filter Schema、Columns、Schema Version 和 Snapshot Semantics；不暴露表名、ORM 字段或 SQL。

### 10.2 Preview

```http
GET /api/v1/reports/preview
```

Query：`report_type`、可选 aware `analysis_as_of`、`preview_limit=20`（1–100）和该类型允许的显式 Filter。

返回 `ResponseModel[ReportPreviewSchema]`，包含 Metadata、Columns、Rows、总行数和 Availability。无匹配数据返回 200 + `EMPTY`。

### 10.3 Export

```http
GET /api/v1/reports/export
```

Query：Preview 的 Report/截点/Filter，加 `format=CSV|XLSX` 与可选 `confirmed_row_count`。成功返回 `StreamingResponse`：

- 安全 RFC 5987 `Content-Disposition`；
- 固定 MIME；
- 可选受控 ASCII Header：`X-Report-Schema-Version`、`X-Analysis-As-Of`、`X-Snapshot-Semantics`；
- 不把用户自由文本放入 Header。

错误：401 未认证、403 越权、409 确认/空报告、422 参数/Filter/行数/文件大小超限。生成前失败使用统一 `ErrorResponse`；开始传输后失败终止连接。

Router 只接收参数、执行认证依赖、调用 Service、转换 Schema/Response；不得引用 ORM、Repository、Provider 或 Serializer。

## 11. Frontend Plan

页面路径 `/reports`，组件 `Reports.vue`：

1. Report Catalog：只显示 API 返回的报告；
2. Filter Panel：按 Catalog 的 Filter Schema 渲染闭合输入；
3. Snapshot Semantics：展示截点与历史能力；
4. Preview Table：按 Columns 原顺序展示，禁止业务计算；
5. Availability Alert：明确 empty/partial/not available；
6. Export Confirmation：显示格式、总行数、Filter、截点和 Snapshot Semantics；
7. Download Status：loading/error/success，并处理 Blob 下载。

Frontend 必须把 Preview 的 `analysis_as_of` 原样用于 Export；409 确认响应后以同一 Query 和 `confirmed_row_count` 重试。若 Count 改变则重新确认，不能自动循环。

文件名优先读取受控 `Content-Disposition`，并移除路径分隔符和控制字符。Frontend 不生成 CSV/XLSX、不重新排序业务结果、不改变 NULL、不推断 Filter、不计算业务结论。

## 12. Security Plan

### 12.1 CSV/XLSX安全

- 对 `=`, `+`, `-`, `@` 及前导空白变体做文本化测试；
- 所有 Header、列和 Sheet 名来自 Registry；
- 用户自由文本不得进入响应 Header 或文件名；
- XLSX 禁止公式、宏、外链和隐藏 Sheet；
- CSV 使用标准 writer，禁止字符串拼接。

### 12.2 资源安全

- 10,000/5,000 行硬上限；
- 25 MiB 文件硬上限；
- 5 MiB 内存 spool 阈值；
- 生成完成后才发送 Header；
- `finally`/response cleanup 关闭临时资源；
- 不提供文件重取、共享链接或固定路径。

### 12.3 权限

- JWT 必需；匿名 401；
- USER/ADMINISTRATOR 都受相同 Catalog、Filter、确认和硬上限约束；
- Service 从认证上下文取范围，不接受客户端 scope；
- V1 不虚构当前系统不存在的团队/行级权限；
- V1 不写 OperationLog。未来下载审计须重新 Architecture Review。

## 13. Testing Plan

### 13.1 Backend

- Contracts：Enum、frozen DTO、标量 Row、Availability、Snapshot；
- Registry：六类且仅六类、列唯一/稳定、版本、重复/未知注册；
- Policies：Filter allowlist、日期、状态、1000/5000/10000、确认重计数、25 MiB；
- Serializers：BOM、CRLF、quote、Unicode、NULL、CSV Injection、XLSX 安全、MIME、Metadata、资源清理；
- Repository：六类 projection、as-of、版本、当前状态语义、Count/Rows 一致、稳定排序、批次、只读；
- Providers：Schema 映射、来源版本、NULL、Availability、无 ORM/Service；
- Service：Clock 一次、完整三流程、权限、Policy、Serializer、异常和分层；
- API：三条 GET、无写方法、JWT、错误码、Schema、Header、Streaming、Dependency Override。

### 13.2 Frontend

- TypeScript 类型与 API Schema 对齐；
- Catalog 驱动 Filter；
- loading/empty/partial/error/success；
- 确认重试和截点复用；
- 下载错误、MIME 和文件名清理；
- `npm exec vue-tsc -- --noEmit`；
- `npm run build`；
- 无依赖和 lockfile 变化。

### 13.3 架构回归

静态/源码检查确认：

- Service/Provider 不调用业务 Service；
- Repository 以外不访问 ORM；
- Serializer/Policy/Registry 无 Database 依赖；
- Repository 无 commit/rollback/flush；
- Router 无 Repository/Provider/ORM；
- 无 Migration、ORM Model、报告持久化或审计写入。

每个实现阶段运行本阶段专项测试及已完成 Phase 10 回归；提交前执行 `git diff --cached --check`。

## 14. Git Commit Strategy

每阶段只精确暂存该阶段允许文件，禁止 `git add .`，不得带入当前工作区其他修改：

| Phase | Commit | 范围 |
| --- | --- | --- |
| 10.1 | `feat(phase10): add reporting contracts` | Contracts、Registry、测试、文档 |
| 10.2 | `feat(phase10): add reporting policies and serializers` | Policies、Serializers、测试、文档 |
| 10.3 | `feat(phase10): add reporting repositories and providers` | Repository、Providers、测试、文档 |
| 10.4 | `feat(phase10): add reporting service` | Service、测试、文档 |
| 10.5 | `feat(phase10): add reporting api` | Schema、Router、Dependency、测试、文档 |
| 10.6 | `feat(phase10): add reporting frontend` | API Client、Types、View、Router/Dashboard入口、文档 |
| 10.7 | `docs(phase10): add reporting module summary` | 仅 Summary 文档 |

## 15. Database Impact Confirmation

Phase 10 V1 不创建 V014，不修改 V001–V013，不新增表，不修改 ORM。明确不持久化 Report Result、Snapshot、Job、File、Cache、History 或 Audit。`SpooledTemporaryFile` 是请求期资源，不是业务存储。

异步任务、报告保存、再次下载、归档、定时报表、分享、对象存储、缓存或导出审计任一需求出现时，必须重新进行 Architecture Review；涉及数据库时另做 Migration Review。

## 16. TBD Closure and Readiness

Architecture Review 的七项 TBD 已全部吸收：

- Catalog：六类；
- 限制：1000 直接阈值、CSV 10000、XLSX 5000、25 MiB 文件上限、确认重计数；
- Snapshot：六类能力矩阵；
- Audit：V1 排除；
- CSV：BOM、CRLF、NULL、公式防护；
- Streaming：完整生成后响应；
- Permission：USER/ADMIN 同 Catalog，Import Errors 排除。

本规划未保留新的 Implementation TBD。若 Implementation Review 发现冻结设计与现有字段、权限或运行环境不兼容，必须回到规划或架构审查，禁止在编码阶段自行改变契约。

## 17. Planning Decision

Implementation Plan 已将 Architecture Review 转换为阶段、文件、接口、规则和测试契约。下一阶段只能进行 **Phase 10 Implementation Review**；Review 通过前不得创建 `backend/services/reporting`、Reporting API 或 `/reports` 页面。
