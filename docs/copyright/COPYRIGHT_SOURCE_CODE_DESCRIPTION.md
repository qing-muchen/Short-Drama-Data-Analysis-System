# 短剧数据管理与分析系统源程序说明

## 1. 文档目的

本文档说明短剧数据管理与分析系统 V1.0 的源程序组织、主要分层和源程序材料整理原则，用于辅助软件著作权源程序提交。本文档不复制大段源码，也不替代正式源程序交存文件。

## 2. 项目目录结构

```text
Short Drama Data Analysis System/
├── backend/                  # Python/FastAPI 后端、模型、服务与测试
├── frontend/                 # Vue 3/TypeScript 前端
├── database/                 # 数据库 DDL 与 V001–V013 Migration
├── docs/                     # 设计、开发、软件、验收和软著材料
├── scripts/                  # 辅助脚本，需独立判断是否纳入交存
├── assets/                   # 项目静态材料
├── README.md                 # 项目说明
└── PROJECT_MASTER.md         # 项目设计基线
```

正式源程序材料应以最终干净冻结 Commit 为准。`.venv/`、`node_modules/`、`dist/`、`__pycache__/`、`.pytest_cache/`、数据库备份、生成报告和临时工具产物不得作为自产源代码混入交存文件。

## 3. 后端结构

Backend 采用 Python 3.12 和 FastAPI，主要目录职责如下。

### 3.1 Router / API Layer

`backend/routers/` 负责：

- HTTP 路径和方法定义；
- JWT/角色依赖；
- Query、Path、Body 参数接收；
- Service 调用；
- 统一响应和错误转换。

Router 不应直接实现 SQL、ORM 查询或复杂业务计算。

### 3.2 Schema Layer

`backend/schemas/` 使用 Pydantic 定义外部 API 的请求与响应结构。API Schema 与内部 Contracts DTO 分离，避免直接暴露 ORM 对象。

### 3.3 Service Layer

`backend/services/` 负责应用流程编排、参数校验、事务边界以及结果组装。Read Model 模块中的 Service 主要编排 Provider 与 Rule，不直接写数据库。

主要服务域包括：

- 认证与用户；
- 基础数据与导入；
- Score、Prediction、Anomaly、Operation Action；
- Explanation 与 Lineage；
- Drama Profile；
- Operation Analytics；
- Data Governance；
- Reporting。

### 3.4 Contracts

Drama Profile、Operation Analytics、Data Governance 和 Reporting 等模块使用纯 Python DTO 描述层间数据。Contracts 主要采用不可变 dataclass，并避免依赖 ORM、Session、Repository 或 API。

### 3.5 Provider Layer

Provider 将 Repository 返回的投影映射为 Contracts/Rule Input：

- 负责字段映射和数据准备；
- 不返回 ORM Model；
- 不执行 SQL；
- 不调用其他业务 Service；
- 不修改业务数据。

### 3.6 Rule Components

规则组件负责确定性、可解释、可测试的纯计算，例如：

- Operation Analytics 的 Action Effect、Lifecycle、Benchmark；
- Data Governance 的 Freshness、Completeness、Consistency；
- Reporting 的 Filter 和 Export Limit Policy。

规则组件不访问数据库、网络或外部模型，不执行自动修复或推荐。

### 3.7 Repository Layer

`backend/repositories/` 负责：

- ORM/SQLAlchemy 查询；
- 时间窗口和 `analysis_as_of` 过滤；
- Revision 选择；
- Read Model Projection；
- 在写业务模块中执行受 Service 控制的数据访问。

Repository 不应包含生命周期、治理状态或报告格式等上层业务判断。

### 3.8 ORM Model

`backend/models/` 定义用户、主数据、短剧、关系、指标快照、导入、评分、质量、预测、异常、运营行动、解释等数据库映射。ORM 结构必须与已审查的 SQL Migration 保持一致。

### 3.9 Tests

`backend/tests/` 包含 Contracts、Rules、Repository、Provider、Service、API 及模型测试。Phase S3 共收集 706 项测试，702 项通过、4 项失败。正式交存前应按冻结记录完成失败项处置和干净环境复验。

## 4. 前端结构

Frontend 使用 Vue 3、TypeScript 和 Vite。

### 4.1 Views

`frontend/src/views/` 提供用户页面，包括：

- 登录与 Dashboard；
- 基础数据与导入；
- 数据分析页面；
- Drama Profile；
- Operation Analytics；
- Data Governance；
- Reports。

页面负责展示、交互和状态管理，不应重新计算后端分析结果。

### 4.2 API Client

`frontend/src/api/` 封装 HTTP 调用，复用统一 Axios Client、Base URL 和 Token interceptor。API Client 不保存业务数据，也不实现新的认证体系。

### 4.3 TypeScript Types

`frontend/src/types/` 定义与后端 Schema 对应的 TypeScript 类型，包括基础数据、分析结果、Availability、治理证据和报告结构。

### 4.4 Router

`frontend/src/router/` 定义页面路径和登录访问控制。后端权限仍是最终授权边界，前端路由保护不能替代 API 鉴权。

### 4.5 Assets 与构建产物

源代码包括 `.vue`、`.ts`、`.css` 等人工开发文件。`frontend/dist/` 和 `frontend/node_modules/` 是生成物或依赖，不属于申请人编写的源程序，不纳入源程序交存。

## 5. 数据库结构

### 5.1 DDL 与 Migration

`database/` 保存数据库初始化和有序 SQL Migration。当前正式范围为：

- `V001__create_core_tables.sql`；
- `V002__create_relation_tables.sql`；
- `V003__create_snapshot_tables.sql`；
- `V004__create_import_quality_tables.sql`；
- `V005__create_operation_log.sql`；
- `V006__create_indexes.sql`；
- `V007__create_import_batches.sql`；
- `V008__create_drama_scores.sql`；
- `V009__create_data_quality_tables.sql`；
- `V010__create_prediction_results.sql`；
- `V011__create_data_anomaly_records.sql`；
- `V012__create_operation_actions.sql`；
- `V013__create_analysis_explanation_tables.sql`。

### 5.2 主要数据关系

数据库围绕以下关系组织：

- 用户与角色；
- Drama 与 Platform、Actor、Director、Company、Tag；
- Drama 与历史指标 Snapshot/Revision；
- Drama 与 Score、Quality、Prediction、Anomaly；
- Drama 与 Operation Action/History；
- 分析结果与 Explanation/Lineage。

Phase 7–10 的 Profile、Operation Analytics、Data Governance 和 Reporting V1 优先采用请求时 Read Model，不新增结果快照或报告文件表。

## 6. 核心设计特点

### 6.1 分层架构

```text
Frontend
  ↓
API / Router
  ↓
Service
  ↓
Providers / Rule Components
  ↓
Repository
  ↓
Database
```

每层只承担明确职责，依赖方向保持单向。

### 6.2 Read Model

Drama Profile、Operation Analytics、Data Governance 和 Reporting 读取已有事实，在请求期间聚合或判断，不为 V1 新增快照、缓存或报告文件表。

### 6.3 确定性与可解释性

分析和治理规则使用固定输入、明确阈值、规则版本和 Evidence。系统不使用 LLM、AI Agent、推荐模型或自动决策模型。

### 6.4 时间与版本追踪

系统通过 `analysis_as_of`、Revision、algorithm/rule/schema version 等信息标识数据截点和规则版本，避免隐式使用当前状态替代历史事实。

### 6.5 安全导出

Reporting 支持 Registry 驱动的固定列顺序、Filter Policy、导出限制、CSV 公式注入防护、XLSX write-only 生成和 MIME 控制。

## 7. 源程序材料整理建议

1. 先完成 S3 中记录的脏工作区处置；
2. 以最终干净 Commit 或 Tag 导出源程序；
3. 排除第三方依赖、虚拟环境、构建产物、缓存、备份和敏感配置；
4. 保留能够体现主要功能和分层结构的 Backend/Frontend 自研代码；
5. 按受理要求生成连续页码、页眉和软件名称/版本标识；
6. 页数不足或超过常规交存范围时，按受理平台规则选择普通交存或例外交存；
7. 对源程序中的账号、Secret、连接串、真实数据进行安全审查；
8. 将最终材料 Hash、生成日期和来源 Commit 记录在申请工作底稿。

## 8. 不纳入源程序交存的内容

- `.git/`；
- `.venv/`、`node_modules/`；
- `dist/`、`__pycache__/`、`.pytest_cache/`；
- `.env`、真实密码、Token、JWT Secret、数据库连接串；
- 数据库备份和真实业务数据；
- 第三方库源码和许可证文件之外的依赖内容；
- 临时截图、日志、测试缓存和一次性生成结果；
- 未确认归属的 `.reasonix/`、`simulation/` 和一次性脚本。

## 9. 当前基线限制

当前为 Conditional Freeze。Phase S4 开始时 HEAD 为 `989c3e69fb0737bd9866bda6071437e5a74aa57d`，但工作区存在未提交源码和未跟踪 ORM 文件。正式源程序材料不得直接从当前混合工作区无差别打包，应在完成归属确认后从干净基线生成。
