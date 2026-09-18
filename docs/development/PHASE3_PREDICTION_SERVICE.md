# Phase 3 Prediction Service

## 1. Service职责

`PredictionService`负责单剧趋势预测的业务编排和事务边界：

```text
PredictionContext
        ↓
as-of历史输入Provider
        ↓
8个连续累计日点
        ↓
PredictionCalculator
        ↓
PredictionRepository
        ↓
OperationLogRepository
```

Service不实现移动平均、不手动计算daily increment、不直接访问ORM或执行SQL、不创建Session，也不让Repository提交事务。

## 2. 输入与输出

主入口：`calculate_prediction(drama_id, analysis_as_of, administrator_id)`。

Service固定：

- `metric_type = PLAY_COUNT`
- `algorithm_version = Moving Average V1.0`
- 结果归属为`drama_id`，不使用scope字段。

成功时构造传给Repository的结果字段：

- `drama_id`
- `metric_type`
- `prediction_date`
- `target_date`
- `predicted_value`
- `algorithm_version`
- `analysis_as_of`

Service返回`PredictionServiceResult`，包含预测对象、`predicted_count`、`skipped_count`和跳过原因。不会生成0或空预测值。

## 3. 数据追溯与窗口构建

历史Provider通过`get_prediction_history`提供带日期、平台、播放量、revision时间和revision状态的事实。Service执行：

1. 仅接受`changed_at <= analysis_as_of`的revision。
2. 排除VOID revision和无效平台。
3. 同一平台同一天选择截止时间前最新revision。
4. 对覆盖完整窗口的共同有效平台按日聚合累计播放量。
5. 只接受连续8个日点，日期升序，不跳过缺失日期。

不足或无效输入返回稳定原因：

- `NO_HISTORY`
- `INSUFFICIENT_HISTORY`
- `DATE_GAP`
- `INVALID_REVISION`
- `INVALID_METRIC`

历史Provider是注入的只读边界，便于后续由Analytics/Repository层实现真实SQL查询；本阶段没有修改现有AnalyticsService或数据库访问接口。

## 4. Calculator与Repository边界

Calculator只接收准备好的8个累计播放量点，负责：

```text
累计值 → 7个daily increment → Moving Average V1.0 → 预测累计值
```

Repository只保存和查询`prediction_results`。Service既不复制Calculator公式，也不直接实例化ORM；通过`PredictionRepository.replace_prediction`传递字段映射。

## 5. 事务设计

成功路径在同一个`BaseService.transaction()`中完成：

1. 读取历史输入。
2. 调用Calculator。
3. 替换PredictionResult。
4. 写入一次`PREDICTION_CALCULATE` OperationLog。
5. 统一commit。

Calculator、Repository或OperationLog出现异常时统一rollback。数据库异常由`BaseService`转换为`PersistenceException`；非数据库Calculator异常向上透传。跳过类业务结果仍写一条成功操作日志，记录`predicted_count=0`和`skipped_count=1`。

OperationLog摘要包含：

- `algorithm_version`
- `metric_type`
- `drama_id`
- `analysis_as_of`
- `predicted_count`
- `skipped_count`
- `skipped_reasons`

## 6. 查询方法

以下方法只委托PredictionRepository，不重新计算或排序：

- `get_latest_prediction`
- `get_prediction_history`
- `get_prediction_range`

## 7. 测试结果

`backend/tests/test_prediction_service.py`覆盖：

- 正常单剧流程及8日窗口构建。
- Calculator调用和异常传播。
- 无历史、历史不足、日期缺口。
- `analysis_as_of`未来revision过滤和同日revision选择。
- INVALID_REVISION、INVALID_METRIC。
- Repository失败回滚。
- OperationLog失败回滚。
- 成功只commit一次。
- 查询方法委托Repository。
- Service不访问ORM、不执行SQL、不实现移动平均。

后续若实现批量预测，应复用同一`PredictionContext`和同一Session，在一个事务中完成整批保存与日志记录；本阶段只实现单剧入口。
