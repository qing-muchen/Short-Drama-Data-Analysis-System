# Phase 6.2 Explanation Query Service and API

## 1. 目标

本阶段提供 Explanation 和 Lineage 的只读查询服务与 HTTP API。查询只消费 V013 已保存结果，不生成解释、不调用 Handler、不修改数据库。

## 2. Service

`AnalysisExplanationQueryService` 负责：

- 校验分页窗口；
- 调用 `AnalysisExplanationQueryRepository`；
- 调用 `AnalysisLineageQueryRepository`；
- 将 Lineage 查询结果封装为统一 `Page`；
- 通过 `BaseService.read` 处理查询异常。

## 3. API

### `GET /api/v1/explanations/{entity_type}/{entity_id}`

支持：

- `module_type`
- `analysis_as_of`
- `algorithm_version`
- `rule_set_version`
- `page`
- `page_size`（最大100）

### `GET /api/v1/lineage/{target_type}/{target_id}`

支持：

- `source_type`
- `relationship_type`
- `page`
- `page_size`（最大100）

两个接口均使用 `ResponseModel[PageResponse[T]]`，并沿用项目统一 `ErrorResponse`。

## 4. 权限

两个查询接口均要求登录用户。USER 和 ADMINISTRATOR 拥有相同查询权限，匿名请求返回 401。

## 5. 边界

- Router 不直接访问 ORM 或 Repository；
- Service 不调用 Handler 或生成 Service；
- Query Repository 不生成解释、不修改数据、不管理事务；
- 前端尚未实现，本阶段不修改 Frontend。

## 6. 测试结果

覆盖：

- OpenAPI 路径与 JWT Bearer；
- Explanation 分页、时间和版本过滤；
- Lineage 过滤和分页；
- 匿名 401；
- 路径和分页参数校验；
- Router 通过 Service Dependency 调用。
