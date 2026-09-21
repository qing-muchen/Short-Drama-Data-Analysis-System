# Phase 5 Operation Action Service

## 1. 职责与依赖

`OperationActionService` 负责运营行动的创建、来源唯一性、状态机、负责人分派、处理记录、审计日志和事务边界。

依赖：

- `OperationActionRepository`
- `OperationActionSourceRepository`
- `OperationActionHistoryRepository`
- `OperationLogRepository`
- 可选只读 `SourceValidationProvider`

Service 不依赖 ScoreService、PredictionService、AnomalyService 或 DataQualityService，也不导入 ORM 或执行 SQL。来源存在性通过只读 Provider 校验。

## 2. Service 接口

- `create_action`：管理员创建 OPEN 行动，可同时保存一个来源证据、CREATE 历史和 ACTION_CREATE 日志。
- `update_status`：管理员执行状态转换，生成 STATUS_CHANGE 或 CLOSE 历史及 ACTION_STATUS_UPDATE 日志。
- `complete_action`：要求完成说明，将 IN_PROGRESS 行动关闭为 COMPLETED。
- `assign_action`：管理员修改负责人，生成 ASSIGN 历史和 ACTION_ASSIGN 日志。
- `add_comment`：管理员或当前负责人添加 COMMENT，不改变状态、优先级或负责人。
- `get_action`、`list_actions`、`get_statistics`：只委托 Repository。

## 3. 状态机

允许：

```text
OPEN → IN_PROGRESS
OPEN → CANCELLED
IN_PROGRESS → COMPLETED
IN_PROGRESS → CANCELLED
```

OPEN 不能直接 COMPLETED；COMPLETED 和 CANCELLED 是不可逆终态。关闭使用 CLOSE 历史事件，非终态转换使用 STATUS_CHANGE。非法转换抛出 `ValidationException`。

## 4. 来源唯一性

ANOMALY、QUALITY、SCORE、MANUAL 是 V1 支持的来源。MANUAL 不允许 reference id，其他来源必须提供正整数 reference id。来源证据摘要必填。

创建行动时，Service 在事务内调用 Repository 查询同一来源是否已关联 OPEN/IN_PROGRESS 行动；存在时抛出 `ConflictException`。COMPLETED/CANCELLED 不阻止后续创建。数据库仍负责行动内部来源组合唯一性。

## 5. 权限

- ADMINISTRATOR：创建、分派和修改状态。
- USER：仅允许对自己负责的行动添加 COMMENT。
- COMMENT 不携带 old/new status，也不修改 Action 主体。

当前角色由调用层传入，API 阶段仍需使用已认证 JWT 用户构造参数，客户端不能自行声明角色。

## 6. OperationLog

记录：

- `ACTION_CREATE`
- `ACTION_ASSIGN`
- `ACTION_STATUS_UPDATE`
- `ACTION_COMMENT`

现有 operation_logs 没有 Action 专用目标外键，因此 Action ID 写入 detail；单剧行动以 drama 为审计目标，全局行动以操作者用户作为目标。本阶段不修改 operation_logs 表结构。

## 7. 事务设计

所有写流程使用 `BaseService.transaction()`：Repository 写入、History 和 OperationLog 全部成功后只 commit 一次；任何 Repository、History 或 OperationLog 异常均 rollback，不能留下部分行动。

Repository 只 flush。查询方法使用 `BaseService.read()` 并保持 Repository 的排序、分页和统计结果。

## 8. 测试结果

测试覆盖创建 Action、Source 和 CREATE History；开放来源冲突与关闭后重建；全部合法/非法状态转换；终态保护；分派、评论权限；全局行动和 MANUAL 来源；Repository、History、OperationLog 失败回滚；查询委托与无 ORM/SQL 边界检查。

Service 专项及关联测试通过。完整后端测试结果：`375 passed`。
