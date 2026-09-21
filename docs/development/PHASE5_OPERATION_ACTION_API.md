# Phase 5 Operation Action API

## 目标

Operation Action API 将异常、质量、评分或人工来源转化为可追踪的运营行动。API 只做参数校验、权限校验、Service 编排和响应转换；状态机、来源去重、历史记录与事务仍由 `OperationActionService` 负责。

## 路由

| 方法 | 路径 | 权限 | 作用 |
|---|---|---|---|
| POST | `/api/v1/operation-actions` | ADMINISTRATOR | 创建行动及来源证据快照 |
| GET | `/api/v1/operation-actions` | USER/ADMINISTRATOR | 分页查询行动 |
| GET | `/api/v1/operation-actions/statistics` | USER/ADMINISTRATOR | 获取状态统计 |
| GET | `/api/v1/operation-actions/{action_id}` | USER/ADMINISTRATOR | 查看行动详情、来源与历史 |
| PATCH | `/api/v1/operation-actions/{action_id}/status` | ADMINISTRATOR | 请求状态转换 |
| PATCH | `/api/v1/operation-actions/{action_id}/assign` | ADMINISTRATOR | 分派负责人 |
| POST | `/api/v1/operation-actions/{action_id}/comments` | USER/ADMINISTRATOR | 添加处理记录 |

静态 `statistics` 路径在动态 `/{action_id}` 之前注册。

## 权限与响应

接口沿用 JWT Bearer、`ResponseModel[T]` 和 `ErrorResponse`。匿名请求返回 401，普通用户对创建、分派和状态变更返回 403，业务不存在返回 404，参数错误返回 422。客户端不能提交状态、创建人或历史记录；状态转换由 Service 统一校验。

## 测试

API 测试使用 FastAPI dependency overrides 注入 Fake Service，不连接数据库，覆盖 OpenAPI 注册、JWT 声明、角色权限、参数校验、分页参数和 Service 参数传递。
