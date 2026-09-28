# Phase 10 Analysis Reporting & Export Center Module Summary

## 1. 模块定位

Phase 10 建立 **Analysis Reporting & Export Center**，定位为系统的 **Reporting / Read Model Layer**。

该模块将 Phase 1–9 已经形成并持久化的系统事实转换为结构稳定、可查询、可预览、可导出的报告。它不生成新的分析结果或业务事实，不重新计算评分、质量、预测、异常或运营效果，也不包含推荐、自动决策、AI、LLM 或 Agent 能力。

Phase 10 的核心价值是提供统一的报告定义、历史截点语义、导出安全策略和用户访问入口，同时保持原业务模块的事实所有权不变。

## 2. 整体架构

```text
Reporting Frontend
        ↓
Reporting API
        ↓
ReportingService
        ↓
Report Providers
        ↓
ReportingRepository
        ↓
Existing Tables
```

辅助组件：

```text
Report Schema Registry ──→ Filter Policy
        │
        ├───────────────→ ReportingService
        │
        └───────────────→ CSV / XLSX Serializers
```

各层职责：

- Frontend：请求 API、展示 Catalog/Preview/Availability、确认导出并接收 Blob。
- API：JWT 认证、HTTP 参数与 Schema 转换、Service 调用、StreamingResponse 返回。
- ReportingService：Filter 校验、Snapshot 冻结、Provider 编排、Availability 和 Response 组装。
- Providers：将 Repository projection 按注册 Schema 映射为不可变 `ReportRow`。
- ReportingRepository：只读查询 Existing Tables，应用时间截点、版本和 Projection 规则。
- Schema Registry：显式声明 Report Schema、列顺序、Filter、格式及版本。
- Policies：执行 Filter allowlist、类型规范化、导出确认与限制判断。
- Serializers：仅将 Schema-bound Row 转换为安全的 CSV/XLSX 字节流。

依赖方向始终单向。Reporting 模块不调用 ScoreService、PredictionService、AnomalyService、OperationActionService、DramaProfileService、DataGovernanceService 或其他业务 Service。

## 3. Contracts + Schema Registry

### 3.1 Report Type

V1 冻结六类 Report：

1. `DRAMA_CATALOG`
2. `SCORE_RESULTS`
3. `DATA_QUALITY_RESULTS`
4. `PREDICTION_RESULTS`
5. `ANOMALY_RECORDS`
6. `OPERATION_ACTIONS`

其中 `DATA_QUALITY_RESULTS` 读取 Phase 2 已持久化的数据质量事实，不调用 Phase 9 Data Governance 请求时检查。

### 3.2 Contracts

Contracts 采用 frozen、slots、纯 Python DTO，主要包括：

- `ReportRequest`、`ReportFilter`；
- `ReportResponse`、`ReportAvailability`；
- `ReportMetadata`；
- `ReportColumn`、`ReportRow`；
- `AnalysisSnapshot`；
- `ExportDescriptor`；
- `FilterDefinition`、`ReportSchema`；
- Report Type、Export Format、Availability、Column Type、Filter Type、Snapshot Semantics 枚举。

DTO 不包含 ORM、Session、Repository、Service、SQL、文件路径或隐式时间读取。

### 3.3 Explicit Schema Registry

Schema Registry 为显式、只读、受版本控制的注册表。每个 Report Schema 固定以下内容：

- `schema_version`；
- Column 名称、显示名、类型、nullable 与 format；
- Column 顺序；
- 允许的 Filter；
- 支持的 Export Format；
- Snapshot Semantics；
- Export Descriptor。

Registry 不扫描数据库、不动态发现字段、不自动生成 Schema，也不执行查询、计算或格式转换。Providers 和 Serializers 均以 Registry 的列顺序为唯一结构依据。

## 4. Policies + Serializers

### 4.1 Filter Policy

Filter Policy 由 Schema Registry 驱动，负责：

- 仅接受 Schema allowlist 内的 Filter；
- 校验 STRING、INTEGER、DATETIME、ENUM 类型；
- 应用声明的默认值；
- 将时间规范化为 timezone-aware UTC；
- 输出结构化 Validation Result。

Filter Policy 不查询数据库、不推断用户意图，也不改变业务事实。

### 4.2 Export Limit Policy

V1 导出限制冻结为：

| 约束 | 限制 |
| --- | ---: |
| 无需确认的筛选后导出 | 最多 1,000 行 |
| CSV 硬上限 | 10,000 行 |
| XLSX 硬上限 | 5,000 行 |
| 文件大小上限 | 25 MiB |
| 内存 Spool 阈值 | 5 MiB |

无有效 Filter 或超过 1,000 行的导出必须由用户确认服务器返回的精确行数。空报告、超过格式行数上限或超过文件大小上限会被结构化拒绝。

### 4.3 CSV Serializer

CSV Serializer 固定执行：

- UTF-8 with BOM；
- CRLF 行结束符；
- Schema 顺序与类型约束；
- 数据库 NULL 语义保持，不将 `None` 转换为 `0`；
- 对以 `=`、`-`、`*`、`@` 开头及前置空白后的公式内容进行 Formula Injection 防护；
- request-scoped spooled stream 和资源关闭。

### 4.4 XLSX Serializer

XLSX Serializer 使用 write-only workbook 与 spooled stream，避免将完整数据集一次性装入内存。它固定 MIME 与 Sheet Schema，将潜在公式写为纯文本，不生成 Macro、External Link 或可执行公式，并在请求结束时释放临时资源。

Serializers 不包含业务计算、Filter 规则或数据查询。

## 5. Repository + Providers

### 5.1 ReportingRepository

Repository 仅执行 Existing Tables 的只读查询，返回 immutable projection，而不返回 ORM Model、SQLAlchemy 对象或 Session。它负责：

- 接收显式 `AnalysisSnapshot`；
- 应用 `analysis_as_of` 时间边界；
- 按数据源能力处理 version/revision；
- 保持数据库 NULL、zero 和 false 语义；
- 生成 Provider 可消费的投影；
- 为 Preview/Export 提供一致的 count 与 row 查询。

Repository 不计算指标、不格式化文件、不判断 Availability，也不执行 commit、rollback、flush 或任何写操作。

### 5.2 Report Providers

V1 Providers：

- `DramaCatalogReportProvider`
- `ScoreResultsReportProvider`
- `DataQualityResultsReportProvider`
- `PredictionResultsReportProvider`
- `AnomalyRecordsReportProvider`
- `OperationActionsReportProvider`

Provider 的唯一转换链为：

```text
Immutable Projection
        ↓
Registry Schema Binding
        ↓
Immutable ReportRow
```

Provider 不执行 SQL、不访问 ORM、不调用 Service 或 Serializer、不增加 Registry 未声明字段，也不重新计算任何已有业务结果。

## 6. ReportingService

`ReportingService` 是请求时编排层，负责：

- 返回稳定顺序的 Report Catalog；
- 调用 Filter Policy；
- 通过注入 Clock 冻结一次 Snapshot；
- 选择对应 Provider；
- 组装 Metadata、Columns、Rows 和 Availability；
- 为导出准备 Report、Schema、Descriptor 和 Limit Decision；
- 将 Provider 异常隔离为结构化 `NOT_AVAILABLE`。

显式提供 `analysis_as_of` 时不读取 Clock；未提供时只调用注入 Clock 一次。同一次请求的 Provider、Metadata 和 Response 共用同一 Snapshot。

Service 不访问 ORM、SQL、Session 或 Repository，不保存文件，也不执行写事务。实际文件序列化由独立的 request-scoped export application flow 调用 Serializer 完成。

## 7. Reporting API

V1 提供三个 GET-only 接口：

| 接口 | 用途 |
| --- | --- |
| `GET /api/v1/reports/catalog` | 返回已注册 Report、Schema、Filter 与支持格式 |
| `GET /api/v1/reports/preview` | 返回 JSON Metadata、Snapshot、Columns、Rows 和 Availability |
| `GET /api/v1/reports/export` | 返回 CSV/XLSX StreamingResponse |

三个接口均由 JWT Bearer 保护：USER 和 ADMINISTRATOR 可访问授权数据，匿名访问返回 401。Router 只负责参数接收、权限依赖、Service 调用和 API Schema 转换，不访问 Repository、Provider、Registry、Serializer、ORM 或 Session。

Preview 最多返回 100 行。Export 正确设置 MIME、`Content-Disposition`、Schema Version 与 Snapshot 响应头，并将参数错误、确认要求、导出限制及不可用状态转换为安全的结构化响应，不暴露内部堆栈。

## 8. Frontend Dashboard

Phase 10 Frontend 页面路径为 `/reports`，复用现有 `requiresAuth` 路由守卫和 Axios Token interceptor。

页面包含：

1. Report Catalog；
2. API Schema 驱动的 Filter Panel；
3. Snapshot 与 `analysis_as_of` 展示；
4. 严格保持 API Column 顺序的 Preview Table；
5. Availability Alert；
6. Export Confirmation；
7. Download Status。

Frontend 不硬编码报告目录，不计算指标或 Availability，不重新排序 Schema 字段，也不生成或解析 CSV/XLSX。下载流程仅为：

```text
Export API
    ↓
Blob
    ↓
Browser Download
```

当服务器返回新的确认行数时，页面要求用户再次确认；Export 失败不会破坏 Catalog 或 Preview 状态。

## 9. Availability 协议

Phase 10 使用显式 Availability：

- `AVAILABLE`：数据可用；
- `PARTIAL`：部分来源或数据可用；
- `EMPTY`：查询成功但没有匹配数据；
- `INSUFFICIENT`：数据不足以形成报告；
- `NOT_AVAILABLE`：来源、版本或处理流程不可用。

非 AVAILABLE 状态携带明确 Reason，必要时附带 Message。Contracts、Service、API 和 Frontend 不使用 `None`、空 Row 或数字 `0` 替代业务状态。

## 10. Snapshot Semantics

V1 支持两种截点语义：

- `AS_OF_RECONSTRUCTED`：数据源具备历史版本能力，按 `analysis_as_of` 重建截点事实；
- `CURRENT_STATE_AT_REQUEST`：只能保证请求时可见的当前状态，同时明确暴露该能力限制。

所有 Snapshot 时间必须 timezone-aware，并统一规范化为 UTC。Service 使用显式时间或注入 Clock 建立 Snapshot；Repository、Provider、Policy 和 Serializer 不隐式读取当前时间。Catalog 明确告知每类 Report 的 Snapshot Semantics，避免将当前状态误解为完整历史重建。

## 11. Export 安全设计

Phase 10 的导出安全措施包括：

- CSV Formula Injection 防护；
- CSV UTF-8 BOM、CRLF、NULL 与 quoting 规则；
- XLSX write-only 与公式纯文本化；
- 1,000 行确认阈值、格式行数硬上限和 25 MiB 文件上限；
- 5 MiB spooled stream 内存阈值；
- 固定 CSV/XLSX MIME 与安全文件名；
- API StreamingResponse；
- request-scoped stream、Workbook 和临时资源释放；
- JWT 身份认证和授权数据边界；
- 安全结构化错误，不返回内部异常堆栈。

Frontend 不绕过确认参数，也不在浏览器中重新构造导出文件。

## 12. Database 影响

Phase 10 V1 为 request-time Reporting Read Model：

- **No Migration**；
- 不新增 Report Result 表；
- 不新增 Report Snapshot 表；
- 不新增 Report File 表；
- 不新增 Cache 表；
- 不新增 Audit 表；
- 不修改 ORM；
- 不修改 Existing Tables。

报告文件只在请求期间生成并通过 StreamingResponse 返回，不写入磁盘归档或数据库。未来若引入异步任务、历史报告、下载审计、文件归档或持久化 Cache，必须重新进行 Architecture Review、Migration Review 和安全审查。

## 13. 测试记录

### 13.1 Backend

| 阶段 | 专项/回归结果 | 主要覆盖 |
| --- | --- | --- |
| Phase 10.1 Contracts + Registry | 与 Phase 10.2 合并回归 `49 passed`（其中本阶段新增测试使累计从 30 增至 49） | Enum、frozen DTO、Snapshot、Schema Version、Column顺序、Filter、Serializer兼容、依赖边界 |
| Phase 10.2 Policies + Serializers | `30 passed` | Filter allowlist/类型/UTC、确认与导出限制、CSV/XLSX安全、资源释放 |
| Phase 10.3 Repository + Providers | 专项 `19 passed`；累计 `68 passed` | Projection、as-of、revision、NULL、六类Provider、Schema映射、只读边界 |
| Phase 10.4 ReportingService | 专项 `24 passed`；累计 `92 passed` | Catalog、Preview、Snapshot一致性、Provider异常隔离、Availability、Export准备 |
| Phase 10.5 Reporting API | 专项 `24 passed`；累计 `116 passed` | GET-only、JWT、Schema、参数、Availability、CSV/XLSX Streaming、安全响应、Dependency边界 |

Repository、Providers、Service 和 API 阶段的 Python `compileall` 检查通过。提交前差异检查通过。

API 测试存在既有 FastAPI TestClient 弃用提示，不影响 Phase 10 测试结果。额外执行 Phase 7–9 API 回归时，Data Governance 与 Operation Analytics 通过；Drama Profile 有 2 项既有 `_IncludedRouter.path` 兼容性失败，在 Reporting 变更外同样可复现，未在 Phase 10 越界修复。

### 13.2 Frontend

- `npm exec vue-tsc -- --noEmit`：通过，无 TypeScript 错误；
- `npm run build`：通过，Vite 生产构建成功；
- `git diff --cached --check`：通过；
- 无新增依赖；
- 无 lockfile 修改。

构建存在既有 chunk-size warning，该提示为非阻塞构建提示。

## 14. Git 历史

### 14.1 设计与规划

| Commit | Message |
| --- | --- |
| `f09c6f4c5a10bc11d612c8612e9348052f16723a` | `docs(phase10): add analysis reporting design proposal` |
| `680f99ebff893560d9ccceea1646eaa01969d691` | `docs(phase10): add analysis reporting architecture review` |
| `11e8bac2fb5a73dcabeeda7466ea69d6860366b5` | `docs(phase10): add analysis reporting implementation plan` |

### 14.2 实现

| 逻辑阶段 | Commit | Message |
| --- | --- | --- |
| Phase 10.1 | `07afb394e1543f5b52662650d4181e550bce01b8` | `feat(phase10): add reporting contracts and schema registry` |
| Phase 10.2 | `1d5ab7a24640cb4b4e45e6c09bb90a3cb7483f10` | `feat(phase10): add reporting policies and serializers` |
| Phase 10.3 | `f45b52ba393dcc98589dc14738e32a303129abe3` | `feat(phase10): add reporting repositories and providers` |
| Phase 10.4 | `39662ea06215df619037761bb402e649d8e21e23` | `feat(phase10): add reporting service` |
| Phase 10.5 | `f325977860b19c5a9dee9e88f2c30751571bcc17` | `feat(phase10): add reporting api` |
| Phase 10.6 | `c5cb1c51d7df54281eea3df36ca9e181e790f469` | `feat(phase10): add reporting frontend` |

由于实际授权顺序，Policies + Serializers 的实现提交早于 Contracts + Schema Registry；上表按冻结的逻辑阶段编号排列，Commit hash 保留真实历史。

## 15. 当前限制与未来扩展

Phase 10 V1 当前限制：

1. 不支持异步报告任务；
2. 不保存历史报告文件；
3. 不提供报告下载或审计表；
4. 不支持超过同步策略上限的大规模后台导出；
5. 不提供定时报告或报告订阅；
6. 不提供持久化 Snapshot；
7. 不提供 Report Cache；
8. `CURRENT_STATE_AT_REQUEST` 数据源不能重建完整历史状态；
9. Report Catalog 为六类显式注册，V1 不支持运行时动态插件；
10. Preview 上限为 100 行，完整数据需通过受限 Export 获取。

可能的未来扩展包括异步 Report Job、历史归档、下载审计、定时报表、更多显式 Report Type 和大数据量后台导出。这些能力会引入持久化、任务状态、文件生命周期、授权与资源治理问题，必须先完成独立 Architecture Review；涉及表、ORM、Cache 或文件元数据持久化时，必须重新进行 Migration Review。

Phase 10 至此形成完整闭环：显式 Schema 定义既有事实，Repository 与 Provider 只读映射，Service 冻结 Snapshot 并编排，API 安全预览和流式导出，Frontend 只负责展示、确认与下载。
