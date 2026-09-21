# Phase 5 Operation Action Center V012 Database + ORM

## 1. 实现范围

本阶段仅完成 V012 Migration、SQLAlchemy ORM 映射和结构测试，没有实现 Repository、Service、API 或 Frontend。

V012 在 V001-V011 之后新增三张表，现有迁移文件保持不变。V011 后 ORM 表数量为 25，V012 后为 28。

## 2. 三表设计

### operation_actions

保存行动当前状态：`action_id`、可空 `drama_id`、标题、描述、优先级、状态、负责人、创建人、截止日期和审计时间。Drama、负责人和创建人均使用 RESTRICT 外键。

状态固定为 `OPEN`、`IN_PROGRESS`、`COMPLETED`、`CANCELLED`；优先级固定为 `LOW`、`MEDIUM`、`HIGH`。标题非空，建立状态、优先级、负责人和 Drama 查询索引。

### operation_action_sources

保存 `ANOMALY`、`QUALITY`、`SCORE`、`MANUAL` 来源及不可变证据快照。`source_reference_id` 是逻辑引用，不建立多态物理外键；`source_evidence_summary` 必填，分析时间和算法版本对 MANUAL 来源可为空。Action 删除时来源 CASCADE，行动内来源组合唯一。

### operation_action_history

保存 CREATE、ASSIGN、STATUS_CHANGE、COMMENT、CLOSE 事件，包含旧/新状态、操作人和处理说明。Action 删除时历史 CASCADE，操作人使用 RESTRICT 外键，按 Action 和创建时间建立稳定查询索引。

## 3. ORM 关系

- `Drama.operation_actions` → `OperationAction` 一对多。
- `OperationAction.sources` → `OperationActionSource` 一对多。
- `OperationAction.history` → `OperationActionHistory` 一对多。
- `User.created_actions`、`User.assigned_actions`、`User.action_history` 分别对应创建人、负责人和历史操作人。

不建立 OperationAction 到 Anomaly、QualityScore 或 Score 的 ORM 关系，来源通过逻辑引用和后续 Service 校验，避免多态外键与循环依赖。

## 4. 约束与事务边界

数据库负责枚举 CHECK、标题非空、来源类型/引用一致性、来源摘要非空、外键和行动内来源唯一。数据库不负责权限和状态转换；后续 Service 负责普通用户 COMMENT 权限、状态机和同一来源开放行动唯一性。

本阶段未实现事务 Service。后续 Repository 不得 commit/rollback，Action、Source、History 与 OperationLog 将由 Service 统一提交。

## 5. 测试

已新增 ORM metadata、关系、CHECK、UNIQUE、Index 和 MySQL DDL 编译测试，并更新模型导入表清单。当前后端全量测试结果为 `349 passed`，其中新增 Operation Action 模型测试通过。隔离 MySQL V001-V012 执行验证和 SQL 约束回归需要可用的 MySQL 8.x 实例；当前环境未执行真实数据库迁移，不能将其结果标记为已验证。本阶段不修改 V001-V011。
