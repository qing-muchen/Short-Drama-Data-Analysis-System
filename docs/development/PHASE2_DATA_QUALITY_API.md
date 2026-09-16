# Phase 2 Data Quality API

## 1. API目标

本阶段为已完成的`DataQualityService`提供统一的HTTP访问层，使管理员可以触发全局数据质量评分，登录用户可以读取当前评分、历史趋势和当前规则集。

API只负责参数校验、JWT鉴权、Service调用和响应DTO转换，不直接访问Repository、ORM或SQL，也不计算维度分、综合分或等级。

统一前缀：

```text
/api/v1/data-quality
```

Phase 2 V1评分上下文保持固定：

```text
score_scope_type = ALL
score_scope_id = 0
algorithm_version = Quality Score V1.0
rule_set_version = DQ Rules 1.0
```

客户端只能在计算请求中提交`score_date`，不能提交或覆盖算法版本、规则集版本及scope。

## 2. 路由设计

| 方法 | 路径 | 权限 | Service调用 | 用途 |
|---|---|---|---|---|
| POST | `/api/v1/data-quality/calculate` | ADMINISTRATOR | `calculate_quality_score()` | 计算并原子替换指定日期的全局质量评分 |
| GET | `/api/v1/data-quality/score` | USER / ADMINISTRATOR | `get_current_quality_score()` | 查询当前质量评分及规则执行明细 |
| GET | `/api/v1/data-quality/history` | USER / ADMINISTRATOR | `get_quality_history()` | 查询质量评分趋势 |
| GET | `/api/v1/data-quality/rules` | USER / ADMINISTRATOR | `get_current_quality_score()` | 返回当前已发布评分所使用的可追溯规则集 |

`/rules`不直接访问RuleRepository。当前Service没有独立的规则查询方法，因此V1将最近一次持久化Score及其已预加载的Rule Result → Rule关系视为当前已发布规则集。尚无评分时返回空规则集；这保证Router不越过Service边界，也避免把未执行的DRAFT规则误报为已发布规则。

## 3. Schema与响应结构

所有成功响应继续使用：

```json
{
  "data": {},
  "message": "success"
}
```

错误继续使用全局`ErrorResponse`：

```json
{
  "code": "NOT_FOUND",
  "message": "Data quality score was not found",
  "details": null
}
```

主要DTO：

- `DataQualityCalculateRequest`：仅含`score_date`。
- `DataQualityCalculationResponse`：返回评分标识、日期、固定scope、算法/规则集版本、规则数量、实体数量、综合分和等级。
- `DataQualityScoreResponse`：返回当前综合分、四维评分、版本追踪字段、统计字段及规则执行明细。
- `DataQualityHistoryResponse`：返回按Service/Repository既定顺序生成的趋势列表。
- `DataQualityRuleListResponse`：返回规则集版本、SHA-256和规则定义列表。

分数范围统一限制为`0-100`；质量等级限制为`S/A/B/C`；维度限制为`COMPLETENESS/ACCURACY/CONSISTENCY/TIMELINESS`；Phase 2 V1 scope通过Literal固定为`ALL/0`。

## 4. 权限设计

- `POST /calculate`使用`AdministratorDependency`，普通USER返回403，未登录返回401。
- 三个GET接口使用`AuthenticatedUserDependency`，允许USER和ADMINISTRATOR。
- OpenAPI中四个接口均声明`JWTBearer`安全方案。

权限解析沿用现有JWT依赖和统一异常处理，不在Router内重复解析Token或判断角色字符串。

## 5. Dependency设计

`get_data_quality_service()`在一个请求级Session中组装：

```text
DataQualityRuleRepository
DataQualityRuleResultRepository
DataQualityScoreRepository
OperationLogRepository
DataQualityService
```

所有Repository与Service共享同一个Session，事务仍完全由Service控制。

规则Evaluator注册表属于规则执行实现，不属于HTTP层。本阶段没有新增Evaluator或计算逻辑；依赖工厂注入空白名单。读取接口可直接使用，计算接口在数据库存在未注册Evaluator时由Service按既有契约拒绝并回滚。后续接入V1规则Evaluator时，只需在组合根替换注册表，不需要修改Router或API契约。

## 6. 请求与响应示例

计算请求：

```http
POST /api/v1/data-quality/calculate
Authorization: Bearer <token>
Content-Type: application/json

{"score_date":"2026-09-16"}
```

历史查询：

```http
GET /api/v1/data-quality/history?start_date=2026-09-01&end_date=2026-09-16&limit=90
Authorization: Bearer <token>
```

`limit`范围为`1-365`。日期格式错误、超出范围的limit、额外提交`rule_set_version/scope_type/scope_id`都会返回统一422响应。

## 7. 异常与空数据约定

- 当前评分不存在：`GET /score`返回404。
- 历史趋势不存在：`GET /history`返回`total=0, items=[]`。
- 尚无已发布评分：`GET /rules`返回当前V1规则集版本及空列表。
- Service业务校验异常：沿用400 `VALIDATION_ERROR`。
- 持久化异常：沿用脱敏的500 `PERSISTENCE_ERROR`。
- Router不捕获并重写Service异常，由全局异常映射统一处理。

## 8. 测试范围

API测试完全使用`dependency_overrides`和Fake DataQualityService，不连接真实数据库，覆盖：

- 四条OpenAPI路径注册、JWT Bearer和统一错误模型。
- 未登录401、USER读取成功、USER计算403、ADMIN计算成功。
- 计算参数和管理员身份正确传递给Service。
- 客户端不能控制规则集版本和scope。
- 当前评分、规则明细、趋势及空数据响应结构。
- 404、请求校验、业务异常和持久化异常映射。
- Dependency组合中的Service与全部Repository共享同一Session。
- Router源码不引用Repository、ORM或Session。

验证结果：

- Data Quality API与相关OpenAPI测试：`17 passed`。
- 完整后端测试：`238 passed`。
- `git diff --check`：通过，无空白错误。

## 9. 设计取舍

- API不重复计算任何评分或等级，所有业务结果来自Service与已持久化数据。
- `/rules`返回最近一次已发布评分的规则快照，优先保证历史可追溯和分层边界。
- API不开放规则在线编辑，也不开放scope和版本选择，避免突破Phase 2 V1冻结范围。
- 未引入新依赖，继续复用Pydantic、FastAPI依赖注入和现有统一响应/异常机制。
