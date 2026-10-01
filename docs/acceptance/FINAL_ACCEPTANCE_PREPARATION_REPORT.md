# Final Acceptance Preparation Report

## 1. 基线信息

- 软件名称：短剧数据管理与分析系统
- 发布版本：V1.0（Release Tag 候选：`v1.0.0`）
- 验收日期：2026-10-01
- Git 分支：`main`
- 产品代码整合基线：`7aa31b3e0017e2ff5df3ec3bae59598bc2fb245c`
- 冻结目标：软件著作权材料、系统验收和 Demo 演示使用的稳定基线

Phase 1–10 已冻结的业务边界保持不变。本阶段没有新增业务模块、API、数据库结构或业务规则。

## 2. 工作区整理

### 2.1 正式基线内容

本轮将此前已通过验收验证、但尚未纳入版本控制的正式产品代码和测试纳入基线，包括批量导入模型与服务、Dashboard/Drama/Tag 前端改进、根路径认证跳转、代理配置及对应测试。代码整合提交为：

`7aa31b3 chore(release): consolidate validated product baseline`

### 2.2 正式文档

历史 Phase 2、3、5、6、7、8 架构与设计文档，以及已有集成验证报告，作为设计追溯材料纳入文档归档提交。

### 2.3 本地保留但不进入 Release 的内容

以下内容保留在本地，但明确排除出 Release 基线：

- `.reasonix/` 与 `reasonix.toml`：本地开发工具运行状态和权限记录。
- `backup_before_v007.sql`：数据库备份，可能包含本地数据，不进入源码发布包。
- `docs/pic/`、`docs/result/`：课程报告截图、DOCX/PDF 与中间 QA 生成物。
- `scripts/*.py`、`scripts/*.ps1`：一次性课程报告生成、审计和格式化辅助脚本。
- `simulation/`：历史模拟数据与生成工具。其中 `simulation/run_import_flow.py` 含本机数据库凭据，未经脱敏和独立安全审查不得纳入 Release。

这些排除项通过 `.gitignore` 显式分类；未删除任何用户文件。

## 3. Demo 验收环境

### 3.1 数据库

- 专用数据库：`short_drama_acceptance_v1`
- 数据库版本：MySQL 8.0.45
- Migration：V001–V013 全部成功执行
- 初始化日期：2026-10-01
- 数据库用途：仅用于本地验收和演示，不作为生产数据库

迁移脚本原文件未修改。由于脚本内固定使用开发库名，验收执行器只在内存中将目标库替换为专用验收库，并使用支持 `DELIMITER` 的解析方式执行 V003；数据库结构仍完全来自 V001–V013。

### 3.2 Demo 账号

| 账号 | 角色 | 验收用途 |
| --- | --- | --- |
| `admin_demo` | `ADMINISTRATOR` | 完整功能和管理能力演示 |
| `user_demo` | `USER` | 普通查询权限演示 |

文档不记录演示密码。账号密码只保存在本地验收环境中。

### 3.3 Demo 数据

验收库包含：

- 5 部短剧、1 个平台、2 个标签；
- 235 条带时间截点的指标快照；
- 5 条评分结果；
- 数据质量规则与全局质量结果；
- 5 条预测结果；
- 2 条异常记录；
- 2 条运营行动及历史/来源数据；
- Explanation 与 Data Lineage 基础记录。

数据覆盖 Dashboard、Drama Profile、Operation Analytics、Data Governance 和 Reporting 的主要查询路径。

## 4. 浏览器验收结果

### 4.1 登录与权限

- `admin_demo` 登录成功。
- `user_demo` 登录成功。
- 未认证访问受保护 Reporting API 返回 401。
- USER 与 ADMINISTRATOR 均可访问授权的只读分析和报告功能。

### 4.2 功能流程

| 模块 | 验收结果 | 关键结果 |
| --- | --- | --- |
| Dashboard | 通过 | 5 部短剧、累计播放及榜单/标签正常展示 |
| Drama Profile | 通过 | Score、Quality、Prediction、Anomaly、Action 聚合展示正常 |
| Operation Analytics | 通过 | Action Effect、Lifecycle、Benchmark 均可查询；Lifecycle 为 `STABLE`，Benchmark 为 `AVAILABLE` |
| Data Governance | 通过 | Overview、Freshness、Completeness、Consistency 与 Evidence 正常展示 |
| Reporting | 通过 | 六类 Catalog、5 行 Preview、CSV/XLSX 下载流程正常 |

Drama Profile 的 Explanation 在本次精简 Demo 数据中显示不可用，属于演示数据语义覆盖不足，不影响 Profile 其余聚合能力或生产代码测试。

Freshness 显示 `WARNING` 且 Availability 为 `AVAILABLE`，原因是 Demo 最新数据延迟超过 86400 秒；该状态用于展示真实治理 Evidence，不属于请求失败。

### 4.3 报告导出

- 未确认导出时返回 409，并给出需确认的 5 行数据范围。
- 确认后 CSV 返回 200、`text/csv; charset=utf-8`、UTF-8 BOM 和受控文件名。
- 确认后 XLSX 返回 200、正确 MIME、受控文件名与有效 ZIP/XLSX 文件头。
- 前端仅接收 Blob 并触发浏览器下载，不解析 CSV、不生成 XLSX。

## 5. 截图材料清单

本轮浏览器验收已捕获并核验以下视图：

1. Drama Profile 综合画像；
2. Operation Analytics Action Effect；
3. Operation Analytics Lifecycle；
4. Operation Analytics Benchmark；
5. Data Governance Overview；
6. Data Governance Evidence Drawer；
7. Reports Catalog；
8. Reports Preview；
9. XLSX 下载成功状态。

最终软著/验收截图导出时，应继续使用 Demo 账号和 Demo 数据，遮盖账号凭据，并补充登录页、Dashboard、CSV 下载和 USER 权限拦截截图。

## 6. 干净环境复现

从提交 `7aa31b3` 使用 `git archive` 创建不含本机环境文件的独立副本，并执行全新依赖安装与验证。

### 6.1 Backend

- Python：3.12.14
- 全新虚拟环境：创建成功
- `pip install -r backend/requirements.txt`：成功
- `python -m compileall -q backend`：成功
- `python -m pytest backend/tests -q`：706/706 通过

仅出现 Starlette TestClient 关于 httpx 兼容层的弃用提示，不影响运行结果。

### 6.2 Frontend

- Node.js：v24.11.1
- npm：11.6.2
- `npm ci`：成功，112 packages，0 vulnerabilities
- `npm exec vue-tsc -- --noEmit`：成功
- `npm run build`：成功，Vite 7.3.6，2361 modules transformed

生产构建存在大于 500 kB 的 chunk size warning，属于非阻塞性能提示；未影响构建产物生成。

## 7. 最终测试结果

| 检查项 | 结果 |
| --- | --- |
| 主工作区 Backend 全量测试 | 706/706 通过 |
| 主工作区 Backend compileall | 通过 |
| 主工作区 Frontend 类型检查 | 通过 |
| 主工作区 Frontend production build | 通过 |
| 干净副本 Backend 全量测试 | 706/706 通过 |
| 干净副本 Backend compileall | 通过 |
| 干净副本 Frontend npm ci | 通过，0 vulnerabilities |
| 干净副本 Frontend 类型检查 | 通过 |
| 干净副本 Frontend production build | 通过 |
| API/浏览器核心验收流程 | 通过 |

## 8. 已知非阻塞问题

1. Starlette TestClient/httpx 兼容层存在弃用警告，未来依赖升级时处理。
2. 前端 production build 存在大 chunk 提示，后续可在不改变业务契约的性能优化阶段处理。
3. 精简 Demo 数据未覆盖 Drama Profile Explanation 的全部语义输入。
4. 本地历史 `simulation/run_import_flow.py` 含硬编码数据库凭据，已排除出 Release，后续如需复用必须先脱敏重构并单独审查。
5. 本地课程报告、截图和备份作为外部验收资产保存，不包含在源码 Release Tag 中。

以上问题均不影响核心用户流程、全量测试、生产构建或 Release 基线复现。

## 9. 冻结与发布结论

完成以下条件后可将状态从 Conditional Freeze 更新为 Final Freeze：

1. 正式代码、正式测试和设计追溯文档均已提交；
2. Git 已跟踪工作区无未提交修改；
3. 本地辅助资产已明确排除且未删除；
4. 主工作区与干净副本验证全部通过；
5. 创建注释 Tag `v1.0.0` 指向最终验收提交。

Release Tag 只标识可复现的软件源码、测试、Migration 与正式文档，不包含本地验收数据库、密码、备份或课程报告中间产物。

