# Phase 5 Operation Action Repository

## 1. 职责

本层负责 `operation_actions`、`operation_action_sources` 和 `operation_action_history` 的 SQLAlchemy 查询与持久化。Repository 不判断权限、不判断状态转换、不创建 OperationLog，也不调用其他模块 Service。

Repository 只使用注入的 Session，并通过 `add`、`execute`、`scalar`、`scalars` 和 `flush` 完成数据库访问；不创建 Session，不执行 `commit` 或 `rollback`。

## 2. 接口

### OperationActionRepository

- `create_action`：接收 ORM 对象或字段映射，保存并 flush。
- `get_action_by_id`：使用 joinedload 一次加载 sources、history、drama、assignee 和 creator，避免详情页 N+1。
- `list_actions`：按 status、priority、assignee_user_id、drama_id 过滤，使用 BaseRepository Page 分页，按 created_at/action_id 倒序。
- `update_action_fields`：仅更新 title、description、priority、assignee_user_id、due_date；不修改 status，不判断状态转换。
- `count_statistics`：使用数据库聚合统计 total 和四种状态数量。

### OperationActionSourceRepository

- `create_source`：保存证据快照并 flush。
- `get_sources_by_action`：按 created_at/source_id 正序查询。
- `exists_source`：在指定 Action 内检查 source_type/source_reference_id 组合是否存在。

### OperationActionHistoryRepository

- `create_history`：保存事件并 flush。
- `get_history_by_action`：按 created_at/history_id 正序返回事件。

状态权限、来源业务存在性、开放行动唯一性和 OperationLog 均留给后续 Service。

## 3. 查询与事务边界

列表查询使用数据库过滤、排序和分页；详情查询使用 joinedload 预加载关系。Repository 不在 Python 层重新排序或聚合业务结果。所有写操作只 flush，使同一 Session 内的后续 Service 操作可见，但最终提交由 Service 统一管理。

## 4. 测试结果

新增测试覆盖创建、详情 eager load、筛选分页、字段更新、数据库聚合、来源查询、历史顺序和事务边界源码检查。完整后端测试在本阶段运行结果为 `357 passed`。

## 5. 后续边界

下一阶段 OperationActionService 将负责：来源类型和逻辑引用校验、状态机、管理员/普通用户权限、同一来源开放行动唯一性、History 事件语义、OperationLog 和事务回滚。Repository 不承担上述业务职责。
