# Phase S3 源码冻结记录

## 1. 冻结目的

本记录用于建立短剧数据管理与分析系统的软件验收基线，服务于：

- 软件著作权材料整理；
- 系统验收与验收复核；
- Demo 环境部署与功能演示；
- 后续问题定位和版本追溯。

冻结基线应当对应一个可识别、可检出、可构建的 Git 版本。冻结后如发生源码、API、数据库结构、Migration、ORM 或核心规则修改，必须重新执行构建验证并更新冻结记录。

## 2. 冻结结论

本次结论为：**有条件冻结，不满足干净源码基线条件**。

原因：验证开始时 Git HEAD 可确定，但工作区已有大量未提交源码修改和未跟踪文件。当前构建与测试反映的是“HEAD 加本地未提交内容”的状态，不能仅依靠 HEAD Commit 完整复现。Phase S3 未修改、删除或提交这些既有内容。

在完成未提交内容归属确认、分批审查和提交或移出工作区之前，不应对外声明当前仓库已完成最终源码冻结。

## 3. Git 基线信息

| 项目 | 记录值 |
| --- | --- |
| 仓库分支 | `main` |
| 验证开始时 HEAD | `7181e2d9a00b706fee4f9c86c08a1928ab6d600f` |
| HEAD 提交信息 | `docs(acceptance): add demo and acceptance documents` |
| HEAD 提交时间 | `2026-09-28T18:17:57+08:00` |
| 冻结检查日期 | `2026-09-28` |
| 时区 | `Asia/Shanghai`（UTC+08:00） |
| 远端关系 | `main...origin/main [ahead 94]` |
| 工作区状态 | 非干净：31 个已跟踪文件被修改，238 个未跟踪文件 |
| 暂存区 | Phase S3 文档提交前为空 |

说明：上述 HEAD 是 Phase S3 验证开始时的代码引用点。Phase S3 最终提交只增加三份验收文档，不吸收现有源码改动。最终文档提交 Hash 以 Git 历史为准。

## 4. 软件环境版本

### 4.1 Backend

| 项目 | 版本/范围 | 来源 |
| --- | --- | --- |
| Python | `3.12.14` | `backend/.venv/Scripts/python.exe --version` |
| Backend Framework | FastAPI `0.141.1` | 项目虚拟环境运行时 |
| FastAPI 声明范围 | `>=0.115,<1.0` | `backend/requirements.txt` |
| pytest | `9.1.1` | 项目虚拟环境 |

系统 PATH 中没有可直接调用的 `python` 命令；本次验证使用项目 `backend/.venv`。部署环境应按部署文档激活虚拟环境后再执行 `python`。

### 4.2 Frontend

| 项目 | 版本 |
| --- | --- |
| Node.js | `v24.11.1` |
| npm | `11.6.2` |
| Vue 声明版本 | `^3.5.21` |
| Vite 构建版本 | `7.3.6` |

### 4.3 Database

| 项目 | 版本/范围 |
| --- | --- |
| MySQL Client | MySQL Community Server Client `8.0.45` |
| Migration 范围 | `V001__create_core_tables.sql` 至 `V013__create_analysis_explanation_tables.sql` |
| Phase S3 数据库变更 | 无 |

本次仅确认客户端版本和仓库中的 Migration 文件范围，未连接数据库服务器，也未执行 Migration。

## 5. 当前冻结模块

冻结候选范围包括：

1. 用户认证与权限：登录、JWT Bearer 认证、USER/ADMINISTRATOR 权限；
2. 基础数据管理：Drama、Actor、Director、Company、Platform、Tag 与导入流程；
3. 数据分析模块：Score、Data Quality、Prediction、Anomaly、Operation Action、Explanation 与 Lineage；
4. Drama 360° Profile：已有结果的只读聚合画像；
5. Operation Analytics：Action Effect、Lifecycle、Benchmark；
6. Data Governance：Freshness、Completeness、Consistency 与 Evidence；
7. Reporting Center：Catalog、Preview、CSV Export、XLSX Export；
8. 软件文档和验收文档：Phase S1、Phase S2 与本次 Phase S3 记录。

上述模块的功能边界以已提交设计、实现归档和软件文档为准。本记录不扩展模块能力。

## 6. 产品边界

当前系统明确不包含：

- LLM 或其他 AI 内容生成能力；
- AI Agent；
- 推荐算法或推荐系统；
- 自动运营决策；
- 自动数据修复；
- 机器学习分类平台；
- 运营动作因果推断。

Operation Analytics 仅描述行动前后观察到的指标变化，不声明运营动作导致变化。Reporting 仅导出已有事实，不产生新指标或新业务事实。

## 7. 构建与测试基线

| 检查项 | 结果 | 结论 |
| --- | --- | --- |
| Backend compileall | 通过 | Python 源文件可编译 |
| Backend 全量测试 | 702 通过，4 失败，共收集 706 项 | 未达到全绿基线 |
| Frontend `vue-tsc` | 通过 | 类型检查通过 |
| Frontend production build | 通过 | 产生非阻塞 chunk size 警告 |
| Git 工作区 | 非干净 | 不满足可复现冻结条件 |

详细命令、异常和警告见 `BUILD_VERIFICATION.md`。

## 8. 已知问题

### 8.1 冻结前已有问题

1. 工作区存在 31 个已跟踪修改和 238 个未跟踪文件，包含 Backend、Frontend、文档、脚本、备份和模拟材料；
2. Backend 全量测试有 4 个失败：2 个 Drama Profile 路由枚举失败、1 个 Contracts 源码字符串边界测试失败、1 个基础路由 OpenAPI 断言失败；
3. FastAPI/Starlette 测试环境产生 2 类依赖弃用警告；
4. 前端构建产生两个超过 500 kB 的压缩前 chunk 警告；
5. `main` 相对 `origin/main` 超前 94 个提交，尚未确认远端同步策略；
6. 系统 PATH 未配置 `python` 命令，需要使用项目虚拟环境；
7. 仓库根目录存在未跟踪数据库备份 `backup_before_v007.sql`，需确认保密等级和归档位置。

### 8.2 本阶段产生的问题

本阶段未修改业务代码，未发现由 Phase S3 文档工作引入的业务问题。

首轮测试曾因 pytest 默认临时目录访问权限产生 10 个 setup error；改用显式 `--basetemp` 后错误消失，故归类为验证环境问题，不计入产品测试失败。首轮 Vite 构建也因沙箱目录访问受限失败；在允许访问的同一环境中重跑后构建通过。

## 9. 冻结规则

冻结后禁止：

- 新增业务模块或 API；
- 修改数据库结构、Migration 或 ORM；
- 修改核心业务规则、统计口径或权限模型；
- 将临时文件、构建产物、真实凭据或数据库备份混入验收提交。

冻结后允许：

- 补充软件著作权和验收文档；
- 完善截图、签署页和演示说明；
- 经审批实施必要 Bug 修复。

任何代码修复均应独立提交，说明影响范围，执行完整回归，并生成新的冻结记录。当前 4 个测试失败和脏工作区必须在最终签署前完成处置或获得书面风险接受。

## 10. 最终验收基线检查

| 范围 | 检查内容 | 当前状态 |
| --- | --- | --- |
| 登录 | 用户登录、JWT、权限控制 | 已纳入 S2 验收流程，待环境实操留证 |
| 核心页面 | Dashboard、Drama Profile、Operation Analytics、Data Governance、Reporting | 前端构建包含对应页面，待 S2 流程实操 |
| 报告 | Preview、CSV、XLSX | 已纳入验收清单，待下载实操留证 |
| 软件材料 | Overview、功能说明、用户手册、架构、部署 | `docs/software/` 已具备 |
| 验收材料 | Demo 数据、流程、清单、冻结与构建记录 | Phase S2/S3 已具备 |
| 可复现性 | 干净工作区、唯一 Commit、全绿测试 | 未满足 |

## 11. 签署条件

最终源码冻结签署前必须至少满足：

1. 明确 31 个已跟踪修改和 238 个未跟踪文件的归属；
2. 将验收所需源码提交到独立、可识别的 Commit，或将非产品材料移出验收仓库；
3. 对 4 个 Backend 失败测试完成修复并回归，或形成正式风险接受记录；
4. 在干净检出环境重新执行 Backend compileall、Backend tests、Frontend typecheck 和 build；
5. 记录最终 Commit/Tag，并确认与远端的同步方式。
