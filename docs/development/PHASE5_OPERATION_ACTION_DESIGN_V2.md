# Phase 5 Operation Action Center Design V2

## 1. 设计目标与模块定位

Phase 5 建设“运营行动与告警处置中心”，把既有分析结果转化为可分派、可追踪、可审计的运营处理流程。

```text
Anomaly / Quality / Score / Manual
                  ↓
          Operation Action
                  ↓
             Assignment
                  ↓
           Status Tracking
                  ↓
         Resolution History
```

本模块不是通用 Todo 或普通任务管理系统。每个行动必须具备受控来源和运营处置语义，并可追溯到异常、质量评分、综合评分或经过说明的人工判断。它不重新计算 Score、Quality、Prediction 或 Anomaly，也不改变这些分析结果。

## 2. 设计原则

1. 分析事实与处置流程分离：已有结果保持只读，行动独立保存。
2. 行动与来源解耦：一个行动可关联多个来源，一个来源也可在历史上关联多个行动。
3. 当前状态与变更历史分离：主体表保存当前值，历史表保存过程事件。
4. Service 管理状态机、权限、来源验证和事务；Repository 只访问数据库。
5. V1 不自动生成行动，不引入动态模板或规则引擎。
6. 所有时间使用 UTC；所有外键默认 `ON DELETE RESTRICT ON UPDATE RESTRICT`。

## 3. 数据模型总览

V012 新增三张表：

```text
users ───────┐
dramas ──────┼── operation_actions
             │          1
             │          ├── N operation_action_sources
             │          └── N operation_action_history
users ───────┘
```

三张表分别表示行动当前状态、分析来源和过程历史，职责不重叠，符合第三范式。

## 4. operation_actions

### 4.1 字段设计

| 字段 | 类型建议 | 空值 | 说明 |
| --- | --- | --- | --- |
| `action_id` | BIGINT UNSIGNED | NOT NULL | 主键，自增 |
| `drama_id` | BIGINT UNSIGNED | NULL | 单剧行动的可选外键；全局质量行动可为空 |
| `title` | VARCHAR(200) | NOT NULL | 行动标题，禁止空字符串 |
| `description` | TEXT | NULL | 运营目标、处理要求和边界 |
| `priority` | VARCHAR(16) | NOT NULL | `LOW/MEDIUM/HIGH/URGENT` |
| `status` | VARCHAR(16) | NOT NULL | `OPEN/IN_PROGRESS/COMPLETED/CANCELLED` |
| `owner_user_id` | BIGINT UNSIGNED | NULL | 当前负责人；未分派时为空 |
| `due_date` | DATE | NULL | 截止日期；未设置 SLA 时为空 |
| `created_by_user_id` | BIGINT UNSIGNED | NOT NULL | 创建人，用于权限与审计 |
| `completed_at` | DATETIME(6) | NULL | 进入 COMPLETED 的时间 |
| `cancelled_at` | DATETIME(6) | NULL | 进入 CANCELLED 的时间 |
| `created_at` | DATETIME(6) | NOT NULL | UTC 创建时间 |
| `updated_at` | DATETIME(6) | NOT NULL | UTC 更新时间 |

`completed_at` 和 `cancelled_at` 有明确业务依据，可支持处理时长和关闭趋势统计，由 Service 根据状态转换维护。V1 不增加完成率、评分、标签、平台名称等无依据字段。

### 4.2 字段审查结论

- `drama_id` 保留但允许为空。异常和单剧评分行动可关联 Drama；全局质量评分行动不应被迫绑定短剧。
- `owner_user_id` 允许为空，因为新建行动可以暂未分派。
- `created_by_user_id` 必须保留，OperationLog 不能替代主体的创建责任关系。
- `due_date` 允许为空；V1 逾期定义为 `due_date < current_date AND status IN (OPEN, IN_PROGRESS)`。
- 不在主体表保存 `source_type/source_id`，避免限制一个行动只能有一个来源。

### 4.3 约束与索引

建议约束：

- CHECK `priority IN ('LOW','MEDIUM','HIGH','URGENT')`。
- CHECK `status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELLED')`。
- CHECK `TRIM(title) <> ''`。
- CHECK COMPLETED 状态与 `completed_at` 一致。
- CHECK CANCELLED 状态与 `cancelled_at` 一致。

建议索引：

- `(status, priority, due_date)`：待办、优先级和逾期查询。
- `(owner_user_id, status, due_date)`：负责人工作台。
- `(drama_id, status, created_at)`：单剧行动历史。
- `(created_at)`：时间趋势统计。

## 5. operation_action_sources

### 5.1 作用与字段

该表保存行动与分析来源的受控多态关联，避免在行动表中建立多张 nullable 外键。

| 字段 | 类型建议 | 空值 | 说明 |
| --- | --- | --- | --- |
| `source_id` | BIGINT UNSIGNED | NOT NULL | 主键，自增 |
| `action_id` | BIGINT UNSIGNED | NOT NULL | 外键到 `operation_actions` |
| `source_type` | VARCHAR(16) | NOT NULL | `ANOMALY/QUALITY/SCORE/MANUAL` |
| `source_reference_id` | BIGINT UNSIGNED | NULL | 逻辑引用；MANUAL 时为空 |
| `source_summary` | TEXT | NOT NULL | 创建时的不可变来源摘要或人工理由 |
| `source_analysis_as_of` | DATETIME(6) | NULL | 来源结果的分析时间点 |
| `source_algorithm_version` | VARCHAR(64) | NULL | 来源结果的算法版本 |
| `created_at` | DATETIME(6) | NOT NULL | UTC 创建时间 |

`source_summary`、`source_analysis_as_of` 和 `source_algorithm_version` 是审计快照，不是运营事实副本。它们保证来源记录状态变化后仍能解释行动创建依据。禁止复制短剧名称、平台名称或完整原始指标。

### 5.2 来源类型

| source_type | 逻辑来源 | V1规则 |
| --- | --- | --- |
| `ANOMALY` | `data_anomaly_records.anomaly_id` | 必须存在；建议用于 A/B 级异常 |
| `QUALITY` | `data_quality_scores.quality_score_id` | 必须存在；摘要说明阻断维度或规则结果 |
| `SCORE` | `drama_scores.id` | 必须存在；由管理员判断是否需要行动 |
| `MANUAL` | 无数据库来源 | `source_reference_id` 必须为空，`source_summary` 必须说明原因 |

Prediction 在 V1 不作为来源类型，不自动触发行动；可在 description 中作为运营上下文引用，但不能形成逻辑关联。

### 5.3 约束与来源验证

- CHECK `source_type` 为四个固定值。
- CHECK MANUAL 与 `source_reference_id IS NULL` 一致；非 MANUAL 必须有正整数引用 ID。
- UNIQUE `(action_id, source_type, source_reference_id)`，防止同一行动重复关联同一分析结果。
- INDEX `(source_type, source_reference_id)`，支持从分析结果反查行动。
- INDEX `(action_id, created_at)`，支持详情加载。

由于多态逻辑引用无法建立单一数据库外键，OperationActionService 必须按 `source_type` 使用只读 Repository 校验来源存在性。V1 同一非 MANUAL 来源只允许存在一个未关闭行动；该跨行动规则由 Service 在事务内检查。MANUAL 来源每个行动最多一个，由 Service 校验。

## 6. operation_action_history

### 6.1 作用与字段

用户需要添加处理记录，而管理员还需要分派和改变状态，因此历史表不能只记录状态变更。V1 增加 `event_type` 以统一表达过程事件。

| 字段 | 类型建议 | 空值 | 说明 |
| --- | --- | --- | --- |
| `history_id` | BIGINT UNSIGNED | NOT NULL | 主键，自增 |
| `action_id` | BIGINT UNSIGNED | NOT NULL | 外键到 `operation_actions` |
| `event_type` | VARCHAR(24) | NOT NULL | `CREATED/COMMENT_ADDED/ASSIGNED/STATUS_CHANGED` |
| `from_status` | VARCHAR(16) | NULL | 状态变化前值 |
| `to_status` | VARCHAR(16) | NULL | 状态变化后值 |
| `from_owner_user_id` | BIGINT UNSIGNED | NULL | 分派前负责人 |
| `to_owner_user_id` | BIGINT UNSIGNED | NULL | 分派后负责人 |
| `changed_by_user_id` | BIGINT UNSIGNED | NOT NULL | 操作者外键 |
| `comment` | TEXT | NULL | 处理说明、完成说明或取消理由 |
| `changed_at` | DATETIME(6) | NOT NULL | UTC 事件时间 |

状态变化事件必须同时具备 `from_status/to_status`；分派事件使用 owner 前后值；处理记录使用 `COMMENT_ADDED`。Service 负责事件字段组合校验，数据库以 CHECK 固定枚举和关键空值规则。

建议索引：

- `(action_id, changed_at, history_id)`：按时间稳定展示处理历史。
- `(changed_by_user_id, changed_at)`：操作者审计。

Action History 用于业务详情回放，OperationLog 用于系统级操作审计；状态和分派变更在同一事务中同时写入两者。

## 7. 状态模型

V1 状态定义：

- `OPEN`：已创建、尚未开始，可未分派。
- `IN_PROGRESS`：已开始处理，必须有负责人。
- `COMPLETED`：处理完成，必须有完成说明并设置 `completed_at`。
- `CANCELLED`：确认无需继续，必须有取消理由并设置 `cancelled_at`。

唯一允许的状态转换：

```text
OPEN → IN_PROGRESS → COMPLETED
OPEN → CANCELLED
IN_PROGRESS → CANCELLED
```

禁止：

- `COMPLETED` 或 `CANCELLED` 再次修改状态。
- 从 `OPEN` 直接进入 `COMPLETED`。
- 无负责人进入 `IN_PROGRESS`。
- 无说明进入 `COMPLETED` 或 `CANCELLED`。

状态机由 Service 实现；Router 只接收目标状态和 comment，Repository 不判断状态合法性。

## 8. 权限模型

### 8.1 ADMINISTRATOR

- 创建行动并关联来源。
- 设置或修改负责人、优先级和截止日期。
- 执行所有允许的状态转换。
- 关闭行动（COMPLETED/CANCELLED）。
- 查看全部行动、来源和历史。

### 8.2 USER

- 查看行动、来源和历史。
- 对自己负责的行动添加 `COMMENT_ADDED` 处理记录。
- V1 不允许创建行动、修改负责人、优先级、截止日期或状态。

权限校验在 OperationActionService 中完成。Router 使用 JWT 用户身份调用 Service，不直接修改 ORM；Repository 不做角色判断。

## 9. Service 与 Repository 架构

### 9.1 分层

```text
Router
  ↓
OperationActionService
  ├── ActionRepository
  ├── ActionSourceRepository
  ├── ActionHistoryRepository
  ├── Source Read Repository
  └── OperationLogRepository
       ↓
     Database
```

OperationActionService 不调用 ScoreService、PredictionService、AnomalyService 或 DataQualityService。来源校验通过各模块的只读 Repository 或专用只读 Provider 完成，避免 Service 间反向耦合。

### 9.2 Service 职责

- `create_action`：校验管理员、字段、来源存在性和开放行动唯一性；保存 Action、Sources、CREATED History 和 OperationLog。
- `assign_owner`：校验负责人，更新 Action，保存 ASSIGNED History 和 OperationLog。
- `transition_status`：校验状态机和说明，更新 Action，保存 STATUS_CHANGED History 和 OperationLog。
- `add_history_comment`：校验用户是否为负责人或管理员，保存 COMMENT_ADDED History。
- `get_actions/get_action/get_statistics`：委托 Repository 查询，不重新计算分析结果。

### 9.3 事务边界

创建行动事务：

```text
Action + Sources + CREATED History + OperationLog → COMMIT
```

状态或分派事务：

```text
Action update + History + OperationLog → COMMIT
```

任何步骤失败统一 rollback。Repository 只能 add、query、update 和 flush，不得 commit、rollback 或创建 Session。

## 10. API V1 设计

统一前缀 `/api/v1`，成功响应使用 `ResponseModel[T]`，错误使用现有 `ErrorResponse`。

### 10.1 POST `/operation-actions`

- 权限：ADMINISTRATOR。
- 请求：`drama_id?`、`title`、`description?`、`priority`、`owner_user_id?`、`due_date?`、`sources`。
- 客户端不得提交 status、created_by、completed_at、cancelled_at。
- 至少一个来源；MANUAL 必须提供来源说明。
- 返回完整行动摘要。

### 10.2 GET `/operation-actions`

- 权限：USER / ADMINISTRATOR。
- 参数：status、priority、owner_user_id、source_type、drama_id、overdue、page、page_size。
- 普通用户是否只看自己负责的行动由 V1 权限策略固定为“可查看全部，不能修改他人行动”。
- 稳定排序：优先级 DESC、due_date ASC、created_at DESC、action_id DESC。

### 10.3 GET `/operation-actions/{action_id}`

- 权限：USER / ADMINISTRATOR。
- 返回 Action、Sources 和按 `changed_at/history_id` 升序的 History。
- 不直接返回来源表完整 ORM，只返回经过 Schema 控制的证据摘要和可导航 ID。

### 10.4 PATCH `/operation-actions/{action_id}/status`

- 权限：ADMINISTRATOR。
- 请求：`status`、`comment`。
- 调用 `transition_status`，Router 不实现状态机。

### 10.5 POST `/operation-actions/{action_id}/history`

- 权限：负责人 USER 或 ADMINISTRATOR。
- 请求只允许 `comment`。
- 创建 `COMMENT_ADDED`，不能借此改变状态、负责人或优先级。

分派负责人建议增加独立接口 `PATCH /operation-actions/{action_id}/owner`。它是 V1 必需能力，否则创建后无法安全重新分派；请求只包含 `owner_user_id`，权限为 ADMINISTRATOR。

统计接口建议为 `GET /operation-actions/statistics`，供 Dashboard 直接获取待处理、优先级、状态、逾期和来源分布，避免前端统计。

## 11. Dashboard V1 设计

页面建议为 `/operation-actions`，展示：

- 待处理数量：OPEN + IN_PROGRESS。
- 优先级分布：LOW/MEDIUM/HIGH/URGENT。
- 状态分布。
- 逾期行动数量和列表。
- 来源类型分布。
- 行动详情：来源证据、负责人、截止日期和处理历史。

管理员显示创建、分派和状态修改入口；普通用户显示查看和添加处理记录入口。前端只消费 API，不判断状态转换、不计算逾期、不重新计算 Score、Quality、Prediction 或 Anomaly。

## 12. V012 Migration 规划

V012 文件建议：

`database/migrations/V012__create_operation_action_tables.sql`

新增：

1. `operation_actions`
2. `operation_action_sources`
3. `operation_action_history`

不修改 V001-V011，不重编号既有 Migration。V012 必须包含主键、外键、CHECK、UNIQUE 和查询索引，并与 SQLAlchemy metadata 保持一致。执行前需确认 V001-V011 在隔离 MySQL 8.x 实例可连续迁移。

## 13. 风险与控制

### 13.1 退化为 Todo 系统

通过强制来源、证据摘要、分析时间和算法版本体现分析系统价值。行动详情必须可导航到来源结果。

### 13.2 行动来源可信性

非 MANUAL 来源由 Service 校验记录存在和类型匹配；已有分析结果只读，不允许行动模块修改来源状态或算法输出。

### 13.3 人工创建质量

V1 只有管理员可创建；MANUAL 必须填写理由；同一来源只能存在一个开放行动；所有创建写 OperationLog。

### 13.4 自动 Action Generator

V1 不实现自动生成。未来可以新增独立 `ActionGenerationPolicy` 和批处理编排器，由其读取分析结果并生成“候选行动”，仍不得嵌入 AnomalyService 或 DataQualityService。候选行动应经管理员确认后才成为正式行动。

### 13.5 多态逻辑引用

`source_reference_id` 无法使用单一物理外键，是 V1 的主要结构风险。通过来源枚举、Service 存在性校验、不可变证据摘要、唯一约束和来源删除限制共同控制。

## 14. 测试规划

- Database/ORM：三表、外键、CHECK、UNIQUE、索引、MySQL DDL 和 V001-V012 迁移。
- Repository：保存、分页、来源查询、历史稳定排序、统计、无 commit/rollback。
- Service：来源校验、开放行动去重、权限、状态转换、分派、历史和事务回滚。
- API：JWT、管理员/用户权限、参数约束、分页、404、统一响应和 Router 边界。
- Dashboard：加载、空数据、错误、筛选、详情、角色按钮和生产构建。

重点边界测试包括：无来源创建、MANUAL 无理由、来源不存在、重复开放行动、无负责人进入处理中、非法终态修改、日志失败回滚。

## 15. 实现准入结论

Design V2 已冻结模块定位、三表职责、来源模型、状态机、权限、事务和 API 边界。完成一次针对以下事项的最终审查后，可进入 V012 Migration 阶段：

1. 确认 `drama_id` 可空策略。
2. 确认 source evidence 快照字段。
3. 确认普通用户只添加处理记录、不修改状态。
4. 确认一个来源仅允许一个开放行动的 Service 约束。

在该审查通过前，不创建 Migration、ORM 或业务代码。
