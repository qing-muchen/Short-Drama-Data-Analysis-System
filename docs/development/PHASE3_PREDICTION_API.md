# Phase 3 Prediction API

## 1. API目标

本层为短剧运营趋势预测提供 HTTP 接口。Phase 3 V1 只暴露下一日累计播放量预测，算法固定为 `Moving Average V1.0`，指标固定为 `PLAY_COUNT`。

Router 只负责请求校验、JWT/角色鉴权、Service 调用和响应转换，不访问 ORM、Repository，也不执行预测计算。

## 2. API列表

| 方法 | 路径 | 权限 | 作用 |
|---|---|---|---|
| POST | `/api/v1/predictions/calculate` | ADMINISTRATOR | 计算单剧下一日预测 |
| GET | `/api/v1/predictions/{drama_id}` | USER / ADMINISTRATOR | 获取最近一次预测 |
| GET | `/api/v1/predictions/{drama_id}/history` | USER / ADMINISTRATOR | 获取预测历史，按 `target_date` 升序 |

静态计算路径和带后缀的 history 路径均在 `/{drama_id}` 动态路径之前注册。

## 3. 请求与响应

### 3.1 计算

请求：

```json
{
  "drama_id": 7,
  "analysis_as_of": "2026-09-16T12:00:00"
}
```

`analysis_as_of` 可选；省略时由 Router 使用当前 UTC 时间。客户端不能提交 `metric_type`、`algorithm_version` 或模型参数。

成功响应使用统一的 `ResponseModel[T]`：

```json
{
  "data": {
    "prediction_id": 11,
    "drama_id": 7,
    "metric_type": "PLAY_COUNT",
    "algorithm_version": "Moving Average V1.0",
    "analysis_as_of": "2026-09-16T12:00:00",
    "target_date": "2026-09-17",
    "predicted_value": 190.0,
    "created_at": "2026-09-16T12:00:00"
  },
  "message": "success"
}
```

响应不暴露 `input_window`、`daily_increment`、revision 或 confidence 等内部细节。

### 3.2 查询

最近预测返回 `PredictionResponse`。历史查询参数 `limit` 默认 20，范围为 1—100，返回 `PredictionHistoryResponse`。无历史记录时返回空 `items`；最近预测不存在时返回 404。

## 4. Service调用关系

```text
JWT Dependency
      ↓
Prediction Router
      ↓
PredictionService
      ↓
PredictionRepository / History Provider
```

计算接口把 `drama_id`、`analysis_as_of` 和管理员用户 ID 传给 `PredictionService.calculate_prediction()`。查询接口分别委托 `get_latest_prediction()` 和 `get_prediction_history()`，不重新排序或重新计算。

当前依赖组合根提供严格的 `analysis_as_of` revision 输入适配器：只读取观测时间和 revision `changed_at` 不晚于截止时间的数据，再交由 Service 构造连续 8 日窗口。该适配器不改变既有 AnalyticsService、Repository 或数据库结构。

## 5. 权限与错误处理

- 计算：仅 `ADMINISTRATOR`。
- 查询：`USER` 和 `ADMINISTRATOR`。
- 匿名请求：401。
- 普通用户计算：403。
- 参数错误：422，统一 `ErrorResponse`。
- 历史不足等 Service 业务跳过：映射为 400，并返回稳定原因。
- 预测不存在：404。
- 持久化异常：500。

所有错误沿用现有全局异常处理器，不新增响应格式。

## 6. 测试结果

`backend/tests/test_prediction_api.py`覆盖：

- OpenAPI 路径和 JWT Bearer 声明。
- 管理员计算、普通用户 403、匿名 401。
- `drama_id`、`limit` 和额外客户端字段校验。
- `analysis_as_of` 和 Service 参数传递。
- 最近预测 404、历史查询和空/分页结果。
- 统一 `ResponseModel` 和 `ErrorResponse` 映射。
- Service 跳过结果到业务错误的转换。

本阶段不修改数据库、Migration、Calculator、Repository、Service 实现或前端。
