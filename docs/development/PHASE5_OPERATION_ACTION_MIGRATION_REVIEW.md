# Phase 5 Operation Action Center V012 Pre-Migration Review

## 1. 审查结论

Design V2 的整体边界清晰，三表模型可以满足运营行动的来源追踪、分派、状态管理和历史审计需求。本审查结论为：**有条件允许进入 V012 Migration；必须按本文件冻结的约束和 Service 规则实现，不修改 V001-V011。**

V012 只新增：

1. `operation_actions`
2. `operation_action_sources`
3. `operation_action_history`

## 2. `drama_id` 可空策略

### 2.1 场景判断

- 单剧异常处理（例如 `PLAY_COUNT_DROP_ANOMALY`）：来源记录本身属于某个 Drama，创建行动时必须关联对应 `drama_id`。
- 全局质量行动（例如全局质量评分或规则集问题）：没有单个 Drama 归属，可以使用 `drama_id = NULL`。
- Score 来源通常是单剧评分，要求关联 Drama；MANUAL 行动可按实际范围选择单剧或全局。

因此 `operation_actions.drama_id` 保持 nullable 是合理的，但 NULL 只表示“行动不是单剧范围”，不能表示未知或漏填。

### 2.2 约束建议

数据库层：

- `drama_id` 可空。
- 非空值使用 `FOREIGN KEY dramas(drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT`。
- 不增加“必须有 drama_id”的 CHECK，因为全局行动是合法业务语义。

业务层：

- `ANOMALY` 和 `SCORE` 来源创建行动时，Service 必须读取来源 Drama，并要求 Action 的 `drama_id` 与来源 Drama 一致。
- `QUALITY` 来源若为全局质量评分，允许 NULL；若未来质量结果扩展到单剧范围，必须在来源协议中明确其目标实体后再允许关联。
- `MANUAL` 来源由管理员明确选择单剧或全局；不能从空值推断范围。
- Action 的 `drama_id` 一旦创建不允许修改；范围变更应创建新行动。

这样可避免一个字段同时承担“单剧归属”和“全局范围”的混淆语义。

## 3. 来源证据快照

### 3.1 必须持久化的字段

`operation_action_sources` 应增加并冻结：

- `source_evidence_summary TEXT NOT NULL`：创建行动时的可读证据摘要或人工理由。
- `source_analysis_as_of DATETIME(6) NULL`：来源结果的分析截点；MANUAL 可为空。
- `source_algorithm_version VARCHAR(64) NULL`：来源结果的算法版本；MANUAL 可为空。

`source_metric_snapshot` 不建议作为完整 JSON 或完整业务结果表副本保存。若实际处置需要一个数值，可增加窄字段 `source_metric_value DECIMAL(18,4) NULL`，但 V1 不是必需字段，优先依赖 evidence summary。

### 3.2 持久化目的与边界

快照用于保证未来 Anomaly 重新检测、Quality 重新评分或 Score 重新计算后，历史行动仍能解释“创建当时为什么产生”。快照不是第二份事实表：

- 不复制完整异常、质量或评分结果。
- 不保存短剧名称、平台名称等可变展示字段。
- 来源原记录仍通过 `source_type/source_reference_id` 查询；快照只保存不可变解释所需的最小元数据。
- 创建后快照字段不可更新。

Service 必须校验：非 MANUAL 来源的 algorithm、analysis_as_of 与来源记录一致；MANUAL 必须提供 evidence summary，其他快照字段为空。

## 4. 普通用户与历史事件权限

### 4.1 事件类型冻结

建议 `event_type` 固定为：

- `CREATE`
- `ASSIGN`
- `STATUS_CHANGE`
- `COMMENT`
- `CLOSE`

`CLOSE` 是进入 COMPLETED 或 CANCELLED 的专门审计事件；`STATUS_CHANGE` 用于 OPEN 与 IN_PROGRESS 之间的转换，避免把关闭语义隐藏在普通状态事件中。

### 4.2 事件字段

`operation_action_history` 保留：

- `history_id` 主键
- `action_id` 外键
- `event_type`
- `from_status` / `to_status`
- `from_owner_user_id` / `to_owner_user_id`
- `changed_by_user_id` 外键
- `comment`
- `changed_at`

字段组合由 Service 校验：

- CREATE：无 from/to，必须有 comment 或初始说明。
- ASSIGN：必须有 owner 前后值。
- STATUS_CHANGE：必须有 status 前后值。
- COMMENT：只要求 comment，不允许改变状态或负责人。
- CLOSE：必须有终态前后值和关闭说明。

### 4.3 USER 权限

普通 USER 只能：

- 查看行动、来源和历史。
- 对自己负责的行动添加 COMMENT 事件。

普通 USER 不得：

- 创建行动。
- 修改负责人、优先级、截止日期。
- 产生 ASSIGN、STATUS_CHANGE 或 CLOSE。
- 通过 COMMENT 事件间接修改状态。

ADMINISTRATOR 可创建、分派、修改状态并关闭行动。所有事件由 Service 以当前 JWT 用户身份写入，客户端不能提交 `changed_by_user_id`。

## 5. 同一来源开放行动唯一性

### 5.1 数据库能力分析

MySQL 普通 UNIQUE 约束无法直接表达“只对父表中 OPEN/IN_PROGRESS 的 Action 生效”：

- `operation_action_sources` 看不到 `operation_actions.status`。
- MySQL 没有跨表部分唯一索引。
- `source_reference_id IS NULL` 的 MANUAL 记录也不会按普通 UNIQUE 约束阻止重复 NULL。

因此不建议为了模拟部分唯一索引，在来源表冗余维护一个易失真的 `active` 字段。

### 5.2 V012 推荐实现

数据库约束：

- UNIQUE `(action_id, source_type, source_reference_id)`：防止同一行动重复关联同一来源。
- INDEX `(source_type, source_reference_id, action_id)`：支持 Service 查找来源的开放行动。
- 不设置跨行动的部分 UNIQUE。

Service 规则：

1. 创建非 MANUAL 来源行动时，在同一事务中查询该来源关联的 Action。
2. 使用 `SELECT ... FOR UPDATE` 锁定可锁定的来源关联行/相关 Action 行，再检查状态是否为 OPEN 或 IN_PROGRESS。
3. 若存在开放行动则拒绝创建；COMPLETED/CANCELLED 行动允许再次创建新的处置行动。
4. MANUAL 来源由 Service 限制每个 Action 一个，且必须有人工理由。

该方案适合 V1，事务边界和并发测试必须覆盖。若未来要求数据库层绝对保证跨行动部分唯一，可考虑专门的来源锁表或数据库触发器，但这会增加迁移和运维复杂度，不纳入 V1。

## 6. 数据库设计审查清单

### 6.1 operation_actions

- 主键：`action_id BIGINT UNSIGNED AUTO_INCREMENT`。
- 外键：`drama_id` 可空且 RESTRICT；`owner_user_id` 可空且 RESTRICT；`created_by_user_id` 必填且 RESTRICT。
- CHECK：priority、status 枚举；标题非空；COMPLETED/CANCELLED 与 completed_at/cancelled_at 一致。
- UNIQUE：不设置标题唯一；同名行动在不同时间或来源下可以合法存在。
- INDEX：`(status, priority, due_date)`、`(owner_user_id, status, due_date)`、`(drama_id, status, created_at)`。

### 6.2 operation_action_sources

- 主键：`source_id BIGINT UNSIGNED AUTO_INCREMENT`。
- 外键：`action_id` RESTRICT；删除行动应先由 Service 处理来源，V1 不级联删除历史。
- CHECK：source_type 枚举；MANUAL 与 reference NULL 一致；非 MANUAL reference 为正数。
- UNIQUE：`(action_id, source_type, source_reference_id)`。
- INDEX：`(source_type, source_reference_id, action_id)`、`(action_id, created_at)`。
- 必填快照：`source_evidence_summary`；analysis_as_of 和 algorithm_version 按来源类型可空。

### 6.3 operation_action_history

- 主键：`history_id BIGINT UNSIGNED AUTO_INCREMENT`。
- 外键：`action_id`、`changed_by_user_id`、owner 前后值均 RESTRICT；历史不可因用户删除而断链。
- CHECK：event_type 枚举；状态和负责人前后字段的组合由数据库基础 CHECK 加 Service 完整校验。
- INDEX：`(action_id, changed_at, history_id)`、`(changed_by_user_id, changed_at)`。
- 不设置历史记录 UPDATE 业务接口；历史写入后不可修改。

## 7. Migration 顺序与兼容性

V012 只新增三张表，不修改 V001-V011，不重编号。依赖顺序为：

```text
V001 → ... → V011 → V012
```

外键依赖现有 `users`、`dramas` 表，V001-V011 已提供这些基础表，因此空库可以按 V001-V012 顺序执行。必须在隔离 MySQL 8.x 实例验证：

- 迁移全部成功。
- 三张表及所有约束、索引存在。
- 外键使用 RESTRICT。
- 现有 V001-V011 文件内容和行为不变。

## 8. ORM 关系审查

建议建立：

- `Drama.operation_actions`：一对多，可选，因为 drama_id 可空。
- `OperationAction.sources`：一对多。
- `OperationAction.history`：一对多。
- `User.owned_actions` 与 `User.created_actions`：分别对应 owner 和 creator。
- `User.action_history_events`：对应 changed_by_user_id。

不建立 Source 到 Anomaly/Quality/Score 的多态 ORM 外键关系；source_reference_id 由 Service 通过对应只读 Repository 验证。这样不会产生循环依赖：Action ORM 只依赖 Drama/User，Source/History 只依赖 Action/User。

## 9. 必须修改项

进入 V012 前必须将以下结论作为实现约束：

1. `drama_id` nullable，并由 Service 按来源类型校验单剧/全局语义。
2. 来源表必须持久化 evidence summary、analysis_as_of 和 algorithm_version 快照。
3. History 必须有 event_type，区分系统事件和人工 COMMENT；USER 只能产生 COMMENT。
4. 同一来源开放行动唯一性由 Service 事务保证，数据库只负责行动内来源唯一和查询索引。
5. `CLOSE` 作为独立事件类型，终态不可逆。

## 10. 建议优化项

- V1 可选增加 `source_metric_value`，但不得扩展成完整结果副本。
- V1 不增加 `action_templates`、自动 Generator 或 Prediction 来源。
- 建议先完成并发创建测试，再决定是否需要专用来源锁表。
- 建议将 `completed_at/cancelled_at` 作为派生审计字段，不允许客户端直接提交。

## 11. 最终准入结论

**允许进入 V012 Migration 阶段，但前提是 SQL/ORM 严格落实本审查的五项必须修改项。**

推荐实现顺序：

1. 冻结 V012 SQL 字段、CHECK、索引和外键。
2. 创建三表 Migration，并在隔离 MySQL 8.x 验证 V001-V012。
3. 创建 ORM 和 metadata/约束测试。
4. 实现三个 Repository，保持无 commit/rollback。
5. 实现 Service、来源校验、状态机和事务测试。

本审查不创建 Migration、不修改 ORM、不修改代码，也不提交 Git。
