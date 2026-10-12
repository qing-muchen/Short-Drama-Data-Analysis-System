# Phase S5.2 用户人工验收清单

> 本清单用于用户人工验收，不等同于 Agent 自动化结论。请使用安全渠道取得账号，不在截图或记录中暴露密码/Token。

## 1. 启动与基线

1. 后端进入 `backend`，激活 Python 3.12 虚拟环境后运行 `python -m uvicorn main:app --host 127.0.0.1 --port 8000`。
2. 前端进入 `frontend`，运行 `npm run dev`，访问 `http://127.0.0.1:5173`。
3. 确认后端实际连接 `short_drama_analysis`，不要使用 `short_drama_acceptance_v1`。
4. 建议浏览器分别使用 1920×1080、1366×768。

## 2. 推荐验收流程

| 顺序 | 页面/数据 | 操作 | 预期结果 | 异常判定 |
|---:|---|---|---|---|
| 1 | `/login` | 管理员登录、刷新页面、退出后访问受保护页面 | 登录成功、刷新保持状态；退出/无 Token 返回登录页 | 页面暴露 Token/密码、匿名可访问业务 API 为失败 |
| 2 | Dashboard | 等待数据加载完成，核对短剧 131、平台 13、总播放量 195,532,834 | 卡片与 API 一致；1366 标题完整 | 首屏可能需约 20 秒；500 或无限加载为失败 |
| 3 | 短剧管理 | 查询 ID 25，查看详情、标签、Profile 跳转 | 数据与 Profile 的“浮生情书”一致 | 关联为空但数据库有数据、分页错乱为失败 |
| 4 | 综合评分 | 将评分日期设为 `2026-09-07` | 排名共 82 条，drama 25 有 C 级详情 | 默认当天为空不是后端故障 |
| 5 | Data Quality | 打开页面；管理员点击重新计算 | 空状态正常；点击后显示“尚未发布可执行规则” | 本阶段没有成功评分用例；出现 500 为失败 |
| 6 | Prediction 成功 | 输入 drama ID 25，查询；管理员可重算 | 展示 `711,830`、`Moving Average V1.0` 和 1 个历史目标日 | 不应显示系统故障 |
| 7 | Prediction 不足 | 输入 drama ID 120，查询后重算 | 查询为空；重算提示需连续 8 天且累计播放量单调不下降 | 伪造空成功、500 或放宽条件为失败 |
| 8 | Anomaly | 打开异常页 | 开发库已有 2 条 C 级、OPEN 的播放量 spike 记录 | 枚举可保留内部代码；列表/统计不一致为失败 |
| 9 | Operation Action | 建议只在隔离库创建测试行动，依次 OPEN→IN_PROGRESS→CANCELLED | 创建、评论、历史和合法状态流转正常；OPEN→COMPLETED 被拒绝 | 开发库测试会留下不可物理删除的审计历史 |
| 10 | Explanation/Lineage | 从 Profile/Prediction 打开解释 | 当前显示暂不可用/空列表 | 不应生成无依据解释；此项待设计接入 |
| 11 | Drama 360 | `/dramas/25/profile` | Score/Prediction 有数据；Quality/Explanation 按实际状态显示 | Profile 不应触发写操作或后台计算 |
| 12 | Operation Analytics | 查询 lifecycle 25；Benchmark 用 platform 1、drama 2 和 3 | Lifecycle 返回；Benchmark 明确显示数据不足/不可比原因 | 不得展示因果结论或推荐 |
| 13 | Data Governance | 打开 Overview/Freshness/Completeness/Consistency | 页面可读，Evidence 可展开；与 Data Quality 评分分开 | 500、把请求时治理误称为持久化评分为失败 |
| 14 | Reports | 逐项选择 6 类报告；预览 Prediction Results；导出 CSV/XLSX | Prediction 预览 1 行；确认行数后 CSV 2 行（表头+数据），XLSX 为有效 ZIP/OOXML | 无确认直接大批导出、文件名含危险字符为失败 |

## 3. 权限验收

开发库当前只有一个 ACTIVE 管理员账号。本阶段在隔离副本创建临时 USER，真实 API 已验证：

- 匿名 Dashboard API：401。
- USER 读取：成功。
- USER 调用 Prediction calculate：403。
- USER 调用 Tag create：403。
- USER 作为行动负责人添加评论：成功。

若用户要在浏览器亲自验证 USER 视图，应先按项目既有账号配置流程在隔离环境创建普通账号，不要修改正式验收账号。

## 4. 导入验收

导入属于持久化操作，应在隔离数据库执行。推荐用唯一名称的 TAG/ACTOR：

1. CSV 与 XLSX 各上传一条合法 MASTER_DATA，状态应从 READY 到 COMPLETED，`imported_rows=1`。
2. 上传非法状态值，状态应为 VALIDATION_FAILED，错误码 `FIELD_VALIDATION`。
3. 再次上传相同标签，状态应为 VALIDATION_FAILED，错误码 `BUSINESS_UNIQUENESS`。
4. 不要把测试数据导入 `short_drama_analysis` 或 `short_drama_acceptance_v1`。

## 5. 当前不应判为通过的项目

- Data Quality 成功计算：缺少受审查规则和生产 evaluator。
- Explanation/Lineage 实际追溯：当前无持久化记录。
- Dashboard 性能：功能正确但加载时间偏长，尚无性能门槛结论。
- 最终用户人工验收：必须由用户完成并签署，本报告不能代替。
