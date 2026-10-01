# Phase 3 Prediction Engine Design V2

> 状态：设计冻结候选版，仅修订文档，不创建Migration、不修改ORM、Backend、Frontend或Dashboard。

## 1. 修订背景

Phase 3 V1的目标是预测短剧运营趋势，而不是进行投资、收益或成功概率预测。架构审查确认：`drama_metric_snapshot_revisions.play_count`是累计播放量，不能直接将累计值序列取移动平均并解释为下一日累计值。

本V2将预测目标重新定义为：

```text
连续8个累计播放量日点
        ↓ 相邻差分
7个daily_increment
        ↓ Moving Average V1.0
预测下一日增量
        ↓ 加到最新累计值
下一日累计播放量预测
```

### 1.1 公式符号说明

业务语义决定下一日累计值应为：

```text
daily_increment(t) = play_count(t) - play_count(t-1)

predicted_increment(t+1) = mean(last 7 daily_increment)

predicted_play_count(t+1)
    = latest_play_count + predicted_increment(t+1)
```

这里使用加法。若使用“`latest_play_count - predicted_increment`”，正常增长序列会被错误地预测为下降；因此V2将该符号明确修正为`+`。

## 2. 已确认事实与V2设计选择

### 2.1 已确认事实

- 运营事实由`drama_metric_snapshots`和不可变的`drama_metric_snapshot_revisions`保存。
- `play_count`、`like_count`、`comment_count`、`favorite_count`、`share_count`采用累计整数语义。
- `snapshot_time`是实际观测时间字段，按业务时区转换为日期。
- 现有Analytics对累计值求和，并通过相邻累计值差计算增长。
- 当前迁移链为V001—V009，V009是Data Quality表迁移。

### 2.2 V1设计选择

- 预测对象：单个`drama_id`的下一日累计播放量。
- 输入窗口：连续8个累计日点，生成7个日增量。
- 算法：`Moving Average V1.0`。
- 目标：单步预测`target_date = prediction_date + 1 day`。
- 平台：全部符合条件的平台聚合为Drama级输入。
- Scope：V1不保存`scope_type/scope_id`，平台聚合是输入过程，不是预测结果作用域。
- 历史追溯：必须按`changed_at <= analysis_as_of`选择当时可见revision。
- 数据不足：无法获得连续8个累计日点时不生成预测。

### 2.3 未来扩展

- 指数平滑必须使用新的`Exponential Smoothing V2.0`，不能覆盖V1历史结果。
- 平台级预测未来增加明确的`drama_platform_id`或独立结果表。
- 点赞、评论和互动率预测需要新的指标语义和算法版本。
- 置信区间和预测误差评估需要独立设计，不在V1伪造字段。

## 3. 数据流程

```text
drama_metric_snapshots
        ↓
snapshot revisions as of analysis_as_of
        ↓
各平台每日最后有效累计值
        ↓
全部可比平台聚合为Drama累计值
        ↓
连续8日累计值校验
        ↓
7个daily_increment
        ↓
PredictionCalculator
        ↓
prediction_results
        ↓
Prediction API
        ↓
Prediction Dashboard
```

预测结果不回写快照表，不建立第二套运营事实表。

## 4. 历史数据选择规则

### 4.1 `analysis_as_of`

`analysis_as_of`是预测输入的硬截止时间：

- `snapshot_time <= analysis_as_of`。
- revision的`changed_at <= analysis_as_of`。
- 预测不能读取截止时间之后才产生的CORRECTION或VOID。
- 当日预测使用当前时刻；历史预测使用指定业务日期结束时刻转换成UTC。

### 4.2 revision选择

不能直接读取当前`current_revision_id`重建历史，因为当前revision可能是在`analysis_as_of`之后产生的修订。

对每个snapshot槽位：

1. 过滤观测时间不晚于`analysis_as_of`的槽位。
2. 从revision链过滤`changed_at <= analysis_as_of`。
3. 选择截止时点可见的最高`version_no`。
4. 若选择的revision为`VOID`，排除该槽位。
5. 复用现有数据质量有效性规则，确定性ERROR数据不参与预测；WARNING可参与但需传播质量提示。

### 4.3 每日观测点

同一平台同一业务日存在多次snapshot时，取该平台当日最后一个有效观测。业务日按Asia/Shanghai确定，数据库时间仍按UTC持久化。

V1不插值、不用0补齐日期、不把不连续观测点假装成连续日点。

## 5. 多平台聚合规则

预测输入来自全部有效且可比平台聚合后的Drama累计播放量：

1. 对每个DramaPlatform独立取得连续8个业务日的日末累计值。
2. 只有覆盖完整8日窗口的平台才进入本次可比平台集合。
3. 各平台相邻累计值做差，形成平台级7个日增量。
4. 同一日期将可比平台日增量求和，得到Drama级日增量。
5. 最新累计基线使用同一可比平台集合在最新日的累计值之和。
6. 计算预测增量并加到该基线，得到下一日累计播放量预测。

平台状态、日末取值、revision版本和质量过滤都必须在同一`analysis_as_of`下确定。平台中途上线、下线或缺失日点时，V1排除该平台出本次可比集合，不动态改变窗口中的平台组成。

平台聚合是预测输入准备过程，不是结果scope；因此预测结果只需要`drama_id`。

## 6. Moving Average V1.0

### 6.1 输入

Calculator接收：

- 连续8个累计播放量日点，按日期升序。
- 最新累计播放量`latest_play_count`。
- 已校验的目标日期。
- 固定窗口7。

Calculator可以在内部从8个累计点生成7个增量，也可以接收Service预先生成的7个增量，但不读取数据库。

### 6.2 计算

```text
increment[i] = cumulative[i] - cumulative[i-1]

predicted_increment
    = (increment[1] + ... + increment[7]) / 7

predicted_value
    = latest_play_count + predicted_increment
```

计算使用`Decimal`和`ROUND_HALF_UP`保留两位小数。`predicted_value`不得小于0；累计值下降和负日增量不自动改为0，应保留并传播质量提示。若计算结果小于0，则返回稳定的计算错误，不保存结果。

### 6.3 数据不足和异常

- 少于连续8个累计日点：`INSUFFICIENT_HISTORY`，不生成预测。
- 空数据或单点数据：同样返回`INSUFFICIENT_HISTORY`。
- 日期缺口：不插值，返回`INSUFFICIENT_HISTORY`。
- 负数、NaN、Infinity或无法转换为Decimal：输入异常，不保存。
- 累计值为0：合法输入。
- 极大但有限的数值：使用Decimal计算；超过数据库范围时由持久化校验拒绝。

## 7. `prediction_results`数据库设计

### 7.1 V1必须保存字段

| 字段 | 类型建议 | 说明 |
|---|---|---|
| `prediction_id` | `BIGINT UNSIGNED` | 主键，自增 |
| `drama_id` | `BIGINT UNSIGNED` | 外键到`dramas.drama_id`，RESTRICT |
| `metric_type` | `VARCHAR(32)` | V1固定`PLAY_COUNT` |
| `prediction_date` | `DATE` | 预测生成的业务日期 |
| `target_date` | `DATE` | V1为下一业务日 |
| `predicted_value` | `DECIMAL(20,2)` | 下一日累计播放量预测 |
| `algorithm_version` | `VARCHAR(64)` | `Moving Average V1.0` |
| `analysis_as_of` | `DATETIME(6)` | 输入数据和revision截止时间 |
| `created_at` | `DATETIME(6)` | 创建时间 |
| `updated_at` | `DATETIME(6)` | 更新时间 |

约束建议：

- `metric_type = 'PLAY_COUNT'`。
- `target_date > prediction_date`；Service固定为下一日。
- `predicted_value >= 0`。
- `CHAR_LENGTH(TRIM(algorithm_version)) > 0`。
- 唯一约束：`(drama_id, metric_type, prediction_date, target_date, algorithm_version)`。

索引建议：

- `(drama_id, metric_type, target_date)`：单剧最新和趋势查询。
- `(prediction_date, metric_type, algorithm_version)`：批次替换和审计。
- `(algorithm_version, target_date)`：版本趋势查询。

### 7.2 `input_window`和`predicted_increment`

这两个字段需要区分数据库事实与计算中间变量：

| 字段 | V1决策 | 原因 |
|---|---|---|
| `input_window` | 不作为V1独立数据库字段 | V1窗口固定为7；可从`algorithm_version`和设计规则解释，避免保存重复常量 |
| `predicted_increment` | 不保存 | 它是从累计点推导的计算中间值，V1对外只承诺累计`predicted_value` |

Calculator和Service内部仍必须保留这两个值用于测试、审计日志和响应转换；API默认不暴露内部增量过程。若未来允许用户选择窗口，或需要展示预测增量，再通过新Migration显式增加字段并升级算法版本。

### 7.3 不保存和未来扩展字段

- `actual_value`：不保存。实际值来自目标日期之后的快照事实。
- `prediction_error`：不保存。误差是`actual - predicted`派生结果；未来可设计独立`prediction_evaluations`表。
- `confidence`：不保存。移动平均V1没有校准置信区间。
- `model_version`：不保存。`algorithm_version`已经是唯一模型身份。
- `scope_type/scope_id`：V1删除，预测结果天然属于`drama_id`。
- `drama_name/platform_name`：不保存，避免违反第三范式。

## 8. Revision追溯策略

V1只保存`analysis_as_of`，不保存单个`revision_id`：

- 一次预测实际使用多个日期、多个平台和多个revision，单列`revision_id`无法表达完整输入。
- revision不可变，配合`changed_at`、`version_no`可以在截止时点重新选择输入。
- 保存单个revision ID会产生错误的“看似可追溯”假象。

未来若需要审计级精确血缘，应新增`prediction_input_revisions`子表，按`prediction_id + snapshot_revision_id + observation_date + sequence_no`保存输入成员，不应将revision ID数组塞进JSON字段。

## 9. 纯Calculator边界

文件：`backend/analytics/prediction.py`

只负责：

```text
连续累计序列
    ↓
daily_increment
    ↓
Moving Average V1.0
    ↓
predicted_increment + latest_play_count
    ↓
PredictionResult
```

不负责：

- 查询snapshot或revision。
- 选择平台、日期或质量规则。
- 创建Session、事务、ORM或HTTP响应。
- 保存结果或记录日志。

## 10. Repository与Service设计

### 10.1 Repository

建议使用两个只读/持久化边界：

- `PredictionInputRepository`：按`analysis_as_of`选择revision、准备日末数据和可比平台输入。
- `PredictionRepository`：保存、按批次替换、查询单剧最新、查询历史和趋势。

Repository不调用Calculator、不计算、不commit、不rollback、不创建Session。

### 10.2 PredictionService

```text
读取as-of历史快照
    ↓
准备连续8日累计点和可比平台集合
    ↓
调用PredictionCalculator
    ↓
创建PredictionResult ORM对象
    ↓
替换同一预测日期/算法版本结果
    ↓
记录一次PREDICTION_CALCULATE操作日志
    ↓
统一commit或rollback
```

Service固定：`PLAY_COUNT`、窗口7、单步目标、`Moving Average V1.0`。Service不复制移动平均公式，Repository不计算。

## 11. API同步设计

### 11.1 计算

```http
POST /api/v1/predictions/calculate
```

权限：`ADMINISTRATOR`。

请求建议：

```json
{
  "prediction_date": "2026-09-18",
  "drama_id": 123
}
```

`drama_id`为空表示批量处理全部符合条件的短剧。客户端不能提交算法版本、指标类型、窗口、scope或目标日期。

响应至少包含：

- `prediction_date`
- `target_date`
- `algorithm_version`
- `generated_count`
- `skipped_count`
- `skipped_reasons`

### 11.2 单剧最新预测

```http
GET /api/v1/predictions/{drama_id}
```

权限：USER和ADMINISTRATOR。返回：

- `drama_id`
- `metric_type`
- `prediction_date`
- `target_date`
- `predicted_value`
- `algorithm_version`
- `analysis_as_of`

不返回`predicted_increment`等内部计算过程。无结果返回统一404。

### 11.3 趋势查询

```http
GET /api/v1/predictions/trend
```

权限：USER和ADMINISTRATOR。静态路径必须在`/{drama_id}`之前注册。参数建议：必填`drama_id`，可选`start_date`、`end_date`和有上限的`limit`。

响应区分：

- `historical`：实际历史累计播放量。
- `predictions`：已保存的未来累计播放量预测。
- `algorithm_version`、`target_date`和`analysis_as_of`。

Router只负责权限、参数、Service调用和`ResponseModel[T]`转换，不访问Repository/ORM，也不计算预测。

## 12. Dashboard同步设计

新增`PredictionAnalysis.vue`，只展示API结果：

1. 历史累计播放量折线。
2. 未来预测累计播放量虚线或不同颜色。
3. 最新预测值、目标日期和算法版本。
4. 分析截止时间和窗口说明“最近7个日增量”。
5. 历史不足、无可比平台和请求失败状态。

V1不展示预测增长率，不在前端计算日增量或移动平均。只有未来新增明确模型后，才可展示对应增长率。

ECharts必须在数据更新后渲染，窗口变化时调用`resize()`，组件卸载时调用`dispose()`。

## 13. 测试要求

### 13.1 Calculator

- 8个累计点正确生成7个日增量。
- 7日增量平均值正确。
- 最新累计值加预测增量得到正确预测值。
- ROUND_HALF_UP和Decimal精度。
- 空数据、单点、少于8点、日期缺口。
- 零值、负值、异常数值和累计回落。
- `Moving Average V1.0`版本传递。

### 13.2 Repository

- 保存和按预测批次替换。
- 单剧最新、历史和趋势排序。
- drama外键、唯一约束、日期和非负预测值CHECK。
- revision as-of查询不得读未来revision。
- 同日多snapshot只取最后有效值。
- 不产生N+1，不commit、不rollback。

### 13.3 Service

- 正常读取→准备输入→Calculator→保存的完整流程。
- 历史不足返回`INSUFFICIENT_HISTORY`且不保存。
- Calculator、Repository、OperationLog失败整体rollback。
- 同一日期重复计算不产生重复结果。
- 客户端无法覆盖指标、窗口、算法版本和目标日期。

### 13.4 API与Dashboard

- 401、USER读取成功、USER计算403、ADMIN计算成功。
- 参数校验、静态`/trend`路由优先、ResponseModel和ErrorResponse。
- Dashboard历史/预测序列、空数据、失败提示、权限按钮。
- TypeScript、ECharts resize和dispose。

## 14. 实现顺序与Migration影响

V2冻结后按以下顺序实现：

1. **V010 Migration**：新增`prediction_results`，不含scope、`input_window`和`predicted_increment`字段。
2. **Prediction ORM**：新增Model和metadata/约束测试，不修改快照ORM。
3. **Prediction Calculator**：实现纯移动平均增量预测和单元测试。
4. **Prediction Repository**：实现输入读取和结果持久化测试。
5. **Prediction Service**：实现业务编排、日志和事务测试。
6. **Prediction API**：实现Schema、Router、Dependency、API测试。
7. **Prediction Dashboard**：实现Client、类型、页面、路由入口、构建验证。

每一步单独提交，禁止`git add .`，不得夹带backend、database、backup、`.reasonix`、批量导入或其他未完成修改。

## 15. V2最终结论

- V1目标：下一日累计播放量。
- V1输入：连续8个累计日点，差分为7个日增量。
- V1模型：`Moving Average V1.0`。
- V1结果：`latest_play_count + predicted_increment`。
- V1结果归属：仅`drama_id`，不保存scope字段。
- V1追溯：保存`analysis_as_of`，按revision `changed_at`回溯。
- V1数据库：实现阶段新增V010和一张`prediction_results`表。

设计V2完成后，**允许进入V010 Migration阶段**，但前提是V010严格遵循本文字段、约束和无scope设计，不得恢复原始累计值直接平均的算法。
