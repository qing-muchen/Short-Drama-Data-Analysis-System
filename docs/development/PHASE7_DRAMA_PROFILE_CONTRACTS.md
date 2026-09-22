# Phase 7 Drama Profile Contracts

## 1. Contracts 定位

Contracts 是 Drama 360° 全景画像中心的纯数据契约层，定义 Provider、DramaProfileService 和未来 API 之间稳定的 DTO 与状态协议。

本层只负责数据结构和边界校验，不查询数据库、不计算指标、不判断业务结果、不持久化数据。

## 2. DTO 结构

- `DramaProfileBasic`：Profile Header 所需的短剧基础信息；
- `ScoreProfileSummary`：评分等级、维度摘要、版本和分析时间；
- `QualityProfileSummary`：质量等级、状态、风险信息和规则集版本；
- `PredictionProfileSummary`：趋势方向、预测状态、版本和分析时间；
- `AnomalyProfileSummary`：活动异常数量、最高等级、最近异常；
- `ActionProfileSummary`：开放行动数量和最近行动；
- `ExplanationProfileSummary`：最近解释与血缘可用性；
- `DramaProfileResponse`：统一聚合响应。

DTO 不暴露 ORM Model、完整业务对象、评分公式、预测输入窗口或异常计算过程。

## 3. Availability 协议

`AvailabilityReason` 是封闭枚举，固定包含：

- `NOT_CALCULATED`；
- `INSUFFICIENT_HISTORY`；
- `NO_ANOMALY`；
- `NOT_DETECTED`；
- `NOT_AVAILABLE`。

`ModuleAvailability` 要求：可用模块不能携带 reason，不可用模块必须携带 reason。这样前端不需要通过 null 推断业务状态。

## 4. 字段设计说明

Profile 采用摘要字段和可选模块 DTO。各模块允许缺失，不要求所有分析结果同时存在。版本和 `analysis_as_of` 由对应 Provider 返回，Profile 不强制跨模块统一时间点。

集合型摘要使用只读语义的元组/映射，避免把完整 ORM 集合直接暴露到聚合层。

## 5. 依赖限制

`contracts.py` 为纯 Python 模块，仅依赖标准库 `dataclasses`、`datetime`、`enum` 和类型标注。

禁止导入或使用：

- SQLAlchemy；
- Session；
- Repository；
- Service；
- 数据库查询函数。

## 6. 测试结果

测试覆盖：

- Availability 枚举完整性和非法值；
- 可用/不可用状态组合校验；
- DTO 正常构造、默认值和 Optional 字段；
- 完整 Profile 与部分模块缺失；
- 基础边界值；
- Contracts 无 ORM、Repository、Service 和数据库依赖。

本阶段不包含 Provider、Repository、Service、API 或 Frontend 实现。
