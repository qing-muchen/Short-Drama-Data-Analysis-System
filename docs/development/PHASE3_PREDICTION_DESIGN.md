# Phase 3 Prediction Engine Design

> 状态：仅设计，不进入实现阶段。本文将已确认事实、Phase 3 V1设计选择和未来扩展明确分开。

## 1. 设计目标与边界

Phase 3的目标是提供短剧运营趋势辅助分析：

```text
历史运营观测
    ↓
趋势整理
    ↓
移动平均预测
    ↓
未来运营指标辅助判断
```

预测对象是运营指标趋势，不是投资预测、收益预测或短剧成功概率预测。预测结果应帮助运营人员判断播放趋势变化、安排复盘和数据采集，而不应被解释为商业收益承诺。

V1只预测`play_count`，采用默认窗口为7个有效观测点的简单移动平均。模型保持确定、可解释、可复算，不引入机器学习训练、外部模型服务或置信度伪精度。

## 2. 当前系统架构影响分析

### 2.1 已确认事实

- 数据库迁移链当前为V001—V009，V009是Data Quality表迁移。
- 运营事实已经由`drama_metric_snapshots`和`drama_metric_snapshot_revisions`保存。
- `drama_metric_snapshots`是短剧—平台—观测时刻的稳定槽位，`current_revision_id`指向当前修订。
- `drama_metric_snapshot_revisions`保存不可变修订链，包含`play_count`、`like_count`、`comment_count`、`favorite_count`、`share_count`等指标。
- 数据库实际时间字段是`snapshot_time`，不是`snapshot_date`；日粒度输入必须由Repository按业务时区转换和聚合。
- 现有Analytics查询按`snapshot_time <= analysis_as_of`截断槽位，但读取的是当前`current_revision_id`。它适合当前分析，不等同于“修订发生时点”的历史重建。
- Phase 1和Phase 2的结果表均保存算法/规则版本及作用域信息，但没有预测结果表。
- 当前前后端边界是`Router → Service → Repository → ORM`，计算核心放在`backend/analytics`，Repository不计算、不提交事务。

### 2.2 影响与不影响

Phase 3只新增预测结果和预测模块，不修改已有运营事实表，不重复建立播放量事实表，不改变AnalyticsService现有评分和Dashboard逻辑。预测模块通过只读输入适配器读取快照历史，通过独立Calculator计算，再由PredictionService持久化结果。

Phase 1综合评分仍读取自己的Analytics/Score链路，Phase 2质量评分仍使用自己的规则与评分链路。预测失败不应阻断已有评分和数据质量展示。

### 2.3 事实、选择与扩展总览

| 类别 | 内容 |
|---|---|
| 已确认事实 | V001—V009迁移存在；快照与不可变revision已保存运营指标；当前字段为`snapshot_time`；现有API使用JWT、ResponseModel和分层架构 |
| V1设计选择 | 新增单一结果表；`PLAY_COUNT`；`ALL/0`；连续7个日聚合点；单步预测；`Moving Average V1.0` |
| 未来扩展 | 平台作用域、点赞/评论/互动率、指数平滑、多步预测、校准后的区间预测和模型元数据 |

## 3. 数据库设计方案

### 3.1 设计选择

**设计选择：**新增一张`prediction_results`结果表，保留每次预测的输入窗口、生成时点、目标日期和算法版本。

**不重复保存：**`drama_name`、`platform_name`、播放量事实、历史快照明细和实际后验值。实际值在未来可继续从快照表读取，避免预测表成为第二个事实表。

### 3.2 `prediction_results`建议字段

| 字段 | 建议类型 | 说明 |
|---|---|---|
| `prediction_id` | `BIGINT UNSIGNED` | 主键，自增 |
| `drama_id` | `BIGINT UNSIGNED` | 外键指向`dramas.drama_id`，RESTRICT |
| `metric_type` | `VARCHAR(32)` | V1固定`PLAY_COUNT` |
| `prediction_date` | `DATE` | 本次预测生成/业务归属日期 |
| `target_date` | `DATE` | 被预测的未来日期，必须晚于`prediction_date` |
| `analysis_as_of` | `DATETIME(6)` | 本次读取历史数据的截止时点，UTC语义 |
| `scope_type` | `VARCHAR(16)` | 预测作用域，V1固定`ALL` |
| `scope_id` | `BIGINT UNSIGNED` | V1固定`0` |
| `input_window` | `SMALLINT UNSIGNED` | 使用的有效观测点数，V1为7 |
| `predicted_value` | `DECIMAL(20,2)` | 预测值，统一保留两位小数 |
| `algorithm_version` | `VARCHAR(64)` | V1为`Moving Average V1.0` |
| `created_at` | `DATETIME(6)` | 创建时间 |
| `updated_at` | `DATETIME(6)` | 更新时间 |

预测结果不是评分结果，因此字段明确采用`scope_type/scope_id`，不沿用`score_scope_*`命名；作用域取值语义仍与前两阶段一致。

### 3.3 主键、外键、唯一约束和索引

建议约束：

- 主键：`prediction_id`。
- 外键：`drama_id → dramas.drama_id`，`ON DELETE RESTRICT ON UPDATE RESTRICT`。
- 作用域CHECK：`scope_type = 'ALL' AND scope_id = 0`。
- 指标CHECK：V1只允许`metric_type = 'PLAY_COUNT'`，未来指标必须通过新Migration扩展。
- 窗口CHECK：`input_window > 0 AND input_window <= 30`，V1 Service固定为7。
- 值CHECK：`predicted_value >= 0`。
- 日期CHECK：`target_date > prediction_date`。
- 版本CHECK：`CHAR_LENGTH(TRIM(algorithm_version)) > 0`。
- 唯一约束：`(drama_id, metric_type, prediction_date, target_date, algorithm_version, scope_type, scope_id)`，防止同一模型同一目标重复写入。

建议索引：

- `(drama_id, metric_type, scope_type, scope_id, target_date)`：单剧最新预测和趋势查询。
- `(scope_type, scope_id, metric_type, prediction_date)`：按批次/作用域查询生成记录。
- `(algorithm_version, metric_type, target_date)`：算法版本对比和运维审计。

### 3.4 是否保存confidence、model_version、actual_value

- `confidence`：V1不保存。简单移动平均没有经过统计校准的置信区间，保存一个未经定义的百分比会制造错误精度。未来若引入区间预测，应新增明确的`lower_bound/upper_bound`或独立证据表，并说明计算方法。
- `model_version`：不单独保存。V1用`algorithm_version`作为模型身份，避免两个版本字段不一致。若未来需要训练模型元数据，再通过新表和新Migration扩展。
- `actual_value`：不保存。实际播放量属于快照事实，应由`drama_metric_snapshots`/`revisions`按目标日期回查；预测与实际对比属于分析查询，不应冗余写入预测结果表。
- `analysis_as_of`：必须保存。它决定预测当时能看到哪些历史修订，是历史追溯和重算审计的关键。

### 3.5 第三范式与历史策略

结果表只保存预测结果自身及指向短剧、版本和作用域的键，不保存短剧名称、平台名称或规则文本，符合第三范式。每次算法版本或`analysis_as_of`不同的预测都保留历史记录；同一预测批次重算时由Service按日期、版本、作用域替换，不静默覆盖其他版本。

当前最新迁移为V009，因此实现阶段应新增V010，而不是修改V001—V009。

## 4. 作用域与指标设计

### 4.1 V1作用域：`ALL / 0`

**设计选择：**V1不开放`PLATFORM`、`TAG`等作用域，固定`ALL / 0`。

这里的`ALL`表示对某一短剧的全部有效平台观测进行统一聚合，并不表示把所有短剧合成一条预测曲线；`drama_id`仍是预测目标实体。这样可以复用Phase 1/2已验证的固定作用域约束，也避免在V1同时解决跨平台模型、平台缺失和平台间口径差异。

未来若支持平台预测，必须通过新Migration、API参数和算法版本显式扩展，不能把现有`ALL`结果解释成平台级结果。

### 4.2 V1指标：`PLAY_COUNT`

`metric_type`必须保留，即使V1只有`PLAY_COUNT`，因为它把当前算法输入和未来指标扩展隔离开。后续可通过新版本支持`LIKE_COUNT`、`COMMENT_COUNT`或`ENGAGEMENT_RATE`，但每种指标都必须定义单位、空值处理和聚合规则。

V1不在预测表增加`like_count`等重复列；未来指标以`metric_type`行扩展或通过独立指标定义表管理。

## 5. 预测模型设计

### 5.1 输入准备

输入适配器读取：

1. `drama_metric_snapshots.snapshot_time`作为观测时间。
2. `analysis_as_of`之前的数据，排除未来观测。
3. 对每个snapshot槽位，从不可变revision中选择`changed_at <= analysis_as_of`的最高版本，而不是无条件读取当前`current_revision_id`；选中的revision为`VOID`时排除该槽位。
4. 同一短剧、平台和业务日期有多个snapshot时，取该日最后一个有效观测；随后将全部有效平台的值求和，形成单剧日聚合点。

**待在实现前确认的事实：**当前字段名不能证明`play_count`是“当日新增播放量”还是“截至观测时的累计播放量”。V1应将预测语义冻结为“下一有效观测点的播放量水平预测”。如果业务确认它是累计值，则结果只能解释为下一时点累计播放量水平，不能解释为新增播放量预测。

输入需要按日期升序、去除未来点，并拒绝负数、非有限数和无法转换的值。V1要求连续7个业务日期都有聚合值，不插值、不用0填补缺失日期。基于revision的`changed_at`回溯能够避免截止时点之后的更正反向改变历史预测输入。

### 5.2 移动平均公式

默认窗口为7：

```text
Prediction(t+1) =
    (value(t-6) + value(t-5) + ... + value(t)) / 7
```

Calculator建议使用`Decimal`并采用`ROUND_HALF_UP`保留两位小数，输入序列不做静默截断、不做异常值缩放。V1只生成下一目标日期的单步预测；多步递归预测会放大误差，留作后续明确版本。

### 5.3 数据不足和异常值策略

为保持模型含义稳定，V1采用严格窗口：连续有效日聚合点少于7个时返回`INSUFFICIENT_HISTORY`，不生成预测结果。空序列、单点数据、总点数不足7或最近7日存在日期缺口都属于该原因，而不是用较短窗口冒充7日移动平均。

- 负数、NaN、Infinity或Decimal转换失败：返回稳定的输入异常，不保存结果。
- 值为0：视为合法观测，不单独报错。
- 极大但有限的值：保留并使用Decimal计算；若超出数据库定义范围，Service在写入前返回持久化校验错误，不静默截断。
- 重复日期：由输入Repository按短剧/日期完成确定性聚合；Calculator本身只接收已排序、无重复的纯序列。

### 5.4 版本策略

V1算法版本固定为`Moving Average V1.0`。未来指数平滑、季节性模型或不同窗口必须使用新版本，例如`Exponential Smoothing V2.0`，并保留旧结果。禁止在相同版本字符串下静默改变窗口、聚合方式或异常处理。

## 6. Calculator、Repository与Service设计

### 6.1 Calculator：`backend/analytics/prediction.py`

Calculator只负责纯计算，建议接口：

```text
calculate_moving_average(
    values: Sequence[Decimal],
    *,
    window: int = 7,
    target_date: date,
    algorithm_version: str = "Moving Average V1.0",
) -> PredictionValue
```

返回值包含`target_date`、`input_window`、`predicted_value`、`algorithm_version`。Calculator不读取数据库、不加载ORM、不创建Session、不保存结果，也不判断权限。

### 6.2 `PredictionRepository`

职责：

- 批量保存或按批次替换`prediction_results`。
- 查询单剧最新预测。
- 查询单剧历史预测。
- 查询指定短剧、指标、日期窗口的趋势。

Repository还需要独立的只读输入边界`PredictionInputRepository`，返回传输中立的日聚合历史点，并负责按`changed_at`回溯revision。V1不修改现有AnalyticsRepository的当前态语义，也不建立新的运营事实表。

禁止：调用Calculator、判断等级、推导预测值、commit、rollback、创建Session。

### 6.3 `PredictionService`

业务编排：

```text
读取历史快照
    ↓
按analysis_as_of准备单剧/全平台输入
    ↓
调用PredictionCalculator
    ↓
生成PredictionResult对象
    ↓
按日期、版本、作用域替换结果
    ↓
由Service统一commit或rollback
```

Service固定V1上下文：`metric_type=PLAY_COUNT`、`scope=ALL/0`、`input_window=7`、`algorithm_version=Moving Average V1.0`。它负责事务和业务错误映射，但不把移动平均公式复制到Service。预测结果与一条批量`PREDICTION_CALCULATE`操作日志应在同一事务中提交，任一步骤失败整体回滚。

现有AnalyticsService不需要大规模重构，也不负责预测编排；预测Calculator位于Analytics模块，预测业务流程由独立PredictionService承担。

## 7. API设计

### 7.1 计算

```http
POST /api/v1/predictions/calculate
```

权限：`ADMINISTRATOR`。

建议请求：

```json
{
  "prediction_date": "2026-09-17",
  "drama_id": 123
}
```

`drama_id`为空表示计算全部符合条件的短剧；V1客户端不能提交`algorithm_version`、`metric_type`、`scope_type`、`scope_id`或`input_window`，这些由Service固定。响应返回批次日期、算法版本、scope、生成数量和跳过原因（例如`INSUFFICIENT_HISTORY`）。

### 7.2 单剧预测

```http
GET /api/v1/predictions/{drama_id}
```

权限：登录用户。返回该短剧最新的`PLAY_COUNT`预测及版本、目标日期、输入窗口和预测值。不存在时返回统一404。

### 7.3 趋势

```http
GET /api/v1/predictions/trend
```

权限：登录用户。静态路径必须注册在`/{drama_id}`之前。建议参数：`drama_id`、可选`start_date`、`end_date`、`limit`。响应返回历史预测记录，按`target_date`稳定升序，供前端绘制历史/预测对比。

### 7.4 响应边界

继续使用`ResponseModel[T]`和`ErrorResponse`。Router只负责参数校验、权限、Service调用和DTO转换，不访问Repository/ORM，不计算移动平均，不补齐缺失日期，不判断预测可信度。

## 8. Dashboard设计

新增`PredictionAnalysis.vue`，建议路径`/predictions`，沿用Vue3、TypeScript、Element Plus和ECharts。

页面展示：

1. 历史播放量与未来预测值折线图，用不同颜色/线型区分历史和预测。
2. 最新预测卡片：预测值、目标日期、`Moving Average V1.0`、窗口7和`analysis_as_of`。
3. 预测上下文：短剧、`PLAY_COUNT`、`ALL/0`、生成日期。
4. 空数据、历史不足和请求失败状态。

前端只消费API结果，不计算平均值、不生成未来日期、不修改算法版本。图表数据变化后更新ECharts，窗口resize时调用`resize()`，卸载时调用`dispose()`。

## 9. 测试方案

### 9.1 Calculator测试

- 7日移动平均公式正确性和两位小数ROUND_HALF_UP。
- 空数据、不足7点、单点数据返回`INSUFFICIENT_HISTORY`。
- 零值、负值、NaN/Infinity、Decimal边界和极大有限值。
- 输入顺序、重复日期预处理后的确定性结果。
- `Moving Average V1.0`版本透传。

### 9.2 Repository测试

- 预测集合保存和批量替换。
- 唯一约束阻止同一批次重复结果。
- 单剧最新预测、历史预测和趋势排序。
- 作用域、算法版本、指标过滤。
- drama外键和日期/数值CHECK约束。
- 输入查询不产生N+1；Repository不commit/rollback。

### 9.3 Service测试

- 正常读取历史→调用Calculator→保存结果完整流程。
- 无历史数据和历史不足时跳过且返回原因。
- Calculator异常、Repository异常和OperationLog异常时整体rollback。
- 同日重复计算替换旧批次，不产生重复结果。
- 固定`PLAY_COUNT`、`ALL/0`、窗口7和算法版本不能被客户端覆盖。

### 9.4 API与Dashboard测试

- API：JWT Bearer、401、USER读取成功、USER计算403、ADMIN计算200。
- API：静态`/trend`路由优先注册、参数范围、错误模型和ResponseModel结构。
- Dashboard：路由注册、请求失败提示、空数据、管理员按钮、TypeScript编译和生产构建。
- ECharts：历史/预测序列渲染、resize和dispose生命周期。

## 10. 迁移与Git计划

当前阶段不创建Migration、不修改数据库、不修改ORM或业务代码。若设计确认，下一实现阶段新增：

```text
database/migrations/V010__create_prediction_results.sql
```

V010必须在隔离MySQL中按V001→V010验证，不修改V001—V009。随后按小步提交：

1. `feat(phase3): add prediction results schema`
2. `feat(phase3): add moving average calculator`
3. `feat(phase3): add prediction repository`
4. `feat(phase3): add prediction service`
5. `feat(phase3): add prediction api`
6. `feat(phase3): add prediction dashboard`

每步使用精确`git add`，不提交Frontend、Dashboard、backup、`.reasonix`或其他未完成修改。

## 11. 架构风险与进入实现前确认项

1. **播放量语义风险：**必须确认是累计值还是日增值，否则“趋势预测”含义会被误读。
2. **快照稀疏风险：**严格7点窗口会产生较多无预测结果，需要在Dashboard清楚显示历史不足，而不是填充假数据。
3. **跨平台聚合风险：**V1固定ALL/0，但必须冻结同日多平台的聚合方式并覆盖测试。
4. **修订追溯风险：**不能直接使用当前`current_revision_id`重建历史；必须按`changed_at <= analysis_as_of`选择当时可见revision。
5. **异常值风险：**移动平均对极端值敏感；V1不静默裁剪，后续可新增异常处理模型版本。
6. **多步预测风险：**V1只做单步，递归多步预测必须作为新算法版本设计。
7. **结果膨胀风险：**全量短剧批量生成需分页读取、批量插入和明确替换边界，避免逐剧N+1。

进入实现前必须确认：播放量业务语义、同日跨平台聚合方式、严格7点窗口策略，以及V010是否只生成单步预测结果。字段命名已冻结为`scope_type/scope_id`。

## 12. 当前结论

- 数据库：当前无变化；实现阶段需要新增V010和`prediction_results`。
- ORM：当前无变化；后续新增PredictionResult映射，不修改快照模型。
- Backend/Frontend：当前无变化；本文仅规定未来模块边界。
- 架构风险：存在但可控，主要集中在指标语义、稀疏数据和跨平台聚合，需要在编码前冻结。
- 是否可以直接实现：**暂不建议直接编码**。先确认第11节的业务口径，再进入V010设计冻结和Calculator实现。
