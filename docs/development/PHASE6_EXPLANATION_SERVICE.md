# Phase 6.1 Analysis Explanation Service

## 1. Service职责

`AnalysisExplanationService` 负责将规则驱动 Handler 的纯数据输出持久化为 Explanation 快照和 Lineage 记录。

它不调用 Score、Prediction、Anomaly 或其他已有业务 Service，也不重新计算任何业务结果。

## 2. 处理流程

```text
ExplanationGenerationRequest
        ↓
输入校验
        ↓
ExplanationHandlerRegistry
        ↓
ExplanationGenerator
        ↓
detail结构校验
        ↓
按完整identity查询已有解释
        ↓
AnalysisExplanationRepository
        ↓ flush
AnalysisLineageRepository
        ↓ flush
一次事务提交
```

类型映射：

- `METRIC → entity_type/module_type = SCORE`；
- `TREND → entity_type/module_type = PREDICTION`；
- `ANOMALY → entity_type/module_type = ANOMALY`。

该映射只存在于 Service，Handler 只认识内部 `ExplanationType`。

## 3. 幂等策略

通过 V013 唯一身份查询：

```text
module_type
entity_type
entity_id
analysis_as_of
algorithm_version
rule_set_version
```

- 不存在：创建 Explanation 和 Lineage；
- 已存在且 summary、detail、Lineage 一致：返回已有记录；
- 已存在但内容或 Lineage 不一致：抛出 `ConflictException`；
- 不覆盖历史快照。

## 4. 事务边界

Explanation 与 Lineage 共享同一 Session 和事务：

```text
BEGIN
  → create explanation
  → flush
  → create lineage
  → flush
COMMIT
```

任一步骤失败，统一 rollback。Handler 在事务外执行，Generator 异常不会产生数据库写入。

## 5. 验证边界

Service 校验：

- ExplanationType；
- entity_id、analysis_as_of和版本字段；
- detail 必须是受控字典；
- 必须包含 reason、inputs、rules、versions、evidence；
- 禁止任意额外字段和业务结果复制字段。

## 6. 测试结果

覆盖：

- Metric、Trend、Anomaly 生成及数据库类型映射；
- Registry 调用；
- detail 结构；
- 相同 identity 幂等返回；
- 内容差异冲突；
- Generator 异常；
- Lineage 持久化失败回滚；
- 不依赖已有业务 Service。
