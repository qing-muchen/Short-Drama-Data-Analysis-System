# Phase 7 Drama 360° 全景画像中心设计提案

## 1. 模块定位

当前系统已经覆盖数据采集、质量评价、综合评分、趋势预测、异常检测、运营处置以及解释与血缘追踪。但现有页面仍以 Score、Quality、Prediction、Anomaly、Action 等模块为中心，运营人员需要在多个页面之间切换才能形成对单部短剧的完整判断。

Drama 360° Profile 用于提供以 Drama 为核心实体的统一只读视角。它是一个 Read Model / Aggregation View，负责聚合已有结果、标记结果可用性并提供模块导航，不产生新的分析事实。

它不是新的分析模型、评分系统、预测系统或异常检测系统，也不替代人工运营判断。

## 2. 设计原则

### 2.1 只读聚合，禁止重新计算

Profile 只能读取已有结果摘要，例如 `get_score_summary()`、`get_prediction_summary()` 和 `get_anomaly_summary()`。禁止在 Profile 流程中调用 `calculate_score()`、`calculate_prediction()` 或 `detect_anomaly()`。

### 2.2 不复制业务结果

V1 不新增 `drama_profiles` 表，不持久化 score value、prediction value、quality score 或 anomaly count。Profile 每次读取最新可用结果，避免与各业务表产生同步和一致性问题。

### 2.3 单向依赖

Profile Service 不调用 ScoreService、DataQualityService、PredictionService、AnomalyService 或 OperationActionService。推荐由各 Provider 直接依赖对应的只读 Repository，Profile Service 只负责聚合 Provider 输出。

### 2.4 明确范围

Profile 响应只提供运营概览、状态、版本、时间和导航所需的摘要，不复制完整业务对象，不扩展为万能查询接口。

## 3. 数据库影响

V1 不新增 Migration、ORM 或业务表。现有数据源已经足够支持画像：

- `dramas`：短剧基础信息；
- `drama_scores`：综合评分；
- `data_quality_scores`：质量评分；
- `prediction_results`：预测结果；
- `data_anomaly_records`：异常记录；
- `operation_actions`：运营行动；
- `analysis_explanations`：解释快照。

新增 `drama_profiles` 会复制多个模块的派生结果，并引入重算、失效和并发更新问题，因此不纳入 V1。若未来确有缓存或物化视图需求，应在性能数据证明必要后单独评审。

## 4. 后端架构

建议新增只读模块目录：

```text
backend/services/drama_profile/
├── contracts.py
├── providers.py
└── service.py
```

调用关系为：

```text
Router
  ↓
DramaProfileService
  ↓
Profile Providers
  ↓
只读 Repositories
  ↓
已有业务表
```

Provider 不修改数据、不管理事务、不触发分析任务。V1 可以将 Provider 保持在一个文件中，待接口稳定且查询复杂度确实增加后再拆分。

## 5. Provider 设计

每个 Provider 只读取一个模块的最小摘要，并返回明确的可用状态和版本信息。

### ScoreProvider

输入 `drama_id`，读取最近评分，输出评分等级、Heat/Growth/Engagement/Lifecycle 摘要、`analysis_as_of` 和 `algorithm_version`。不重新评分。

### QualityProvider

读取质量评分，输出质量等级、状态、风险提示、`score_date`、`analysis_as_of` 和 `rule_set_version`。质量不存在时返回明确缺失原因。

### PredictionProvider

读取最新预测，输出预测状态、目标日期、趋势方向（若已有结果提供）、`algorithm_version` 和 `analysis_as_of`。不执行移动平均。

### AnomalyProvider

读取当前短剧异常，输出活动异常数量、最高严重等级、最近异常及其状态。需要区分没有异常和尚未完成检测。

### ActionProvider

读取 `OPEN`、`IN_PROGRESS` 行动及最近处理记录，输出待处理行动摘要。不存在行动时返回空列表，不创建行动。

### ExplanationProvider

读取最近解释和血缘入口，输出解释摘要、解释 ID、模块和版本。它只引用 Explanation Query Repository，不重新生成解释。

## 6. Profile Service

核心接口：

```python
get_profile(drama_id: int) -> DramaProfileResponse
```

Service 职责：

1. 校验短剧是否存在；
2. 并行或批量协调各 Provider 的只读查询；
3. 组装统一响应；
4. 记录每个模块的可用性和缺失原因；
5. 将 Provider 错误转换为统一的服务层错误。

Service 不进行业务计算、排序重写、状态修改、Action 创建或分析触发。Provider 的查询应使用批量或一次性聚合查询，避免循环中的 N+1 访问。

## 7. Response 设计

建议响应结构：

```json
{
  "drama": {
    "drama_id": 1,
    "drama_code": "D001",
    "drama_name": "示例短剧"
  },
  "availability": {
    "score": true,
    "quality": true,
    "prediction": false,
    "anomaly": true,
    "action": true,
    "explanation": false
  },
  "performance": {},
  "quality": {},
  "trend": {},
  "risk": {},
  "operations": {},
  "explanations": {}
}
```

每个模块摘要必须携带自身时间和版本字段，不能强制不同模块共享同一个 `analysis_as_of`。V1 采用 `latest available`：每个 Provider 返回自身最新有效结果。

缺失策略：

- Score：`available=false`；
- Prediction：区分 `INSUFFICIENT_HISTORY` 与 `NOT_CALCULATED`；
- Anomaly：区分 `NO_ANOMALY` 与 `NOT_DETECTED`；
- Action：返回空列表；
- Explanation：返回 `available=false`，不自动生成解释。

## 8. API 设计

新增只读接口：

```text
GET /api/v1/dramas/{drama_id}/profile
```

USER 和 ADMINISTRATOR 均可访问。V1 不提供 POST、PUT 或 PATCH，不通过 Profile 触发评分、预测、异常检测、质量计算或行动变更。

参数仅包括路径中的 `drama_id`；未来如增加时间截点或版本选择，应先进行独立的历史一致性设计，不能隐式改变 `latest available` 语义。

## 9. Frontend 设计

新增页面规划：`DramaProfile.vue`，路径：

```text
/dramas/:id/profile
```

页面采用摘要卡片和模块导航：

- Header：剧名、平台、标签；
- Performance Card：综合评分；
- Quality Card：质量等级与状态；
- Trend Card：预测摘要；
- Risk Card：异常摘要；
- Operations Card：开放行动；
- Explanation Card：解释入口。

点击卡片进入现有 Score、Prediction、Anomaly、Action 详情或打开 Explanation Viewer。前端只渲染 API 结果，不重新计算评分、预测、质量、异常数量或状态转换。

页面必须处理 loading、部分模块缺失、整体错误和空结果状态。

## 10. 性能设计

V1 使用普通同步只读查询，不引入缓存层。每个 Provider 必须避免按记录循环查询，列表类数据应使用批量查询、聚合查询和必要的预加载。应为 Profile 接口设置合理的响应范围，避免返回完整历史记录。

在 Review 阶段应记录各 Provider 的查询耗时和总响应时间。只有当实际数据规模证明同步聚合成为瓶颈时，才评估缓存、异步预计算或数据库物化视图。

## 11. 测试规划

### Provider 测试

- 正常返回摘要；
- 对应数据不存在；
- 多版本结果选择最新有效记录；
- 不产生 N+1 查询；
- 不调用写入或计算逻辑。

### Service 测试

- 完整 Profile 组装；
- 部分模块缺失；
- Prediction 历史不足与未计算状态区分；
- Anomaly 无异常与未检测状态区分；
- Provider 异常处理；
- 不依赖已有业务 Service。

### API 测试

- USER/ADMINISTRATOR 权限；
- 不存在短剧返回 404；
- Response 结构和 availability 字段；
- 不暴露完整业务结果或写入接口。

### Frontend 测试

- loading、empty、error、success；
- 模块缺失卡片展示；
- 详情跳转；
- 不在前端执行业务计算。

## 12. 风险分析与控制

### 风险一：Profile 变成万能 Service

控制方式：冻结 Provider 输出 DTO 和响应范围，禁止在 Profile Service 中加入业务计算与写操作。

### 风险二：响应无限膨胀

控制方式：只返回摘要、状态、版本和导航 ID；完整历史通过已有模块页面查询。

### 风险三：模块版本不一致

控制方式：每个模块独立返回 `analysis_as_of`、`algorithm_version` 和 `rule_set_version`，前端明确展示“各模块最新可用结果”。

### 风险四：查询性能下降

控制方式：Provider 批量查询、预加载和查询计时；暂不引入未经数据证明的缓存机制。

### 风险五：前端重复实现业务逻辑

控制方式：前端仅根据 `availability` 和 Provider 返回状态展示，不推导等级、趋势或异常数量。

## 13. 实施计划

本提案确认后，建议按以下顺序实施并分别验证：

1. Architecture Review，冻结响应范围和缺失状态；
2. Provider contracts 与只读查询适配；
3. `DramaProfileService` 聚合与错误处理；
4. Schema、只读 Router 和 API 测试；
5. `DramaProfile.vue` 与详情导航；
6. 集成测试、性能基线和文档归档。

V1 实施过程中不新增 Migration，不创建 `drama_profiles` 表，也不修改 Phase 1–6 的业务模块。

## 14. 当前结论

Phase 7 具备较好的模块互补价值：它将已有分析能力组织成以 Drama 为中心的运营视图，但不重复实现任何分析逻辑。当前文档属于 Design Proposal，下一步应进入 Architecture Review；在 Review 通过前，不进入 Backend、Frontend、ORM 或数据库实现。
