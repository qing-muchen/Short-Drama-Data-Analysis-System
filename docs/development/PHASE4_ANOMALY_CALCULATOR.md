# Phase 4 Anomaly Detection Calculator

## 1. 实现范围

本阶段实现纯计算模块：

```text
backend/analytics/anomaly_detection.py
```

同时新增：

```text
backend/tests/test_anomaly_detection.py
```

本模块不访问数据库、ORM、snapshot、revision、Session或其他Service，也不执行平台聚合、结果保存和事务管理。Repository、Service、Router和Dashboard属于后续阶段。

## 2. 纯计算输入输出

Calculator接收已经由上层准备好的数值序列：

- `drama_id`
- `analysis_as_of`
- 历史指标序列
- 当前检测值
- 对互动率检测额外提供当前`play_count`

Calculator不假设输入来自哪个数据库表，只负责对输入序列执行冻结规则。

### 2.1 `AnomalyFinding`

异常命中时返回：

| 字段 | 说明 |
|---|---|
| `drama_id` | 短剧标识 |
| `metric_type` | `PLAY_COUNT`或`ENGAGEMENT_RATE` |
| `anomaly_type` | 四种V1异常类型之一 |
| `severity` | `A/B/C` |
| `analysis_as_of` | 输入分析截止时间 |
| `baseline_value` | 历史基准均值 |
| `actual_value` | 当前检测窗口实际值 |
| `deviation_value` | 实际值减历史基准 |
| `evidence_summary` | 可解释证据文本 |
| `algorithm_version` | 固定为`Rule-based Detection V1.0` |

数据库V011将该对象映射为`data_anomaly_records`，Calculator本身不创建ORM对象。

### 2.2 非异常结果

`AnomalyDetectionResult.status`区分：

- `ANOMALY`：包含`AnomalyFinding`。
- `NORMAL`：输入有效但未达到异常阈值。
- `NOT_APPLICABLE`：业务条件不适用，例如互动率播放量低于门槛。
- `INSUFFICIENT_HISTORY`：历史点少于2个，不能计算基线。

## 3. 固定版本和常量

```text
algorithm_version = Rule-based Detection V1.0
minimum_history_points = 2
recommended_baseline_window = 7
minimum_play_count_threshold = 100
```

Calculator允许接收2—7个历史点以支持边界测试；Service正常运行时应准备连续7日基线。超过7个点时取最近7个点，保证窗口固定。

## 4. 四类异常实现

### 4.1 `PLAY_COUNT_GROWTH_ANOMALY`

输入为历史7日播放增长值和当前1日增长值。累计播放量的差分和平台聚合由Service完成，Calculator只接收已经准备好的增长序列。

```text
actual_value = current daily growth
baseline_value = mean(previous growth values)
deviation_value = actual_value - baseline_value
```

只有正向偏离达到阈值才命中。负向偏离交由`PLAY_COUNT_DROP_ANOMALY`判断。

### 4.2 `PLAY_COUNT_DROP_ANOMALY`

输入与增长异常相同，但只接受负向偏离：

```text
z_score <= -2
```

当前增长值必须是非负数。累计播放量出现负差分属于数据质量问题，由上层Data Quality协议阻断，不在Calculator中伪造普通下降异常。

### 4.3 `ENGAGEMENT_RATE_ANOMALY`

互动率公式：

```text
(like_count + comment_count + favorite_count + share_count) / play_count
```

Calculator提供无数据库的`calculate_engagement_rate()`辅助函数。异常检测接收当前互动率、历史互动率和当前播放量。

门槛：

- `play_count = 0`：返回`NOT_APPLICABLE / ZERO_PLAY_COUNT`。
- `0 < play_count < 100`：返回`NOT_APPLICABLE / BELOW_MINIMUM_PLAY_COUNT`。
- 当前播放量达到100后才执行互动率偏离检测。

### 4.4 `DATA_SPIKE_ANOMALY`

V1检测当前指标相对历史均值的正向单日突增。支持的指标为`PLAY_COUNT`和`ENGAGEMENT_RATE`；对互动类原始指标的日增量聚合由后续Service准备。

当前值高于历史均值且：

```text
z_score >= 2
```

才生成`DATA_SPIKE_ANOMALY`。负向变化不使用该类型。

## 5. Z-score和零方差规则

### 5.1 标准情况

对历史序列使用总体标准差：

```text
mean = sum(history) / n
std = sqrt(sum((x - mean)^2) / n)
z = (current - mean) / std
```

当前值不参与历史均值和标准差计算。

### 5.2 严重等级

统一函数`determine_anomaly_severity()`：

| `abs(z_score)` | severity |
|---:|---|
| `< 2` | 不生成异常，返回`None` |
| `2 - < 3` | `C` |
| `3 - < 4` | `B` |
| `>= 4` | `A` |

数据库V011只保存A/B/C编码，等级具体由Calculator计算。A表示最严重，C表示较低严重等级。

### 5.3 标准差等于0

禁止除零。标准差为0时：

- `z_score = None`。
- 计算绝对偏差`abs(current - mean)`。
- 只要方向符合对应异常类型且偏差非零，就生成异常。
- 严重等级固定为`C`。
- 证据文本标记`threshold_mode=ABSOLUTE_DEVIATION_FALLBACK`。

该回退规则是V1的确定性行为，不将零方差数据误标为无限Z-score异常。

### 5.4 样本不足和非法值

- 历史少于2个点：`INSUFFICIENT_HISTORY`，不生成结果。
- 空历史：`INSUFFICIENT_HISTORY`。
- 负值、NaN、Infinity或无法转换为Decimal：抛出带稳定错误码的`AnomalyCalculationError`。
- Calculator不自动插值、不填0、不截尾、不修正输入。

## 6. 证据文本

每个异常finding包含确定性的`evidence_summary`，至少说明：

- 当前值。
- 历史均值。
- 历史标准差。
- 偏差值。
- Z-score或`NULL`。
- 使用的阈值模式。
- 互动率最小播放量门槛（适用时）。

示例：

```text
current_value=13.000000; baseline_mean=10.0000;
baseline_std=0.534522; deviation=3.0000;
z_score=5.612486; threshold_mode=Z_SCORE
```

该文本用于后续Service保存到V011的`evidence_summary`字段。Calculator不保存完整历史数组，不包含短剧名称、平台名称或数据库对象。

## 7. 异常处理边界

Calculator负责数学输入有效性：

- `INVALID_DRAMA_ID`
- `INVALID_ANALYSIS_AS_OF`
- `INVALID_METRIC_VALUE`
- `NEGATIVE_METRIC_VALUE`
- `NON_FINITE_VALUE`
- `ZERO_PLAY_COUNT`
- `INVALID_METRIC_TYPE`

Calculator不判断：

- snapshot/revision是否在`analysis_as_of`之前。
- 平台是否有效或是否应该聚合。
- Data Quality规则是否ERROR/WARNING。
- 是否写入、替换或删除异常记录。
- HTTP状态码、权限和事务。

这些判断分别由AnalyticsService、DataQualityService、AnomalyService和Router负责。

## 8. 测试结果

新增`backend/tests/test_anomaly_detection.py`，覆盖：

- Z-score均值和总体标准差。
- A/B/C边界及低于阈值。
- 播放增长和下降方向。
- 标准差为0的绝对偏差回退。
- 历史不足和空输入。
- 互动率公式、零播放和最小播放量100门槛。
- 数据突增正向检测。
- 负数、NaN、Infinity和非法上下文。
- 证据文本内容。
- 算法版本和结果确定性。

验证结果：

```text
Calculator专项：16 passed
Backend完整pytest：306 tests collected and passed
```

## 9. 后续Service边界

后续AnomalyService必须：

1. 从AnalyticsService获取已按`analysis_as_of`和revision规则过滤的数据。
2. 准备连续窗口和Drama级平台聚合结果。
3. 调用本Calculator，不复制Z-score或等级公式。
4. 将`AnomalyFinding`转换为`DataAnomalyRecord`。
5. 通过Repository保存并由Service管理事务和OperationLog。

本阶段停止于纯计算核心，不实现上述Repository、Service、API或Dashboard。
