# Phase 7 Drama 360° 全景画像中心 Implementation Review

## 1. 审查结论

Phase 7 Design V2 已明确将 Drama 360° Profile 定义为只读 Read Model / Aggregation Layer。本次实施准入审查确认其定位、边界、依赖方向和缺失状态协议清晰，允许进入 Backend Contracts 实现阶段。

本结论不授权创建数据库表、Migration、ORM 或任何分析计算模块。后续实现必须严格遵守本审查冻结项。

## 2. 模块定位最终确认

Drama 360° Profile 不是新业务实体，也不是新的评分、预测、异常检测或质量模型。其职责限定为：

- 聚合已有分析结果；
- 展示已有状态和版本；
- 提供模块详情导航。

Profile 不生成新的业务事实，不保存业务结果副本，不替代人工运营决策。

## 3. 数据库边界

Phase 7 V1 不创建 V014 Migration，不新增 `drama_profiles` 表，也不修改以下既有表：

- `dramas`；
- `drama_scores`；
- `data_quality_scores`；
- `prediction_results`；
- `data_anomaly_records`；
- `operation_actions`；
- `analysis_explanations`。

现有数据源已足够支持实时只读聚合。任何缓存、物化视图或画像快照方案都必须基于后续性能证据单独评审。

## 4. 依赖方向审查

冻结的依赖方向为：

```text
DramaProfileService
        ↓
Profile Providers
        ↓
Read Repositories
```

禁止 DramaProfileService 调用 ScoreService、PredictionService、AnomalyService、OperationActionService 或其他业务编排 Service。Profile 层只能读取既有结果，不能成为新的业务中心或模块间的反向协调器。

## 5. Backend 实现边界

允许新增目录：

```text
backend/services/drama_profile/
├── __init__.py
├── contracts.py
├── providers.py
└── service.py
```

V1 不新增 Calculator、Repository、Migration 或 ORM。Provider 使用已有只读 Repository；如果现有 Repository 缺少必要的只读摘要能力，应先进行最小、独立的接口评审，不得在 Profile Service 中直接写 SQL 或访问 ORM。

## 6. Contracts 设计审查

首个实现阶段应先完成纯数据 DTO，不依赖 SQLAlchemy、Session 或业务 Service。`DramaProfileResponse` 至少包含：

- `drama`；
- `availability`；
- `performance`；
- `quality`；
- `trend`；
- `risk`；
- `operations`；
- `explanations`。

DTO 必须与 ORM 分离，禁止返回 SQLAlchemy Model 或完整业务结果对象。摘要 DTO 只包含展示、状态、版本、时间和导航所需的信息。

## 7. Provider 实现审查

允许实现以下只读 Provider：

- `ScoreProfileProvider`：评分等级、维度摘要、算法版本和分析时间；
- `QualityProfileProvider`：质量等级、状态、风险信息、规则集版本；
- `PredictionProfileProvider`：最新预测状态、目标日期、算法版本和分析时间；
- `AnomalyProfileProvider`：当前异常数量、最高严重等级和最近异常；
- `ActionProfileProvider`：OPEN/IN_PROGRESS 数量、最近行动和更新时间；
- `ExplanationProfileProvider`：最近解释、版本和血缘入口。

所有 Provider 必须只读，不调用 Service，不重新计算，不修改数据库，不返回 ORM 对象。应通过批量查询或已有聚合接口避免 N+1。

## 8. Service 实现审查

允许实现：

```python
get_profile(drama_id: int) -> DramaProfileResponse
```

Service 负责调用 Provider、聚合 DTO、处理模块缺失并返回统一响应。禁止 commit、写数据库、触发分析任务、创建行动或重新排序和重算业务结果。

## 9. Availability 协议

前端不得通过 `null` 推断业务状态。每个模块都必须返回统一的可用性结构，例如：

```json
{
  "available": false,
  "reason": "INSUFFICIENT_HISTORY"
}
```

V1 冻结原因：

- Score：`NOT_CALCULATED`；
- Prediction：`INSUFFICIENT_HISTORY`、`NOT_CALCULATED`；
- Anomaly：`NO_ANOMALY`、`NOT_DETECTED`；
- Action：无行动返回空列表；
- Explanation：`NOT_AVAILABLE`，不自动生成解释。

## 10. 版本策略

采用 `latest available`。每个模块独立选择自身最新有效结果，不要求所有模块共享同一 `analysis_as_of`，因为当前没有 Global Snapshot 机制。

有结果时，各模块应返回适用的：

- `analysis_as_of`；
- `algorithm_version`；
- `rule_set_version`。

前端应明确这是各模块的最新可用结果，而非同一时间点的全局快照。

## 11. API 与 Frontend 准入

允许后续新增只读接口：

```text
GET /api/v1/dramas/{drama_id}/profile
```

USER 和 ADMINISTRATOR 均可查看。禁止 POST、PUT、PATCH，以及通过 Profile 触发任何分析或行动变更。

允许新增 `DramaProfile.vue`，路径为 `/dramas/:id/profile`，展示 Header、Performance、Quality、Trend、Risk、Operation 和 Explanation 卡片。前端只能展示 API 返回数据和导航入口，不得计算指标、判断等级或生成解释。

## 12. 性能审查

V1 不引入 Cache、Materialized View 或 Snapshot。Provider 必须避免重复查询和 N+1，实施时应记录单个 Provider 与整体接口耗时。只有性能基线证明同步聚合不可接受后，才可另行评估优化方案。

## 13. 测试准入要求

### Contracts

- DTO 字段与类型；
- Availability 状态枚举；
- ORM 隔离。

### Provider

- 正常数据；
- 数据缺失；
- 多版本结果；
- latest available 选择；
- 无写操作和 N+1。

### Service

- 完整 Profile；
- 部分模块缺失；
- Prediction 和 Anomaly 缺失原因区分；
- Provider 异常处理；
- 不调用既有业务 Service。

### API 与 Frontend

- USER/ADMINISTRATOR 权限；
- Response Schema；
- Drama 不存在；
- loading、empty、error、success；
- 前端不执行业务计算。

## 14. 风险与控制

| 风险 | 控制措施 |
| --- | --- |
| Profile 演化为万能 Service | Provider 隔离，冻结 DTO 和职责 |
| 复制业务结果 | 不建画像表，只返回摘要 |
| 响应持续膨胀 | 限制为摘要、状态、版本和导航 ID |
| 模块版本不一致 | 各模块返回独立时间和版本，采用 latest available |
| 聚合查询性能下降 | 批量 Repository 查询、预加载和性能基线 |
| 前端承担业务逻辑 | availability 协议由后端提供，前端只展示 |

## 15. 最终准入判断

允许进入 **Phase 7 Backend Contracts 实现阶段**。

实施顺序必须为：

1. 首先实现 `contracts.py` 和 DTO 单元测试；
2. 再实现只读 Providers；
3. 实现 `DramaProfileService`；
4. 设计并实现只读 API；
5. 最后实现 Frontend Profile 页面。

准入的前提与冻结项：

- 不需要 Migration；
- 不需要 ORM 修改；
- 不新增 `drama_profiles`；
- 不调用已有业务 Service；
- 不重新计算或复制业务结果；
- 不在本阶段引入缓存、物化视图或全局快照。

## 16. 当前状态

- 未修改 Backend；
- 未修改 Frontend；
- 未修改 Database；
- 未创建 Migration；
- 当前仅完成 Implementation Review；
- 下一步允许进入 Backend Contracts 实现。
