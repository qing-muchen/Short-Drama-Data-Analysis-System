# Phase 3 Prediction Architecture Review

> 审查对象：`PHASE3_PREDICTION_DESIGN.md`
> 审查范围：架构与设计，不创建Migration，不修改数据库、ORM、Backend、Frontend或Dashboard。

## 1. 审查结论摘要

原设计的分层、版本化结果、`analysis_as_of`、纯Calculator和独立预测表方向正确，但在进入V010前必须修订两个核心问题：

1. `play_count`已经能够确认是累计播放量，不能直接对最近7个累计值取平均后当作下一日累计值。
2. V1只有短剧整体预测，`drama_id`已经完整标识预测对象；固定且恒为`ALL/0`的scope字段属于过早扩展，建议V1删除。

建议V1算法改为：从连续8个日末累计观测形成7个日增量，对7个日增量计算移动平均，再将预测增量加到最新累计值，得到下一日累计播放量预测。

当前结论：**暂不允许直接创建V010**。应先形成设计修订版并冻结累计值预测公式、跨平台可比集合、scope删除和revision回溯规则。

## 2. 数据语义审查

### 2.1 已确认事实

`drama_metric_snapshot_revisions.play_count`代表**累计播放量（方案A）**，不是时间窗口新增播放量。

证据：

- `PROJECT_MASTER.md`第7.7.4节明确将`play_count`、like/comment/favorite/share定义为跨平台累计指标，并规定Drama Overall先取各平台as-of最新有效快照再求和。
- 第7.7.5节明确规定“累计快照禁止在时间区间内直接求和”，区间新增量必须用结束累计值减去基准累计值。
- 第8.3.5节将累计值下降定义为`CUMULATIVE_REGRESSION`。
- 第10.5.2节明确写明五项指标“均按累计整数语义生成”。
- `backend/analytics/metrics.py`中的`aggregate_raw()`对各平台当前累计值求和。
- `backend/analytics/growth.py`用当前累计值减去前序/基准累计值计算增长，而不是把`play_count`当作当期新增量。

因此本项不是“待确认风险”，而是已确认业务语义。

### 2.2 对原设计的影响

原设计公式：

```text
mean(cumulative_play_count[d-6 ... d])
```

会在正常增长序列中得到低于最新累计值的结果，不能解释为下一日累计播放量预测。例如累计序列`100, 120, ..., 220`的均值必然低于220。

必须改为：

```text
daily_increment[d] = cumulative[d] - cumulative[d-1]

predicted_increment[d+1]
    = mean(last 7 daily increments)

predicted_cumulative[d+1]
    = cumulative[d] + predicted_increment[d+1]
```

V1持久化的`metric_type = PLAY_COUNT`和`predicted_value`应明确表示“下一目标日期的累计播放量预测”。预测增量可以作为Calculator返回的解释字段，但V1不必冗余持久化。

算法版本建议仍使用`Moving Average V1.0`，但版本文档必须冻结“对日增量移动平均、输出下一日累计值”的语义。若坚持直接预测日增量，则`metric_type`必须改为`PLAY_COUNT_DAILY_INCREMENT`，不能继续叫`PLAY_COUNT`。

## 3. 预测输入设计审查

### 3.1 连续窗口

计算7个日增量需要连续8个日末累计点，而不是7个累计点：

```text
8 cumulative daily points
        ↓ difference
7 daily increments
        ↓ moving average
1 next-day prediction
```

日期缺失时不插值、不自动补0、不缩短窗口。任一必需业务日期缺失时返回`INSUFFICIENT_HISTORY`，不生成预测。单点、空数据或少于8个累计日点均属于历史不足。

“连续日”按Asia/Shanghai业务自然日分组；持久化时间仍遵循UTC。历史日期的`analysis_as_of`应取该业务日期结束时刻转换后的UTC，而不是服务器本地时间。

### 3.2 snapshot revision选择

历史预测禁止读取`analysis_as_of`之后才产生的修订。不能无条件沿用`snapshot.current_revision_id`，因为它代表当前revision，会把未来CORRECTION或VOID带回历史输入。

输入Repository必须对每个snapshot槽位：

1. 限制`snapshot_time <= analysis_as_of`。
2. 在revision中限制`changed_at <= analysis_as_of`。
3. 选择该截止时点可见的最高`version_no`。
4. 若该revision为`VOID`，排除该snapshot。
5. 复用当前有效数据质量政策，排除确定不可用的ERROR数据；WARNING可参与但需要传播风险提示。

### 3.3 同日与多平台聚合

同一DramaPlatform一天可能有多次采样。建议先取每个平台该业务日最后一个有效累计快照，再进行计算。

V1跨平台预测必须采用可比平台集合，避免平台上线/下线造成累计总量突跳：

- 每个平台至少需要覆盖用于计算的连续8个业务日。
- 在平台内计算7个日增量。
- 对相同日期的各平台日增量求和，形成Drama Overall日增量。
- 最新累计基线使用同一可比平台集合的日末累计值求和。

如果某平台中途加入、下线或缺失日点，V1应将其排除出本次可比集合并返回样本说明；不能在窗口中途改变平台集合。

累计值下降可能来自真实平台纠正。依据现有规范不应自动截为0，但预测结果需要携带质量提示；如果7日平均增量导致最终累计预测小于0，则输入非法且不得保存。

### 3.4 `analysis_as_of`

`analysis_as_of`是V1必须字段和查询条件，不只是展示字段。它同时约束snapshot、revision和质量证据的可见范围，并用于历史追溯。

原设计保留该字段正确，可以保留。

## 4. `prediction_results`表审查

### 4.1 V1必须字段

| 字段 | 结论 | 说明 |
|---|---|---|
| `prediction_id` | 保留 | `BIGINT UNSIGNED`主键 |
| `drama_id` | 保留 | 预测目标，外键到`dramas` |
| `metric_type` | 保留 | V1固定`PLAY_COUNT`，语义为累计播放量预测 |
| `prediction_date` | 保留 | 预测业务批次日期 |
| `target_date` | 保留 | V1应为`prediction_date + 1 day` |
| `input_window` | 保留 | 值为7，表示7个日增量；底层需要8个累计点 |
| `predicted_value` | 保留 | 下一目标日累计播放量预测，`DECIMAL(20,2)` |
| `algorithm_version` | 保留 | `Moving Average V1.0` |
| `analysis_as_of` | 保留 | 防止未来数据和未来revision进入输入 |
| `created_at` | 保留 | 技术创建时间 |
| `updated_at` | 保留 | 与项目统一时间字段规范一致 |

唯一约束建议调整为：

```text
(drama_id, metric_type, prediction_date, target_date, algorithm_version)
```

索引建议：

- `(drama_id, metric_type, target_date)`：单剧最新和趋势查询。
- `(prediction_date, metric_type, algorithm_version)`：批次替换和审计。
- `(algorithm_version, target_date)`：版本查询。

约束建议：

- `metric_type = 'PLAY_COUNT'`。
- `input_window = 7`或至少`input_window > 0`，其中V1由Service固定7。
- `predicted_value >= 0`。
- `target_date > prediction_date`，Service进一步固定为下一日。
- 算法版本非空。

### 4.2 V1不应增加的字段

- `actual_value`：不增加。实际累计值属于snapshot事实，目标日期到达后查询事实表即可。
- `prediction_error`：不增加。误差是`actual - predicted`派生结果；若未来需要冻结模型评估，应建立独立`prediction_evaluations`，避免把尚未发生的实际结果混入预测记录。
- `confidence`：不增加。简单移动平均V1没有校准的概率或置信区间，存百分比会制造错误精度。
- `model_version`：不增加。`algorithm_version`已经承担模型身份，不能维护两套可能冲突的版本字段。
- `drama_name`、`platform_name`：不增加，均可通过外键查询。

### 4.3 未来扩展字段或结构

- 指数平滑或其他模型使用新的`algorithm_version`。
- 经校准的区间预测可通过`lower_bound/upper_bound`和新Migration增加。
- 预测评估采用独立`prediction_evaluations`表。
- 精确输入血缘采用子表，不把revision ID数组塞入JSON或单列。

## 5. Scope设计审查

### 5.1 结论

V1建议只依赖`drama_id`，删除`scope_type`和`scope_id`。

理由：

- `drama_id`已经明确预测对象。
- V1没有平台级、标签级或全系统级预测API。
- `ALL/0`只是“该短剧所有可比平台”的算法输入说明，不是独立业务实体。
- 每行重复保存常量`ALL/0`不会增加辨识能力，却增加CHECK、唯一键、Repository过滤和API字段。
- 若未来支持平台预测，正确外键很可能是`drama_platform_id`，而不是无类型外键的`scope_id`。

删除固定scope不违反第三范式，反而让V1表意更清晰。算法响应可以用说明字段表达“Drama Overall / comparable platforms”，无需持久化伪扩展字段。

### 5.2 未来平台扩展

平台预测应通过新Migration显式增加`drama_platform_id`或独立平台预测表，并使用新算法版本。不能把V1按全部平台聚合的结果重新解释为平台级结果。

因此，原设计的`scope_type/scope_id`属于**必须修改设计项**。

## 6. Revision追溯方案比较

### 6.1 方案A：保存revision引用

一次预测会使用多个日期、多个平台和多个revision，一个`revision_id`列无法表达全部输入。如果选择方案A，必须增加类似：

```text
prediction_input_revisions
- prediction_id
- snapshot_revision_id
- observation_date
- sequence_no
```

优点：输入血缘精确，可直接证明预测使用了哪些revision。

缺点：数据量显著增加；批量预测会产生大量血缘行；需要新增表、索引和级联策略；还需要记录质量过滤和平台集合才能完全重现。

### 6.2 方案B：只保存`analysis_as_of`

利用revision不可变、`changed_at`和`version_no`，输入查询可重新选择截止时点可见的revision。

优点：结构简单，符合V1展示目标，不在结果表保存多值或JSON引用。

缺点：必须保证所有影响输入的规则均具有as-of语义；当前DataQualityIssue状态、DramaPlatform状态等并非全部版本化时，无法达到审计级完全重放。

### 6.3 推荐

V1采用方案B：保存`analysis_as_of`，不保存单个`revision_id`，也不增加输入revision JSON。实现必须使用正确的as-of revision查询，并保留不可变预测结果。

未来若出现审计级精确血缘要求，再新增`prediction_input_revisions`子表。不能在V1结果表里增加一个含义不完整的`revision_id`。

## 7. Calculator边界审查

`backend/analytics/prediction.py`只接收已经准备好的、按日期排序的累计日点或7个日增量，返回确定性预测结果。

允许职责：

- 校验窗口和数值。
- 从8个连续累计点计算7个日增量，或接收Service已准备的7个日增量。
- 使用`Decimal`和`ROUND_HALF_UP`计算移动平均。
- 返回预测增量、累计预测值、窗口和算法版本的传输中立结果。

禁止职责：

- 查询snapshot、revision、DramaPlatform或质量问题。
- 创建/管理Session。
- commit、rollback或保存ORM。
- 判断JWT权限、生成HTTP响应。

为保持Calculator纯度，推荐传入`latest_cumulative_value`和7个已验证日增量；日期连续性、revision选择和平台可比集合由Service/Input Repository准备并验证。

## 8. Repository与Service边界审查

### 8.1 Repository

建议拆分：

- `PredictionInputRepository`：执行as-of revision选择、有效数据过滤、日末取值和可比平台读取，返回DTO。
- `PredictionRepository`：替换/保存预测结果，查询最新预测、历史预测和预测趋势。

Repository只做查询和持久化，不计算移动平均、不判断算法版本、不commit或rollback。

### 8.2 PredictionService

Service负责：

```text
读取as-of历史数据
    ↓
校验连续日期和可比平台集合
    ↓
准备7个日增量
    ↓
调用PredictionCalculator
    ↓
创建并替换PredictionResult
    ↓
记录一次PREDICTION_CALCULATE日志
    ↓
统一commit / rollback
```

Service固定`PLAY_COUNT`、窗口7、单步目标日期和`Moving Average V1.0`。Repository不计算，Calculator不访问数据库。原设计的分层方向通过。

## 9. API边界审查

### 9.1 POST `/api/v1/predictions/calculate`

权限：仅`ADMINISTRATOR`，设计通过。

建议请求：

```json
{
  "prediction_date": "2026-09-17",
  "drama_id": 123
}
```

`drama_id`可为空，表示计算所有符合条件短剧。客户端不能提交`algorithm_version`、`metric_type`、窗口、`target_date`或scope。

响应建议包含：预测日期、目标日期、算法版本、窗口、成功数量、跳过数量和按原因聚合的`skipped_reasons`。

### 9.2 GET `/api/v1/predictions/{drama_id}`

权限：USER和ADMINISTRATOR。返回单剧最新预测；无结果返回统一404。可选`prediction_date`只能作为历史定位参数，不能触发重算。

### 9.3 GET `/api/v1/predictions/trend`

权限：USER和ADMINISTRATOR。参数建议：必填`drama_id`，可选`start_date`、`end_date`和有上限的`limit`。

响应应区分：

- `historical`: 实际累计播放量序列。
- `predictions`: 已持久化预测序列。
- `algorithm_version`、`input_window`、`analysis_as_of`。

静态`/trend`必须在`/{drama_id}`之前注册。三个接口继续使用`ResponseModel[T]`和`ErrorResponse`。Router只校验、鉴权、调用Service和转换响应。

API总体方向通过，但原设计应删除scope相关请求/响应字段，并明确累计值语义。

## 10. Dashboard审查

`PredictionAnalysis.vue`只展示API返回数据，禁止在前端计算移动平均、日增量、累计预测、目标日期或版本。

建议展示：

1. 历史累计播放量实线。
2. 下一目标日期累计预测点或虚线。
3. 算法版本`Moving Average V1.0`。
4. 窗口“最近7个日增量”。
5. `analysis_as_of`和预测目标日期。
6. 历史不足、被质量规则排除和无可比平台集合等空状态。

ECharts必须处理resize和dispose。管理员显示计算按钮，普通用户只查看。该边界可以保留。

## 11. 测试审查

原测试规划基本完整，但应补充：

- 8个累计点形成7个日增量并得到正确累计预测。
- 直接对累计值取平均的错误实现保护测试。
- 日期缺口、跨平台缺点和平台集合变化。
- 累计值下降、负平均增量及预测值下界。
- `analysis_as_of`之后的CORRECTION/VOID不得进入历史输入。
- `analysis_as_of`之前的最新revision正确生效。
- 同一日多快照只取日末有效值。
- scope字段不存在的ORM/数据库契约。
- `/trend`静态路由优先于`/{drama_id}`。
- Service任一步骤或OperationLog失败整体回滚。

## 12. 必须修改与可以保留

### 12.1 必须修改设计项

1. 将`play_count`从“待确认”改为已确认累计语义。
2. 移动平均输入改为7个日增量；输入需要连续8个日末累计点。
3. `predicted_value`明确为下一日累计播放量预测。
4. 删除V1的`scope_type/scope_id`，只以`drama_id`标识预测对象。
5. 输入查询必须按`changed_at <= analysis_as_of`选择当时可见revision，不能直接读当前revision。
6. 冻结同日末值和跨平台可比集合聚合规则。
7. 更新唯一约束、索引、API响应和测试方案以移除scope。

### 12.2 可以保留设计项

- 独立`prediction_results`结果表。
- `metric_type`、`algorithm_version`和`analysis_as_of`。
- V1单步预测与版本化算法。
- 不保存`actual_value`、`prediction_error`和未经校准的`confidence`。
- Calculator置于`backend/analytics/prediction.py`。
- Router → Service → Repository → ORM分层。
- PredictionRepository不计算、不commit。
- 前端只展示API结果。
- V010新增迁移且不修改V001—V009。

## 13. Git与实施计划

设计修订确认后，按以下顺序实施并精确提交：

1. **V010 Migration**

   文件：`database/migrations/V010__create_prediction_results.sql`、数据库约束测试、数据库设计文档。

   提交建议：`feat(phase3): add prediction results schema`

2. **ORM**

   文件：`backend/models/prediction.py`、`models/__init__.py`、Drama关系（若设计确认需要）、ORM metadata测试。

   提交建议：`feat(phase3): add prediction orm model`

3. **Calculator**

   文件：`backend/analytics/prediction.py`、纯计算测试、算法文档。

   提交建议：`feat(phase3): add moving average prediction calculator`

4. **Repository**

   文件：PredictionInputRepository、PredictionRepository、注册、Repository测试和文档。

   提交建议：`feat(phase3): add prediction repositories`

5. **Service**

   文件：PredictionService、注册、事务/回滚测试和文档。

   提交建议：`feat(phase3): add prediction service`

6. **API**

   文件：Prediction Schema、Router、Dependency、路由注册、API/OpenAPI测试和文档。

   提交建议：`feat(phase3): add prediction api`

7. **Dashboard**

   文件：API Client、TypeScript类型、PredictionAnalysis页面、路由/Dashboard入口、前端文档。

   提交建议：`feat(phase3): add prediction dashboard`

每一步禁止`git add .`，不得夹带backend/frontend无关修改、backup、`.reasonix`、批量导入或文档生成文件。

## 14. 最终决定

### 通过项

- 新增独立预测结果表的方向。
- 保留`metric_type`、`algorithm_version`、`analysis_as_of`。
- Calculator、Service、Repository和Router分层。
- 单步、可解释、无外部模型依赖的V1目标。
- API权限和Dashboard只展示原则。

### 风险项

- 累计指标若直接取均值会产生业务错误。
- 平台集合变化和日期缺失会破坏序列可比性。
- current revision会向历史预测泄漏未来修订。
- `analysis_as_of`方案不能单独提供审计级完整输入血缘。
- 数据质量状态若不具备as-of版本，完整复放仍有限制。

### 是否允许进入V010 Migration阶段

**当前不允许。**

进入V010前必须先修订并确认：

1. 7个日增量/8个累计日点的算法输入。
2. 下一日累计播放量的`predicted_value`语义。
3. 删除`scope_type/scope_id`。
4. as-of revision查询规则。
5. 跨平台可比集合规则。

上述五项冻结后，可以进入V010 Migration设计与实现。
