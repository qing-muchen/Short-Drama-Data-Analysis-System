# Phase S5.2 验收缺陷清单

| 编号 | 模块 | 严重度 | 问题/复现条件 | 实际结果 | 根因 | 修改文件/方案 | 验证 | 状态 |
|---|---|---:|---|---|---|---|---|---|
| S5.2-001 | Operation Action | P1 | 隔离库调用 `POST /operation-actions` | HTTP 500，事务回滚 | Service 向 `operation_logs` 传入不存在的 `detail` 列 | `backend/services/operation_action_service.py`；使用已有 `summary` 保存 action ID | 专项 21 passed；真实创建/状态机/评论/取消成功；全量 706 passed | 已修复 |
| S5.2-002 | Data Quality UI | P2 | 无评分时打开页面 | 把预期 404 显示为英文错误 | 页面未按设计把 current score 404 当空状态 | `DataQualityAnalysis.vue`、`api-error.ts` | Edge 两分辨率无错误 Alert | 已修复 |
| S5.2-003 | Prediction UI | P2 | 查询/重算 drama 120 | 无结果或不足被显示为英文通用错误 | 页面未读取 HTTP 状态和 `details.reason` | `PredictionAnalysis.vue`、`api-error.ts` | Edge：空状态正常；重算显示连续 8 日条件 | 已修复 |
| S5.2-004 | Dashboard | P2 | 1366×768 打开 Dashboard | 标题被导航挤成三行 | Header 在 1366 宽度仍强制左右布局 | `Dashboard.vue` 增加 1500px 响应式断点 | Edge 截图复核，无水平溢出 | 已修复 |
| S5.2-005 | Data Quality | P1 | 管理员执行质量评分 | HTTP 400 `NO_ACTIVE_RULE_SET`，无法生成评分 | 规则表为 0；无规则数据 Migration；生产 evaluator/evidence provider 未实现且注册表为空 | 不允许凭空创建规则；需单独设计并审批 | DB、代码、文档与 API 四方证据一致 | 阻塞/待确认 |
| S5.2-006 | Dashboard | P2 | 加载概览/排行/趋势 | 单接口约 8.1～15.7 秒，完整首屏约 19 秒 | 大量历史修订的 as-of 聚合查询成本高；尚未做执行计划审计 | 本阶段不改算法或索引；建议单独性能任务 | 真实 API 计时与 Edge 走查 | 待处理 |
| S5.2-007 | 多页面 | P3 | Reports、Anomaly、Profile、Governance | 中英文业务词与内部标识混用 | 展示层缺少统一词典 | 保留 API/枚举兼容；后续统一前端展示 | 浏览器截图 | 待产品确认 |
| S5.2-008 | Explanation/Lineage | P2 | 查询现有 Score/Prediction/Anomaly 解释 | 查询 API 正常但两表均为 0，Profile 显示暂不可用 | 生成 Service/handlers 存在，但未接入现有计算工作流，也无生成 API | 不生成无依据解释；需确认接入点与幂等策略 | API 200 空页；DB 行数 0 | 待设计确认 |
| S5.2-009 | Data Quality UI | P3 | 查看四维雷达图 | 英文维度名与中文页面混用 | 展示文案未本地化 | 仅替换前端展示文字 | TypeScript/build/Edge 通过 | 已修复 |
| S5.2-010 | Composite Score UI | P3 | 当天无评分但历史有 2026-09-07 评分 | 初始页面为空，需手动选日期 | 默认日期为当天 | 是否自动选择最新评分涉及产品语义 | 浏览器复现 | 待产品确认 |

说明：S5.2-005 是完整 Data Quality 成功路径的阻塞项。因此本阶段不宣称“全功能人工验收就绪”，但其他模块可以进入用户人工验收。
