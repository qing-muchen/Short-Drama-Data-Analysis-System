# Phase 6.2 Explanation Query Repository

## 1. 目标

本阶段增加 Explanation 和 Lineage 的只读查询层，为后续 API 和嵌入式详情页提供稳定查询接口。

查询层不生成解释、不调用 Handler、不重新计算任何业务结果，也不修改 V013 ORM或表结构。

## 2. Repository接口

### `AnalysisExplanationQueryRepository`

- `get_explanations_by_entity(...)`：按实体查询历史解释，支持模块、分析截点、算法版本、规则集版本和分页；
- `get_latest_explanation(...)`：按实体和模块查询最新解释。

解释历史统一按 `analysis_as_of DESC, explanation_id DESC` 排序，确保同一截点下结果稳定。

### `AnalysisLineageQueryRepository`

- `get_lineage_by_target(...)`：按目标查询来源，支持 `source_type` 和 `relationship_type` 过滤。

Lineage 统一按 `created_at ASC, lineage_id ASC` 排序，保持来源展示顺序稳定。

## 3. 事务边界

Repository 只执行 SQLAlchemy ORM `select` 和分页查询：

- 不创建 Session；
- 不调用 `commit()`；
- 不调用 `rollback()`；
- 不解析解释内容；
- 不访问 Score、Prediction、Anomaly 或其他业务 Service。

## 4. 测试结果

覆盖：

- 实体查询和分页；
- 模块、版本和时间过滤；
- 最新解释稳定排序；
- Lineage 来源和关系过滤；
- 无事务管理和 Session 创建行为。
