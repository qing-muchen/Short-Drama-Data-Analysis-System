# 短剧数据管理与分析系统架构说明

## 1. 架构目标

系统采用前后端分离、领域模块化和分层架构，目标是：

- 将页面、HTTP、业务编排、规则计算和数据访问职责分离；
- 保持依赖方向单向，避免跨模块 Service 调用和循环依赖；
- 对需要聚合的功能优先采用只读 Read Model；
- 保留 `analysis_as_of`、Revision、算法版本和规则版本等追溯信息；
- 将写事务限制在明确的业务 Service 中；
- 不在展示层重复业务计算。

## 2. 总体架构图

```text
┌───────────────────────────────────────────────┐
│ Frontend                                      │
│ Vue 3 / TypeScript / Element Plus / ECharts  │
└──────────────────────┬────────────────────────┘
                       ↓ HTTPS / JSON / Blob
┌───────────────────────────────────────────────┐
│ API Layer                                     │
│ FastAPI Router / JWT / Pydantic Schema        │
└──────────────────────┬────────────────────────┘
                       ↓
┌───────────────────────────────────────────────┐
│ Service Layer                                 │
│ Transaction Service / Orchestration Service   │
└──────────────────────┬────────────────────────┘
                       ↓
┌───────────────────────────────────────────────┐
│ Providers / Rule Components                   │
│ DTO Mapping / Deterministic Pure Rules        │
└──────────────────────┬────────────────────────┘
                       ↓
┌───────────────────────────────────────────────┐
│ Repository Layer                              │
│ Query / Projection / as-of / Revision         │
└──────────────────────┬────────────────────────┘
                       ↓
┌───────────────────────────────────────────────┐
│ Database                                      │
│ MySQL 8 / ORM Mapping / V001–V013             │
└───────────────────────────────────────────────┘
```

基础 CRUD 和需要写入的分析模块通常采用：

```text
Router → Service → Repository → ORM / Database
```

只读聚合与治理模块通常采用：

```text
Router → Orchestration Service → Providers / Rules → Repository → Existing Data
```

## 3. 前端层

### 3.1 技术组成

- Vue 3 Composition API；
- TypeScript；
- Vite；
- Vue Router；
- Pinia；
- Axios；
- Element Plus；
- ECharts。

### 3.2 职责

前端负责：

- 页面展示和响应式布局；
- 表单、筛选、分页和用户确认；
- 调用公开 API；
- 管理 loading、empty、error 和 success 状态；
- 通过现有拦截器携带 Token；
- 展示服务端返回的分析、Availability、Evidence 和 Snapshot；
- 接收导出 Blob 并触发浏览器下载。

前端不负责：

- 重新计算评分、预测、异常、生命周期、Benchmark 或数据治理状态；
- 访问数据库或后端内部 Service；
- 生成 CSV/XLSX 内容；
- 推断缺失数据的业务含义；
- 执行后端权限判断。

### 3.3 路由与认证

业务页面使用 `meta.requiresAuth`。全局路由守卫检查本地认证状态，并在需要时请求当前用户。后端仍是最终权限边界，前端路由不能代替 JWT 与角色验证。

## 4. API 层

### 4.1 技术组成

API 使用 FastAPI 和 Pydantic Schema，统一前缀为 `/api/v1`。健康检查为 `GET /health`。

### 4.2 职责

API 层负责：

- Path、Query、Body 和文件参数接收；
- 参数格式与范围校验；
- JWT 身份和角色依赖；
- 调用对应 Service；
- 内部 DTO 与公开 Schema 转换；
- 统一成功响应和错误响应；
- 报告 StreamingResponse。

Router 不应执行 SQL、直接访问 ORM、管理事务或承载复杂业务规则。Read Model Router 只依赖对应的 Application Service。

## 5. Service 层

### 5.1 事务型 Service

基础数据维护、导入、评分计算、预测、异常状态和运营行动等写操作由业务 Service 管理。Service 负责跨行校验、业务状态转换、事务提交或回滚，并通过 Repository 访问数据。

### 5.2 编排型 Service

DramaProfileService、OperationAnalyticsService、DataGovernanceService 和 ReportingService 属于只读编排层，主要负责：

- 参数校验；
- 冻结统一 `analysis_as_of`；
- Provider 与 Rule 编排；
- Availability 聚合；
- Response DTO 组装；
- 模块异常隔离。

编排型 Service 不直接访问 ORM、SQL 或 Session，不调用其他业务 Service，也不执行写事务。

## 6. Providers 与 Rule Components

### 6.1 Providers

Provider 位于 Repository 和编排 Service 之间，负责：

- 将只读 Projection 转换为 Contracts DTO；
- 准备纯规则组件的输入；
- 按注册 Schema 映射输出；
- 保留 NULL、zero、Availability 和版本语义。

Provider 不执行 SQL、不返回 ORM、不写数据库，也不调用业务 Service。不同模块是否允许 Provider 调用 Rule 以该模块冻结设计为准；Phase 8/9 中 Rule 由 Service 显式编排。

### 6.2 Rule Components

Rule Component 是确定性的纯计算组件：

```text
Input DTO → Deterministic Evaluation → Result DTO
```

Rules 不访问数据库、网络、Repository、Session 或当前时间；规则版本作为结果追溯信息返回。Operation Analytics 和 Data Governance 均采用版本化规则。

## 7. Repository 层

Repository 集中管理数据访问，负责：

- ORM 查询和 Projection；
- 分页、筛选和排序；
- `analysis_as_of` 时间边界；
- Revision/Version 选择；
- VOID 或状态过滤；
- 为写 Service 提供受控持久化接口。

只读 Repository 不执行质量判断、生命周期分类、Benchmark、报告格式转换或其他业务规则。面向 Provider 的只读查询优先返回不可变 Projection，而非暴露 ORM 对象。

## 8. 数据库层

### 8.1 数据库技术

- MySQL 8.x；
- `utf8mb4` / `utf8mb4_0900_ai_ci`；
- UTC 时间基线；
- SQLAlchemy 2 ORM；
- PyMySQL 驱动。

### 8.2 Schema 演进

数据库基线由根目录有序 SQL Migration 管理：

```text
V001 Core Tables
V002 Relation Tables
V003 Snapshot Tables
V004 Import / Quality Tables
V005 Operation Log
V006 Indexes
V007 Import Batches
V008 Drama Scores
V009 Data Quality Results
V010 Prediction Results
V011 Anomaly Records
V012 Operation Actions
V013 Analysis Explanation / Lineage
```

当前 `backend/alembic/versions` 没有业务 revision，因此部署不能用 Alembic 代替上述 SQL 文件。

### 8.3 数据完整性

数据库通过主键、唯一约束、外键、CHECK、索引和历史 Revision 维护数据一致性。密码只保存 bcrypt 哈希；历史快照、分析结果和操作记录用于追溯，不应被 Read Model 修改。

## 9. 认证与安全架构

```text
Login Request
    ↓
AuthService + bcrypt verify
    ↓
JWT Access Token
    ↓
Bearer Dependency
    ↓
Current ACTIVE User + Role Check
```

安全措施包括：

- 不公开注册；
- bcrypt 密码哈希；
- JWT 有效期；
- USER / ADMINISTRATOR 角色依赖；
- Pydantic 参数校验；
- 文件扩展名、大小和内容校验；
- 统一错误结构，不暴露密码哈希和内部堆栈；
- CSV Formula Injection 防护；
- XLSX write-only 和导出资源释放。

## 10. 模块架构

### 10.1 Drama Profile

```text
DramaProfile.vue → Profile API → DramaProfileService
                  → Six Profile Providers → Existing Repositories
```

该模块为 Aggregation Read Model，单个 Provider 故障被隔离为模块级不可用。

### 10.2 Operation Analytics

```text
Operation Analytics UI → API → OperationAnalyticsService
                       → Providers → Repository
                       → Versioned Rules
```

模块只描述关联和前后变化，不进行因果推断、排名或推荐。

### 10.3 Data Governance

```text
Data Governance UI → API → DataGovernanceService
                   → Providers → DataGovernanceRepository
                   → Freshness / Completeness / Consistency Rules
```

该模块为 SYSTEM scope 的 request-time Read Model，不自动修复或保存治理结果。

### 10.4 Analysis Reporting

```text
Reports.vue → Reporting API → ReportingService
            → Report Providers → ReportingRepository

Schema Registry → Filter Policy / Service / Serializers
```

报告在请求期间序列化并流式返回，不持久化文件或报告快照。

## 11. Availability 与 Snapshot

不同模块根据自身契约使用显式 Availability。共同原则是：

- 不使用 `None` 代替业务状态；
- 区分真实零值、空结果、未计算、历史不足和不可用；
- 保留 Reason 与 Message；
- 聚合模块允许部分可用；
- 单模块错误不应无条件导致整个聚合失败。

`analysis_as_of` 表示分析使用的数据截止时间。能够重建历史的数据源使用 as-of/revision 查询；只能提供当前状态的数据源必须显式标记 `CURRENT_STATE_AT_REQUEST`，不能伪装为历史快照。

## 12. 部署拓扑

推荐生产拓扑：

```text
Browser
   ↓ HTTPS
Reverse Proxy / Static Web Server
   ├── /              → Frontend dist
   └── /api, /health  → Uvicorn/FastAPI
                              ↓
                           MySQL 8
```

推荐使用同源反向代理，避免跨域配置与 Token 暴露风险。前端生产构建不直接连接数据库，后端数据库账号应采用最小必要权限。

## 13. 架构边界总结

系统各层必须保持以下约束：

1. Frontend 只使用公开 API；
2. Router 不执行 SQL 和业务计算；
3. 编排 Service 不访问 ORM；
4. Provider 不调用业务 Service；
5. Rule 不访问数据库和网络；
6. Repository 不承担分析规则；
7. Read Model 不修改源模块结果；
8. 新增持久化结果、Cache、Job 或 Snapshot 前必须进行 Migration Review；
9. 不在现有架构中引入 AI、自动推荐或自动决策。
