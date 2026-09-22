# Phase 7 Drama Profile Providers

## 1. Provider 定位

Provider 是 Drama 360° Profile 的只读聚合读取层，负责调用既有 Repository，将已有分析结果转换为 Contracts 定义的 Profile DTO。

Provider 不计算指标、不写入数据、不触发分析任务、不管理事务，也不返回 SQLAlchemy ORM 对象。

## 2. 依赖方向

```text
Provider → Repository → Existing Data
```

Provider 不依赖 ScoreService、PredictionService、AnomalyService、OperationActionService 或 Explanation Service，也不创建 Session。

## 3. 六类 Provider

- `ScoreProfileProvider`：读取指定短剧最新 ALL 作用域评分；
- `QualityProfileProvider`：读取全局质量评分结果；
- `PredictionProfileProvider`：读取 PLAY_COUNT 最新预测；
- `AnomalyProfileProvider`：读取短剧异常记录和活动状态；
- `ActionProfileProvider`：读取短剧 OPEN/IN_PROGRESS 行动；
- `ExplanationProfileProvider`：读取已有解释快照和血缘可用性。

## 4. Repository → DTO 映射

Provider 通过属性读取或 Repository DTO 映射结果，不导出数据库字段集合。Score 映射维度摘要，Quality 映射等级和风险状态，Prediction 映射预测状态与版本，Anomaly 映射活动异常摘要，Action 映射开放行动数量，Explanation 映射摘要和解释 ID。

Provider 不复制完整业务对象，不执行计算公式，也不重新判断已有结果的业务等级。

## 5. Availability 处理

统一使用 `ModuleAvailability` 和 `AvailabilityReason`：

- Score/Quality 无结果：`NOT_CALCULATED`；
- Prediction 无结果：`NOT_CALCULATED`，若 Repository 提供历史不足状态则使用 `INSUFFICIENT_HISTORY`；
- Anomaly 无记录：区分 `NO_ANOMALY` 与 Repository 提供的 `NOT_DETECTED`；
- Action 无行动：模块仍然可用，返回空列表；
- Explanation 无解释：`NOT_AVAILABLE`。

## 6. 测试结果

测试覆盖：

- 六类 Provider 的正常结果映射；
- 各模块无数据状态；
- Prediction 历史不足；
- Anomaly 无异常与未检测；
- Action 空列表；
- Explanation 血缘可用性；
- Provider 不依赖 Service、Calculator，不执行 commit/rollback。

本阶段不包含 DramaProfileService、API Router 或 Frontend 实现。
