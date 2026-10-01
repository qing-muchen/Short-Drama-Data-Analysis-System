# Phase 5 Operation Action Center 架构审查

## 1. 审查结论

运营行动与告警处置中心适合作为 Phase 5，但需要以“分析结果的处置闭环”为边界，而不是重新实现评分、质量判断、预测或异常检测。

审查结论为：**有条件通过，可进入 Design V2 修订，不允许直接进入数据库或代码实现。**

必须遵守以下总原则：

- Score、Data Quality、Prediction、Anomaly 只读提供分析结果。
- Operation Action 独立保存行动生命周期，不修改已有异常、质量、评分或预测记录。
- 行动创建必须有明确来源或人工理由，不能退化为无约束 Todo。
- Action Service 负责流程和权限，不重新判断来源结果的业务含义。

## 2. 与已有模块的边界

| 模块 | 负责的问题 | Phase 5 的关系 |
| --- | --- | --- |
| Score | 短剧当前综合表现如何 | 可作为行动来源或详情上下文，不重新计算评分 |
| Data Quality | 数据是否可信 | 可将 ERROR 质量问题转为处置行动，不修改质量结果 |
| Prediction | 下一日趋势如何 | 只提供预测证据，不把预测直接当作行动结论 |
| Anomaly | 当前行为是否偏离正常范围 | A/B 级异常可触发候选行动，不修改异常状态 |
| Operation Action | 谁在何时采取什么运营措施，结果如何 | 新增的流程闭环 |

因此该模块不与已有模块重复。它消费分析结果，管理负责人、优先级、截止时间、处理说明和完成状态。

## 3. 是否独立保存行动

建议新增独立的 `operation_actions` 实体，不在 `data_anomaly_records` 中增加负责人、截止时间或处理描述字段。原因如下：

1. 一个异常可能产生多个行动，异常记录与行动不是一对一关系。
2. 一个行动可以处理多个相关来源，尤其是质量问题和异常同时发生时。
3. 行动有独立生命周期和权限，不应改变分析事实的不可变性。
4. 历史分析结果需要保持原始状态，避免“处理完成”被误解为“异常消失”。

建议的表集合：

- `operation_actions`：行动当前状态和主体信息。
- `operation_action_sources`：行动与来源结果的关联。
- `operation_action_history`：状态、负责人、优先级等变更历史。

`action_templates` 不建议作为 V1 必需表。若后续出现稳定的运营处置模板，再通过独立设计增加；不能为了预留字段而提前引入模板管理复杂度。

## 4. 数据模型建议

### 4.1 Action 主体

建议保留以下字段：

| 字段 | 建议 | 说明 |
| --- | --- | --- |
| `action_id` | 必须 | BIGINT 主键 |
| `title` | 必须 | 人类可读的行动标题 |
| `description` | 可选 | 行动目标、执行要求和处理说明 |
| `priority` | 必须 | 建议固定 `LOW/MEDIUM/HIGH/URGENT` |
| `status` | 必须 | 建议 `OPEN/IN_PROGRESS/COMPLETED/CANCELLED` |
| `owner_user_id` | 可选 | 当前负责人，外键到 users；未分派时为空 |
| `due_date` | 可选 | 截止日期；无时表示未设定 SLA |
| `created_at` / `updated_at` | 必须 | 统一 UTC 时间 |

`drama_id` 不建议直接作为 Action 主体的必填字段。因为行动可能处理全局质量问题或多个短剧。若 V1 明确只允许单剧行动，可保留可空的 `drama_id`，但不能同时把它当作来源关联的替代品。

不建议在主体表保存 `source_type`、`source_id`、短剧名称、平台名称或复制的 anomaly/quality/prediction 数值。这些属于关联或证据，不是行动实体的固有属性。

### 4.2 来源关联

建议支持以下来源类型：

- `ANOMALY`
- `QUALITY`
- `SCORE`
- `MANUAL`

`PREDICTION` 不建议作为 V1 自动行动来源；预测可作为行动详情中的上下文，但不应单独触发处置。`MANUAL` 来源没有数据库对象 ID，必须要求创建理由或说明。

不建议在 `operation_actions` 中采用 `source_type + source_id` 单字段多态关联作为唯一设计，因为数据库无法对 `source_id` 建立真正的外键，也无法防止指向不存在的对象。推荐：

```text
operation_actions
        1
        ↓
operation_action_sources
        ↓ N
source_type + source_id
```

该关联表是受控多态关联：Service 根据 `source_type` 白名单校验来源存在性和权限，数据库通过 `(action_id, source_type, source_id)` 唯一约束防止重复关联。若后续需要强数据库外键，可为每种来源拆分专用关联表，但 V1 不建议过度扩张表数量。

### 4.3 第三范式审查

上述模型符合第三范式：行动主体属性只依赖 `action_id`，来源关联单独建表，状态变更历史按事件保存，不把短剧名称、异常证据或评分值冗余复制到行动主体。`source_type` 的枚举约束、优先级和状态约束应在数据库 CHECK 与 Service 校验中同时保持一致。

## 5. 状态与历史模型

建议 V1 状态：

- `OPEN`：已创建，尚未开始。
- `IN_PROGRESS`：已有负责人并正在处理。
- `COMPLETED`：行动完成并需要保留完成说明。
- `CANCELLED`：经确认无需继续处理。

建议使用 `operation_action_history` 保存状态、负责人、优先级和截止时间的变更前后值、操作者和变更时间。不能仅依赖 `operation_logs`，原因是：

- `operation_logs` 记录系统操作摘要，适合审计“发生过什么”。
- Action History 需要支持行动详情页的顺序重放和前后值查询。

两者应协同：状态变更在同一事务中写入 Action History 和 OperationLog。`resolved_at/resolved_by` 可由完成状态推导，也可作为查询优化字段；若保存，必须由 Service 在状态进入 `COMPLETED` 时统一维护，不能允许客户端任意填写。

合法状态转换建议冻结为：

```text
OPEN → IN_PROGRESS → COMPLETED
OPEN → CANCELLED
IN_PROGRESS → CANCELLED
```

已完成或已取消的行动默认不可重新打开，若确有需要应创建新行动，避免历史语义混乱。

## 6. 权限设计

### ADMINISTRATOR

- 创建系统行动和人工行动。
- 分派或修改负责人。
- 修改优先级、截止时间和状态。
- 关联或解除来源。
- 查看全部行动和历史。

### USER

- 查看被授权范围内的行动。
- 查看来源证据和处理历史。
- 更新自己负责行动的处理说明，是否允许推进状态需在 Design V2 冻结。

建议 V1 只允许管理员创建、分派、关闭行动；普通用户可查看并补充处理记录。这样可以防止普通用户批量创建无意义行动，同时保留协同处理能力。所有权限最终由后端 Service 校验，Router 不直接判断业务关系。

## 7. 架构影响

建议新增：

- Database：`operation_actions`、`operation_action_sources`、`operation_action_history`。
- ORM：对应三类实体及 users 的负责人关系。
- Repository：行动主体、来源和历史的查询与持久化。
- Service：来源校验、权限、状态机、事务和日志。
- API：创建、列表、详情、状态更新、负责人分派、历史查询。
- Dashboard：待办统计、优先级、逾期行动、来源分布和处理趋势。

V1 不需要新的 Calculator。行动模块不计算 Score、Quality、Prediction 或 Anomaly；如需逾期统计，只做日期和状态查询，不定义新的评分算法。

与现有模块的关系保持单向读取：

```text
Score / DataQuality / Prediction / Anomaly
                    ↓ read-only
             OperationActionService
```

不得让 AnomalyService 或其他既有 Service 反向依赖 OperationActionService。自动生成行动如需实现，应由独立编排入口调用多个只读模块，而不是修改已有模块核心逻辑。

## 8. API 与 Dashboard 边界

API 规划应至少覆盖：

- `POST /api/v1/operation-actions`：管理员创建行动。
- `GET /api/v1/operation-actions`：按状态、优先级、负责人、来源和逾期条件分页查询。
- `GET /api/v1/operation-actions/{action_id}`：详情及来源、历史。
- `PATCH /api/v1/operation-actions/{action_id}`：管理员更新主体字段。
- `PATCH /api/v1/operation-actions/{action_id}/status`：执行状态转换。
- `GET /api/v1/operation-actions/statistics`：待办、逾期和来源统计。

Dashboard 只消费 API，展示待办总数、优先级分布、逾期数量、来源类型、负责人工作量和处理趋势。前端禁止自行判断状态转换、逾期规则或来源有效性。

## 9. 风险分析与控制建议

### 9.1 退化为简单 Todo

风险：只保存标题和状态，无法体现分析平台价值。

控制：强制来源关联、保留证据入口、保存处理历史，并在详情中展示来源的分析时间和算法版本。

### 9.2 人工大量创建无意义行动

风险：行动数量膨胀，统计失真，运营人员失去信任。

控制：V1 仅管理员创建；ANOMALY/QUALITY 来源要求来源存在且未被取消；同一来源默认只能有一个开放行动；支持合并多个来源到一个行动；对 MANUAL 来源要求理由。

### 9.3 自动生成过度耦合

风险：把每个异常或质量问题都自动转成任务，改变既有模块事务和性能特征。

控制：V1 不自动生成，先提供“创建候选行动”或管理员确认；未来自动化应由独立策略配置和批处理流程承担。

### 9.4 来源对象被删除或历史不可追溯

风险：多态来源无法使用普通外键，来源记录状态变化后行动证据不完整。

控制：来源对象采用 RESTRICT 或软删除策略；创建行动时保存不可变的 evidence summary、analysis_as_of 和 algorithm_version 摘要，但不复制原始事实表字段。

## 10. 必须调整项与可保留项

必须在 Design V2 中调整：

1. 从单表 `source_type/source_id` 方案升级为 Action 与 Action Source 分离。
2. 明确 V1 来源白名单和 MANUAL 来源理由要求。
3. 冻结状态机、管理员与普通用户的动作边界。
4. 增加 Action History，不以 OperationLog 单独承担行动历史。
5. 明确同一来源开放行动的唯一性和重复创建规则。

可以保留：

- 独立保存运营行动、不修改已有异常表的原则。
- `title`、`description`、`priority`、`status`、`owner_user_id`、`due_date` 和统一时间字段。
- Router → Service → Repository → ORM 的分层架构。

## 11. 实现准入结论

当前设计有业务价值并与现有模块互补，但原始候选字段仍不足以支撑多来源、历史审计和状态权限。**暂不允许进入 Migration 或代码实现；允许进入 Phase 5 Design V2 修订。**

Design V2 完成并评审通过后，建议顺序为：数据库模型冻结 → V012 Migration/ORM → Repository → Service/状态机 → API → Dashboard → 集成测试。
