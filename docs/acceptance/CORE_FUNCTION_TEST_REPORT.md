# Phase S5.2-B 核心功能测试记录

执行日期：2026-10-12

## 1. 自动化测试

| 检查 | 结果 |
|---|---|
| Data Quality + Explanation 专项 pytest | 129 passed |
| Backend 全量收集 | 706 tests |
| Backend 全量执行 | 706 passed，0 failed，0 skipped |
| Python compileall | PASS |
| `vue-tsc --noEmit` | PASS |
| Frontend production build | PASS，2361 modules transformed |

构建仅报告既有的 >500 kB chunk 警告，本阶段未包含性能优化。

## 2. 环境性失败记录

第一次从 `backend/` 运行全量测试，两个源码结构测试因相对路径基准错误失败；另有十个 `tmp_path` 测试因系统默认 pytest 临时目录访问被拒绝而 setup error。

第二、三次已改到仓库根目录，但沙箱内新建 pytest 目录仍带受限 ACL。最终在沙箱外、仓库根目录、独立 `--basetemp` 下运行，706/706 通过。未修改、删除、跳过或弱化任何测试。

## 3. 真实 API + 开发库测试

使用 FastAPI `TestClient` 加载真实应用及 `backend/.env` 指向的 `short_drama_analysis`，通过已有管理员账号登录；凭据和 Token 未输出或写入报告。

| 检查 | HTTP / 结果 |
|---|---|
| 登录 | 200 |
| 当前质量评分 | 404 |
| 质量历史 | 200 / 0 |
| 规则列表 | 200 / 0 |
| 质量计算 | 400 / `NO_ACTIVE_RULE_SET` |
| Score Explanation | 200 / 0 |
| Prediction Explanation | 200 / 0 |
| Anomaly Explanation | 200 / 0 |
| 匿名质量查询 | 401 |
| 匿名解释查询 | 401 |

质量计算前后 `data_quality_scores=0`、`data_quality_rule_results=0`，操作日志总数也未变化，证明预期业务失败没有留下部分写入。

## 4. 数据完整性

最终只读复核应保持：31 表、131 dramas、64,255 snapshots、64,255 revisions、82 scores、1 prediction、2 anomalies、0 Data Quality score、0 explanation、0 lineage。正式验收库仅做读取核对，没有执行 DDL/DML。

## 5. 浏览器状态

本阶段未取得新的可核查浏览器截图。Edge headless/CDP 尝试未稳定完成会话，因此浏览器项标为 **NOT VERIFIED IN S5.2-B**。同一 HEAD 的 S5.2 既有截图可作为历史基线，但没有被冒充为本阶段新证据。

待设计批准并实现后，必须重新执行：

1. Data Quality 成功评分、规则明细、证据、历史和错误分类。
2. Score、Prediction、Anomaly 的 Explanation Drawer 成功态和真实 Lineage。
3. 重复计算、解释幂等、来源失效和事务失败的浏览器/API 联合验证。

