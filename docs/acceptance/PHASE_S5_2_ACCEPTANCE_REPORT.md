# Phase S5.2 功能预验收报告

执行日期：2026-10-12（Asia/Shanghai）  
执行性质：自动化验证、真实浏览器内部预验收、最小缺陷修复  
结论边界：不代表用户最终人工验收通过

## 1. 总体结论

Phase S5.2 已完成代码/数据库审计、隔离写测试、主要 API 验证、真实 Edge 双分辨率走查、四项缺陷修复和全量回归。Prediction、Operation Action、Import、Composite Score、Anomaly、Profile、Governance、Reporting 等已验证路径可用；开发库 31 表及 131 部短剧、64,255 条快照与修订均保持不变；正式验收库和 `v1.0.0` 未修改。

系统可以进入**除 Data Quality 成功计算、Explanation/Lineage 实际追溯之外的用户人工验收**。不建议宣布“全功能验收就绪”，因为 Data Quality 缺少初始规则和生产 evaluator/evidence 实现，这是明确的 P1 阻塞项，需要用户批准新的业务设计与实现范围。

## 2. Git 与环境基线

| 项目 | 结果 |
|---|---|
| 起始分支/HEAD | `main` / `69269ca28f48ff8b3e5714bb1ac885d81e7b80fa` |
| S5.1 提交 | `f822f531…`、`69269ca…` 均存在 |
| Release Tag | `v1.0.0` 仍指向 `0e350381d1fd7a16eaa9da5cf9bb92c24285c7de` |
| Backend | Python 3.12 / FastAPI / SQLAlchemy / Pydantic |
| Frontend | Vue 3 / TypeScript / Element Plus / Vite |
| Database | MySQL 8.0.45；目标 `short_drama_analysis` |

本阶段代码提交：

- `8d48ecf` — `fix(backend): repair operation action audit logging`
- `993d9db` — `fix(frontend): clarify analysis states and responsive layout`

## 3. 数据安全与隔离

在任何功能写测试前，对开发库执行 `mysqldump --single-transaction --quick --routines --triggers --events --hex-blob`：

| 项目 | 结果 |
|---|---|
| 文件 | `backup_phase_s5_2_short_drama_analysis_20261012_171116.sql`（Git 忽略） |
| 大小 | 13,203,837 bytes |
| SHA-256 | `9AA113ED9DA1E8FB11162A59B1FDA0451D33953183E4EFBA5FF61B775CEBB288` |
| 时间 | 2026-10-12 17:11:17 +08:00 |
| 恢复验证 | 恢复至 `short_drama_s5_2_20261012_171116`；31 表、131 dramas、64,255 snapshots/revisions、82 scores、1 prediction、52 FK 一致 |
| 清理 | 验证结束后已删除该隔离数据库；备份保留，可重新恢复 |

所有 Import、CRUD、Composite Score 重算、Prediction 重算、Anomaly detect、Operation Action 状态流转均在隔离库执行。开发库仅执行读取和登录；未插入测试业务数据。`short_drama_acceptance_v1` 全程只读。

最终数据核验：

| 指标 | 开发库 | 正式验收库 |
|---|---:|---:|
| 表数 | 31 | 31 |
| dramas | 131 | 5 |
| snapshots | 64,255 | 未改 |
| revisions | 64,255 | 未改 |
| drama_scores | 82 | 未改 |
| prediction_results | 1 | 5 |
| data_anomaly_records | 2 | 未改 |
| operation_actions | 0 | 未改 |
| data_quality_rules/scores | 0 / 0 | 未改 |

## 4. Data Quality 结果

真实根因不是 S5.1 表结构恢复失败，而是业务规则/evaluator 链尚未交付：

- 三张 ORM/表和查询链完整。
- 开发库无规则、规则结果或评分。
- 生产依赖工厂显式注入空 evaluator registry。
- 仓库没有生产 evaluator、Evidence Repository、规则数据 Migration 或初始化命令。
- 无活动规则时 HTTP 400 + `NO_ACTIVE_RULE_SET` 符合现有契约。
- 手工插入规则会继续触发 evaluator 缺失，因此不能作为安全修复。

本阶段只修复了前端错误分类和说明，没有改变阈值、权重、公式或创建规则。详见 [DATA_QUALITY_REVIEW_REPORT.md](DATA_QUALITY_REVIEW_REPORT.md)。

## 5. 各模块真实验证

| 模块 | 验证方式 | 结果 |
|---|---|---|
| Auth/RBAC | 真实 API + Edge | ADMIN/临时 USER 登录 200；匿名 401；USER Prediction/Tag 写操作 403；响应不含 password_hash。 |
| Dashboard | 7 个 API + Edge | 131 dramas、421（隔离导入后 422）actors、110 directors、78 companies、13 platforms；数值与 API 一致。查询偏慢。 |
| 基础数据 | 真实 API/隔离 CRUD | Drama 131、Actor 421、Director 110、Company 78、Platform 13、Tag 30；Tag create/update/deactivate 通过。 |
| Import | 隔离真实上传 | CSV、XLSX 各导入 1 行成功；非法状态 `FIELD_VALIDATION`；重复 Tag `BUSINESS_UNIQUENESS`。 |
| Composite Score | 隔离重算 + 查询 | 2026-09-07 计算 82 条；排名、等级分布、drama 25 查询 200；公式未改。 |
| Data Quality | API/DB/Edge | 查询为空且稳定；计算 400 `NO_ACTIVE_RULE_SET`；成功路径阻塞。 |
| Prediction | API/DB/Edge | drama 25 重算/持久化/历史：711,830；drama 120：400 `INSUFFICIENT_HISTORY`；页面区分空数据与不足。 |
| Anomaly | 隔离 detect + 查询 | detect 200；开发基线 2 条 C 级 OPEN spike 记录保持；列表/统计 200。 |
| Operation Action | 隔离 API | 修复前 create 500；修复后 create、assign context、USER comment、合法状态、取消/完成均通过；非法 OPEN→COMPLETED 返回 400。 |
| Explanation/Lineage | API/DB/Profile | 两查询 API 200 空页；两表为 0；生成 Service 未接入计算流，无法验证实际追溯。 |
| Drama 360 | API/Edge | drama 25 聚合 200；Score/Prediction 有数据，Quality/Explanation 按真实状态显示，不触发写。 |
| Operation Analytics | API/Edge | lifecycle 25 200；platform 1 + drama 2/3 返回 `INSUFFICIENT/INCOMPARABLE_SCOPE`；Effectiveness 无合格完成窗口，空集合。 |
| Data Governance | 4 API + Edge | Overview/Freshness/Completeness/Consistency 200；与持久化 Data Quality 评分职责分离。 |
| Reporting | 6 Preview + 2 Export | Catalog 6 类；Prediction 1 行；无确认返回 409；确认后 CSV 213 bytes/2 lines、XLSX 5,038 bytes/`PK` 签名，文件名安全。 |

## 6. 已修复缺陷

1. **P1 Operation Action HTTP 500**：traceback 为 `Unknown mapped columns: ['detail']`。删除非法列，改用现有 `summary` 携带 action ID，并添加回归断言。
2. **P2 Data Quality 空状态误报**：current score 404 不再显示错误；无规则计算显示中文业务原因。
3. **P2 Prediction 错误分类**：无最新结果作为空状态；`NO_HISTORY/INSUFFICIENT_HISTORY/DATA_QUALITY_BLOCKED` 显示中文原因。
4. **P2 Dashboard 1366 布局**：增加响应式断点，标题与导航不再互相挤压。

完整清单见 [ACCEPTANCE_ISSUE_REGISTER.md](ACCEPTANCE_ISSUE_REGISTER.md)。

## 7. UI/UX 浏览器结果

- Edge 1920×1080 与 1366×768；最终轮次 0 个 HTTP 500、0 个控制台错误。
- 页面级水平溢出为 0。
- Dashboard 1366 布局修复后已重新截图核验。
- Data Quality 空状态和无规则失败提示清楚。
- Prediction 25 实际值和 120 不足提示均通过。
- Reports、Anomaly、Profile、Governance 仍有中英文混用，登记为 P3。

详见 [UI_UX_REVIEW_REPORT.md](UI_UX_REVIEW_REPORT.md) 与 `docs/acceptance/evidence/phase_s5_2/`。

## 8. 回归测试

| 门禁 | 结果 |
|---|---|
| Operation Action 专项 | 21 passed |
| Backend 全量 | 706 collected / 706 passed |
| Python compileall | passed |
| Frontend vue-tsc | passed |
| Frontend production build | passed，2361 modules transformed |
| 浏览器最终轮次 | 0 HTTP 500；0 console error |
| Git diff check | passed（仅行尾转换提示） |

非阻塞警告：Starlette/httpx2 弃用警告；Vite 两个公共 chunk 超过 500 kB。

## 9. 未解决事项与风险

- **P1**：Data Quality 成功计算缺少业务规则、Evidence Repository 和生产 evaluator；未经业务确认不得实现。
- **P2**：Dashboard API 约 8.1～15.7 秒，首屏约 19 秒；需要独立执行计划/索引审计。
- **P2**：Explanation/Lineage 表为空，生成服务没有接入现有分析计算链；不能声称可追溯功能已验收。
- **P3**：跨页面中英文展示词典不统一。
- **P3**：Score 页是否默认最新评分日需产品确认。

## 10. 阶段判定

- **自动化测试通过**：是，706/706；前端类型检查/构建通过。
- **Agent 浏览器验证通过**：已覆盖的页面与场景通过；同时记录上述限制。
- **用户人工验收通过**：否，尚未由用户执行。
- **进入人工验收条件**：可对非阻塞模块开始；要宣布全功能可验收，需先决定并完成 Data Quality 规则/evaluator，或由用户明确接受该功能不在当前 V1 验收范围。

用户操作步骤见 [FUNCTIONAL_ACCEPTANCE_CHECKLIST.md](FUNCTIONAL_ACCEPTANCE_CHECKLIST.md)。本阶段不会自动进入 Phase S6。
