# Phase 6.1 Explanation Validator

## 1. 目标

本阶段将 Explanation 生成结果校验从 `AnalysisExplanationService` 中抽离为独立的 `ExplanationValidator`，使 Service 只负责编排。

Validator 不访问数据库、不访问 ORM、不调用 Handler，也不负责生成解释。

## 2. 校验内容

### GeneratedExplanation

- `detail` 必须是字典；
- 必须包含 `reason`、`inputs`、`rules`、`versions`、`evidence`；
- 允许 Trend Handler 的受控扩展字段：`trend_direction`、`window_length`、`model_description`；
- 禁止 `score_value`、`prediction_value`、`full_result`、`complete_snapshot`；
- LineageSource 必须包含合法的 `source_type`、正数 `source_id` 和 `relationship_type`。

### Context映射

- `METRIC → SCORE/SCORE`；
- `TREND → PREDICTION/PREDICTION`；
- `ANOMALY → ANOMALY/ANOMALY`。

数据库枚举映射仍由 Service 负责，Handler 不感知数据库枚举。

## 3. Service调整

`AnalysisExplanationService` 注入并调用 `ExplanationValidator`：

```text
Request
  → Context mapping validation
  → Registry / Handler
  → GeneratedExplanation validation
  → Repository / transaction
```

原先位于 Service 内的 detail 和 lineage 校验逻辑已移除。

## 4. 测试结果

覆盖：

- 正常 detail；
- 非字典 detail；
- 禁止字段；
- Context 映射错误；
- 非法 LineageSource；
- 三种内部 ExplanationType 映射。
