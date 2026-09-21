# Phase 5 Operation Action Module Summary

## 1. 模块定位

Phase 5 建立 Operation Action Center，将 Anomaly、Data Quality、Composite Score 和 Prediction 等分析结果转化为可分派、可处理、可审计的运营处置闭环。它不是普通 Todo 系统，也不重新计算或修改任何分析结果。

行动中心只消费已有分析结果，通过逻辑来源引用和证据快照保留解释上下文；分析模块不反向依赖 Operation Action。

## 2. 架构总览

```text
Analysis Modules
      ↓
Operation Action
      ↓
Service 状态机
      ↓
History / OperationLog
      ↓
API
      ↓
Dashboard
```

数据库由 ORM 映射，Repository 负责数据访问，Service 负责状态转换、来源唯一性、权限业务规则、历史记录和事务，API 负责鉴权、参数校验与响应转换，Vue 前端只展示 API 结果并发起用户操作。

## 3. V012 数据库设计

V012 新增三张表：

- `operation_actions`：行动主实体。`drama_id` 可为空，以支持单剧行动和全局质量行动；保存标题、描述、优先级、状态、负责人、创建人和截止日期。
- `operation_action_sources`：行动来源及证据快照。保存 `source_type`、`source_reference_id`、`source_evidence_summary`、`source_analysis_as_of` 和 `source_algorithm_version`。
- `operation_action_history`：不可变处理记录。保存 `event_type`、状态变化、操作人、评论和时间。

数据库约束包括状态和优先级 CHECK、来源类型和事件类型 CHECK、同一行动来源唯一约束、主外键约束以及面向状态、负责人、来源和历史查询的索引。来源采用逻辑 `source_reference_id`，没有复制短剧名称、平台名称或完整分析结果表。

## 4. ORM关系

```text
Drama 1 ── N OperationAction
OperationAction 1 ── N OperationActionSource
OperationAction 1 ── N OperationActionHistory
User ── creator / assignee / operator
```

没有建立 OperationAction 到 Anomaly、QualityScore、DramaScore 或 PredictionResult 的强外键关系，避免多态来源导致的循环依赖；来源证据通过弱关联和快照保持历史可解释性。

## 5. Repository层

三个 Repository 各自负责单一数据实体：

- `OperationActionRepository`：创建、详情、列表分页、字段更新和状态统计。
- `OperationActionSourceRepository`：创建来源、查询来源、检查行动内来源唯一性及开放行动来源。
- `OperationActionHistoryRepository`：创建和查询行动历史。

Repository 只执行 ORM 查询、写入和 `flush`，不创建 Session、不提交或回滚事务、不判断权限、不实现状态机和来源业务规则。

## 6. Service层

`OperationActionService` 提供：

- `create_action`
- `update_status`
- `complete_action`
- `assign_action`
- `add_comment`
- `get_action`
- `list_actions`
- `get_statistics`

V1 状态机为：

```text
OPEN → IN_PROGRESS → COMPLETED
  └──────────────→ CANCELLED
IN_PROGRESS ────→ CANCELLED
```

已完成或已取消的行动不可再次转换；OPEN 不能直接完成。状态合法性、管理员权限、来源唯一性和评论规则均由 Service 执行，非法转换返回业务校验错误。

## 7. 事务设计

一次创建或变更操作在同一个 Session 中完成：

```text
Action / Source
      ↓
History
      ↓
OperationLog
      ↓
COMMIT
```

任一 Repository、History 或 OperationLog 操作失败，Service 统一 rollback，避免产生部分行动、孤立来源或缺失审计记录。

## 8. API设计

统一前缀为 `/api/v1/operation-actions`：

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| POST | `/operation-actions` | ADMINISTRATOR | 创建行动 |
| GET | `/operation-actions` | USER / ADMINISTRATOR | 分页查询 |
| GET | `/operation-actions/statistics` | USER / ADMINISTRATOR | 状态统计 |
| GET | `/operation-actions/{action_id}` | USER / ADMINISTRATOR | 查看详情 |
| PATCH | `/operation-actions/{action_id}/status` | ADMINISTRATOR | 状态变更 |
| PATCH | `/operation-actions/{action_id}/assign` | ADMINISTRATOR | 分派负责人 |
| POST | `/operation-actions/{action_id}/comments` | USER / ADMINISTRATOR | 添加评论 |

接口沿用 JWT Bearer、`ResponseModel[T]` 和 `ErrorResponse`。Router 不访问 ORM、Repository 或 Session，也不判断状态转换和来源重复。

## 9. Dashboard设计

页面路径为 `/operation-actions`，包含：

- 行动总数及 OPEN、IN_PROGRESS、COMPLETED、CANCELLED 统计卡片
- 服务端状态和优先级筛选的行动列表
- 行动详情抽屉
- 来源证据与分析时间、算法版本
- CREATE、ASSIGN、STATUS_CHANGE、COMMENT、CLOSE 时间线
- 管理员状态更新、负责人分派和行动创建
- 登录用户评论
- 状态分布 ECharts 环形图

前端不计算状态转换、不判断来源唯一性、不生成 History 或 OperationLog，仅调用后端 API 并展示结果。

## 10. 测试记录

Phase 5 覆盖数据库约束、ORM关系、Repository 数据访问、Service 状态机与事务、API 权限和响应结构，以及前端类型和生产构建验证。

- Backend：数据库、Repository、Service、API 测试均通过。
- Frontend：`npm exec vue-tsc -- --noEmit` 通过。
- Frontend：`npm run build` 通过；构建中的 chunk size warning 为非阻塞提示。

## 11. Git提交记录

| Commit | Message | 内容 |
|---|---|---|
| `5ed2d8a` | `feat(phase5): add operation action database schema` | V012 数据库与 ORM |
| `7b705ab` | `feat(phase5): add operation action repositories` | 三个 Repository |
| `5404f27` | `feat(phase5): add operation action service` | Service 状态机与事务编排 |
| `4814f3d` | `feat(phase5): add operation action api` | Schema、Router、API测试 |
| `7883b3a` | `feat(phase5): add operation action dashboard` | API Client、页面与入口 |
| 待提交 | `docs(phase5): add operation action module summary` | 本归档文档 |

## 12. 当前限制与未来方向

当前版本：

- 没有自动行动生成器
- 没有 Action 模板
- 没有来源实时同步
- 没有 SLA 管理
- 没有复杂工作流编排

这些能力保留给后续独立阶段，避免当前行动中心退化为无分析依据的 Todo 系统。
