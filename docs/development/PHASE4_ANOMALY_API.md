# Phase 4 Anomaly Detection API

## 1. API目标

本层将 Phase 4 的结构化异常发现结果通过统一的 FastAPI `/api/v1` 接口暴露给管理端和分析端：

```text
HTTP Router
    ↓
AnomalyService
    ↓
AnomalyRepository / OperationLogRepository
```

Router只负责请求校验、JWT权限、Service调用和响应转换，不导入ORM、Repository或Calculator，不创建Session，也不控制事务。

## 2. 路由列表

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| POST | `/api/v1/anomalies/detect` | ADMINISTRATOR | 执行一次as-of异常检测 |
| GET | `/api/v1/anomalies` | USER / ADMINISTRATOR | 分页查询异常记录 |
| GET | `/api/v1/anomalies/{drama_id}` | USER / ADMINISTRATOR | 查询单剧异常历史 |
| GET | `/api/v1/anomalies/statistics` | USER / ADMINISTRATOR | 查询异常统计 |
| PATCH | `/api/v1/anomalies/{record_id}/status` | ADMINISTRATOR | 更新处置状态 |

`/detect`、`/statistics`等静态路径在动态短剧路径之前注册，避免被`/{drama_id}`误匹配。

## 3. 请求与响应

### 3.1 执行检测

请求只允许客户端提交`analysis_as_of`，算法版本、指标、异常类型、等级和状态均由后端固定或由检测结果产生。

```json
POST /api/v1/anomalies/detect
{
  "analysis_as_of": "2026-09-20T00:00:00"
}
```

响应使用`ResponseModel[AnomalyDetectionResponse]`：

```json
{
  "data": {
    "analysis_as_of": "2026-09-20T00:00:00",
    "algorithm_version": "Rule-based Detection V1.0",
    "detected_count": 12,
    "skipped_count": 3,
    "skip_reasons": {
      "INSUFFICIENT_HISTORY": 2,
      "DATA_QUALITY_BLOCKED": 1
    }
  },
  "message": "success"
}
```

### 3.2 异常列表

支持`analysis_as_of`、`metric_type`、`anomaly_type`、`severity`、`status`、`page`和`page_size`过滤，`page_size`最大为100。返回`ResponseModel[PageResponse[AnomalyResponse]]`。

`AnomalyResponse`将持久化的`anomaly_id`转换为API字段`record_id`，并展开已由Repository eager-load的短剧编码和名称；不重新计算异常等级或排序。

### 3.3 单剧异常历史

```text
GET /api/v1/anomalies/{drama_id}
```

无记录时返回统一`ErrorResponse`格式的404。

### 3.4 统计

统计响应包括：

- `total_count`；
- A/B/C严重等级分布；
- OPEN、ACKNOWLEDGED、RESOLVED、IGNORED状态分布；
- Repository提供的指标类型分布（PLAY_COUNT、ENGAGEMENT_RATE）。

统计数据直接来自Service委托的Repository聚合，不在Router中重新统计。

### 3.5 状态更新

```json
PATCH /api/v1/anomalies/9/status
{
  "status": "ACKNOWLEDGED"
}
```

状态仅允许`OPEN`、`ACKNOWLEDGED`、`RESOLVED`、`IGNORED`。Service负责状态持久化和`ANOMALY_STATUS_UPDATE`操作日志，Router只传递用户身份和参数。

## 4. 权限设计

- 检测和状态更新：`ADMINISTRATOR`；
- 查询接口：登录的`USER`或`ADMINISTRATOR`；
- 匿名请求：401；
- 普通用户调用检测或状态更新：403。

所有路由沿用现有JWT Bearer依赖和全局`ErrorResponse`异常处理，不新增错误格式。

## 5. Dependency组装

`get_anomaly_service()`按请求注入一个Session，并组装：

```text
Session
├── _AnomalyHistoryProvider
├── AnomalyRepository
└── OperationLogRepository
        ↓
   AnomalyService
```

历史Provider读取`changed_at <= analysis_as_of`的revision，并附带短剧、平台和数据质量问题计数；Service负责最终revision选择、窗口准备和质量协同。Router不接触这些实现细节。

## 6. 测试结果

新增`backend/tests/test_anomaly_api.py`，覆盖：

- OpenAPI路径、静态路由和JWT Bearer声明；
- 管理员检测成功与`analysis_as_of`参数传递；
- 匿名401、普通用户403；
- 列表分页和全部过滤参数；
- 单剧查询、404和统计响应；
- 管理员状态更新与Service参数；
- 请求额外字段、ID、枚举和分页边界校验；
- `ResponseModel`和`ErrorResponse`映射；
- Router不导入Repository、ORM、Calculator且不控制事务。

本阶段测试结果：

```text
Anomaly API定向测试：18 passed
完整后端回归测试：345 passed
```

## 7. 设计取舍

- API不开放算法参数，避免客户端改变V1规则身份；
- 异常详情保留解释性`evidence_summary`，但不暴露内部revision和计算中间变量；
- 统计接口沿用现有Repository返回的指标分布，未为API阶段扩展Repository查询逻辑；
- 前端和Dashboard不在本阶段实现。
