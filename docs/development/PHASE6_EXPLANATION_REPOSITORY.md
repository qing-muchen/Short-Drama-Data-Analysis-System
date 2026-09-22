# Phase 6.1 Explanation Repository

## 1. 职责

本阶段新增两个 Repository，对应 V013 的两张运行时解释表：

- `AnalysisExplanationRepository`：访问 `analysis_explanations`；
- `AnalysisLineageRepository`：访问 `analysis_lineage_records`。

Repository 只负责 ORM 查询、添加和 `flush()`，不生成解释，不调用 Handler，也不判断版本一致性或幂等冲突。

## 2. 接口

### AnalysisExplanationRepository

- `get_by_identity(...)`：严格匹配模块、实体、分析截点、算法版本和规则集版本；
- `create_explanation(explanation)`：保存一个 ORM 对象并 flush；
- `get_by_entity(entity_type, entity_id)`：按分析截点和 ID 倒序查询实体的历史解释。

### AnalysisLineageRepository

- `create_many(lineage_records)`：批量保存 Lineage ORM 对象并 flush；
- `get_by_target(target_type, target_id)`：按创建时间和 ID 正序查询目标的来源关系。

## 3. 事务边界

Repository：

- 不创建 Session；
- 不调用 `commit()`；
- 不调用 `rollback()`；
- 不实现内容一致性比较；
- 不抛出 Service 层 Conflict 或业务状态异常。

事务由后续 `ExplanationService` 管理，Explanation 和 Lineage 应在同一事务中写入。

## 4. 与 V013 的关系

Repository 只映射：

- `analysis_explanations`；
- `analysis_lineage_records`。

没有跨模块 Foreign Key，也没有与 Score、Prediction、Anomaly、Quality 或 Operation Action 建立 ORM relationship。

## 5. 测试结果

覆盖：

- Explanation 创建和 flush；
- 完整 identity 条件查询；
- 不同算法版本和分析时间共存；
- Lineage 批量创建和目标查询；
- 无 commit、rollback、Session 创建行为。
