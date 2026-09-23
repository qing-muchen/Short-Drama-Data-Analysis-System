# Phase 8 Operation Analytics API

## 1. API 定位

Phase 8 API 将 `OperationAnalyticsService` 暴露为只读 HTTP 查询接口。API 不创建新的业务事实，不持久化分析结果，也不调用 ORM、Repository、Provider 或 Rule Component。

调用链固定为：

```text
Client
  -> FastAPI Router
  -> OperationAnalyticsService
  -> Providers
  -> Rules
  -> Contracts
```

## 2. 接口列表

| Method | Path | 用途 | 权限 |
| --- | --- | --- | --- |
| GET | `/api/v1/operations/effectiveness` | 查询运营行动完成前后的指标变化 | USER / ADMINISTRATOR |
| GET | `/api/v1/dramas/{drama_id}/lifecycle` | 查询单剧生命周期阶段 | USER / ADMINISTRATOR |
| GET | `/api/v1/dramas/benchmark` | 查询显式 Drama 集合的同平台统计比较 | USER / ADMINISTRATOR |

三个接口均由 JWT Bearer 保护，不注册 POST、PUT、PATCH 或 DELETE 操作。

### 2.1 Operation Effectiveness

查询参数：

- `action_id`：可选，正整数；
- `drama_id`：可选，正整数；
- `analysis_as_of`：可选、带时区的 ISO 8601 时间，Service 统一转换为 UTC；
- `page`：默认 1；
- `page_size`：默认 20，范围 1-100。

返回稳定分页信息、批次 Availability，以及行动前后窗口、指标变化和非因果免责声明。响应不存在 `success`、`causal_result` 或 `recommendation` 字段。

### 2.2 Lifecycle

路径参数 `drama_id` 必须为正整数；`analysis_as_of` 为可选分析截止时间。返回生命周期阶段、规则版本、Availability、证据摘要与分析 revision。

### 2.3 Benchmark

查询参数：

- `drama_ids`：重复查询参数形式传递，2-20 个 Drama ID；
- `platform_id`：正整数；
- `analysis_as_of`：可选分析截止时间。

静态路径 `/dramas/benchmark` 在动态 Drama 路由之前注册，防止 `benchmark` 被解释为 `drama_id`。结果只包含统计比较，不包含排名、胜者或推荐。

## 3. Schema 设计

HTTP Schema 与 Service Contracts 分离，Router 使用 Pydantic `model_validate(..., from_attributes=True)` 完成边界转换。

主要响应 Schema：

- `OperationEffectivenessResponseSchema`；
- `OperationEffectivenessPageResponseSchema`；
- `LifecycleResponseSchema`；
- `BenchmarkResponseSchema`；
- `AnalysisAvailabilitySchema`；
- 窗口、指标变化、Lifecycle evidence、Benchmark member 等嵌套 Schema。

所有成功响应统一使用 `ResponseModel[T]`：

```json
{
  "data": {},
  "message": "success"
}
```

业务异常、认证异常和参数校验继续使用现有 `ErrorResponse`，不新增错误格式。

## 4. 权限模型

Router 使用 `AuthenticatedUserDependency`：

- `USER`：允许查询全部三个接口；
- `ADMINISTRATOR`：允许查询全部三个接口；
- 匿名请求：返回 HTTP 401。

Phase 8 API 不包含写操作，因此不要求管理员专属权限。

## 5. Dependency 组装

`get_operation_analytics_service()` 是请求级 composition root。它复用同一个数据库 Session 创建只读 `OperationAnalyticsRepository`，并组装：

- `OperationEffectivenessProvider`；
- `LifecycleInputProvider`；
- `BenchmarkProvider`；
- `ActionEffectCalculator`；
- `LifecycleClassifier`；
- `BenchmarkCalculator`；
- `AnalysisRevisionBuilder`；
- `SystemClock`。

Router 只依赖 `OperationAnalyticsServiceDependency`，不感知上述组件及 Session。

## 6. Router 边界

`backend/routers/operation_analytics.py` 仅包含：

- 路径和查询参数声明；
- JWT 用户依赖；
- Service 调用；
- Contracts 到 HTTP Schema 的转换。

Router 不导入 SQLAlchemy、ORM Model、Repository、Provider、Rule Component 或 Session，不执行分析规则或数据库操作。

## 7. 测试记录

API 单元测试使用 FastAPI `dependency_overrides` 注入 Fake Service，不连接真实数据库。覆盖：

- 三条路径与 GET-only 约束；
- 匿名 401；
- USER 与 ADMINISTRATOR 查询权限；
- ResponseModel 和嵌套 Schema 转换；
- Availability 原样保留；
- `analysis_as_of`、过滤条件和分页参数传递；
- Benchmark 静态路径优先与参数校验；
- OpenAPI JWT Bearer、参数和响应模型；
- Router 源码分层边界。

验证命令：

```text
backend/.venv/Scripts/python.exe -m pytest -q backend/tests/test_operation_analytics_api.py
```

结果：Phase 8.5 API 测试 11 项通过；Phase 8 Contracts、Rules、Providers、Service 与 API 联合回归 55 项通过。完整后端测试除 4 项工作区既有 Phase 7/通用 Router 断言失败外均通过；这些失败不属于本阶段允许修改范围。
