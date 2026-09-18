# Phase 3 Prediction Module Summary

## 1. Phase 3目标

Phase 3为短剧运营平台增加“运营趋势辅助分析”能力。模块基于历史运营事实，预测短剧下一日的累计播放量，帮助运营人员观察播放趋势和安排后续运营动作。

本模块不是投资预测、收益预测或短剧成功概率预测，也不替代人工决策。预测结果仅表达在固定历史数据截止点和固定算法版本下的运营趋势估计。

Phase 3的完整链路为：

```text
历史运营快照
    ↓
按 analysis_as_of 选择可见 revision
    ↓
全部有效平台聚合为短剧级累计播放量
    ↓
Prediction Calculator
    ↓
prediction_results
    ↓
Prediction API
    ↓
Prediction Dashboard
```

## 2. 整体架构

Phase 3保持现有分层架构：

```text
Router
  ↓
PredictionService
  ↓
PredictionRepository
  ↓
PredictionResult ORM
  ↓
prediction_results
```

预测算法独立放置在`backend/analytics/prediction.py`，只接收经过Service准备的累计播放量序列，不查询数据库、不选择revision、不管理事务。

各层职责如下：

- **Calculator**：完成累计播放量差分、7日移动平均和下一日累计值预测。
- **Repository**：保存、替换和查询预测结果，不计算预测，不`commit`或`rollback`。
- **Service**：确定`analysis_as_of`、准备历史输入、调用Calculator、组织持久化和OperationLog事务。
- **API**：负责认证、参数校验、Service调用和统一响应转换。
- **Dashboard**：只展示API结果，不在浏览器端重新计算预测。

## 3. 数据库设计

V010新增`prediction_results`表，预测结果独立保存，不重复建立运营事实表。

核心字段：

| 字段 | 用途 |
|---|---|
| `prediction_id` | BIGINT UNSIGNED自增主键 |
| `drama_id` | 关联`dramas.drama_id`的外键 |
| `metric_type` | V1固定为`PLAY_COUNT` |
| `prediction_date` | 预测生成日期 |
| `target_date` | 被预测的下一日 |
| `predicted_value` | 下一日累计播放量预测值，DECIMAL(20,2) |
| `algorithm_version` | V1固定为`Moving Average V1.0` |
| `analysis_as_of` | 输入快照和revision的时间截止点 |
| `created_at` / `updated_at` | 记录生命周期时间 |

约束和索引：

- `drama_id`使用`RESTRICT`外键，避免删除仍有预测记录的短剧。
- `(drama_id, metric_type, target_date, algorithm_version)`保证同一短剧、指标、目标日期和算法版本只有一条结果。
- `metric_type`和`algorithm_version`不能为空，`predicted_value >= 0`。
- `(drama_id, metric_type, target_date)`支持单剧查询和趋势查询。
- `(metric_type, target_date)`支持指标维度的日期查询。

表结构遵循第三范式，不保存`drama_name`、`platform_name`、`daily_increment`、`input_window`或`confidence`等冗余和V1非持久化字段。平台聚合属于输入准备过程，预测结果天然归属于`drama_id`，因此V1不增加scope字段。

## 4. Calculator设计

算法版本固定为`Moving Average V1.0`，预测目标为下一日累计播放量。

### 4.1 输入与计算

Calculator需要8个按日期升序排列的连续累计播放量日点：

```text
[play_count(day1), ..., play_count(day8)]
```

相邻累计值生成7个日增量：

```text
daily_increment[i] = play_count[i + 1] - play_count[i]
```

预测增量为7个日增量的算术平均值：

```text
predicted_increment = mean(7个daily_increment)
predicted_value = latest_play_count + predicted_increment
```

结果使用`Decimal`计算，并按`ROUND_HALF_UP`保留两位小数。正常零增长和零播放量是合法输入；累计值倒退、负数、非有限数值或历史不足会返回稳定错误，不生成伪造的零预测。

### 4.2 Calculator边界

Calculator不负责：

- 查询snapshot或revision。
- 聚合平台和补齐日期。
- 创建Session、ORM对象或事务。
- 保存预测结果或写操作日志。

## 5. Repository设计

`PredictionRepository`只负责`prediction_results`的数据访问：

- `save_prediction()`：保存单条预测并`flush`。
- `replace_prediction()`：替换同一短剧、指标、算法和目标日期的旧结果。
- `get_latest_prediction()`：按`analysis_as_of`、创建时间和主键倒序获取最近结果。
- `get_predictions_by_drama()`：按目标日期升序查询短剧预测历史。
- `get_prediction_range()`：按目标日期范围查询结果。
- `delete_prediction_scope()`：删除指定短剧、指标和算法版本的预测结果。

Repository复用Service传入的Session，不创建Session，不调用Calculator，不承担数据选择或业务判断，也不执行`commit()`和`rollback()`。唯一约束或外键异常向上层传播，由Service统一处理事务。

## 6. Service流程

`PredictionService`负责单剧预测业务编排，流程如下：

```text
创建PredictionContext
    ↓
确定 analysis_as_of
    ↓
读取截止点之前可见的历史snapshot/revision
    ↓
构建同一短剧、连续8日、全部有效平台聚合的累计序列
    ↓
调用 PredictionCalculator
    ↓
创建 PredictionResult
    ↓
Repository保存或替换结果
    ↓
写入一次 PREDICTION_CALCULATE 操作日志
    ↓
统一 commit / rollback
```

### 6.1 时间截点和revision追溯

- 当前预测使用当前时刻作为`analysis_as_of`；历史预测使用调用方指定的时间截点。
- 只读取`snapshot_time <= analysis_as_of`的数据。
- 只选择`changed_at <= analysis_as_of`的revision，禁止使用截止点之后产生的修订覆盖历史输入。
- 同一平台同一业务日取最后一个有效观测；不插值、不用0补齐日期。
- 无法得到连续8个累计日点时返回`INSUFFICIENT_HISTORY`，不保存结果。

预测结果持久化、OperationLog写入在同一个事务中。任一Calculator、Repository或日志错误都会整体回滚，避免出现只有预测结果或只有日志的部分成功状态。

## 7. API设计

Phase 3 API统一挂载在`/api/v1`下，Router只调用PredictionService。

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| POST | `/api/v1/predictions/calculate` | ADMINISTRATOR | 计算指定短剧下一日预测 |
| GET | `/api/v1/predictions/{drama_id}` | 登录用户 | 查询最近一次预测 |
| GET | `/api/v1/predictions/{drama_id}/history` | 登录用户 | 查询预测历史，支持limit分页 |

计算请求只允许提交`drama_id`和可选`analysis_as_of`。`metric_type`和`algorithm_version`由Phase 3 V1固定，客户端不能覆盖。响应通过现有`ResponseModel[T]`返回，预测详情包括：

- `prediction_id`
- `drama_id`
- `metric_type`
- `algorithm_version`
- `analysis_as_of`
- `target_date`
- `predicted_value`
- `created_at`

API不暴露`daily_increment`、内部窗口或revision明细。无预测返回统一404，权限和参数错误沿用现有ErrorResponse体系。

## 8. Dashboard设计

新增`PredictionAnalysis.vue`并注册`/predictions`路由，页面包括：

1. 短剧选择和查询区域。
2. 当前预测卡片，展示目标日期、预测累计播放量、算法版本、指标和数据截止时间。
3. 历史预测折线图，横轴为`target_date`，纵轴为API返回的`predicted_value`。
4. 预测结果说明：结果基于历史累计播放量变化趋势，仅用于运营分析参考。
5. loading、error、empty和success状态。

管理员可以看到重新预测按钮，普通用户隐藏该按钮；最终权限仍由后端校验。ECharts实例在数据加载后初始化，监听窗口resize，并在组件卸载时dispose。前端不重新计算日增量、移动平均或等级。

## 9. 测试结果

### 9.1 Backend

归档前在当前工作区执行：

```text
286 passed in 8.01s
```

Phase 3专项覆盖数据库/ORM约束、Calculator、Repository、Service和API边界，包括历史不足、日期缺口、revision时间过滤、唯一约束、事务回滚、权限和统一响应结构等场景。

### 9.2 Frontend

- `vue-tsc --noEmit`：通过。
- `npm run build`：通过，Vite成功生成生产构建产物。
- 构建存在已有的chunk size非阻塞warning（部分压缩后chunk超过500 kB），未修改构建配置或依赖。

## 10. Phase 3限制

Phase 3 V1明确保持最小可解释范围：

- 仅预测`PLAY_COUNT`。
- 仅进行单剧、单步下一日预测。
- 仅使用`Moving Average V1.0`。
- 输入必须有连续8个累计播放量日点。
- 不保存scope、confidence、actual_value、prediction_error、input_window或predicted_increment。
- 不进行多算法比较、模型自动选择或前端自行计算。
- 不将预测结果解释为收益、成功概率或投资建议。

## 11. 未来扩展方向

后续可在新算法版本和独立迁移的前提下扩展：

- `Exponential Smoothing V2.0`等指数平滑模型。
- 点赞、评论、收藏、分享和互动率等多指标预测。
- 多步预测和平台级预测作用域。
- 独立预测评估表，记录实际值、误差、MAE/RMSE等模型评估指标。
- 置信区间和模型评估可视化。
- 更细粒度的输入血缘表，保存预测使用的snapshot revision集合。

扩展不得静默覆盖`Moving Average V1.0`历史结果，必须通过新的算法版本、字段或Migration保持历史可追溯性。

## 12. Phase 3版本记录

| 阶段 | Commit |
|---|---|
| Database + ORM | `2911fcba2ede0fdd1342f0c249f5bc56ed922f4e` |
| Calculator | `75d8c2089501412dcf6a57feb8850e2017dd2f6a` |
| Repository | `61f0ef430c40b5b7b948b019e63db696cd897a75` |
| Service | `62d8616cdd948c15d21c2120830325561406b0c1` |
| API | `c43ee5fca18681082fe72b0687ed6fc3fecc49d3` |
| Dashboard | `bde0fa77cccafe055a9d942b3f32ff0497a8e873` |

Phase 3至此完成从历史运营数据、可解释预测算法、持久化、业务编排、API到可视化展示的闭环。
