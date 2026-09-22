# Phase 6.1 Explanation Contracts + Handler Registry

## 1. 目标

本阶段建立 Analysis Explanation Service 的纯 Python 基础设施，不连接数据库，不访问 ORM，也不实现 Service、Repository、API 或前端。

解释生成采用规则驱动方式，后续 Handler 必须产生确定性结果，不接入 LLM、网络服务或模型 SDK。

## 2. 文件结构

```text
backend/services/explanation/
├── __init__.py
├── contracts.py
└── registry.py
```

## 3. 数据契约

### `ExplanationType`

Registry 内部业务键：

- `METRIC`
- `TREND`
- `ANOMALY`

它不直接等同于 V013 的数据库 `entity_type`。后续 Service 负责映射，例如 `METRIC → SCORE`、`TREND → PREDICTION`。

### `LineageSource`

描述一个逻辑来源：

- `source_type`
- `source_id`
- `relationship_type`

该对象只描述来源，不建立 Foreign Key，也不执行来源查询。

### `ExplanationContext`

携带实体、模块、分析截点、算法版本、规则集版本、业务 payload 和来源集合。`payload` 在本阶段保持为只读映射，具体结构由后续 Metric、Trend、Anomaly Handler 定义。

### `GeneratedExplanation`

包含：

- `summary`
- `detail`
- `lineage_sources`

`detail` 必须是字典，并拒绝 `score_value`、`prediction_value` 和完整业务对象等持久化结果字段。

## 4. Registry职责

`ExplanationHandlerRegistry` 使用显式注册：

- 注册一个 `ExplanationType` 对应的 Generator；
- 防止重复注册覆盖；
- 查询未注册类型时抛出明确异常；
- 不使用动态 import、插件扫描或自动发现。

Generator 通过 `ExplanationGenerator` Protocol 约束，只有：

```python
generate(context: ExplanationContext) -> GeneratedExplanation
```

## 5. 明确不包含的能力

本阶段不包含：

- SQLAlchemy、Session 或 ORM；
- Repository 和数据库写入；
- Service 事务；
- Score、Prediction、Anomaly 计算；
- HTTP API、权限和响应模型；
- LLM 或外部网络调用。

后续 Service 将把这些纯数据契约转换为 `analysis_explanations` 和 `analysis_lineage_records` 的持久化对象。

## 6. 测试

测试覆盖：

- Context、LineageSource 和 GeneratedExplanation 创建；
- detail 类型和禁止字段校验；
- Registry 注册、解析、重复注册和未知类型；
- Mock Generator 对 Protocol 的兼容性。
