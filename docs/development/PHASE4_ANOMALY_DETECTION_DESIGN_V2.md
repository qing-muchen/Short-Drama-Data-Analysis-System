# Phase 4 Anomaly Detection Design V2

> 状态：Phase 4实现冻结版。本文件吸收`PHASE4_ANOMALY_DETECTION_REVIEW.md`的审查意见，是V011及后续实现的唯一设计依据。本阶段只新增文档，不修改代码、数据库、Migration、ORM、API或Frontend。

## 1. 设计目标

Phase 4面向短剧运营数据发现当前行为相对历史常态的异常偏离，并将结果保存为可解释、可查询、可追溯的结构化异常记录。

异常检测结果的正式定义是：

> 某个算法版本在某个分析截止时间，对某个短剧指标行为偏离历史基准的分析结论。

异常记录保存的是`anomaly finding`，不是：

- 原始运营事实。
- Data Quality问题。
- 未来预测结果。
- 对短剧收益、投资价值或成功概率的判断。

完整数据流：

```text
历史运营事实
    ↓ AnalyticsService按analysis_as_of读取
指标级数据质量判断
    ↓ ERROR阻断 / WARNING继续并标记
连续历史窗口
    ↓
Rule-based Detection V1.0
    ↓
data_anomaly_records
    ↓
Anomaly API
    ↓
Anomaly Dashboard
```

## 2. 模块边界

### 2.1 Data Quality

回答“数据是否可信”。负责缺失、格式、取值范围、关联一致性和及时性等质量判断。

Data Quality ERROR可以阻断某个指标参与异常检测；Data Quality WARNING不直接构成异常，也不改变异常类型和严重等级。

### 2.2 Anomaly Detection

回答“当前指标行为是否偏离历史正常范围”。它只消费已准备好的历史序列和质量决策，不重复实现Data Quality规则。

### 2.3 Prediction

回答“未来趋势如何”。Phase 4 V1不使用预测值作为异常基线，不把预测误差解释为异常，也不调用PredictionService重新计算预测。

Prediction Dashboard未来可以并列展示预测和异常，但两个模块的计算、持久化和事务彼此独立。

### 2.4 Analytics

AnalyticsService是历史运营指标的唯一业务读取入口。AnomalyService不得绕过它直接查询snapshot ORM，也不得复制平台聚合和revision选择逻辑。

AnalyticsService需要提供按`analysis_as_of`读取Drama级历史日指标的只读契约。若当前接口尚不满足，Phase 4实现时只增加兼容的读取方法，不重构现有Analytics算法。

## 3. Phase 4 V1固定常量

| 项目 | 冻结值 |
|---|---|
| 算法版本 | `Rule-based Detection V1.0` |
| 基线窗口 | 当前点之前连续7个业务日 |
| 检测窗口 | 当前1个业务日 |
| 时区 | 业务日为`Asia/Shanghai`，数据库时间为UTC |
| Z-score标准差 | 7个基线点的总体标准差 |
| LOW阈值 | 绝对Z-score `>= 2.0` |
| MEDIUM阈值 | 绝对Z-score `>= 3.0` |
| HIGH阈值 | 绝对Z-score `>= 4.0` |
| 互动率最小播放量 | `100` |
| Decimal舍入 | `ROUND_HALF_UP`，持久化按字段精度 |

阈值、窗口和最小播放量不能由API客户端传入。任何调整必须升级`algorithm_version`，不能静默改变V1历史语义。

## 4. 异常类型定义

### 4.1 `PLAY_COUNT_GROWTH_ANOMALY`

#### 输入

- 同一Drama连续9个业务日的累计`play_count`。
- 相邻累计值生成8个日增量。
- 前7个日增量为基线，最后1个日增量为当前检测值。

#### 指标语义

```text
daily_increment(t) = play_count(t) - play_count(t-1)

actual_value = current daily_increment
baseline_value = mean(previous 7 daily_increment)
deviation_value = actual_value - baseline_value
```

`actual_value`不是累计播放总量，而是当前检测日的播放量增量。

#### 异常定义

- 当前增量必须为非负。
- `deviation_value > 0`。
- 同时满足Z-score阈值和`PLAY_COUNT`最小绝对偏差`100`。
- 标准差为0时使用第5.5节的绝对偏差回退。

#### 输出解释

表示当前日播放量增长显著高于此前7日正常增长水平。它可能来自内容爆发、活动投放或数据变化，不自动代表数据错误。

### 4.2 `PLAY_COUNT_DROP_ANOMALY`

#### 输入和指标语义

与增长异常相同：连续9个累计点生成前7个基线日增量和1个当前日增量。

```text
actual_value = current non-negative daily_increment
baseline_value = mean(previous 7 daily_increment)
deviation_value = actual_value - baseline_value
```

#### 异常定义

- 当前日增量必须非负。
- `deviation_value < 0`。
- 绝对Z-score和绝对偏差均达到阈值。

该类型表达“播放增长速度显著下降”，不表达累计播放总量真实减少。

#### 数据缺失和累计回退

- 日期不连续：返回`DATE_GAP`，不检测。
- 当前累计值小于前一日：返回`DATA_QUALITY_BLOCKED`，不生成下降异常。
- revision无效或指标级ERROR：返回`DATA_QUALITY_BLOCKED`。
- 不允许用0补齐缺失日期，也不允许把累计值回退当作运营下降。

### 4.3 `ENGAGEMENT_RATE_ANOMALY`

#### 互动率公式

同一业务日、同一Drama、同一有效平台集合聚合后：

```text
engagement_rate
  = (like_count + comment_count + favorite_count + share_count)
    / play_count
```

所有字段使用相同`analysis_as_of`和revision可见性规则。

#### 输入

- 当前业务日互动率。
- 此前连续7个业务日互动率作为基线。

```text
actual_value = current engagement_rate
baseline_value = mean(previous 7 engagement_rate)
deviation_value = actual_value - baseline_value
```

#### 最小播放量门槛

V1冻结：

```text
minimum_play_count_threshold = 100
```

- 当前累计`play_count = 0`：`NOT_APPLICABLE / ZERO_PLAY_COUNT`。
- 当前累计`0 < play_count < 100`：`NOT_APPLICABLE / BELOW_MINIMUM_PLAY_COUNT`。
- 基线中任一日`play_count < 100`：该日不是有效基线点；因此连续7日条件不成立，返回`INSUFFICIENT_HISTORY`。

门槛用于避免极小分母导致单次互动产生极端比率，并不表示低播放量数据不可信。

#### 异常定义

互动率正向或负向偏离均可触发。除Z-score阈值外，还必须满足最小绝对偏差`0.010000`，即1个百分点。

### 4.4 `DATA_SPIKE_ANOMALY`

#### 检测指标

V1只检测以下累计互动指标的单日增量突变：

- `LIKE_COUNT`
- `COMMENT_COUNT`
- `FAVORITE_COUNT`
- `SHARE_COUNT`

`PLAY_COUNT`由增长和下降异常负责，避免重复类型。

#### 时间窗口

每个指标需要连续9个累计日点，生成前7个基线日增量和1个当前日增量。

```text
actual_value = current metric daily_increment
baseline_value = mean(previous 7 metric daily_increment)
deviation_value = actual_value - baseline_value
```

#### 最小绝对偏差

| metric_type | V1最小绝对偏差 |
|---|---:|
| `LIKE_COUNT` | `20` |
| `COMMENT_COUNT` | `5` |
| `FAVORITE_COUNT` | `10` |
| `SHARE_COUNT` | `5` |

正向或负向偏离均可触发。累计值回退属于质量阻断，不生成`DATA_SPIKE_ANOMALY`。

### 4.5 类型优先级和去重

检测顺序冻结为：

1. 数据连续性和质量资格检查。
2. 累计回退检查。
3. 按异常类型执行Calculator。
4. 同一`metric_type + anomaly_type + analysis_as_of`只保留一个结果。

`DATA_SPIKE_ANOMALY`不检测`PLAY_COUNT`，因此不会与播放增长/下降重复。互动率是派生比率，可以与单个互动指标突变同时存在；它们表达不同信号，允许分别保存。

## 5. 算法规则

### 5.1 基线统计

对前7个连续有效基线点：

```text
n = 7
baseline_mean = sum(x_i) / n
baseline_std = sqrt(sum((x_i - baseline_mean)^2) / n)
deviation_value = actual_value - baseline_mean
```

当前检测值不参与均值和标准差计算，防止异常值稀释自身偏差。

### 5.2 标准差大于0

```text
z_score = deviation_value / baseline_std
```

必须同时满足：

1. 异常类型要求的方向。
2. `abs(z_score) >= 2.0`。
3. `abs(deviation_value)`达到该指标最小绝对偏差。

严重等级：

- `2.0 <= abs(z_score) < 3.0`：`LOW`。
- `3.0 <= abs(z_score) < 4.0`：`MEDIUM`。
- `abs(z_score) >= 4.0`：`HIGH`。

Z-score在V1中只是可解释偏差分，不代表概率、置信区间或统计显著性。

### 5.3 样本不足和日期缺口

- 基线少于7个有效点：`SKIPPED / INSUFFICIENT_HISTORY`。
- 日期不连续：`SKIPPED / DATE_GAP`。
- 输入为空：`SKIPPED / NO_HISTORY`。
- 不插值、不前向填充、不以0补齐。

### 5.4 极端值和非法值

- 负累计计数：`SKIPPED / INVALID_METRIC`。
- NaN、Infinity或无法转换为Decimal：`SKIPPED / NON_FINITE_VALUE`。
- 累计值回退：`SKIPPED / DATA_QUALITY_BLOCKED`。
- 超过V011 DECIMAL范围：在构造ORM前返回`VALUE_OUT_OF_RANGE`。
- V1不做截尾、缩尾或静默修正，避免隐藏真实输入。

### 5.5 标准差等于0的绝对偏差回退

当`baseline_std = 0`时不计算Z-score：

```text
deviation_score = NULL
fallback_ratio = abs(deviation_value) / minimum_absolute_deviation
```

只有达到方向要求和最小绝对偏差才触发：

- `1 <= fallback_ratio < 2`：`LOW`。
- `2 <= fallback_ratio < 4`：`MEDIUM`。
- `fallback_ratio >= 4`：`HIGH`。

该回退完全使用冻结的绝对偏差常量。基线均值为0时也适用，不做除以基线均值的相对变化计算。

### 5.6 Calculator输出

纯Calculator返回：

- `ANOMALY`：类型、指标、严重等级、基线、实际值、偏差、可选Z-score和证据摘要。
- `NORMAL`：输入有效但未达到阈值。
- `NOT_APPLICABLE`：业务条件不适用，例如互动率低于最小播放量。
- `SKIPPED`：历史、日期、质量或数值异常导致无法判断。

Calculator不查询数据库、不读取规则表、不创建ORM对象、不管理Session或事务。

### 5.7 为什么V1不使用机器学习

- 当前系统需要稳定、可解释且可复现的规则结果。
- 历史样本量和异常标签不足以支撑可靠监督学习。
- 机器学习会引入训练数据版本、模型文件、漂移、评估和部署复杂度。
- 规则模型容易覆盖边界测试，适合第一版软件能力展示。

未来使用MAD、EWMA、Isolation Forest等算法时必须采用新的算法版本和独立评审。

## 6. 数据质量协同协议

### 6.1 判断责任

DataQualityService负责返回指标级质量决策，AnomalyService只消费决策，不复制质量规则。

建议只读契约输入：

- `drama_id`
- `metric_type`
- `start_date/end_date`
- `analysis_as_of`

输出：`PASS/WARNING/ERROR/UNKNOWN`以及相关规则代码摘要。

### 6.2 冻结处理规则

| 质量结果 | AnomalyService行为 |
|---|---|
| `ERROR` | 阻断对应指标，返回`DATA_QUALITY_BLOCKED` |
| `WARNING` | 继续检测，并在`evidence_summary`中保存质量警告摘要 |
| `PASS` | 正常检测 |
| `UNKNOWN` | 继续检测，但保存`quality_status=UNKNOWN`，不得表述为可信 |

全局`data_quality_scores`只用于摘要展示，不能单独阻断某个Drama、日期和指标。阻断必须来自与检测输入相关的指标级确定性ERROR。

### 6.3 事务关系

AnomalyService只读取已存在的质量结果，不触发DataQualityService重新计算。异常保存和质量评分不处于同一事务，避免跨模块耦合。

## 7. 数据库设计V2

### 7.1 `data_anomaly_records`

V011新增一张异常记录表：

| 字段 | 类型建议 | 约束 | 说明 |
|---|---|---|---|
| `anomaly_id` | `BIGINT UNSIGNED` | PK, AUTO_INCREMENT | 主键 |
| `drama_id` | `BIGINT UNSIGNED` | NOT NULL, FK | 关联Drama |
| `metric_type` | `VARCHAR(32)` | NOT NULL | 被检测指标 |
| `anomaly_type` | `VARCHAR(48)` | NOT NULL | 四种冻结异常类型之一 |
| `severity` | `VARCHAR(16)` | NOT NULL | `LOW/MEDIUM/HIGH` |
| `status` | `VARCHAR(16)` | NOT NULL DEFAULT `OPEN` | 处置状态 |
| `anomaly_date` | `DATE` | NOT NULL | 当前检测点的业务日期 |
| `detected_at` | `DATETIME(6)` | NOT NULL | 实际执行检测的UTC时间 |
| `analysis_as_of` | `DATETIME(6)` | NOT NULL | 输入和revision截止点 |
| `algorithm_version` | `VARCHAR(64)` | NOT NULL | `Rule-based Detection V1.0` |
| `baseline_value` | `DECIMAL(24,6)` | NOT NULL | 前7点均值 |
| `actual_value` | `DECIMAL(24,6)` | NOT NULL | 当前日增量或互动率 |
| `deviation_value` | `DECIMAL(24,6)` | NOT NULL | 实际值减基线值 |
| `deviation_score` | `DECIMAL(12,6)` | NULL | Z-score；绝对回退时为空 |
| `evidence_summary` | `JSON` | NOT NULL | 可解释证据摘要 |
| `resolved_at` | `DATETIME(6)` | NULL | 进入RESOLVED的时间 |
| `created_at` | `DATETIME(6)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(6)` | NOT NULL | 更新时间 |

### 7.2 异常证据

V1增加`evidence_summary`，冻结为算法解释性证据，不保存完整原始日点：

```json
{
  "window_size": 7,
  "sample_count": 7,
  "baseline_start_date": "2026-09-11",
  "baseline_end_date": "2026-09-17",
  "baseline_std": "120.000000",
  "threshold_mode": "Z_SCORE",
  "z_score_threshold": "2.000000",
  "minimum_absolute_deviation": "100.000000",
  "minimum_play_count_threshold": null,
  "quality_status": "PASS",
  "quality_rule_codes": []
}
```

零方差时`threshold_mode = ABSOLUTE_DEVIATION`。互动率记录`minimum_play_count_threshold = 100`。

`evidence_summary`不能保存`drama_name`、`platform_name`、完整snapshot、完整revision或历史点数组。原始事实仍从snapshot/revision表按`analysis_as_of`重建。

### 7.3 `rule_id/rule_version`决策

V1不增加`rule_id`或`rule_version`：

- 规则不可由用户在线编辑。
- `anomaly_type + algorithm_version`已经冻结规则语义。
- `evidence_summary`保存当次使用的阈值摘要。

未来支持动态规则配置时，再通过新Migration增加`data_anomaly_rules`、`rule_version`和结果外键，不能为V1建立没有来源的规则引用。

### 7.4 唯一约束和重复检测

冻结唯一键：

```text
(drama_id, metric_type, anomaly_type, analysis_as_of, algorithm_version)
```

规则：

- 相同Drama、指标、异常类型、截止时间和算法版本的重复检测是幂等操作，不允许生成重复记录。
- 同一业务日但不同`analysis_as_of`允许保存不同检测快照，避免新revision覆盖历史检测结果。
- `detected_at`表示任务执行时间，不参与身份。
- 查询“当前异常”时按`analysis_as_of DESC, detected_at DESC, anomaly_id DESC`选择最新快照。

若相同检测身份重算后为`NORMAL/NOT_APPLICABLE/SKIPPED`，只允许删除仍为`OPEN`的自动异常记录；非OPEN记录保留并由OperationLog记录重算差异。

### 7.5 外键和CHECK约束

- `drama_id → dramas.drama_id`，`ON DELETE RESTRICT ON UPDATE RESTRICT`。
- `anomaly_type`限制为四种V1类型。
- `severity IN ('LOW','MEDIUM','HIGH')`。
- `status IN ('OPEN','ACKNOWLEDGED','RESOLVED','IGNORED')`。
- `baseline_value >= 0`、`actual_value >= 0`。
- `deviation_score IS NULL OR deviation_score`处于V011冻结的DECIMAL范围。
- `status = 'RESOLVED'`时`resolved_at IS NOT NULL`；其他状态`resolved_at IS NULL`。
- 字符串字段去除空白后非空。

`deviation_value = actual_value - baseline_value`由Service构造和测试保证。是否使用MySQL表达式CHECK在V011隔离验证时确认。

### 7.6 索引

- 唯一键：`uq_anomaly_detection_identity`。
- `(drama_id, anomaly_date DESC, anomaly_id DESC)`：单剧历史。
- `(anomaly_date DESC, severity, status)`：全局列表。
- `(anomaly_type, anomaly_date DESC)`：类型趋势。
- `(status, severity, detected_at DESC)`：处置查询。
- `(analysis_as_of DESC, algorithm_version)`：检测快照查询。

### 7.7 第三范式

不保存：

- `drama_name`、`platform_name`。
- 预测结果副本或质量评分副本。
- 操作人员姓名。
- 完整历史指标数组。

`resolved_by_user_id`不保存。操作人由`operation_logs`记录，异常表只保存领域状态和`resolved_at`，避免双重审计来源。

## 8. 状态模型

### 8.1 状态和转换

```text
OPEN → ACKNOWLEDGED → RESOLVED
  └───────────────→ IGNORED
ACKNOWLEDGED ─────→ IGNORED
```

- `OPEN`：系统新检测到，尚未确认。
- `ACKNOWLEDGED`：运营人员已确认并跟进。
- `RESOLVED`：问题或运营事件已处理完成，写入`resolved_at`。
- `IGNORED`：确认无需处理，`resolved_at`保持为空。

V1不支持终态重新打开。若未来需要重新打开，必须增加状态历史表或新版本设计。

### 8.2 状态API和审计

状态变化必须通过Service和API完成，不能由Repository或前端直接判断。V1增加：

```http
PATCH /api/v1/anomalies/{anomaly_id}/status
```

权限：`ADMINISTRATOR`。每次状态变化写一条`ANOMALY_STATUS_UPDATE`操作日志，记录旧状态、新状态、异常ID和时间。事务包含状态更新和日志，任一失败整体回滚。

## 9. 历史追溯规则

### 9.1 `analysis_as_of`

`analysis_as_of`是所有输入的硬截止点：

- `snapshot_time <= analysis_as_of`。
- revision满足`changed_at <= analysis_as_of`。
- 同一snapshot选择截止点可见的最高`version_no`。
- 截止点可见revision为VOID时排除该观测。
- 禁止使用截止点之后产生的revision修正历史检测。

### 9.2 每日点和平台聚合

- 业务日按`Asia/Shanghai`确定。
- 同一平台同一业务日取截止点前最后一个有效观测。
- 只有覆盖完整窗口的平台进入可比平台集合。
- 整个窗口使用同一可比平台集合，避免平台加入/退出造成虚假突变。
- Drama级每日累计值为有效可比平台集合的合计。

### 9.3 重复检测

相同`analysis_as_of`和算法版本重复执行必须得到确定性相同结果，并通过唯一约束幂等。不同`analysis_as_of`属于不同检测快照，允许并存。

## 10. Service架构

### 10.1 分层职责

#### AnomalyCalculator

只负责：均值、总体标准差、Z-score、绝对偏差回退、方向、等级和证据摘要。

#### AnomalyRepository

只负责：异常记录保存/幂等替换、分页、过滤、最新快照、详情、聚合和状态更新；允许`flush`，禁止`commit/rollback`和Session创建。

#### AnomalyService

负责：

1. 创建统一检测上下文。
2. 确定`analysis_as_of`和业务日期。
3. 调用AnalyticsService获取as-of历史日指标。
4. 调用DataQualityService获取指标级质量决策。
5. 构造连续窗口和固定可比平台集合。
6. 执行资格检查并调用Calculator。
7. 构造异常ORM对象并委托Repository保存。
8. 写一次批量`ANOMALY_DETECT`日志。
9. 统一`commit`或`rollback`。

Service不实现均值、标准差、Z-score或严重等级公式，不直接执行SQL，不创建Session。

#### Router

只负责JWT权限、参数校验、Service调用和Response转换。禁止访问ORM、Repository、Calculator或直接执行SQL。

### 10.2 检测事务

一次检测事务：

```text
保存/幂等替换异常结果
    +
清理同一检测身份下仍为OPEN的失效自动结果
    +
写一次ANOMALY_DETECT日志
    +
commit
```

任何Repository或OperationLog失败时整体rollback。Calculator和数据准备失败发生在写事务前，不能产生部分记录。

### 10.3 检测日志

一次批量操作只记录一条日志，detail包含：

- `analysis_as_of`
- `algorithm_version`
- `candidate_count`
- `anomaly_count`
- `normal_count`
- `not_applicable_count`
- `skipped_count`
- `skipped_reasons`
- `anomaly_type_counts`

不为每个异常生成一条操作日志。

## 11. API设计V2

统一前缀：`/api/v1/anomalies`，成功使用`ResponseModel[T]`，错误使用现有`ErrorResponse`。

### 11.1 执行检测

```http
POST /api/v1/anomalies/detect
```

权限：`ADMINISTRATOR`。

请求：

```json
{
  "drama_id": 123,
  "analysis_as_of": "2026-09-19T23:59:59+08:00"
}
```

- `drama_id`可选；为空表示检测全部候选Drama。
- `analysis_as_of`可选；为空由Service使用当前时间。
- 客户端禁止提交算法版本、指标、窗口、阈值、严重等级或scope。

响应：

```json
{
  "data": {
    "analysis_as_of": "2026-09-19T15:59:59Z",
    "algorithm_version": "Rule-based Detection V1.0",
    "candidate_count": 100,
    "anomaly_count": 12,
    "normal_count": 70,
    "not_applicable_count": 8,
    "skipped_count": 10,
    "skipped_reasons": {
      "INSUFFICIENT_HISTORY": 6,
      "DATA_QUALITY_BLOCKED": 4
    }
  },
  "message": "success"
}
```

### 11.2 异常列表

```http
GET /api/v1/anomalies
```

权限：登录USER和ADMINISTRATOR。

过滤参数：

- `start_date/end_date`
- `drama_id`
- `metric_type`
- `anomaly_type`
- `severity`
- `status`
- `algorithm_version`
- `page`（默认1）
- `page_size`（默认20，最大100）
- `latest_only`（默认true）

排序固定：`anomaly_date DESC`，严重等级显式`HIGH → MEDIUM → LOW`，最后`anomaly_id DESC`。

列表项返回异常ID、Drama ID、指标、类型、等级、状态、异常日期、截止时间、基线、实际值、偏差、算法版本和简化证据。

### 11.3 单剧异常历史

```http
GET /api/v1/anomalies/{drama_id}
```

权限：登录USER和ADMINISTRATOR。

支持与列表相同的日期、类型、等级、状态、算法版本、分页和`latest_only`过滤，但固定`drama_id`。返回稳定排序的历史异常。

### 11.4 状态更新

```http
PATCH /api/v1/anomalies/{anomaly_id}/status
```

权限：`ADMINISTRATOR`。

请求只允许提交目标`status`。Service校验状态转换，`RESOLVED`写入`resolved_at`，并与OperationLog在同一事务提交。

### 11.5 路由顺序

静态`/detect`必须在`/{drama_id}`之前注册。若状态路由与Drama动态路径放在同一Router中，使用明确的`/{anomaly_id}/status`结构并通过HTTP方法和路径完整匹配；OpenAPI测试必须验证无路由遮蔽。

## 12. Dashboard设计V2

新增`AnomalyAnalysis.vue`，路由`/anomalies`，只展示API结果：

1. 异常总数、OPEN数量、HIGH数量、涉及Drama数量。
2. LOW/MEDIUM/HIGH严重等级分布。
3. 按日期和异常类型展示趋势。
4. 异常短剧排行。
5. 可过滤、分页的异常列表。
6. 异常详情：指标、类型、等级、状态、实际值、基线、偏差、算法版本、`analysis_as_of`、质量状态和证据摘要。
7. 管理员检测按钮和状态操作，普通用户只读。

前端禁止：

- 重新计算互动率、均值、标准差或Z-score。
- 判断异常类型、等级或状态转换是否合法。
- 使用预测结果替代异常API结果。

页面必须支持loading、error、empty和success状态。ECharts监听resize并在卸载时dispose。

## 13. 测试方案

### 13.1 Calculator

- 四种异常的正常、异常和方向场景。
- 连续9点差分、7点基线和当前点不进入基线。
- Z-score阈值`2/3/4`及边界前后值。
- 每个指标最小绝对偏差。
- 标准差为0的`1x/2x/4x`回退边界。
- 互动率公式、播放量0、播放量99/100门槛。
- 历史不足、日期缺口、负累计值、累计回退。
- NaN、Infinity、大Decimal和ROUND_HALF_UP。
- 类型去重、算法版本和证据摘要确定性。

### 13.2 Repository

- 单条/批量保存和flush。
- 同一唯一身份重复写入幂等。
- 不同`analysis_as_of`历史快照并存。
- 最新快照、单剧历史、全局分页和过滤。
- 严重等级稳定排序。
- OPEN自动结果清理和非OPEN结果保留。
- 状态更新和`resolved_at`约束。
- 外键、UNIQUE、CHECK、JSON证据。
- 不commit、不rollback、不创建Session、不调用Calculator。

### 13.3 Service

- Analytics → Quality → Calculator → Repository → Log完整流程。
- ERROR阻断、WARNING继续、UNKNOWN继续并标记。
- 全局质量分不能单独阻断指标。
- as-of snapshot/revision过滤，禁止未来revision。
- 固定平台集合和日期连续性。
- 无历史、日期缺口、累计回退和NOT_APPLICABLE。
- 重复检测幂等，不同截止点保留历史。
- 无命中时只清理OPEN自动记录。
- Repository/OperationLog失败整体rollback。
- 成功只commit一次。
- 不访问Prediction计算，不复制Calculator公式。

### 13.4 API

- OpenAPI路径和JWT Bearer。
- 匿名401、USER查询200、USER检测/状态更新403、ADMIN成功。
- `analysis_as_of`时区、Drama ID、枚举和分页校验。
- 禁止额外提交算法参数。
- 过滤条件和Service参数传递。
- ResponseModel、ErrorResponse和证据Schema。
- 状态转换错误映射。
- 静态路径优先级和Router分层边界。

### 13.5 Dashboard

- TypeScript类型通过。
- API调用、权限按钮、过滤和分页。
- loading/error/empty/success。
- 严重等级、趋势、排行和详情渲染。
- ECharts resize/dispose。
- `vue-tsc --noEmit`和`npm run build`通过。

## 14. V011 Migration准备事项

V011文件计划：

```text
database/migrations/V011__create_data_anomaly_records.sql
```

进入实现前必须执行：

1. 确认正式迁移序列V001—V010完整且不可修改。
2. 使用本文字段、唯一键、CHECK和索引创建`data_anomaly_records`。
3. 确认MySQL 8.x对JSON、DATETIME(6)、DECIMAL和CHECK的支持。
4. 对`analysis_as_of`唯一键和多历史快照进行隔离数据库验证。
5. 验证`status/resolved_at`组合约束。
6. 验证`evidence_summary`只保存摘要，不保存冗余业务实体。
7. 验证外键RESTRICT和索引列顺序。
8. 运行V001—V011空库迁移、ORM metadata和现有后端回归测试。

V011只新增异常记录表，不修改snapshot、Data Quality、Score、Prediction或Drama表结构。

## 15. 实现顺序

Design V2冻结后按以下阶段独立提交：

1. V011 Migration + Anomaly ORM +数据库约束测试。
2. AnomalyCalculator +纯计算测试。
3. AnomalyRepository +数据访问测试。
4. AnomalyService +质量协同和事务测试。
5. Anomaly Schema/Router/API测试。
6. Anomaly Dashboard +前端构建验证。
7. Phase 4归档文档。

## 16. Design V2准入结论

本V2已经冻结：

- 异常finding语义和四种异常类型。
- 7日基线、1日检测窗口和累计指标差分规则。
- Z-score阈值、最小绝对偏差和零方差回退。
- 互动率最小播放量100。
- Data Quality ERROR/WARNING/UNKNOWN协同协议。
- `analysis_as_of` revision过滤和历史快照唯一性。
- `evidence_summary`、状态模型和状态API。
- Calculator、Repository、Service和Router职责边界。

在V011严格遵循本文字段和约束、且不恢复原始设计中已否决的覆盖式唯一性后，**允许进入V011 Database + ORM实现阶段**。
