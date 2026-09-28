# Phase S2 软件验收检查清单

## 1. 使用说明

本清单用于短剧数据管理与分析系统 V1.0 的演示验收。执行人应在“结果”栏填写 `Pass`、`Fail` 或 `N/A`，并在“证据/备注”栏记录截图文件名、错误编号或说明。

判断原则：

- `Pass`：实际结果符合文档和现有契约；
- `Fail`：可复现且与预期不符；
- `N/A`：本次验收明确不适用，必须说明原因；
- Availability 的 EMPTY、INSUFFICIENT、NOT_AVAILABLE 若与 Demo 数据和契约一致，不应自动判定为 Fail；
- 不允许通过修改代码、数据库 Schema 或规则现场改变验收结果。

## 2. 验收基本信息

| 项目 | 内容 |
| --- | --- |
| 软件版本/Commit | |
| 验收日期 | |
| 验收人员 | |
| 演示人员 | |
| 环境地址 | |
| Database/备份标识 | |
| `T_demo`（UTC） | |
| 浏览器及版本 | |

## 3. 环境与数据检查

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| ENV-01 | Database | MySQL 8 可用 | 数据库连接正常 |  |  |
| ENV-02 | Database | V001–V013 | 全部按顺序应用 |  |  |
| ENV-03 | Backend | Health | `/health` 返回 `status=ok` |  |  |
| ENV-04 | Frontend | 页面访问 | 登录页正常加载 |  |  |
| ENV-05 | API | `/api/v1` | Frontend 可调用 Backend |  |  |
| ENV-06 | Time | UTC 基线 | `T_demo` 已记录且时间明确 |  |  |
| ENV-07 | Demo Data | 主数据 | 5 部 Demo Drama 及关系存在 |  |  |
| ENV-08 | Demo Data | 历史指标 | 4 部同平台 Drama 有 30 日完整数据 |  |  |
| ENV-09 | Demo Data | Action 窗口 | Before/After 各 7 日完整 |  |  |
| ENV-10 | Security | 敏感信息 | 页面和截图无密码、Token、连接串 |  |  |

## 4. 登录与权限

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| AUTH-01 | 登录 | `user_demo` 登录 | 登录成功并进入 Dashboard |  | `01_login.png` |
| AUTH-02 | 登录 | `admin_demo` 登录 | 登录成功并进入 Dashboard |  |  |
| AUTH-03 | 身份 | 当前用户 | 正确显示/识别角色 |  |  |
| AUTH-04 | 路由 | 未登录访问 | 跳转登录页或 API 返回 401 |  |  |
| AUTH-05 | USER权限 | 查询页面 | USER 可访问授权查询和分析 |  |  |
| AUTH-06 | USER权限 | 管理写操作 | 不开放或后端返回 403 |  | `14_permission.png` |
| AUTH-07 | ADMIN权限 | 管理入口 | 管理员可访问导入等授权入口 |  |  |
| AUTH-08 | 安全 | 密码哈希 | 页面/API 不返回 password_hash |  |  |

## 5. Dashboard 与导航

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| DASH-01 | Dashboard | 页面加载 | 无整体阻塞错误 |  | `02_dashboard.png` |
| DASH-02 | Dashboard | 核心数量 | 数量指标正确显示 |  |  |
| DASH-03 | Dashboard | 播放与互动 | 总播放量、平均互动率可读 |  |  |
| DASH-04 | Dashboard | 排行 | Heat/Growth/Potential 有 Demo 数据 |  |  |
| DASH-05 | Dashboard | 趋势 | 近 30 日趋势正常渲染 |  |  |
| DASH-06 | Dashboard | 质量摘要 | Quality 状态正常显示 |  |  |
| DASH-07 | Dashboard | 标签 | 热门标签数据和图表正常 |  |  |
| DASH-08 | Dashboard | 刷新 | 可重新加载且状态正常 |  |  |
| DASH-09 | Navigation | Profile入口 | 可进入短剧/Profile 路径 |  |  |
| DASH-10 | Navigation | Phase 8–10入口 | Analytics、Governance、Reports 均可访问 |  |  |

## 6. 数据管理与导入

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| DATA-01 | Drama | 列表加载 | 分页列表正常 |  |  |
| DATA-02 | Drama | 条件筛选 | 名称/状态/标签筛选有效 |  |  |
| DATA-03 | Drama | 详情 | 基础信息和关系正确 |  |  |
| DATA-04 | Master Data | Actor/Platform/Tag | 列表和查询正常 |  |  |
| IMP-01 | Import | 文件类型 | 接受合法 CSV/XLSX |  |  |
| IMP-02 | Import | 校验 | 创建任务并显示校验状态 |  |  |
| IMP-03 | Import | 错误列表 | 错误行和原因可查看 |  |  |
| IMP-04 | Import | 确认 | 管理员可确认合格任务 |  |  |
| IMP-05 | Import | USER权限 | 普通用户不能执行管理员导入 |  |  |

## 7. 基础数据分析

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| ANA-01 | Score | 排行 | Demo score_date 排行正常 |  | `03_score_prediction.png` |
| ANA-02 | Score | 维度 | Heat/Growth/Engagement/Lifecycle/Total 完整 |  |  |
| ANA-03 | Score | 版本 | 等级、算法版本和分析时间可见 |  |  |
| ANA-04 | Quality | 当前结果 | 总分、等级和四维度显示 |  |  |
| ANA-05 | Quality | 历史/规则 | 历史和规则信息可查看 |  |  |
| ANA-06 | Prediction | 最新结果 | 目标日期、预测值和版本显示 |  |  |
| ANA-07 | Prediction | 历史 | 主剧历史预测可查看 |  |  |
| ANA-08 | Anomaly | 统计和列表 | Demo 异常记录显示 |  |  |
| ANA-09 | Anomaly | 筛选 | Metric/Severity/Status 筛选有效 |  |  |
| ANA-10 | Anomaly | Evidence | 基线、实际值、偏差和摘要显示 |  |  |
| ANA-11 | Availability | 历史不足 | 不以 0 伪造缺失结果 |  |  |

## 8. 运营行动与解释血缘

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| ACT-01 | Actions | 列表/统计 | OPEN/IN_PROGRESS/COMPLETED 可展示 |  |  |
| ACT-02 | Actions | 详情 | 标题、优先级、负责人、状态正确 |  |  |
| ACT-03 | Actions | Source | ANOMALY/MANUAL 来源及摘要显示 |  |  |
| ACT-04 | Actions | History | CREATE/ASSIGN/STATUS/COMMENT 历史显示 |  |  |
| ACT-05 | Actions | 权限 | 写操作符合 USER/ADMIN 规则 |  |  |
| EXP-01 | Explanation | 摘要 | 主剧最新解释可查看 |  |  |
| EXP-02 | Lineage | 血缘 | 来源、版本和分析时间可追溯 |  |  |

## 9. Drama Profile

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| PROF-01 | Profile | 路由与选择 | 主剧 Profile 正常打开 |  | `04_drama_profile.png` |
| PROF-02 | Profile | Drama Header | 名称和基础信息正确 |  |  |
| PROF-03 | Profile | Performance | Score 摘要和版本显示 |  |  |
| PROF-04 | Profile | Quality | Quality 状态和风险显示 |  |  |
| PROF-05 | Profile | Trend | Prediction/趋势显示 |  |  |
| PROF-06 | Profile | Risk | 异常数量和最近异常显示 |  |  |
| PROF-07 | Profile | Operations | 行动状态和最近行动显示 |  |  |
| PROF-08 | Profile | Explanations | 摘要和血缘入口显示 |  |  |
| PROF-09 | Profile | Availability | 状态和 Reason 正确 |  |  |
| PROF-10 | Profile | 异常隔离 | 单模块缺失不导致整页失败 |  |  |

## 10. Operation Analytics

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| OPS-01 | Action Effect | 查询 | 主 Action 返回结果 |  | `05_operation_effect.png` |
| OPS-02 | Action Effect | 时间窗口 | T0、Before 7日、After 7日正确 |  |  |
| OPS-03 | Action Effect | 指标变化 | 值、差值和方向显示 |  |  |
| OPS-04 | Action Effect | 非因果语义 | 不出现“导致增长”等结论 |  |  |
| OPS-05 | Lifecycle | GROWTH | DEMO_DRAMA_001 符合预期 |  | `06_lifecycle_benchmark.png` |
| OPS-06 | Lifecycle | STABLE | DEMO_DRAMA_002 符合预期 |  |  |
| OPS-07 | Lifecycle | DECLINE | DEMO_DRAMA_003 符合预期 |  |  |
| OPS-08 | Lifecycle | 不足状态 | DEMO_DRAMA_005 明确显示 |  |  |
| OPS-09 | Benchmark | 比较范围 | 同平台 4 部 Drama |  |  |
| OPS-10 | Benchmark | 时间窗口 | 滚动 30 个完整自然日 |  |  |
| OPS-11 | Benchmark | 统计 | 成员指标和组中位数显示 |  |  |
| OPS-12 | Benchmark | 边界 | 无排名、最佳或推荐 |  |  |
| OPS-13 | Availability | 状态 | AVAILABLE/PARTIAL/INSUFFICIENT 等正确 |  |  |

## 11. Data Governance

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| GOV-01 | Overview | SYSTEM scope | Scope 和 analysis_as_of 正确 |  | `07_governance_overview.png` |
| GOV-02 | Overview | Overall Availability | 状态与模块结果一致 |  |  |
| GOV-03 | Freshness | 状态 | 最新时间、延迟和版本显示 |  |  |
| GOV-04 | Completeness | 状态 | coverage、missing items 和版本显示 |  |  |
| GOV-05 | Consistency | 状态 | issue count 和版本显示 |  |  |
| GOV-06 | Evidence | Drawer | 可打开/关闭且内容完整 |  | `08_governance_evidence.png` |
| GOV-07 | Evidence | 字段 | Type、Message、Source、Metadata 显示 |  |  |
| GOV-08 | Evidence | 分页 | 分页不影响其他模块 |  |  |
| GOV-09 | Boundary | 不自动修复 | 无修改或修复入口 |  |  |
| GOV-10 | Isolation | 单模块失败 | 其他模块继续显示 |  |  |

## 12. Reporting

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| RPT-01 | Catalog | 六类Report | 全部显示且来自API |  | `09_reports_catalog.png` |
| RPT-02 | Catalog | Schema信息 | Version、Columns、Filters、Formats 显示 |  |  |
| RPT-03 | Filter | 动态输入 | 按 API Filter Definition 展示 |  |  |
| RPT-04 | Preview | 请求成功 | Demo Filter 返回数据 |  | `10_reports_preview.png` |
| RPT-05 | Preview | Snapshot | as_of、timezone、semantics 显示 |  |  |
| RPT-06 | Preview | Column顺序 | 与 Schema 顺序一致 |  |  |
| RPT-07 | Preview | NULL语义 | NULL 不显示为 0 |  |  |
| RPT-08 | Availability | 五种状态契约 | 状态、Reason、Message 原样展示 |  |  |
| RPT-09 | Export | 确认 | Report、格式、行数、截点显示 |  | `11_export_confirmation.png` |
| RPT-10 | CSV | 下载 | 文件名、MIME、扩展名正确 |  | `12_csv_result.png` |
| RPT-11 | CSV | 内容 | BOM、CRLF、Header、中文、NULL 正确 |  |  |
| RPT-12 | CSV | 公式安全 | 潜在公式内容已安全转义 |  |  |
| RPT-13 | XLSX | 下载 | MIME、扩展名和文件可打开 |  | `13_xlsx_result.png` |
| RPT-14 | XLSX | 内容 | Sheet、Header、值和NULL正确 |  |  |
| RPT-15 | XLSX | 安全 | 无 Macro/External Link，公式为文本 |  |  |
| RPT-16 | Export | 再确认 | 服务器行数变化时要求再次确认 |  |  |
| RPT-17 | Export | 限制说明 | CSV/XLSX/25MiB限制明确 |  |  |
| RPT-18 | Isolation | 导出失败 | Catalog和Preview不被清空 |  |  |

## 13. 架构与只读边界抽查

| 编号 | 模块 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- | --- |
| ARC-01 | Frontend | 业务计算 | 不在前端重算分析结果 |  |  |
| ARC-02 | Profile | Read Model | 不触发新的分析计算 |  |  |
| ARC-03 | Operation Analytics | No Causality | 只描述关联与变化 |  |  |
| ARC-04 | Governance | No Mutation | 不修改或补齐数据 |  |  |
| ARC-05 | Reporting | No Persistence | 不保存报告文件/快照/缓存 |  |  |
| ARC-06 | Database | No New Migration | 当前最高为 V013 |  |  |
| ARC-07 | Product Boundary | No AI | 无 LLM、Agent、推荐、自动决策 |  |  |

## 14. 截图与材料检查

| 编号 | 检查项 | 预期结果 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- |
| PIC-01 | 登录截图 | 无密码、Token |  | `01_login.png` |
| PIC-02 | Dashboard截图 | 概览和入口完整 |  | `02_dashboard.png` |
| PIC-03 | Profile截图 | 六模块可识别 |  | `04_drama_profile.png` |
| PIC-04 | Operation截图 | Action/Lifecycle/Benchmark |  | `05_*`, `06_*` |
| PIC-05 | Governance截图 | Overview与Evidence |  | `07_*`, `08_*` |
| PIC-06 | Reports截图 | Catalog/Preview/Confirm |  | `09_*`–`11_*` |
| PIC-07 | Export截图 | CSV和XLSX结果 |  | `12_*`, `13_*` |
| PIC-08 | 敏感信息检查 | 全部截图通过脱敏检查 |  |  |
| PIC-09 | 文档引用 | 截图与检查项编号关联 |  |  |

## 15. 验收结果汇总

| 分类 | Pass | Fail | N/A | 备注 |
| --- | ---: | ---: | ---: | --- |
| 环境与数据 |  |  |  |  |
| 登录与权限 |  |  |  |  |
| Dashboard |  |  |  |  |
| 数据管理与导入 |  |  |  |  |
| 基础分析 |  |  |  |  |
| Drama Profile |  |  |  |  |
| Operation Analytics |  |  |  |  |
| Data Governance |  |  |  |  |
| Reporting |  |  |  |  |
| 架构边界 |  |  |  |  |
| 截图材料 |  |  |  |  |

## 16. 问题记录

| 问题编号 | 检查项 | 严重程度 | 复现步骤 | 实际结果 | 处理状态 |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

严重程度建议：

- Blocker：主流程无法继续；
- Major：核心功能不符合契约但有替代路径；
- Minor：不影响核心结果的展示或文档问题。

## 17. 验收签署

| 角色 | 姓名/标识 | 结论 | 日期 | 签名/备注 |
| --- | --- | --- | --- | --- |
| 演示负责人 |  |  |  |  |
| 技术负责人 |  |  |  |  |
| 验收人员 |  |  |  |  |

最终结论：

- [ ] 通过；
- [ ] 有条件通过，问题已记录；
- [ ] 不通过，需要独立修复阶段。

验收结束后应恢复或封存 Demo 数据基线，停用不再使用的演示账号，并清理本地导出文件。Phase S2 不授权现场修改业务代码或数据库结构。
