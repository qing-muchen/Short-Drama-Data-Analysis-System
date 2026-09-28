# Phase S2 软件验收与演示流程

## 1. 目的与原则

本文档定义短剧数据管理与分析系统 V1.0 的标准验收演示顺序。流程以真实用户操作为主线，覆盖系统登录、Dashboard、核心分析、Drama Profile、Operation Analytics、Data Governance 和 Reporting。

验收遵循以下原则：

- 使用独立 Demo 数据库和虚构数据；
- 全流程使用同一个 `T_demo`；
- 不临时修改代码、规则、数据库 Schema 或权限；
- 不把空状态、历史不足或 Availability 误判为系统错误；
- Action Effect 只描述行动前后变化，不作因果声明；
- 记录实际结果、截图和异常，不为通过验收而篡改输出。

## 2. 验收信息记录

| 项目 | 记录 |
| --- | --- |
| 软件名称 | 短剧数据管理与分析系统 |
| 软件版本/Commit | ______________________________ |
| 验收日期 | ______________________________ |
| 验收人员 | ______________________________ |
| 演示人员 | ______________________________ |
| Frontend URL | ______________________________ |
| Backend URL | ______________________________ |
| Database | ______________________________ |
| `T_demo`（UTC） | ______________________________ |
| Demo 数据版本/备份 | ______________________________ |
| 浏览器及版本 | ______________________________ |

## 3. 演示账号

| 用户名 | 角色 | 演示用途 | 密码记录 |
| --- | --- | --- | --- |
| `admin_demo` | ADMINISTRATOR | 管理入口、导入、计算和完整访问 | 不在文档记录，通过安全渠道提供 |
| `user_demo` | USER | 普通查询、分析查看、治理和报告导出 | 不在文档记录，通过安全渠道提供 |

建议主流程先使用 `user_demo` 展示普通用户能力，再使用 `admin_demo` 补充管理员专属操作和权限对照。

## 4. 验收前置检查

### 4.1 环境

1. MySQL 8 正常运行；
2. V001–V013 已按顺序应用；
3. Backend 环境变量正确；
4. `GET /health` 返回 `{"status":"ok"}`；
5. Frontend 可以访问 Backend `/api/v1`；
6. 浏览器允许下载文件；
7. 系统时间和数据库时间使用 UTC 基线；
8. 已关闭会泄露 Token、密码或连接串的调试输出。

### 4.2 数据

1. `admin_demo` 和 `user_demo` 均为 ACTIVE；
2. `DEMO_DRAMA_001–005` 存在；
3. 主剧 `DEMO_DRAMA_001` 的 Score、Quality、Prediction、Anomaly、Action、Explanation 已准备；
4. Platform A 下至少 4 部 Drama 有 30 日完整 Metric；
5. Action Effect 主 Action 的 Before/After 各 7 日完整；
6. Governance 主基线可查询；
7. 六类 Report 有可预览数据；
8. 数据库已建立演示前恢复点。

### 4.3 浏览器

1. 使用新建浏览器会话或清理旧 Token；
2. 打开开发者工具 Network 页备用，但正式截图不显示敏感 Header；
3. 设置统一窗口尺寸和缩放比例；
4. 准备单独的安全下载目录；
5. 关闭包含个人信息的其他标签页和通知。

## 5. 流程 1：系统登录与权限

### 5.1 普通用户登录

```text
打开系统
    ↓
输入 user_demo 账号密码
    ↓
单击登录
    ↓
进入 Dashboard
```

操作步骤：

1. 访问 Frontend URL；
2. 确认显示“短剧数据管理与分析系统”登录页；
3. 输入 `user_demo` 和安全渠道提供的密码；
4. 单击“登录”；
5. 确认进入 `/dashboard`；
6. 刷新页面，确认有效会话下仍可访问；
7. 访问一个普通用户允许的分析页面。

预期结果：

- 登录成功；
- Dashboard 正常加载；
- USER 可访问查询与分析页面；
- 管理员专属写入口不应向 USER 开放；
- 请求使用 Bearer Token，页面不显示 Token 内容。

### 5.2 权限对照

1. 退出或清理当前会话；
2. 使用 `admin_demo` 登录；
3. 确认管理员可看到数据导入等授权入口；
4. 不必在主演示中执行破坏性操作；
5. 对一个无权限场景进行安全验证时，预期返回 403。

验收证据：登录页、USER Dashboard、ADMINISTRATOR Dashboard 各一张截图；禁止截取密码或 Token。

## 6. 流程 2：Dashboard 展示

```text
登录成功
    ↓
Dashboard 加载
    ↓
查看概览 / 排行 / 趋势 / 质量 / 标签
    ↓
确认模块导航
```

操作步骤：

1. 查看核心数量指标；
2. 查看总播放量、平均互动率和质量问题数；
3. 查看 Heat、Growth、Potential 排行；
4. 查看近 30 日运营趋势；
5. 查看数据质量摘要和热门标签；
6. 核对 Profile、Operation Analytics、Data Governance、Reports 等入口；
7. 单击“刷新数据”，确认页面可重新加载。

预期结果：

- 页面无整体阻塞错误；
- 图表和表格与 Demo 数据一致；
- 数量和趋势不出现 `undefined`、`NaN` 或未格式化空值；
- 模块入口均指向正确认证路由；
- 单区域加载失败时不会清空其他成功区域。

## 7. 流程 3：基础分析抽查

### 7.1 Score

1. 进入综合评分；
2. 选择 Demo score_date；
3. 查看排行和等级分布；
4. 查看 `DEMO_DRAMA_001` 的维度分数、总分、等级和算法版本。

### 7.2 Quality

1. 进入 Phase 2 数据质量页面；
2. 查看总分、等级和四个维度；
3. 查看历史结果和规则信息。

### 7.3 Prediction

1. 进入播放趋势预测；
2. 选择 `DEMO_DRAMA_001`；
3. 查看最新预测、目标日期和历史列表；
4. 核对 Moving Average V1.0 与 `analysis_as_of`。

### 7.4 Anomaly

1. 进入异常检测；
2. 查看统计和列表；
3. 筛选 OPEN 或指定 Severity；
4. 查看主剧异常 Evidence。

预期结果：四类结果均来自后端，版本和时间可见；前端不重新计算。

## 8. 流程 4：Drama 360° Profile

```text
Dashboard
    ↓
短剧管理 / Drama 360° 入口
    ↓
选择 DEMO_DRAMA_001
    ↓
进入 /dramas/{id}/profile
    ↓
查看 360° 画像
```

操作步骤：

1. 从 Dashboard 进入短剧列表；
2. 搜索“星光之下”或代码 `DEMO_DRAMA_001`；
3. 进入该短剧的 Profile；
4. 查看 Drama Header；
5. 查看 Performance、Quality、Trend；
6. 查看 Risk、Operations、Explanations；
7. 核对算法/规则版本和分析时间；
8. 使用合法导航入口进入一个详情页面后返回；
9. 可选：打开 `DEMO_DRAMA_005`，确认模块不足不会使整页失败。

预期结果：

- 基础信息与选择的 Drama 一致；
- 六个模块聚合正常；
- Availability 明确；
- 当前无异常与尚未检测可以区分；
- 单模块不可用不影响其他模块；
- 页面不触发新的评分、预测或异常检测。

## 9. 流程 5：Operation Analytics

### 9.1 Action Effect

```text
进入运营分析中心
    ↓
选择/查询主 Action
    ↓
查看 Before / After
    ↓
查看指标变化与 Availability
```

验证：

- T0 来自首个 COMPLETED History；
- Before/After 均为 7 个完整业务日；
- 显示变化方向、规则版本和分析时间；
- 页面或结果包含非因果语义；
- 不出现“该行动导致增长”等结论。

### 9.2 Lifecycle

1. 查询 `DEMO_DRAMA_001`，预期 GROWTH；
2. 查询 `DEMO_DRAMA_002`，预期 STABLE；
3. 查询 `DEMO_DRAMA_003`，预期 DECLINE；
4. 查询 `DEMO_DRAMA_005`，预期历史不足或明确不可用；
5. 核对规则版本和双 7 日证据。

### 9.3 Benchmark

1. 选择 `PLATFORM_DEMO_A`；
2. 输入/选择 `DEMO_DRAMA_001–004`；
3. 发起 Benchmark；
4. 查看滚动 30 日窗口；
5. 查看成员指标和组中位数；
6. 确认没有排名、最佳短剧或推荐。

预期结果：Action Effect、Lifecycle、Benchmark 可分别加载，Availability 与 Demo 数据一致，单模块错误不影响其他区域。

## 10. 流程 6：Data Governance

```text
进入数据治理中心
    ↓
查看 Overview
    ↓
查看 Freshness
    ↓
查看 Completeness
    ↓
查看 Consistency
    ↓
打开 Evidence Drawer
```

操作步骤：

1. 进入 `/data-governance`；
2. 核对 scope 为 SYSTEM；
3. 核对 `analysis_as_of` 与本次请求；
4. 查看总体 Availability；
5. 查看 Freshness status、delay 和 rule version；
6. 查看 Completeness coverage、missing items 和 rule version；
7. 查看 Consistency issue count 和 rule version；
8. 分别打开 Evidence Drawer；
9. 核对 Evidence Type、Message、Source、Metadata；
10. 若 Evidence 分页，验证翻页不影响其他卡片。

预期结果：

- 三类状态均由 API 返回；
- 正常主基线显示真实 HEALTHY/AVAILABLE 或可解释的实际状态；
- Evidence 足以定位判断依据但不复制完整业务对象；
- 页面不提供自动修复、推荐或 AI 解释；
- 单模块请求失败不会清空其他模块。

## 11. 流程 7：Reporting

### 11.1 Catalog

1. 从 Dashboard 进入“分析报告中心”；
2. 确认 URL 为 `/reports`；
3. 核对六类 Report；
4. 选择一个报告；
5. 查看 description、schema_version、supported_formats 和 snapshot_semantics。

### 11.2 Filter 与 Preview

1. 选择 `DRAMA_CATALOG` 或 `SCORE_RESULTS`；
2. 使用 Catalog 返回的 Filter 输入 Demo 条件；
3. 可选填写统一 `T_demo`；
4. 将 Preview 行数设置为 20；
5. 单击“查看预览”；
6. 核对 Availability、Snapshot、总行数和来源版本；
7. 核对表格 Column 顺序与 Catalog 一致；
8. 核对 NULL 显示不被替换为 0。

### 11.3 CSV Export

1. 选择 CSV；
2. 打开确认对话框；
3. 核对 Report Type、格式、行数和截点；
4. 确认下载；
5. 核对扩展名、文件名和中文内容；
6. 使用文本编辑器检查 UTF-8 BOM、CRLF 和 Column 顺序；
7. 使用专用安全 Demo 值检查公式内容已转义。

### 11.4 XLSX Export

1. 选择 XLSX；
2. 确认并下载；
3. 使用 Excel 或兼容软件打开；
4. 核对 Sheet、Header、类型、NULL 和中文内容；
5. 确认潜在公式按文本显示；
6. 确认文件没有 Macro 或外部链接提示。

### 11.5 确认与限制

1. 对无有效 Filter 的报告发起导出；
2. 确认服务器要求精确行数确认；
3. 再次确认后下载；
4. 不通过人为扩大 Demo 数据触发 25 MiB 压力测试；
5. 验收时说明 CSV 10,000 行、XLSX 5,000 行硬上限。

预期结果：Catalog、Preview、CSV、XLSX 均可用，导出 Blob 由浏览器直接下载，前端不生成文件。

## 12. 流程 8：权限收尾验证

1. 使用 USER 尝试访问管理员专属写操作；
2. 确认后端返回 403 或界面不开放该操作；
3. 清除认证状态后访问 `/reports` 或 `/data-governance`；
4. 确认跳转登录页或 API 返回 401；
5. 重新登录，确认系统恢复正常；
6. 不在验收时修改真实账号或生产数据。

## 13. 截图规划

建议将最终截图保存到验收材料专用目录，文件名使用序号和功能名称。不得提交包含密码、Token、数据库连接串或真实敏感数据的截图。

| 序号 | 建议文件名 | 页面/对象 | 截图目的 |
| --- | --- | --- | --- |
| 01 | `01_login.png` | 登录页 | 软件名称、账号输入和登录入口 |
| 02 | `02_dashboard.png` | Dashboard | 核心指标、排行、趋势和导航 |
| 03 | `03_score_prediction.png` | 分析页 | Score 或 Prediction 版本化结果 |
| 04 | `04_drama_profile.png` | Drama Profile | 单剧多模块 360° 聚合 |
| 05 | `05_operation_effect.png` | Operation Analytics | Action Before/After 和非因果语义 |
| 06 | `06_lifecycle_benchmark.png` | Operation Analytics | Lifecycle 与 Benchmark |
| 07 | `07_governance_overview.png` | Data Governance | Overall、Freshness、Completeness、Consistency |
| 08 | `08_governance_evidence.png` | Evidence Drawer | Evidence Type、Source、Metadata |
| 09 | `09_reports_catalog.png` | Reports | Catalog、Filter 和 Schema Version |
| 10 | `10_reports_preview.png` | Reports | Snapshot、Availability、Column、Rows |
| 11 | `11_export_confirmation.png` | Export Dialog | Report Type、格式、行数确认 |
| 12 | `12_csv_result.png` | CSV 文件 | Header、中文、NULL、公式安全 |
| 13 | `13_xlsx_result.png` | XLSX 文件 | Sheet、Header、值和安全打开 |
| 14 | `14_permission.png` | 权限结果 | USER/ADMINISTRATOR 权限差异 |

截图要求：

- 浏览器窗口尺寸一致；
- 页面标题、关键状态和版本信息清晰；
- 不使用裁剪掩盖错误；
- 可对密码、Token、连接串进行不可逆遮盖；
- 文件导出截图应使用 Demo 数据；
- 每张截图在验收报告中引用对应检查项编号。

## 14. 异常记录方式

发现问题时记录：

| 字段 | 内容 |
| --- | --- |
| 检查项编号 | 例如 `RPT-04` |
| 时间 | UTC/本地时区明确标注 |
| 用户角色 | USER / ADMINISTRATOR |
| 页面与请求 | URL、操作步骤，不记录 Token |
| 预期结果 | 文档定义结果 |
| 实际结果 | 页面状态、错误码、Availability |
| 截图/日志引用 | 安全处理后的文件名 |
| 是否阻塞 | Blocker / Major / Minor |
| 复现性 | Always / Intermittent / Once |

不得直接修改生产数据或业务规则来消除验收问题。修复应进入独立授权阶段。

## 15. 验收完成条件

满足以下条件后可结束 Phase S2 演示：

- 所有必选检查项有 Pass/Fail 记录；
- 登录、Dashboard、Profile、Operation Analytics、Data Governance、Reports 主路径通过；
- CSV 和 XLSX 均完成一次有效下载和内容检查；
- 关键截图完整且无敏感信息；
- 所有失败项已记录复现步骤和影响；
- Demo 数据库可以恢复到演示前基线；
- 未在验收过程中修改代码、Schema、Migration 或规则。
