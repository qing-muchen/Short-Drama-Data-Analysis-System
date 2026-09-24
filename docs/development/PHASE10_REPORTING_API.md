# Phase 10 Analysis Reporting API

## 1. API定位

Phase 10.5提供Analysis Reporting & Export Center的只读HTTP入口：

```text
HTTP Request
    ↓
Reporting Router
    ↓
Request-scoped Reporting Dependency
    ↓
ReportingService
    ↓
Report Providers
```

Router只负责认证、参数接收、API Schema转换和HTTP Response。它不访问Repository、Provider、Schema Registry、Serializer、ORM或Session，不执行报告计算、SQL或事务。

本阶段不修改Database、Migration或Frontend。

## 2. 接口列表

全部接口使用现有JWT Bearer认证，仅支持GET。

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/api/v1/reports/catalog` | 返回六类Report、Schema Version、Columns、Filters、Formats和Snapshot语义 |
| GET | `/api/v1/reports/preview` | 返回有限行JSON Preview及Availability |
| GET | `/api/v1/reports/export` | 返回CSV或XLSX `StreamingResponse` |

未提供POST、PUT、PATCH或DELETE接口。

## 3. Catalog API

`GET /api/v1/reports/catalog`调用`ReportingService.get_catalog()`，Router不读取Registry。

每项`ReportCatalogSchema`包含：

- `report_type`；
- `title`与`description`；
- `schema_version`；
- 有序Column定义；
- Filter定义；
- `supported_formats`；
- `snapshot_semantics`。

Catalog仅暴露公开报告协议，不返回数据库表名、ORM字段或SQL。

## 4. Preview API

`GET /api/v1/reports/preview`参数：

- `report_type`：六类闭合Enum；
- `filters`：URL编码的JSON object，仅用于传递Registry声明的结构化Filter；
- `analysis_as_of`：可选timezone-aware ISO 8601；
- `page_size`：1–100，默认20。

流程：

1. FastAPI验证Enum、aware datetime与page size；
2. API Schema层把`filters`解析为JSON object；
3. 请求级Reporting依赖把API Enum映射为内部Contract Enum；
4. ReportingService执行Filter Policy、Snapshot和Provider编排；
5. Router将`ReportResponse`显式映射为`ReportPreviewSchema`并包装为`ResponseModel`。

Preview保留全部Availability状态：`AVAILABLE`、`PARTIAL`、`EMPTY`、`INSUFFICIENT`、`NOT_AVAILABLE`。非AVAILABLE状态携带Contracts提供的reason，不使用空body或伪造零值行。

## 5. API Schema设计

`backend/schemas/reporting.py`定义独立于内部dataclass的Pydantic Schema：

- `ReportTypeSchema`；
- `ExportFormatSchema`；
- `ReportAvailabilityStatusSchema`；
- `ReportAvailabilityReasonSchema`；
- `ReportColumnSchema`；
- `ReportFilterDefinitionSchema`；
- `ReportCatalogSchema`；
- `AnalysisSnapshotSchema`；
- `ReportMetadataSchema`；
- `ReportAvailabilitySchema`；
- `ReportPreviewSchema`；
- `ReportExportResponse`文档模型。

映射函数逐字段转换Contracts DTO，不直接向HTTP暴露内部dataclass。

## 6. Dependency组装

`get_reporting_service()`按请求生命周期组装：

1. `ReportSchemaRegistry`；
2. `ReportingRepository`；
3. 六类Report Provider及Provider Registry；
4. `ReportFilterPolicy`；
5. `ExportLimitPolicy`；
6. `ReportingSystemClock`；
7. `ReportingService`；
8. CSV/XLSX Serializer；
9. `ReportingApiService`专用HTTP导出流程。

Router只注入`ReportingServiceDependency`。Repository、Provider、Registry与Serializer均封装在Composition Root和专用导出流程内部。

`ReportingApiService`不产生分析事实：它代理Catalog/Preview，并在Export时协调已完成的`ReportingService.prepare_export()`、安全Serializer、最终文件大小限制及请求期资源释放。

## 7. 权限模型

- `USER`：允许Catalog、Preview和Export其授权数据；
- `ADMINISTRATOR`：同样允许查询和导出，不绕过报告限制；
- 匿名：`401 Unauthorized`；
- 不满足现有用户角色策略：`403 Forbidden`。

API不新增角色或权限系统。

## 8. Export Streaming设计

`GET /api/v1/reports/export`参数：

- `report_type`；
- `filters`；
- `analysis_as_of`；
- `export_format=CSV|XLSX`；
- `confirmation`：需要确认时传入先前响应给出的准确行数。

导出流程：

1. ReportingService准备Report Rows、Schema、Descriptor和行数限制Decision；
2. 需要确认时返回`409 EXPORT_CONFIRMATION_REQUIRED`；
3. 行数超限返回结构化`400 EXPORT_LIMIT_EXCEEDED`；
4. 来源不可用返回结构化`400 REPORT_NOT_AVAILABLE`；
5. 专用导出流程按Format选择Phase 10.2安全Serializer；
6. Serializer生成请求期spooled stream；
7. 再次执行25 MiB文件大小限制；
8. 校验Serializer MIME/extension与Registry Descriptor一致；
9. Router返回`StreamingResponse`；
10. iterator `finally`与BackgroundTask共同保证请求期资源关闭。

### 8.1 CSV安全

继续复用Phase 10.2策略：

- UTF-8 BOM；
- CRLF；
- Formula Injection防护；
- Schema驱动NULL处理；
- 固定Column顺序。

### 8.2 XLSX安全

- write-only Workbook；
- request-scoped spool；
- 公式文本防护；
- 正确MIME；
- stream完成或异常后关闭资源。

### 8.3 Headers

成功响应包含：

- `Content-Type`；
- 安全ASCII `Content-Disposition`文件名；
- `Content-Length`；
- `X-Report-Schema-Version`；
- `X-Analysis-As-Of`；
- `X-Snapshot-Semantics`。

文件名由Registry的`filename_template`、UTC截点和净化后的Schema Version生成，不允许路径分隔符或换行。

## 9. 错误处理

- 非法JSON Filter及Filter Policy错误：结构化`400`；
- FastAPI传输形状错误，例如非法Enum、naive datetime、page size越界：项目统一`422 REQUEST_VALIDATION_ERROR`；
- 匿名：`401`；
- 权限不足：`403`；
- 导出确认：`409`；
- 来源不可用或导出超限：结构化`400`；
- Serializer异常：`400 EXPORT_FAILED`，不返回内部异常堆栈。

流开始前的错误均返回JSON `ErrorResponse`。流开始后不尝试拼接JSON错误，也不持久化半成品文件。

## 10. Router边界验证

AST边界测试确认`backend/routers/reporting.py`：

- 不导入ORM、SQLAlchemy、Repository、Provider、Registry或Serializer；
- 不调用`commit`、`rollback`、`flush`、`query`或`execute`；
- 不生成CSV/XLSX；
- 只调用请求级Reporting Dependency并转换Schema/Response。

## 11. 测试记录

API专项测试覆盖：

- 三条GET-only路由及OpenAPI注册；
- USER、ADMINISTRATOR、匿名401和权限不足403；
- Catalog Schema、Version、Columns、Filters与Formats；
- Preview Filter、aware `analysis_as_of`和`page_size`传递；
- page size边界及安全参数错误；
- 五种Availability状态；
- CSV Streaming、BOM、MIME、Headers和Formula Injection防护；
- XLSX Streaming、MIME及Workbook内容；
- confirmation协议；
- 行数超限和来源不可用；
- 请求级Dependency组装；
- Router架构边界。

执行：

```text
python -m pytest tests/test_reporting_api.py -q
```

结果：`24 passed`。测试环境存在既有FastAPI TestClient依赖弃用提示，不影响结果。

Phase 10.1–10.5完整回归：`116 passed`。

OpenAPI检查：三条Reporting路由存在且均为GET-only。

Python `compileall`：通过。

额外执行既有Phase 7–9 API回归时，Data Governance与Operation Analytics测试通过；`test_drama_profile_api.py`中2项既有测试因当前FastAPI将已包含Router表示为无`path`属性的`_IncludedRouter`而失败。该失败在Drama Profile测试单独运行时同样复现，与Reporting路由、Service或导出流程无关，本阶段未越界修改该测试或FastAPI集成方式。

## 12. 下一阶段边界

下一阶段可进入Phase 10.6 Reporting Frontend Implementation，实现`/reports`页面、API Client、TypeScript类型、Preview和下载交互。不得修改Reporting业务计算、Database、Migration或ORM。
