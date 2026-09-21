# Phase 4 Anomaly Detection Module Summary

## 1. Phase 4 目标与定位

Phase 4 面向短剧运营数据，发现播放量、互动率等指标的异常变化，并形成可追溯、可解释的结构化异常记录。模块定位是运营分析辅助工具：它不替代人工判断，不进行收益预测，也不承担 Phase 3 的未来趋势预测职责。

V1 使用 `Rule-based Detection V1.0`，强调规则透明、结果可解释和可测试。

## 2. 系统架构

完整链路如下：

```text
Database
  ↓
ORM
  ↓
Calculator
  ↓
Repository
  ↓
Service
  ↓
API
  ↓
Dashboard
```

- Database/ORM：保存 `data_anomaly_records` 及其约束、索引和 Drama 关联。
- Calculator：接收已准备好的历史指标序列，执行异常规则和数学计算，不访问数据库。
- Repository：负责异常记录的查询、批量保存、状态更新和统计，不创建 Session、不提交事务。
- Service：负责 analysis-as-of 数据准备、质量协同、平台聚合、Calculator 编排、事务和 OperationLog。
- API：负责鉴权、参数校验、统一响应和 Service 调用。
- Dashboard：展示 API 结果，提供筛选、详情和管理员状态操作，不重新计算异常。

## 3. Database 设计

V011 新增表 `data_anomaly_records`。核心字段包括：

- `drama_id`
- `metric_type`
- `anomaly_type`
- `severity`
- `status`
- `analysis_as_of`
- `algorithm_version`
- `baseline_value`
- `actual_value`
- `deviation_value`
- `evidence_summary`

数据库约束固定四类异常类型、A/B/C 严重等级和 `OPEN`、`ACKNOWLEDGED`、`RESOLVED`、`IGNORED` 状态，并通过历史唯一约束防止同一短剧、指标、异常类型、分析时间点和算法版本被重复生成。表中不冗余保存短剧名称或平台名称。

## 4. Calculator 设计

Calculator 版本为 `Rule-based Detection V1.0`，支持：

- `PLAY_COUNT_GROWTH_ANOMALY`
- `PLAY_COUNT_DROP_ANOMALY`
- `ENGAGEMENT_RATE_ANOMALY`
- `DATA_SPIKE_ANOMALY`

播放量增长、下降和突变规则使用 Z-score；绝对 Z-score 达到 2、3、4 时分别进入 C、B、A 级别。历史标准差为 0 时使用绝对偏差回退，避免除零并保持可解释性。互动率定义为 `(like + comment + favorite + share) / play_count`，播放量低于 100 时不适用互动率检测。每条 finding 都生成包含当前值、基准和偏差说明的 `evidence_summary`。

## 5. Repository 设计

主要接口：

- `save_anomalies`
- `get_anomalies`
- `get_by_drama`
- `get_latest_anomalies`
- `get_trend`
- `update_status`
- `get_statistics`

Repository 只负责 ORM 数据访问，不计算异常、不选择规则、不处理 revision，不创建 Session，不执行 `commit` 或 `rollback`，仅在需要时 `flush`，事务由 Service 统一管理。

## 6. Service 设计

检测流程为：

```text
analysis_as_of
  ↓
历史 revision 读取
  ↓
数据质量过滤
  ↓
指标聚合
  ↓
Calculator
  ↓
保存异常
  ↓
OperationLog
```

历史输入严格满足 `changed_at <= analysis_as_of`，避免未来 revision 污染历史检测；VOID revision 按历史有效性规则处理。ERROR 级数据质量问题阻断检测，WARNING 允许继续。异常记录和操作日志处于同一个事务中，任一步骤失败则统一回滚。

## 7. API 设计

| 方法 | 路径 | 权限 | 用途 |
| --- | --- | --- | --- |
| POST | `/api/v1/anomalies/detect` | ADMINISTRATOR | 执行检测 |
| GET | `/api/v1/anomalies` | USER / ADMINISTRATOR | 分页筛选异常 |
| GET | `/api/v1/anomalies/{drama_id}` | USER / ADMINISTRATOR | 查看单剧异常 |
| GET | `/api/v1/anomalies/statistics` | USER / ADMINISTRATOR | 获取统计数据 |
| PATCH | `/api/v1/anomalies/{record_id}/status` | ADMINISTRATOR | 更新异常状态 |

接口使用 JWT Bearer 鉴权、`ResponseModel` 成功响应和 `ErrorResponse` 错误响应。Router 不访问 ORM、Repository 或 Calculator。

## 8. Dashboard 设计

页面路径为 `/anomalies`，基于 Vue3、TypeScript 和 ECharts 实现，包含：

- 异常总数及 A/B/C 分布
- OPEN 数量
- 服务端筛选的异常列表和分页
- 异常趋势折线图
- 异常详情抽屉
- 管理员状态更新入口

Frontend 只展示 API 结果。当前后端未提供独立趋势接口，页面使用已有异常列表按 `analysis_as_of` 做展示层日期聚合，不参与异常判定。

## 9. 测试结果

- Backend：最终阶段全量 pytest `345 passed`。
- 覆盖 ORM 约束、Calculator 规则、Repository 查询与事务边界、Service 编排与回滚、API 权限和响应结构。
- Frontend：`vue-tsc --noEmit` 通过。
- Frontend：`npm run build` 通过，Vite 生产构建完成。
- 构建存在既有 chunk size 非阻塞 warning，未修改构建配置。

## 10. Git 提交记录

| 阶段 | Commit | Message |
| --- | --- | --- |
| Design | `3b36108` | `docs(phase4): add anomaly detection design` |
| Review | `a823e66` | `docs(phase4): add anomaly detection review` |
| Design V2 | `cc72846` | `docs(phase4): update anomaly detection design v2` |
| Database + ORM | `2001d63` | `feat(phase4): add anomaly detection database schema` |
| Calculator | `601c58b` | `feat(phase4): add anomaly detection calculator` |
| Repository | `69c8ed6` | `feat(phase4): add anomaly detection repository` |
| Service | `351c232` | `feat(phase4): add anomaly detection service` |
| API | `12edb92` | `feat(phase4): add anomaly detection api` |
| Dashboard | `865e916` | `feat(phase4): add anomaly detection dashboard` |

## 11. Phase 4 限制与未来方向

当前限制：

- 仅使用规则模型，不是机器学习模型。
- 不进行未来趋势预测，不替代 Phase 3 Prediction。
- 不自动执行运营决策，不替代人工审核。
- 检测指标和异常类型仍为 V1 固定集合。

未来可扩展：

- 增加更多异常规则和指标。
- 引入可审计的 ML 异常检测模型。
- 自动化根因分析与证据关联。
- 支持更细粒度的平台、标签或运营场景维度。
