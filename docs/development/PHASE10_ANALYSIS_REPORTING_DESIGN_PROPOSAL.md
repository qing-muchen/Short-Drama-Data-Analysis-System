# Phase 10 Analysis Reporting & Export Center Design Proposal

> 状态：Design Proposal。本文档不授权 Backend、Frontend、Database、Migration 或 ORM 实现；完成后必须进入 Architecture Review。

## 1. Module Position

### 1.1 定位

Phase 10 建设 **Analysis Reporting & Export Center（分析报告与导出中心）**，归属 Reporting Layer / Read Model Layer。

当前系统能够在不同页面查询短剧、评分、质量、预测、异常、行动、解释、运营分析和数据治理结果，但缺少统一、受权限约束、与当前筛选条件一致的结构化交付出口。Phase 10 解决以下问题：

1. 用户如何导出当前有权查看的查询或分析结果；
2. 导出文件如何保留 `analysis_as_of`、筛选条件、来源类型和版本信息；
3. CSV 与 Excel 如何使用相同列定义和 NULL 语义；
4. 如何防止无边界全库导出、跨模块口径漂移和前端自行拼装数据。

目标用户：

- `USER`：导出其有权查询的分析结果；
- `ADMINISTRATOR`：导出其有权查询的业务与治理结果。

V1 只生成结构化 CSV / XLSX 文件和 JSON Preview，不生成 Word、PDF、PPT、自然语言报告、AI 总结或运营建议。

### 1.2 核心原则

- 导出是已有事实的传输表示，不是新的分析模型；
- 导出范围必须与当前筛选条件和权限一致；
- 同一次 Preview 与 Export 必须使用明确的分析截点和报告 Schema 版本；
- 不调用已有业务 Service，不修改来源数据；
- 不持久化报告文件、导出快照或缓存；
- 不重新计算 Score、Prediction、Anomaly、Lifecycle、Benchmark 或 Data Governance 状态。

## 2. Existing System Boundary

### 2.1 读取范围

V1 候选报告目录冻结为只读取已有持久化事实：

| Report Type | 来源 | V1输出边界 |
| --- | --- | --- |
| `DRAMA_CATALOG` | Drama、发行关系与基础资料 | 当前授权短剧目录及显式筛选结果 |
| `SCORE_RESULTS` | 已持久化 Drama Score | 已有评分结果、维度摘要和版本字段 |
| `DATA_QUALITY_RESULTS` | Phase 2 持久化质量结果 | 已有质量评分和规则结果摘要 |
| `PREDICTION_RESULTS` | 已持久化 Prediction Result | 已有预测结果、状态、分析截点和算法版本 |
| `ANOMALY_RECORDS` | 已持久化 Anomaly Record | 异常类型、严重度、状态、证据摘要和版本 |
| `OPERATION_ACTIONS` | Operation Action、Source、History | 行动事实、来源快照和历史事件 |
| `ANALYSIS_EXPLANATIONS` | Explanation、Lineage | 已保存解释快照、版本和最小血缘引用 |

导出模块可以使用相应表的只读 Repository 或专用 Reporting Repository projection，但不能调用 ScoreService、PredictionService、AnomalyService、OperationActionService、ExplanationService、DramaProfileService、OperationAnalyticsService 或 DataGovernanceService。

### 2.2 V1排除范围

Phase 8 Operation Analytics 和 Phase 9 Data Governance 的结果仅在请求期间存在。Phase 10 V1 不复制其规则，也不通过跨 Service 调用获取结果，因此暂不把 Lifecycle、Benchmark、Action Effect 或 Governance Result 纳入文件导出。

Phase 10 不修改：

- Phase 1–9 的数据、状态机、规则、版本或权限；
- 已有 Score、Quality、Prediction、Anomaly、Action、Explanation 记录；
- Dashboard、Drama Profile、Operation Analytics 或 Governance 的响应语义；
- 导入临时数据和未确认数据。

### 2.3 与现有模块边界

- Analysis 模块负责产生事实；Reporting 只选择、投影、序列化；
- Explanation 模块负责解释；Reporting 不生成解释文本；
- Data Governance 负责可信状态；Reporting 只传播来源中已有的质量提示；
- Frontend 负责发起 Preview/Download；不在浏览器中重新聚合或生成文件；
- OperationLog 是否记录下载行为尚未冻结，见 `[TBD-P10-04]`。

## 3. Architecture Overview

目标架构：

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

纯转换链：

```text
Report Row DTO
    ↓
Report Schema Registry
    ↓
CSV / XLSX Serializer
    ↓
Streaming HTTP Response
```

### 3.1 Frontend

负责报告类型和筛选条件输入、Preview 展示、范围确认、下载触发以及 loading/empty/error/success 状态。Frontend 不选择数据库字段、不计算分析指标、不修改导出行。

### 3.2 API

负责 JWT 认证、Query 校验、Service 调用、JSON Schema 转换及文件流响应。API 不访问 ORM、Repository、Provider 或 Serializer 内部实现。

### 3.3 Service

负责冻结 `analysis_as_of`、校验 Report Type / Format / Filter、调用对应 Provider、应用行数与权限边界、选择 Schema 版本并协调 Serializer。Service 不执行 SQL、不重算业务结果、不写数据库。

### 3.4 Providers

每个 Provider 只把 Repository projection 转换为稳定 Report Row DTO，并传播来源版本和 Availability。Provider 不调用 Rule、Serializer 或其他 Service。

### 3.5 Repository

只读查询层，负责筛选、排序、计数、`analysis_as_of` 条件、Revision 选择和 projection。Repository 不决定报告列、不生成文件、不判断业务结论。

### 3.6 Schema Registry / Serializer

Schema Registry 是显式静态配置，定义每种 Report Type 的列名、顺序、数据类型、NULL 表示和 `report_schema_version`。Serializer 只把已准备的 Row DTO 转成 CSV/XLSX，不查询数据、不改变值。

## 4. Database Impact Analysis

### 4.1 V1决议

Phase 10 V1 不创建 Migration，不新增业务表，不修改 ORM。

明确不新增：

- `report_jobs`；
- `report_results`；
- `report_snapshots`；
- `report_files`；
- `report_cache`；
- `export_history`。

文件在单次 HTTP 请求期间生成并流式返回，不保存到数据库或服务器长期目录。现有表足以支持已冻结的持久化事实报告。

### 4.2 Read Model限制

分析结果表可以按其 `analysis_as_of`、版本或创建时间读取历史结果；但 Drama 等可变当前状态表未必支持任意历史截点重建。Response Metadata 必须声明：

- `AS_OF_RECONSTRUCTED`：来源具有可验证的截点/Revision 语义；
- `CURRENT_STATE_AT_REQUEST`：只能导出请求时当前状态，不声称历史重建。

禁止把 `updated_at <= analysis_as_of` 误写成完整历史状态恢复。

### 4.3 未来持久化条件

若未来需要异步大文件、下载历史、已发布报告、报告审批、定期报表、文件重试或长期审计文件，必须重新进行 Architecture Review、Database Design 与 Migration Review。

## 5. Core Components

### 5.1 Contracts

建议目录：`backend/services/reporting/contracts.py`。

Enums：

- `ReportType`：七种 V1 持久化事实报告；
- `ExportFormat`：`CSV`、`XLSX`；
- `ReportAvailabilityStatus`：`AVAILABLE`、`PARTIAL`、`EMPTY`、`NOT_AVAILABLE`；
- `ReportAvailabilityReason`：`NO_MATCHING_DATA`、`MISSING_SOURCE`、`UNSUPPORTED_FILTER`、`SOURCE_VERSION_MISMATCH`、`LIMIT_EXCEEDED`、`EXPORT_FAILED`；
- `SnapshotSemantics`：`AS_OF_RECONSTRUCTED`、`CURRENT_STATE_AT_REQUEST`。

DTO：

- `ReportFilter`：冻结的过滤条件值对象；
- `ReportColumn`：列 key、标题、类型、nullable；
- `ReportSchema`：Report Type、列集合、Schema Version；
- `ReportMetadata`：类型、格式、`analysis_as_of`、筛选摘要、行数、来源版本、Snapshot Semantics；
- `ReportAvailability`；
- `ReportRow`：JSON-safe、不可变的键值集合；
- `ReportPreview`：Metadata、列定义、有限预览行、Availability；
- `ReportExportRequest`：内部请求契约，不是数据库实体；
- `ReportStreamDescriptor`：文件名、MIME、Metadata 和只读字节迭代器描述。

Contracts 使用纯 Python immutable DTO，不导入 ORM、Session、FastAPI 或 openpyxl。

### 5.2 Rules / Policies

Phase 10 不包含分析规则。需要两个确定性纯组件：

#### ReportFilterValidator

- 输入：Report Type、Filter、用户可见范围描述；
- 输出：规范化 Filter 或明确 Validation Error；
- 不访问数据库，不推断缺失字段。

#### ExportLimitPolicy

- 输入：预计行数、格式、是否已确认范围；
- 输出：允许、需要确认或拒绝；
- 版本：`Export Limit Policy V1.0`；
- 阈值等待 `[TBD-P10-02]` 冻结。

这些组件不计算业务指标，不决定 Score、Quality、Prediction 或 Anomaly 结论。

### 5.3 Repository

建议文件：`backend/repositories/reporting_repository.py`。

职责：

- `count_rows(report_type, filters, analysis_as_of)`；
- 分批迭代或分页读取 projection；
- 应用现有有效数据、状态和权限范围条件；
- 对支持历史语义的来源选择截点前有效 Revision；
- 使用稳定排序，确保 Preview 与 Export 可复现；
- 只返回 immutable projection，不返回 ORM Model。

禁止：业务计算、文件序列化、跨 Service 调用、commit、rollback、flush。

### 5.4 Providers

V1 推荐显式 Provider Registry，不做动态扫描：

- `DramaCatalogReportProvider`；
- `ScoreReportProvider`；
- `DataQualityReportProvider`；
- `PredictionReportProvider`；
- `AnomalyReportProvider`；
- `OperationActionReportProvider`；
- `ExplanationReportProvider`。

Provider 接收规范化 Filter 和统一 `analysis_as_of`，返回 `ReportMetadata`、`ReportAvailability` 与 `ReportRow` 流。Provider 不返回 ORM、不调用 Serializer、不调用其他 Service。

### 5.5 Service

建议：`ReportingService`。

接口：

- `get_catalog()`：返回支持的 Report Type、Format、Filter 和 Schema Version；
- `preview_report(request)`：计数并返回有限预览；
- `export_report(request)`：执行相同查询语义并返回 Stream Descriptor。

Service负责：

1. 冻结一次 UTC `analysis_as_of`；
2. 校验格式、报告类型和 Filter；
3. 解析认证上下文允许的范围；
4. 通过显式 Registry 选择 Provider；
5. 执行 Count / Limit Policy；
6. 选择 Report Schema 和 Serializer；
7. 保证 Preview 与 Export 使用相同列和 NULL 语义；
8. 返回显式 Availability。

Service 不直接查询 ORM、不修改数据、不创建报告记录、不调用业务 Service。

### 5.6 Serialization

- CSV：UTF-8 with BOM 是否作为默认编码由 `[TBD-P10-05]` 冻结；
- XLSX：使用项目现有 `openpyxl`，只写值、标题和基础格式，不执行公式；
- NULL：不得替换为数值 0；CSV/XLSX 空值表示等待 Review 冻结；
- 日期时间：输出带时区 ISO 8601，同时在 Metadata 中声明 UTC；
- 防公式注入：以 `=`, `+`, `-`, `@` 开头的文本必须按文本写入，具体转义规则需在 Review 冻结；
- 文件名：使用 Report Type、UTC 截点和 Schema Version 的安全字符组合，不包含用户原始自由文本。

## 6. API Proposal

V1 只设计 JWT 保护的 GET 接口：

### 6.1 Catalog

```http
GET /api/v1/reports/catalog
```

返回：支持的 Report Type、Export Format、Filter Schema、列 Schema Version 和权限可见性。

### 6.2 Preview

```http
GET /api/v1/reports/preview
```

Query：

- `report_type`；
- `analysis_as_of?`；
- Report Type 允许的显式筛选条件；
- `preview_limit`，V1 建议最大 100；
- `format` 仅用于显示目标格式约束，不生成文件。

Response：`ResponseModel[ReportPreviewSchema]`，包含列、有限样例行、预计总行数、Availability、Snapshot Semantics、Schema Version 和来源版本。

### 6.3 Export

```http
GET /api/v1/reports/export
```

Query 与 Preview 使用同一 Filter 契约，并增加：

- `format=CSV|XLSX`；
- 大范围确认参数，具体协议见 `[TBD-P10-02]`。

Response：`StreamingResponse`，设置受控的 `Content-Type`、`Content-Disposition` 和报告元数据 Header。文件流接口不套用 JSON `ResponseModel`；参数错误、权限错误和生成前失败继续使用现有 `ErrorResponse`。流开始后的错误传播策略见 `[TBD-P10-06]`。

### 6.4 权限

- `USER`：允许导出其可查询范围；
- `ADMINISTRATOR`：允许导出其可查询范围；
- 匿名：401；
- V1 不提供创建、更新、删除、发布或保存报告的写接口。

禁止把任意表名、列名、排序 SQL 或自由查询表达式作为客户端参数。

## 7. Frontend Proposal

页面路径：`/reports`。

建议页面：`frontend/src/views/reporting/ReportingCenter.vue`。

页面结构：

1. Report Catalog Card：选择后端允许的 Report Type；
2. Filter Panel：仅显示 Catalog 返回的闭合 Filter；
3. Analysis Cutoff / Snapshot Semantics Card；
4. Preview Table：显示列定义、有限行和预计总量；
5. Availability Alert：展示缺失、空结果或来源版本问题；
6. Export Confirmation Dialog：展示格式、范围、预计行数和截点；
7. Download Status：loading、empty、error、success。

Frontend 只提交筛选参数并展示 Preview，不计算指标、不重新排序业务结果、不自行拼 CSV/XLSX、不改变 NULL、不生成报告结论。

下载使用现有 Axios Token 机制处理 Blob/Stream。文件名优先使用受控 `Content-Disposition`；Frontend 必须校验并清理文件名中的路径字符。

## 8. Availability Protocol

### 8.1 Status

- `AVAILABLE`：来源完整且可生成报告；
- `PARTIAL`：报告可生成，但部分来源字段或版本不可用，必须携带原因；
- `EMPTY`：查询成功，但当前筛选没有匹配行；
- `NOT_AVAILABLE`：来源、权限范围、Schema 或生成条件不允许形成报告。

### 8.2 Reasons

- `NO_MATCHING_DATA`；
- `MISSING_SOURCE`；
- `UNSUPPORTED_FILTER`；
- `SOURCE_VERSION_MISMATCH`；
- `LIMIT_EXCEEDED`；
- `EXPORT_FAILED`。

`EMPTY` 不等于错误，且不得用一行全 0 数据代替。`PARTIAL` 必须在 Preview 和导出 Metadata 中保留相同原因。不得使用 `None`、空字符串或 HTTP 200 空 body 表达业务状态。

## 9. Version Strategy

V1 使用以下版本信息：

- `report_schema_version`：每种 Report Type 的列名、顺序、类型和 NULL 语义版本；
- `export_policy_version`：行数限制、确认和允许格式策略版本；
- `source_versions`：来源结果携带的 algorithm/rule/model/schema version 集合；
- `analysis_as_of`：本次读取的数据截止点；
- `snapshot_semantics`：是否支持真实历史截点重建。

V1 不引入 Report Registry 数据表或版本管理平台。Schema 和 Policy 使用显式代码配置并纳入测试。改变列语义、NULL 表示、筛选口径或类型必须提升 `report_schema_version`；仅修改展示标题是否需要升版须在 Architecture Review 冻结。

## 10. Testing Strategy

### 10.1 Contracts

- Enum 闭合值；
- immutable DTO；
- Report Type / Format / Availability 组合；
- Row 仅含 JSON-safe 值；
- Snapshot Semantics 必填；
- 无 ORM、Session、FastAPI 依赖。

### 10.2 Policies and Serializer

- Filter 允许/拒绝矩阵；
- 行数边界和确认协议；
- 相同输入产生相同列和值；
- CSV quoting、换行、UTF-8、NULL 和公式注入；
- XLSX 单元格类型、空值、Sheet 名和最大行数；
- Serializer 不访问数据库或 Service。

### 10.3 Repository

- `analysis_as_of` 过滤；
- Revision / VOID 选择；
- 权限与筛选范围；
- 稳定排序；
- Count 与 Row 查询一致；
- projection 而非 ORM；
- 无 commit、rollback、flush。

### 10.4 Providers

- projection 到 Row DTO 映射；
- 来源版本传播；
- NULL 不转 0；
- Empty / Partial Availability；
- 不调用 Rule、Serializer 或其他 Service。

### 10.5 Service

- Clock 只调用一次；
- Preview / Export 使用相同 Schema；
- Provider Registry 选择；
- Limit Policy；
- 权限范围不扩大；
- 模块异常转换为安全错误；
- 不访问 ORM、不写事务、不调用业务 Service。

### 10.6 API

- Catalog、Preview、Export 路由；
- JWT、USER / ADMINISTRATOR、匿名 401；
- Query 422；
- Preview Schema 与 Availability；
- CSV/XLSX MIME、Content-Disposition 和流内容；
- 不存在未经设计的 POST/PUT/PATCH/DELETE；
- Router 不访问 Repository、Provider、Serializer 或 ORM。

### 10.7 Frontend

- API / TypeScript Schema 对齐；
- loading、empty、partial、error、success；
- Preview 与确认范围展示；
- 下载错误处理和文件名安全；
- `npm exec vue-tsc -- --noEmit`；
- `npm run build`；
- 无新增依赖或 lockfile 变化，除非 Review 明确批准。

## 11. Risks and Limitations

### 11.1 数据规模与内存

同步 XLSX 生成可能消耗较多内存。V1 必须冻结行数上限和流式策略；未冻结前不得进入实现。

### 11.2 历史重建误导

部分可变业务表没有完整 temporal history。必须暴露 Snapshot Semantics，禁止把当前状态导出描述为历史截点快照。

### 11.3 跨模块口径漂移

控制方式：显式 Report Schema、来源版本、统一 `analysis_as_of`、Provider Registry 和列级测试；不允许 Frontend 自行拼接。

### 11.4 权限泄露

导出通常比页面浏览风险更高。Service 必须使用认证上下文生成范围，客户端不能提交任意 scope 或表名。当前系统只有 USER / ADMINISTRATOR 两类角色，尚无细粒度行权限。

### 11.5 CSV公式注入

所有用户来源文本必须按纯文本安全输出。转义策略未冻结前不得发布 CSV Export。

### 11.6 审计缺口

严格 Read Model 不写 OperationLog，但重要导出可能需要审计。该冲突必须在 Review 中解决，不能由实现阶段自行决定。

### 11.7 当前限制

- 不导出 Phase 8/9 的临时计算结果；
- 不生成 PDF、Word、PPT、图表图片或自然语言报告；
- 不保存文件、不支持异步任务和历史下载；
- 不支持计划任务、邮件发送、分享链接或外部对象存储；
- 不支持自由 SQL、任意列选择或用户自定义公式；
- 不提供 AI 总结、推荐或自动决策。

### 11.8 TBD Registry

#### [TBD-P10-01] V1 Report Catalog最终准入

- 问题：七种候选 Report Type 是否全部进入首版尚未经过逐项数据契约审查；
- 影响：Contracts、Provider 数量、API Filter 和 Frontend Catalog；
- 当前处理：Design Proposal 将其作为候选全集，Architecture Review 必须冻结首版最小集合，未准入类型不得实现。

#### [TBD-P10-02] 行数上限与大范围确认协议

- 问题：CSV/XLSX 最大行数、无筛选阈值及二次确认参数未冻结；
- 影响：性能、内存、用户误操作和 API 契约；
- 当前处理：实现前必须通过压测预算或明确课程规模上限，冻结 `Export Limit Policy V1.0`。

#### [TBD-P10-03] 各来源的历史截点能力

- 问题：各表对任意 `analysis_as_of` 的历史重建能力不同；
- 影响：Report Metadata 和用户对历史快照的理解；
- 当前处理：逐 Report Type 形成能力矩阵，不能证明历史重建时固定为 `CURRENT_STATE_AT_REQUEST`。

#### [TBD-P10-04] 导出审计与只读边界

- 问题：重要下载是否必须写 OperationLog；
- 影响：如果写日志，Phase 10 不再是严格无写事务模块；
- 当前处理：V1 Proposal 不写日志。Architecture Review 应选择保持纯只读，或拆分独立审计职责并重新定义事务边界。

#### [TBD-P10-05] CSV编码、NULL和公式转义

- 问题：BOM、空值文本和公式注入转义尚未冻结；
- 影响：Excel 兼容性、安全性和下游解析；
- 当前处理：Serializer 实现前必须形成逐值测试矩阵。

#### [TBD-P10-06] 流开始后的错误语义

- 问题：HTTP Header 发送后无法再返回统一 JSON ErrorResponse；
- 影响：大文件中途失败的客户端体验和可诊断性；
- 当前处理：优先在开始流前完成查询验证和生成准备；具体临时文件/内存/流式选择由 Review 冻结。

#### [TBD-P10-07] 导入错误报告权限

- 问题：PROJECT_MASTER 将导入错误列为可导出内容，但当前普通用户对导入任务的读取边界需要专项确认；
- 影响：是否增加 `IMPORT_ERRORS` Report Type；
- 当前处理：V1 候选目录暂不包含 Import Errors，权限冻结后再评审。

## 12. Implementation Plan

Design Proposal 通过 Architecture Review 和 Implementation Planning 后，建议按以下阶段实施：

### Phase 10.1 — Contracts and Schema Registry

实现 immutable Contracts、闭合 Enum、Report Schema Registry、单元测试和文档。冻结首版 Report Catalog、列定义、NULL 语义和版本。

### Phase 10.2 — Policies and Serializers

实现 Filter Validator、Export Limit Policy、CSV/XLSX Serializer、安全转义、确定性测试和文档。不访问数据库。

### Phase 10.3 — Reporting Repository and Providers

实现只读 projection 查询、Count、批量读取、七类中获准的 Providers、as-of / Revision 测试和文档。不实现 Service。

### Phase 10.4 — ReportingService

实现 Clock、Provider Registry、Preview/Export 编排、Availability、权限范围和异常处理。不实现 API。

### Phase 10.5 — Reporting API

实现 Schema、Dependency、Catalog/Preview/Export Router、JWT、StreamingResponse 和 API 测试。不实现 Frontend。

### Phase 10.6 — Reporting Frontend

实现 API Client、TypeScript Types、`/reports` 页面、Preview、确认与下载状态，并执行 TypeScript 和生产构建验证。

### Phase 10.7 — Module Summary

归档架构、边界、Report Catalog、版本、测试、Git 历史、限制和未来扩展。

每个阶段独立提交并精确暂存。任何实现开始前必须满足：Architecture Review 通过、所有阻断性 TBD 关闭、Implementation Plan 和 Review 完成。当前阶段完成后只允许进入 Architecture Review，不授权编码。
