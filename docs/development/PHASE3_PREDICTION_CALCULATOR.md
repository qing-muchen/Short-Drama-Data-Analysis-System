# Phase 3 Prediction Calculator

## 1. 实现边界

本阶段新增数据库无副作用的Prediction Calculator，只处理已准备好的累计播放量日点：

```text
8个连续累计播放量日点
        ↓
7个daily increment
        ↓
Moving Average V1.0
        ↓
下一日累计播放量
```

Calculator不查询数据库、不读取snapshot或revision、不执行平台聚合、不保存结果，也不管理事务。历史数据选择、`analysis_as_of`、revision截止规则和平台聚合由后续Repository/Service负责。

## 2. 算法定义

算法版本固定为：`Moving Average V1.0`。

输入模型为`CumulativePlayCountPoint`，包含：

- `observation_date`
- `play_count`

输入必须按日期升序排列。Calculator取最新的8个点，要求这8个日期连续且每天一个点：

```text
daily_increment[i] = play_count[i + 1] - play_count[i]
predicted_increment = mean(7个daily_increment)
predicted_value = latest_play_count + predicted_increment
```

这里使用加法是累计指标的语义要求。原任务描述中的减法会使正增长序列预测为下降，和已冻结的`PHASE3_PREDICTION_DESIGN_V2.md`不一致；本实现以冻结设计为准。

最终`predicted_increment`和`predicted_value`均使用`Decimal`并以`ROUND_HALF_UP`保留两位小数。结果还包含：

- `prediction_date`
- `target_date`
- `target_metric = PLAY_COUNT`
- `algorithm_version = Moving Average V1.0`
- `predicted_increment`

结果只是内存中的Calculator输出，不写入数据库。

## 3. 异常处理

| 场景 | 错误码 |
|---|---|
| 输入为空 | `EMPTY_INPUT` |
| 少于8个累计点 | `INSUFFICIENT_HISTORY` |
| 日期不连续或不足8个日点 | `INSUFFICIENT_DAILY_POINTS` |
| 日期顺序不是严格升序 | `INVALID_DATE_SEQUENCE` |
| 累计播放量下降 | `INVALID_CUMULATIVE_SEQUENCE` |
| 负数播放量 | `INVALID_PLAY_COUNT` |
| NaN或Infinity | `NON_FINITE_PLAY_COUNT` |
| 非法日期或点结构 | `INVALID_OBSERVATION_DATE` / `INVALID_INPUT_POINT` |

零播放量和零增长是合法输入。Calculator不把负日增量静默改为零；累计值回落直接返回稳定错误，交由Service记录数据质量问题。

## 4. 测试结果

`backend/tests/test_prediction_calculator.py`覆盖：

- 8点正常计算及7个增量。
- 累计播放量加预测增量的公式。
- 超过8点时使用最新窗口。
- 空输入和历史不足。
- 日期缺口及输入顺序。
- 累计值下降、零增长。
- 负数、NaN、Infinity。
- Decimal大数值计算。
- `ROUND_HALF_UP`稳定精度。
- 算法版本和指标名称固定。

## 5. 后续边界

后续PredictionRepository负责读取已经按`analysis_as_of`筛选、按全部有效平台聚合的输入；PredictionService负责调用本Calculator并保存`PredictionResult`。Calculator不应被扩展为数据库访问层，也不应在前端重复实现移动平均。
