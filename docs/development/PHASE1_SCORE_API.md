# Phase 1 Score API

## API目标

Score API向已认证用户提供Composite Score V1.0结果查询，并允许管理员按指定日期同步触发整批评分计算。API层只负责参数校验、权限、Service调用和响应转换，不访问Repository、ORM或评分计算函数。

Phase 1固定使用`Composite Score V1.0`和`ALL / 0`作用域，客户端不能提交算法版本或作用域参数。

## 路由设计

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/v1/scores/calculate` | 计算并替换指定日期的评分集合 |
| GET | `/api/v1/scores/ranking` | 按日期分页查询评分排行 |
| GET | `/api/v1/scores/level-distribution` | 查询指定日期的等级分布 |
| GET | `/api/v1/scores/{drama_id}` | 查询单个短剧的最近评分 |

静态路径在动态`/{drama_id}`之前注册。排行要求显式传入`score_date`，支持`page`、`page_size`和可选的`S/A/B/C`等级过滤。

## 权限设计

- `POST /scores/calculate`仅允许`ADMINISTRATOR`，并将当前管理员`user_id`传给ScoreService用于批量操作日志。
- 三个查询接口允许`ADMINISTRATOR`和`USER`访问。
- 缺少有效JWT返回401，普通用户触发计算返回403。

## 请求与响应

计算请求只包含：

```json
{
  "score_date": "2026-09-14"
}
```

成功响应统一使用`ResponseModel[T]`：

```json
{
  "data": {
    "score_date": "2026-09-14",
    "algorithm_version": "Composite Score V1.0",
    "score_scope_type": "ALL",
    "score_scope_id": 0,
    "calculated_count": 90,
    "skipped_count": 10,
    "skipped_reasons": {
      "INSUFFICIENT_HISTORY": 10
    }
  },
  "message": "success"
}
```

排行响应使用统一分页结构。Router保持ScoreRepository既有顺序，只根据分页偏移生成展示排名。单剧无评分时返回404；等级分布无数据时返回S/A/B/C四个零值。

## 设计取舍

- API不暴露算法版本和作用域，避免客户端绕过Phase 1固定上下文。
- 评分字段以0到100的JSON数值输出，数据库继续使用两位定点小数保存。
- 短剧编号和名称由Router从已预加载的Drama关系中展平，仅用于传输展示。
- Router不捕获并改写Service异常，继续使用项目全局异常处理器。
- 计算接口同步返回结果；本阶段不引入后台任务、Router事务或请求ID中间件。

## 测试结果

2026-09-14完成验证：

- Score API、Router、Schema和认证相关定向测试：38项通过。
- 完整后端回归测试：157项通过，耗时5.84秒。
- 测试使用`dependency_overrides`和Fake ScoreService，不连接真实数据库。
- 已覆盖OpenAPI注册、JWT Bearer、401/403/200、请求校验、Service参数传递、分页、等级过滤、404及统一错误映射。
