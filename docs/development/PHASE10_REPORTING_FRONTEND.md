# Phase 10.6 Analysis Reporting Frontend

## 1. 页面定位

`/reports` 是 Phase 10 Analysis Reporting & Export Center 的只读前端入口，提供报告目录浏览、动态 Filter 配置、报告预览、导出确认和浏览器下载。

前端只消费 Reporting API 返回的既有事实，不计算指标、不调整报告内容、不生成 CSV/XLSX，也不绕过服务端导出限制。页面复用现有认证路由和 Axios Token interceptor。

## 2. 文件结构

- `frontend/src/api/reporting.ts`：Catalog、Preview、Export API Client 与二进制响应处理。
- `frontend/src/types/reporting.ts`：与后端 API Schema 对齐的 TypeScript 类型。
- `frontend/src/views/reports/Reports.vue`：报告目录、Filter、Snapshot、Preview、Availability、导出确认和下载状态。
- `frontend/src/router/index.ts`：注册受认证保护的 `/reports` 路由。
- `frontend/src/views/Dashboard.vue`：增加“分析报告中心”导航入口。

## 3. API Client 设计

API Client 复用 `frontend/src/api/axios.ts`，不新增 Token 保存或认证逻辑。

| 方法 | HTTP接口 | 行为 |
| --- | --- | --- |
| `getReportCatalog` | `GET /api/v1/reports/catalog` | 返回服务端注册的 Report Schema 列表 |
| `getReportPreview` | `GET /api/v1/reports/preview` | 传递 `report_type`、JSON Filter、`analysis_as_of` 和 `page_size` |
| `exportReport` | `GET /api/v1/reports/export` | 传递格式与确认行数，接收 Blob 和下载响应头 |

Export Client 不解析 CSV/XLSX 内容。它只解析 HTTP 错误响应和 `Content-Disposition` 文件名，并将 Blob 交给页面触发浏览器下载。服务器返回 `EXPORT_CONFIRMATION_REQUIRED` 时，错误对象保留服务器确认行数，供页面发起第二次用户确认。

## 4. TypeScript 类型设计

类型覆盖：

- 六种 `ReportType`；
- `CSV`、`XLSX` 两种 `ExportFormat`；
- `AVAILABLE`、`PARTIAL`、`EMPTY`、`INSUFFICIENT`、`NOT_AVAILABLE`；
- Availability Reason、Column Type、Filter Value Type 和 Snapshot Semantics；
- `ReportColumn`、`ReportFilterDefinition`、`ReportCatalog`；
- `AnalysisSnapshot`、`ReportMetadata`、`ReportPreview`；
- Preview/Export 参数、Blob 下载描述和下载状态。

`ReportRow` 使用 `Record<string, ReportCellValue>` 表达动态列；实际展示顺序始终采用 API 返回的 `columns` 数组，不依赖对象键顺序，也不在前端补充列。

## 5. 页面结构

页面由以下区域组成：

1. Report Catalog：从 Catalog API 加载报告名称、说明、Schema Version、支持格式和 Snapshot Semantics。
2. Filter Panel：按 Catalog API 的 Filter Definition 动态生成输入项。
3. Snapshot：显示 Preview API 返回的 `analysis_as_of`、时区和截点语义。
4. Preview Table：严格按 Preview API 的 Column 顺序显示 Row。
5. Availability Alert：原样展示状态、Reasons 和 Message。
6. Export Confirmation：显示 Report Type、格式、数据截点和服务器确认行数。
7. Download Status：独立展示下载成功或错误，不影响 Catalog 和 Preview。

页面不使用图表，因此未引入新的 ECharts 实例或生命周期处理。

## 6. Preview 流程

用户从 API 返回的 Catalog 中选择报告并填写动态 Filter。页面仅执行传输层类型映射：INTEGER Filter 转换为数字，其余 Filter 保持输入字符串。可选 `analysis_as_of` 不由前端自动生成。

Preview 请求成功后，页面展示服务端返回的 Metadata、Snapshot、Availability、Columns 和 Rows；请求失败只更新 Preview 错误状态，不清空或破坏 Catalog。

## 7. Export 下载流程

导出必须基于已获得的 Preview。用户选择服务端声明支持的格式并打开确认对话框，确认后请求 Export API，始终携带 `confirmation` 行数。

如果数据在 Preview 与 Export 之间发生变化，服务端可返回新的确认行数；页面显示服务器响应并要求用户再次确认。成功响应按 `Blob -> Object URL -> 浏览器下载` 处理，完成后释放 Object URL。前端不读取或生成文件内容。

## 8. Availability 与状态隔离

Availability 状态直接来自 API：

- `AVAILABLE`
- `PARTIAL`
- `EMPTY`
- `INSUFFICIENT`
- `NOT_AVAILABLE`

页面不通过 `null` 推断业务可用性。Catalog、Preview 与 Export 分别维护 `loading / empty / error / success` 状态：任一请求失败不会覆盖其他模块的已加载数据。

## 9. Router 与 Dashboard

新增 `/reports` 路由，并复用 `meta.requiresAuth` 和现有全局守卫。USER 与 ADMINISTRATOR 均沿用后端授权访问，前端不新增角色判断。

Dashboard 仅新增“分析报告中心”跳转入口，不修改 Dashboard 现有数据请求或业务逻辑。

## 10. 安全与架构边界

- 不在前端保存 Token，认证由现有 Axios interceptor 处理。
- 不包含 CSV/XLSX 生成、解析或安全转义逻辑；文件安全由后端 Serializer 保证。
- 不计算指标、Availability、数据质量、排名或推荐。
- 不直接访问 Repository、Service、Database 或后端内部接口。
- 文件名移除路径分隔符和换行符，避免响应头文件名影响下载目标。

## 11. 验证记录

- `npm exec vue-tsc -- --noEmit`：通过，无 TypeScript 错误。
- `npm run build`：通过，Vite 生产构建成功。
- 构建存在既有的 chunk size warning；该提示不阻塞构建，且本阶段未新增依赖。
- 未修改 lockfile。
- `git diff --cached --check`：提交前执行并记录。
