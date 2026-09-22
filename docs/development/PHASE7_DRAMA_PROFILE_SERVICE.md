# Phase 7 Drama Profile Service

## 1. Service 定位

`DramaProfileService` 是 Drama 360° Profile 的只读聚合编排层。它将六个 Profile Provider 的 DTO 组装为统一 `DramaProfileResponse`，不产生新的业务事实。

## 2. 依赖方向

```text
DramaProfileService → Profile Providers → Read Repositories
```

Service 通过构造器注入 Provider，不自行创建 Provider，不依赖 ScoreService、PredictionService、AnomalyService、OperationActionService 或 Explanation Service。

## 3. Provider 聚合流程

`get_profile(drama_id)` 依次获取 Score、Quality、Prediction、Anomaly、Action 和 Explanation 摘要，并分别映射到 `performance`、`quality`、`trend`、`risk`、`operations` 和 `explanations`。

## 4. Response 组装

Service 同时生成 `availability` 映射，使前端能明确判断每个模块的状态。Drama 基础信息通过可选 Basic Provider 注入；V1 没有专用基础信息 Provider 时，使用带 ID 的明确 DTO 占位标题，不访问 ORM。

## 5. Availability 处理

Provider 返回的状态原样保留，例如 `INSUFFICIENT_HISTORY` 不会被转换成 `NOT_AVAILABLE`。Service 只负责聚合，不重新解释状态。

## 6. 异常隔离策略

单个 Provider 抛出异常时，该模块返回 `available=false` 和 `NOT_AVAILABLE`，其他模块仍正常返回。这样单个读取源故障不会使整个 Profile 请求失败。

## 7. 测试结果

测试覆盖：

- 完整六模块 Profile；
- 部分模块缺失状态保留；
- 单个 Provider 异常隔离；
- 六个 Provider 调用；
- Drama ID 校验；
- Basic Provider 注入；
- 不调用业务 Service、不执行事务操作、不访问 ORM。

本阶段不包含 API、Schema、Frontend、数据库或 Migration 修改。
