# Phase 9 Data Governance Frontend

## 1. 页面定位

Phase 9.6 提供 `/data-governance` 数据治理与质量监控页面。页面只读取并展示 Phase 9 API 返回的治理结果，不计算 Freshness 延迟、Completeness 覆盖率或 Consistency 状态，不执行质量规则、阈值判断、Evidence 解释、数据修复、自动化或 AI 推断。

页面面向登录后的 `USER` 与 `ADMINISTRATOR`，复用现有全局路由守卫与 JWT Token 拦截器。

## 2. API Client

文件：`frontend/src/api/dataGovernance.ts`。

封装四个只读调用：

- `getDataGovernanceOverview()` → `GET /data-quality/overview`；
- `getFreshnessQuality()` → `GET /data-quality/freshness`；
- `getCompletenessQuality()` → `GET /data-quality/completeness`；
- `getConsistencyQuality()` → `GET /data-quality/consistency`。

Client 使用已有 `apiClient`、Base URL 和 Token interceptor，不拼接 Token、不新增认证逻辑。四个方法均解包项目统一 `ApiResponse<T>`，支持可选的 `analysis_as_of`；三个明细接口同时支持 Evidence 的 `page/page_size`。

## 3. TypeScript 类型

文件：`frontend/src/types/dataGovernance.ts`。

类型与 Phase 9.5 Schema 对齐：

- Enum union：`QualityStatus`、`AvailabilityStatus`、`AvailabilityReason`、`GovernanceScope`、`QualityIssueType`；
- 协议：`DataQualityAvailability`、`EvidenceItem`、`EvidencePage`；
- 结果：`FreshnessResult`、`CompletenessResult`、`ConsistencyResult`；
- 概览：`DataGovernanceResponse`；
- 查询：`DataGovernanceQuery`、`DataGovernanceDetailQuery`。

类型中不存在 AI、推荐、修复、排名或写操作字段。Decimal 覆盖率按 API JSON 字符串原样保存和展示，Frontend 不重新计算百分比。

## 4. 页面结构

文件：`frontend/src/views/dataGovernance/DataGovernance.vue`。

页面由以下区域组成：

1. Header：模块定位、返回 Dashboard、刷新入口；
2. Health Overview：整体 Availability、SYSTEM scope、`analysis_as_of`、规则集版本；
3. Freshness Card：QualityStatus、Availability、API 返回的延迟秒数、规则版本、分析时间；
4. Completeness Card：QualityStatus、Availability、API 返回的覆盖率、缺失项、规则版本；
5. Consistency Card：QualityStatus、Availability、API 返回的问题数量、规则版本；
6. Evidence Drawer：展示选中模块的 Evidence。

页面不引入图表。当前信息以状态卡和 Evidence 列表表达更直接，因此没有新增 ECharts 初始化或生命周期管理。

## 5. Availability 展示

页面按后端闭合状态显示固定文案：

- `AVAILABLE`：数据可用；
- `PARTIAL`：部分数据不可用；
- `INSUFFICIENT`：历史数据不足；
- `NOT_AVAILABLE`：暂不可用。

`AvailabilityReason` 仅转换为对应中文标签，不合并、不覆盖、不推断新的状态。QualityStatus 和 Availability 分别展示，避免把数据不可用与质量失败混为一类。

## 6. Evidence Drawer

Drawer 原样展示 API 的：

- `evidence_type`；
- `message`；
- `source`；
- `metadata`。

Metadata 仅格式化为 JSON 文本以便阅读，不进行二次分析或生成新结论。没有 Evidence 时显示明确空状态。

## 7. 状态与异常隔离

Overview、Freshness、Completeness、Consistency 分别维护：

- loading；
- empty；
- error；
- success。

页面使用四个独立 API 请求和独立错误状态。单个模块请求失败时，仅对应 Card 显示错误和重试入口，其他模块继续展示。全局刷新使用 `Promise.allSettled`，不会因一个请求失败中止其他请求。

## 8. Router 与 Dashboard

路由：

```text
/data-governance
```

路由设置 `requiresAuth: true`，复用现有登录守卫。Dashboard Header 增加“数据治理中心”导航按钮，未修改其他 Dashboard 业务逻辑。

## 9. 边界确认

Frontend 不包含：

- Freshness delay、coverage ratio 或 Consistency 的计算；
- Quality Rule 或阈值；
- Evidence 分析或状态推导；
- 数据修改、修复按钮、自动化、推荐或 AI；
- Backend Service、Repository、ORM 或 Database 调用。

## 10. 验证结果

执行：

```text
npm exec vue-tsc -- --noEmit
npm run build
```

结果：

- TypeScript 检查通过；
- Vite 生产构建通过；
- Vue 页面和懒加载路由编译成功；
- 未新增依赖；
- package manifest 与 lockfile 未修改；
- 构建仅报告现有 chunk size 非阻塞警告，未修改构建配置。
