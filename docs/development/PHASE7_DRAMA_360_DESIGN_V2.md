# Phase 7 Drama 360° 全景画像中心 Design V2

## 1. 模块定位

Phase 7 建设 Drama 360° 全景画像中心，定位为只读的 Read Model / Aggregation Layer。它以 Drama 为核心实体，聚合 Score、Quality、Prediction、Anomaly、Operation Action 和 Explanation 的已有结果，为用户提供统一状态视图与导航入口。

核心链路：

```text
Score / Quality / Prediction / Anomaly / Operation Action / Explanation
                              ↓
                 Drama Profile Aggregation
                              ↓
                       统一展示与导航
```

Profile 不是新分析模型、新评分系统、新预测系统、新异常检测系统或新业务实体。已有模块负责产生业务事实，Profile 只负责读取、聚合和展示。

## 2. 架构原则

### 2.1 不产生新的业务事实

允许调用只读摘要能力，如 `get_score_summary()`、`get_prediction_summary()` 和 `get_anomaly_summary()`；禁止调用 `calculate_score()`、`calculate_prediction()`、`detect_anomaly()`，也不触发质量计算或行动创建。

### 2.2 不复制已有结果

V1 不创建 `drama_profiles` 表，不保存 score value、prediction value、quality score、anomaly count 或 action status。所有结果在原业务表中维护，Profile 请求时读取最新可用结果，避免产生同步和历史冲突。

### 2.3 依赖方向

```text
DramaProfileService → Profile Providers → Read Repositories
```

Profile Service 禁止调用 ScoreService、PredictionService、AnomalyService、DataQualityService 或 OperationActionService。Profile 属于读取聚合层，已有 Service 属于业务编排层，二者不能形成循环依赖。

### 2.4 DTO 隔离

Provider 只返回 Profile DTO，不返回 SQLAlchemy ORM Model。Profile 层不向 API 或前端泄露 ORM 对象，也不复制完整业务结果。

## 3. 数据库影响

Phase 7 V1 不新增 Migration，不创建 V014，也不修改 V001-V013。以下现有表已足够支撑画像：

- `dramas`；
- `drama_scores`；
- `data_quality_scores`；
- `prediction_results`；
- `data_anomaly_records`；
- `operation_actions`；
- `analysis_explanations`。

新增画像快照表会复制多个模块的派生状态，导致失效、并发更新和历史语义不一致，因此明确排除。只有经过性能基线证明实时聚合不可接受时，才另行评估缓存或物化视图。

## 4. 后端架构与 Provider

建议目录：

```text
backend/services/drama_profile/
├── contracts.py
├── providers.py
└── service.py
```

V1 不过度拆分 Provider 文件。Provider 只读、不计算、不写库、不访问其他 Service，并通过对应 Repository 完成批量或聚合查询。

### ScoreProfileProvider

来源为 Score Repository，输出 `ScoreProfileSummary`：评分等级、Heat/Growth/Engagement/Lifecycle 摘要、`analysis_as_of` 和 `algorithm_version`。禁止重新执行评分公式。

### QualityProfileProvider

来源为 Data Quality Repository，输出 `QualityProfileSummary`：质量等级、质量状态、风险信息、`analysis_as_of` 和 `rule_set_version`。

### PredictionProfileProvider

来源为 Prediction Repository，输出 `PredictionProfileSummary`：最新预测状态、趋势方向（若已有结果提供）、目标日期、`analysis_as_of` 和 `algorithm_version`。禁止执行移动平均。

### AnomalyProfileProvider

来源为 Anomaly Repository，输出 `AnomalyProfileSummary`：当前异常数量、最高严重等级、最近异常及其 `analysis_as_of`。必须区分无异常和未检测。

### ActionProfileProvider

来源为 Operation Action Repository，输出 `ActionProfileSummary`：OPEN 数量、IN_PROGRESS 数量、最近行动和最近更新时间。无行动时返回空列表。

### ExplanationProfileProvider

来源为 Explanation Query Repository，输出 `ExplanationProfileSummary`：最近解释、解释版本和血缘查询入口。不自动生成解释。

## 5. DTO 设计

建议定义以下纯数据 DTO：

- `DramaSummary`：`drama_id`、`drama_code`、`drama_name` 及页面所需基础信息；
- `AvailabilityStatus`：`available`、可选 `reason`；
- `ScoreProfileSummary`；
- `QualityProfileSummary`；
- `PredictionProfileSummary`；
- `AnomalyProfileSummary`；
- `ActionProfileSummary`；
- `ExplanationProfileSummary`。

DTO 只保留摘要、状态、版本、时间和导航所需 ID，不包含完整历史列表或完整业务对象。

## 6. Profile Service

核心接口：

```python
get_profile(drama_id: int) -> DramaProfileResponse
```

职责：

1. 校验 Drama 是否存在；
2. 调用各 Provider；
3. 聚合 DTO；
4. 处理模块缺失和统一错误；
5. 返回包含 availability 的 Profile Response。

禁止业务计算、数据写入、状态修改、Action 创建及分析任务触发。Service 不重新排序 Provider 结果，也不隐式执行重算。

## 7. Response Schema

```json
{
  "drama": {
    "drama_id": 1,
    "drama_code": "D001",
    "drama_name": "示例短剧"
  },
  "availability": {},
  "performance": {},
  "quality": {},
  "trend": {},
  "risk": {},
  "operations": {},
  "explanations": {}
}
```

各模块摘要必须独立携带自身的 `analysis_as_of`、`algorithm_version` 和 `rule_set_version`（适用时）。不要求所有模块共享同一时间点。

## 8. Availability 协议

前端不得通过 `null` 推断业务状态。每个模块使用统一结构：

```json
{
  "available": false,
  "reason": "INSUFFICIENT_HISTORY"
}
```

V1 固定缺失原因：

- Score：`NOT_CALCULATED`；
- Prediction：`INSUFFICIENT_HISTORY` 或 `NOT_CALCULATED`；
- Anomaly：`NO_ANOMALY` 或 `NOT_DETECTED`；
- Action：无行动返回空列表；
- Explanation：`NOT_AVAILABLE`，不自动生成解释。

## 9. 版本策略

V1 采用 `latest available`，每个 Provider 独立选择本模块最新有效结果。当前系统没有 Global Snapshot 机制，不强制跨模块统一 `analysis_as_of`。

每个模块在有结果时返回：

- `analysis_as_of`；
- `algorithm_version`；
- `rule_set_version`（适用时）。

## 10. API 设计

新增只读接口：

```text
GET /api/v1/dramas/{drama_id}/profile
```

USER 和 ADMINISTRATOR 均可访问。V1 不提供 POST、PUT、PATCH，也不允许通过 Profile 触发分析或修改运营行动。不存在的 Drama 返回统一 404 错误。

## 11. Frontend 设计

新增页面 `DramaProfile.vue`，路径：

```text
/dramas/:id/profile
```

页面结构：

```text
Header
  ↓
Performance Card
  ↓
Quality Card
  ↓
Trend Card
  ↓
Risk Card
  ↓
Operation Card
  ↓
Explanation Card
```

页面只展示 API 返回结果，支持跳转到 Score、Prediction、Anomaly、Action 详情及 Explanation Viewer。前端禁止计算分数、风险、趋势、异常数量或状态转换，并处理 loading、empty、error、success 和部分模块缺失。

## 12. 性能设计

V1 不引入 Cache、Materialized View 或 Profile Snapshot。Provider 应使用批量查询、聚合查询和必要的预加载，避免按模块记录循环产生 N+1。应记录 Provider 与总请求耗时，为未来性能决策提供依据。

## 13. 测试方案

### Provider 测试

- 正常摘要返回；
- 数据不存在；
- 多版本结果选择最新有效记录；
- 缺失原因正确；
- 不返回 ORM Model；
- 无 N+1 查询和写操作。

### Service 测试

- 完整 Profile；
- 部分模块缺失；
- Prediction 历史不足与未计算区分；
- Anomaly 无异常与未检测区分；
- Provider 异常处理；
- 不调用已有业务 Service。

### API 测试

- USER/ADMINISTRATOR 权限；
- Drama 不存在返回 404；
- availability 和响应结构；
- 只读边界。

### Frontend 测试

- loading、empty、error、success；
- 模块缺失卡片；
- 详情导航；
- 不执行任何业务计算。

## 14. 风险分析

### 风险一：Profile 演化为万能 Service

以 Provider 合同和摘要 DTO 限制边界，禁止加入计算和写入职责。

### 风险二：Response 无限膨胀

只返回摘要、状态、版本、时间和导航 ID，完整历史由已有模块提供。

### 风险三：模块版本不一致

显示每个模块自身的时间和版本，并在界面标注“各模块最新可用结果”。

### 风险四：查询性能

通过批量 Repository 查询、预加载和性能基线控制；没有数据依据时不引入缓存。

### 风险五：前端重复实现业务逻辑

前端只依据 availability 和 Provider 返回状态展示，不推导等级、风险、趋势或异常数量。

## 15. 实施计划

1. Phase 7.1：实现 Backend Contracts；
2. Phase 7.2：实现 Profile Providers；
3. Phase 7.3：实现 `DramaProfileService`；
4. Phase 7.4：实现 Schema、只读 Router 和 API 测试；
5. Phase 7.5：实现 Frontend `DramaProfile.vue`；
6. Phase 7.6：完成模块总结与性能基线归档。

各阶段均不得修改 V001-V013，不创建 `drama_profiles` 表，不改变 Phase 1–6 的业务模块。

## 16. 冻结结论

Design V2 将 Phase 7 冻结为只读聚合层：不新增业务事实、不复制结果、不反向调用业务 Service、不新增数据库 Migration。后续可在本设计基础上进入 Phase 7 Backend 实现，但必须保持 Provider、DTO、Availability 和 latest available 语义不变。
