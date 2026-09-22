# Phase 6 Explanation Database

## 1. V013范围

V013 新增三张表：`analysis_explanations`、`analysis_lineage_records` 和 `metric_dependencies`。不修改 V001-V012，也不修改 Score、Quality、Prediction、Anomaly 或 Operation Action 表。

## 2. 表结构

### analysis_explanations

保存已有分析结果的解释快照。`entity_type` 支持 SCORE、QUALITY、PREDICTION、ANOMALY、ACTION；`module_type` 支持 SCORE、QUALITY、PREDICTION、ANOMALY、OPERATION_ACTION。`detail` 使用 JSON，但由未来 Service 按固定 reason、inputs、rules、versions、evidence 结构校验，不保存完整业务结果。

`algorithm_version` 和 `rule_set_version` 使用非空 `N/A` 哨兵值，保证唯一约束在 MySQL 中行为稳定。唯一身份包含模块、实体、分析截点和两个版本字段。

### analysis_lineage_records

保存目标结果与输入来源之间的弱关联关系。支持 EXPLANATION、SCORE、QUALITY、PREDICTION、ANOMALY、ACTION 目标，以及 METRIC、SNAPSHOT、RULE、PREDICTION_INPUT、ANOMALY_EVIDENCE 来源。核心 ID 均为 NOT NULL，不建立跨模块 Foreign Key。

### metric_dependencies

保存静态、版本化的指标依赖图。V1 不在运行时生成依赖关系，不引入模型注册中心；通过 `(parent_metric, child_metric, module_type, algorithm_version)` 唯一约束防止重复配置，并禁止自依赖。

## 3. 索引与约束

三表均使用 BIGINT UNSIGNED 自增主键、InnoDB、utf8mb4 和 UTC 时间。Explanation 按实体、模块和创建时间索引；Lineage 按目标、来源和创建时间索引；Dependency 按父指标和子指标索引。枚举、非空文本、正 ID、自依赖和唯一性由 CHECK/UNIQUE 约束保护。

## 4. ORM

新增：

- `AnalysisExplanation`
- `AnalysisLineageRecord`
- `MetricDependency`

ORM 只映射三张表自身字段，没有建立到 Score、Quality、Prediction、Anomaly、Action 或其他业务模型的 relationship。

## 5. 测试

结构测试覆盖模型导入、metadata 注册、字段类型、JSON 类型、CHECK、UNIQUE、索引、MySQL DDL 编译和无跨模块外键。`test_models_import.py` 同步验证 V013 三张表和全局 metadata 计数。`database/tests/constraint_test.sql` 增加了解释重复身份、非法枚举、Lineage 弱关联和指标自依赖约束场景。

如果部署环境提供 MySQL 8.x，应按 V001-V013 顺序执行迁移并验证表数量、约束和索引；没有可用 MySQL 实例时，不将未执行状态伪装为通过。
