# 全链路集成测试计划（Integration Test Plan V0.1）

- 任务：TASK-PHASE6-01
- 日期：2026-09-08
- 状态：**仅设计，不执行**；实际结果留待后续联调 Task 填写，不伪造结果。

## 1. 测试记录模板

每个用例统一记录以下字段：

| 字段 | 说明 |
| --- | --- |
| 测试编号 | 唯一编号，如 IT-01 |
| 测试目标 | 验证的链路/能力 |
| 前置条件 | 环境、数据、账号、权限 |
| 执行步骤 | 可重复的操作步骤 |
| 预期结果 | 冻结需求/设计定义的期望 |
| 实际结果 | 执行后填写 |
| 状态 | DESIGNED / PASS / FAIL / BLOCKED |

---

## 2. Test Flow 01：用户登录

- 测试编号：IT-01
- 测试目标：验证 Frontend Login → Auth API → JWT 签发 → Dashboard 访问闭环。
- 前置条件：
  - MySQL、Backend、Frontend 均按《Development Run Guide》启动。
  - `users` 表存在至少一个 `ACTIVE` 的 `ADMINISTRATOR` 账号。
- 执行步骤：
  1. 浏览器访问 `http://localhost:5173/login`。
  2. 输入正确用户名/密码，提交。
  3. 观察是否进入 `/dashboard` 并加载概览。
  4. 刷新页面，确认仍保持登录。
  5. 登出/清除 `access_token` 后访问 `/dashboard`，确认被重定向到 `/login`。
- 预期结果：
  - `POST /api/v1/auth/login` 返回 `access_token`；前端写入 localStorage 并请求 `/auth/me`。
  - Dashboard 正常加载；刷新不掉线；无 token 访问受保护页被 Router Guard 拦截。
- 实际结果：待执行。
- 状态：DESIGNED。

---

## 3. Test Flow 02：数据查询

- 测试编号：IT-02
- 测试目标：验证 Frontend → API → Service → Repository → Database 只读链路与分页/筛选。
- 前置条件：
  - 数据库已执行 DDL/Migration 基线。
  - 已存在 Drama/Actor/Platform 样例数据（可通过导入或手工 INSERT）。
- 执行步骤：
  1. 登录后进入 `/dramas`。
  2. 观察列表加载、总数与分页。
  3. 按名称搜索、按状态筛选、重置筛选。
  4. 进入 `/actors`、`/platforms` 重复查询。
- 预期结果：
  - 各列表调用对应 API，返回 `Pagination<T>`，页面渲染条数与 `total` 一致。
  - 搜索/筛选参数正确传递（`name_contains`、`status`）。
- 实际结果：待执行。
- 状态：DESIGNED。

---

## 4. Test Flow 03：数据管理（Drama / Actor / Platform CRUD）

- 测试编号：IT-03
- 测试目标：验证管理员写操作（新增/编辑/停用）与普通用户只读的 UI+API 一致性。
- 前置条件：
  - 已登录 `ADMINISTRATOR` 账号；另准备一个 `ACTIVE` 的 `USER` 账号。
  - 数据库存在可操作的主数据。
- 执行步骤：
  1. ADMINISTRATOR 登录，在 `/dramas`、`/actors`、`/platforms` 分别执行新增、编辑、停用。
  2. 每次操作后确认列表刷新且数据变化。
  3. USER 登录，进入三个管理页，确认新增/编辑/停用按钮不可见，列表可读。
  4. 用 USER 直接调用写 API（绕过 UI），确认后端拒绝（403/权限错误）。
- 预期结果：
  - 管理员写操作成功且数据库落库；停用为逻辑停用，历史数据保留。
  - USER 前端只读；后端仍拒绝未授权写请求（后端为最终安全边界）。
- 实际结果：待执行。
- 状态：DESIGNED。

---

## 5. Test Flow 04：数据导入

- 测试编号：IT-04
- 测试目标：验证 CSV/XLSX → ImportJob → Validation → Confirm → Database 两阶段导入链路。
- 前置条件：
  - 已登录 `ADMINISTRATOR`。
  - 准备符合固定模板的 CSV 与 XLSX 各一份，以及一份含错误行的文件。
- 执行步骤：
  1. 进入 `/imports`，选择模板文件与导入类型，上传并校验。
  2. 任务进入 READY 后打开 `/imports/:id`，核对总行/有效行/错误行。
  3. 对含错误文件打开 `/imports/:id/errors`，核对错误定位与消息。
  4. 返回任务详情，点击确认正式导入。
  5. 在目标主数据页核对导入结果。
- 预期结果：
  - `POST /api/v1/import/jobs` 创建任务并完成校验。
  - 错误分页只显示源行号/字段/错误类型/消息，不暴露原始敏感值。
  - `POST /api/v1/import/jobs/{id}/confirm` 单事务写入，状态流转正确。
- 实际结果：待执行。
- 状态：DESIGNED。

---

## 6. Test Flow 05：分析展示

- 测试编号：IT-05
- 测试目标：验证 Snapshot 数据 → Analytics Service → Dashboard/Analytics 页面展示链路。
- 前置条件：
  - 已通过导入或直接 SQL 写入有效 Snapshot 数据（含 as-of 最新有效 revision）。
  - Dashboard 与分析中心可访问。
- 执行步骤：
  1. 进入 `/dashboard`，核对概览计数、Heat/Growth/Potential Top 10、趋势与质量摘要。
  2. 进入 `/analytics`，搜索并选择短剧，点击“开始分析”。
  3. 核对 AnalysisContext、核心指标、Growth、Heat、Potential、Insight 展示。
  4. 从 `/dramas` 点击“分析”直达 `/analytics?drama_id=...`。
- 预期结果：
  - Dashboard API 与分析汇总 API 返回与 Snapshot 一致的结果；前端不重新计算模型。
  - 页面 NULL/空态/错误态展示符合冻结口径；Potential 不含预测/推荐表述。
- 实际结果：待执行。
- 状态：DESIGNED。

---

## 7. 性能测试规划（仅方案，不生成结果）

| 编号 | 场景 | 目标阈值 | 数据规模 | 状态 |
| --- | --- | --- | --- | --- |
| PT-01 | 普通查询（列表/搜索/分页） | 约 2 秒 | 10 万级 Snapshot 环境 | DESIGNED |
| PT-02 | Dashboard 全量加载 | 约 3 秒 | 10 万级 Snapshot 环境 | DESIGNED |
| PT-03 | 单剧分析汇总 | 3–5 秒 | 10 万级 Snapshot 环境 | DESIGNED |

说明：以上阈值为既有设计引用值，本 Task 不执行压测、不生成任何虚假性能数据；实测数据待后续性能 Task 在 10 万级数据环境采集并注明环境与并发条件。

## 8. 状态汇总

| 流程 | 测试编号 | 状态 |
| --- | --- | --- |
| 用户登录 | IT-01 | DESIGNED |
| 数据查询 | IT-02 | DESIGNED |
| 数据管理 | IT-03 | DESIGNED |
| 数据导入 | IT-04 | DESIGNED |
| 分析展示 | IT-05 | DESIGNED |
| 性能测试 | PT-01 ~ PT-03 | DESIGNED |
