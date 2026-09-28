# 短剧数据管理与分析系统操作说明

## 1. 使用说明

本操作说明适用于短剧数据管理与分析系统 V1.0 的软件著作权材料和验收演示。实际菜单、按钮和数据状态以当前部署环境及用户权限为准。

演示应使用 `docs/acceptance/DEMO_DATA_PLAN.md` 中规划的 Demo 数据，禁止展示真实密码、Token、数据库连接串或未经脱敏的商业数据。

## 2. 运行前提

1. Backend、Frontend 和 MySQL 服务已按部署说明启动；
2. 数据库已按 `V001–V013` 完成初始化；
3. 已准备 ACTIVE 状态的演示账号；
4. 已导入或准备可展示各模块的 Demo 数据；
5. 浏览器可以访问系统前端地址；
6. 演示人员已记录统一分析截点 `T_demo`。

## 3. 登录系统

操作步骤：

1. 在浏览器中打开系统；
2. 确认登录页显示“短剧数据管理与分析系统”；
3. 输入已分配的用户名和密码；
4. 单击登录按钮；
5. 登录成功后进入 Dashboard。

预期结果：

- 有效账号进入系统；
- 无效凭据显示明确错误；
- 未认证用户不能直接访问受保护页面；
- 页面不显示密码或 Token。

## 4. Dashboard

登录后在 Dashboard 查看：

- 系统数据概览；
- 核心指标或趋势；
- 主要模块入口；
- 当前用户可访问的导航。

从 Dashboard 可进入基础数据、数据分析、Drama Profile、Operation Analytics、Data Governance 和 Reports。普通用户与管理员看到的操作入口可能不同，权限判断以后端为准。

## 5. 数据管理

### 5.1 查看基础数据

1. 从导航进入短剧或相关基础资料页面；
2. 使用页面提供的名称、状态、平台或标签等已有筛选条件；
3. 查看列表和详情；
4. 管理员可在授权范围内执行页面已有的维护操作。

### 5.2 数据导入

1. 进入数据导入页面；
2. 选择系统支持的 CSV/XLSX 文件；
3. 上传并等待校验；
4. 查看校验结果和错误行；
5. 仅在校验结果符合预期时执行确认；
6. 查看导入任务最终状态。

不要使用非模板字段、真实敏感数据或超出系统现有规则的文件进行软著截图。

## 6. 数据分析

1. 从 Dashboard 或导航进入数据分析中心；
2. 选择需要查看的分析模块；
3. 选择或筛选目标短剧；
4. 查看指标、分析时间、版本和 Availability；
5. 根据需要查看 Score、Quality、Prediction 或 Anomaly 的详情；
6. 如页面提供 Explanation/Lineage 入口，可展开查看结果依据。

分析结果由后端已有规则生成。用户不应把预测理解为收益保证，也不应把异常状态解释为自动运营结论。

## 7. Drama Profile

操作流程：

```text
Dashboard
  ↓
Drama Profile
  ↓
选择短剧
  ↓
查看综合画像
```

操作步骤：

1. 进入 Drama Profile 页面；
2. 选择具有完整演示数据的短剧；
3. 查看基础信息；
4. 查看 Performance、Quality、Trend、Risk 和 Operations；
5. 查看 Explanation 或数据来源入口；
6. 核对各区域的 Availability。

Profile 是只读聚合页面，不提供修改评分、预测、异常或行动事实的操作。

## 8. Operation Analytics

操作流程：

```text
进入运营分析中心
  ↓
选择 Action Effect / Lifecycle / Benchmark
  ↓
设置页面已有参数
  ↓
查看分析结果和 Availability
```

### 8.1 Action Effect

1. 选择已有完成记录的运营行动；
2. 查看 Before/After 时间窗口；
3. 查看指标变化和方向；
4. 核对分析截点与可用状态。

页面展示的是行动发生后的指标变化，不代表行动导致变化。

### 8.2 Lifecycle

1. 选择短剧；
2. 查看当前生命周期阶段；
3. 查看规则版本和分析时间；
4. 数据不足时查看明确的 Availability。

### 8.3 Benchmark

1. 选择同平台的目标短剧集合；
2. 保持系统规定的数量和时间范围；
3. 查看统计比较结果；
4. 不将统计比较解释为排名或推荐。

## 9. Data Governance

操作流程：

```text
进入数据治理中心
  ↓
查看 Overview
  ↓
查看 Freshness / Completeness / Consistency
  ↓
打开 Evidence
```

操作步骤：

1. 进入 `/data-governance`；
2. 查看系统 Scope、`analysis_as_of` 和总体 Availability；
3. 查看 Freshness 状态与数据时间证据；
4. 查看 Completeness 覆盖率、缺失项和证据；
5. 查看 Consistency 问题数量和证据；
6. 打开 Evidence Drawer 查看 type、message、source 和 metadata。

前端只展示 API 返回的状态，不重新计算延迟、覆盖率或一致性。

## 10. Reporting Center

操作流程：

```text
进入 Reports
  ↓
选择报告
  ↓
设置允许的筛选条件
  ↓
Preview
  ↓
确认导出
  ↓
下载 CSV 或 XLSX
```

### 10.1 选择报告

1. 进入 `/reports`；
2. 等待 Report Catalog 加载；
3. 查看报告名称、描述、Schema Version 和支持格式；
4. 选择需要的报告。

报告列表来自 API，不应由演示人员在浏览器中临时构造。

### 10.2 设置 Filter 与 Snapshot

1. 根据页面显示的 Filter 定义填写筛选条件；
2. 如需要，选择允许的 `analysis_as_of`；
3. 确认页面显示的数据截点；
4. 不填写 Schema 未提供的字段。

### 10.3 Preview

1. 单击 Preview；
2. 查看 Availability；
3. 按后端返回的列顺序查看预览表；
4. 数据为空或不足时，记录页面显示的明确状态。

### 10.4 Export

1. 选择 CSV 或 XLSX；
2. 查看报告类型、格式和限制提示；
3. 执行导出确认；
4. 调用 Export；
5. 等待浏览器下载完成；
6. 检查文件名、扩展名和内容可打开性。

前端不生成或解析 CSV/XLSX。若超出行数或文件大小限制，应保留系统返回的明确错误，不绕过确认和限制策略。

## 11. 退出与安全

1. 完成演示后退出系统；
2. 确认认证状态被清除；
3. 关闭包含导出数据的文件；
4. 将截图和导出文件保存在验收材料目录；
5. 删除或遮盖截图中的敏感信息；
6. 不将演示密码记录在操作手册或截图中。

## 12. 常见状态说明

| 状态 | 用户理解 |
| --- | --- |
| AVAILABLE | 数据正常可展示 |
| PARTIAL | 部分数据可用，需查看原因 |
| EMPTY | 查询成功但没有匹配记录 |
| INSUFFICIENT / INSUFFICIENT_HISTORY | 数据或历史窗口不足 |
| NOT_AVAILABLE | 当前无法评估或提供结果 |

不同模块的枚举名称以实际 API 为准。用户不得用 0 或空白页面替代这些状态。

## 13. 截图操作要求

软著截图应按以下顺序采集：

1. 登录界面；
2. Dashboard 首页；
3. 数据分析页面；
4. Drama Profile 页面；
5. Operation Analytics 页面；
6. Data Governance 页面；
7. Reports 页面；
8. CSV 和 XLSX 导出结果。

每张截图应显示软件名称或可识别的模块标题，使用 Demo 数据，保持相同版本和主题，并遮盖账号、密码、Token、连接串及真实敏感数据。

详细截图编号和验收对应关系见 `docs/acceptance/ACCEPTANCE_FLOW.md` 与 `COPYRIGHT_MATERIAL_CHECKLIST.md`。
