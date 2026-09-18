# Phase 4 Data Anomaly Detection Design

> 状态：Phase 4设计稿。本阶段只定义架构、数据模型、检测规则和测试方案，不创建Migration、ORM、API或前端代码。

## 1. 背景

系统在前三个阶段已经形成三类基础能力：

- Phase 1 Composite Score：将运营指标转换为可解释的综合评价。
- Phase 2 Data Quality Governance：判断数据是否完整、准确、一致和及时。
- Phase 3 Prediction Module：根据历史累计播放量变化预测下一日累计播放量。

Phase 4补充“当前运营行为是否偏离历史常态”的判断。它面向短剧运营数据发现异常增长、异常下降、互动率偏离和单日指标突变，并将检测结果保存为结构化、可查询、可追溯的异常记录。

Phase 4不是机器学习预测系统，不预测收益、成功概率或投资价值，也不把业务上的高增长自动认定为数据错误。

### 1.1 三个模块的职责边界

| 模块 | 回答的问题 | 典型结果 |
|---|---|---|
| Data Quality | 数据是否可信 | 缺失、格式错误、关联不一致、规则失败 |
| Prediction | 未来趋势如何 | 下一日累计播放量预测 |
| Anomaly Detection | 当前行为是否偏离历史常态 | 异常增长、异常下降、互动率异常、数据突变 |

数据质量结果是异常检测的输入门槛或风险标记，不是异常检测结果；预测结果可以提供对照值，但不能代替历史行为基线。三个模块分别保存各自的事实和结果，避免职责混合。

## 2. 目标与范围

### 2.1 Phase 4 V1目标

```text
历史运营指标 + 当前观测 + 数据质量状态 + 可选预测对照
                        ↓
               Rule-based Detection V1.0
                        ↓
               data_anomaly_records
                        ↓
                 Anomaly API/Dashboard
```

V1实现：

- Drama级异常检测，不增加平台或标签作用域。
- 固定、可解释、可重复测试的规则模型。
- 固定算法版本`Rule-based Detection V1.0`。
- 保存异常发生日期、检测截止时间、实际值、基线值和偏差。
- 支持按日期、类型、严重等级、状态和短剧查询历史异常。

### 2.2 V1不实现

- 在线训练或复杂机器学习异常模型。
- 用户在线编辑检测公式和阈值。
- 自动修复运营数据。
- 自动阻断Analytics、Score或Prediction计算。
- 自动将业务异常转换为Data Quality issue。
- 平台级、标签级或公司级异常结果。

## 3. 异常类型定义

### 3.1 播放量异常增长

类型：`PLAY_COUNT_SPIKE`

输入为Drama级连续累计播放量。Service先计算当前日增量，并准备此前连续7个有效日增量作为基线窗口。Calculator判断当前日增量是否显著高于历史均值。

该结果表示“增长行为异常”，可能是内容爆发、活动投放或数据问题，不直接代表数据错误。

### 3.2 播放量异常下降

类型：`PLAY_COUNT_DROP`

累计播放量本身通常不应下降，因此需要区分：

- 当前日增量仍为非负，但显著低于历史增长水平：作为运营下降异常检测。
- 累计播放量发生负差分：属于累计事实回退的数据质量风险，V1返回`DATA_QUALITY_BLOCKED`并交由Phase 2处理，不生成普通运营下降异常。

### 3.3 互动率异常

类型：`ENGAGEMENT_RATE_ANOMALY`

互动率定义为：

```text
engagement_rate
  = (like_count + comment_count + favorite_count + share_count)
    / play_count
```

Service准备当前互动率和此前连续7个有效日点的互动率。`play_count = 0`时不计算比率，不产生伪造的0值，由Service返回稳定跳过原因`ZERO_PLAY_COUNT`。

互动率高于或低于历史范围都可能触发异常。异常方向通过`deviation_value`的正负和响应中的派生方向表达，不为同一语义额外建立冗余类型。

### 3.4 数据突变

类型：`DATA_MUTATION`

检测播放、点赞、评论、收藏和分享等单日指标变化显著偏离历史基线的情况。V1通过`metric_type`区分具体指标，不为每个指标建立新的异常类型。

数据突变是一种行为异常记录。若同一观测同时命中Data Quality规则，异常记录保留质量风险标识或跳过原因，原始质量问题仍由Phase 2负责。

### 3.5 严重等级

V1固定三档：

- `LOW`：超过提示阈值，需要关注。
- `MEDIUM`：明显偏离基线，建议人工复核。
- `HIGH`：极端偏离或伴随明确数据质量风险，应优先处理。

等级只能由Calculator根据冻结阈值返回，Repository、Router和Frontend不得重新判断。

## 4. 数据库设计

### 4.1 新增表

计划通过V011新增`data_anomaly_records`，不修改V001—V010和已有业务表。

建议字段：

| 字段 | 类型建议 | 约束 | 说明 |
|---|---|---|---|
| `anomaly_id` | `BIGINT UNSIGNED` | PK, AUTO_INCREMENT | 异常记录主键 |
| `drama_id` | `BIGINT UNSIGNED` | NOT NULL, FK | 关联`dramas.drama_id` |
| `metric_type` | `VARCHAR(32)` | NOT NULL | `PLAY_COUNT`等受检指标 |
| `anomaly_type` | `VARCHAR(48)` | NOT NULL | 固定异常类型 |
| `severity` | `VARCHAR(16)` | NOT NULL | `LOW/MEDIUM/HIGH` |
| `anomaly_date` | `DATE` | NOT NULL | 被判定异常的业务日期 |
| `detected_at` | `DATETIME(6)` | NOT NULL | 实际执行检测的UTC时间 |
| `analysis_as_of` | `DATETIME(6)` | NOT NULL | 输入数据和revision的硬截止点 |
| `algorithm_version` | `VARCHAR(64)` | NOT NULL | `Rule-based Detection V1.0` |
| `baseline_value` | `DECIMAL(24,6)` | NOT NULL | 历史窗口基线值 |
| `actual_value` | `DECIMAL(24,6)` | NOT NULL | 当前观测或派生指标值 |
| `deviation_value` | `DECIMAL(24,6)` | NOT NULL | `actual_value - baseline_value` |
| `deviation_score` | `DECIMAL(12,6)` | NULL | 可解释的Z-score；零方差回退时可为空 |
| `status` | `VARCHAR(16)` | NOT NULL | 处置状态 |
| `created_at` | `DATETIME(6)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(6)` | NOT NULL | 更新时间 |

`anomaly_date`是业务异常发生日期，`detected_at`是任务执行时间，两者语义不同，必须同时保留。`analysis_as_of`确保历史检测不会读取截止时间之后产生的revision。

### 4.2 状态设计

V1建议状态：

- `OPEN`：待处理。
- `ACKNOWLEDGED`：已确认并进入跟进。
- `RESOLVED`：已完成处理。
- `IGNORED`：确认无需处理。

状态只表示运营处置生命周期，不改变算法检测事实。重新检测不能静默覆盖人工已维护的状态。

### 4.3 主外键与约束

- 主键：`anomaly_id`。
- 外键：`drama_id → dramas.drama_id`，`ON DELETE RESTRICT ON UPDATE RESTRICT`。
- 唯一约束建议：

```text
(drama_id, metric_type, anomaly_type, anomaly_date, algorithm_version)
```

该约束保证相同算法对同一Drama、指标、异常类型和业务日重复检测时可以幂等更新，而不是产生重复记录。重算命中已有身份时更新检测数值和`analysis_as_of`，但保留非`OPEN`的人工处置状态；未再次命中的旧记录是否清理只限仍为`OPEN`且属于同一检测日期和算法版本的自动记录。

CHECK约束建议：

- `metric_type`、`anomaly_type`和`algorithm_version`去除空白后非空。
- `severity IN ('LOW', 'MEDIUM', 'HIGH')`。
- `status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'IGNORED')`。
- `baseline_value >= 0`、`actual_value >= 0`。
- `deviation_value = actual_value - baseline_value`由Service和测试保证；MySQL DECIMAL表达式CHECK是否采用需在V011验证阶段确认。

`deviation_value`虽然可由两个数相减得到，但保存它有利于固定当次算法输出和历史审计；不保存Drama名称、平台名称或完整输入窗口。

### 4.4 索引设计

- `(drama_id, anomaly_date DESC, anomaly_id DESC)`：单剧历史查询。
- `(anomaly_date DESC, severity, status)`：全局异常列表和筛选。
- `(anomaly_type, anomaly_date DESC)`：异常类型趋势。
- `(status, severity, detected_at DESC)`：待处理严重异常查询。

避免为低选择性的单列`severity`或`status`重复建立无效索引。

### 4.5 第三范式与不保存内容

`data_anomaly_records`只保存异常检测结果和必要追溯字段，不保存：

- `drama_name`、`platform_name`。
- 历史日点数组或快照JSON副本。
- 当前用户姓名等操作人员信息；操作审计由`operation_logs`负责。
- 预测结果的冗余副本；需要时通过Service按ID/日期查询。
- Data Quality结果详情；质量记录仍归Phase 2表管理。

V1不增加`scope_type/scope_id`。异常结果天然属于`drama_id`，全部有效平台聚合是输入过程。未来平台级检测应通过新Migration显式设计平台外键。

## 5. 算法设计

### 5.1 选择Rule-based Detection V1.0的原因

V1采用“滚动历史基线 + Z-score + 确定性回退阈值”，而不是复杂机器学习：

- 规则可解释，可向运营人员说明触发原因。
- 对当前有限历史数据要求较低。
- 输出确定，便于边界和回归测试。
- 不引入训练、模型文件、漂移监控或额外依赖。
- 适合软件著作权系统展示，同时保留未来升级算法版本的空间。

### 5.2 输入和窗口

Calculator接收已经由Service校验和排序的数据：

- 当前值`actual_value`。
- 此前连续7个有效历史值`baseline_series`。
- 指标类型、检测类型和冻结阈值配置。

Calculator不接收ORM对象，不查询数据库。基线窗口不包含当前日，防止当前异常值稀释自身偏差。

### 5.3 基线和偏差

```text
baseline_mean = mean(previous 7 values)
baseline_std = population_stddev(previous 7 values)
deviation_value = actual_value - baseline_mean

if baseline_std > 0:
    deviation_score = deviation_value / baseline_std
```

使用`Decimal`完成输入转换、均值、偏差和阈值比较，最终持久化值按字段精度使用`ROUND_HALF_UP`。

### 5.4 阈值建议

以下阈值为V1冻结候选，进入Calculator实现前需通过样本回放确认并写入算法常量：

| 严重等级 | Z-score绝对值 |
|---|---|
| LOW | `>= 2.0` |
| MEDIUM | `>= 3.0` |
| HIGH | `>= 4.0` |

方向规则：

- `PLAY_COUNT_SPIKE`：只接受正偏差。
- `PLAY_COUNT_DROP`：只接受负偏差。
- `ENGAGEMENT_RATE_ANOMALY`和`DATA_MUTATION`：正负偏差均可触发。

为避免均值接近0导致比例失真，V1不单独使用增长率作为唯一触发条件。可设置每个指标的最小绝对偏差门槛，必须同时满足Z-score阈值和最小偏差，降低小数值噪声误报。

### 5.5 零方差回退

当历史7日数值完全相同时，标准差为0，Z-score无定义。V1不能除0，也不能将任何微小变化判为无限异常。

回退规则：

- `deviation_score = NULL`。
- 使用该指标冻结的`absolute_threshold`和`relative_threshold`联合判断。
- 基线为0时只使用绝对阈值，不计算相对变化率。

阈值应属于算法版本常量或只读配置，不由API客户端传入，防止相同算法版本产生不同含义。

### 5.6 异常与跳过结果

纯Calculator返回三类结果：

- `ANOMALY`：包含类型、等级、基线、实际值、偏差和可选Z-score。
- `NORMAL`：输入有效但未超过阈值，不保存异常记录。
- `SKIPPED`：历史不足、日期不连续、零播放量、非有限值或质量不可用，返回稳定原因。

建议跳过原因：`NO_HISTORY`、`INSUFFICIENT_HISTORY`、`DATE_GAP`、`ZERO_PLAY_COUNT`、`INVALID_METRIC`、`DATA_QUALITY_BLOCKED`。

### 5.7 算法版本

V1固定：

```text
Rule-based Detection V1.0
```

未来调整窗口、阈值、标准差算法或异常定义时必须升级为新的`algorithm_version`，不能静默改变V1历史语义。

## 6. Backend架构

### 6.1 分层

```text
Anomaly Router
    ↓
AnomalyService
    ↓
AnalyticsService / PredictionService / DataQualityService
    ↓
AnomalyCalculator
    ↓
AnomalyRepository
    ↓
data_anomaly_records
```

现有服务只提供输入和状态，不能反向依赖AnomalyService，从而避免循环依赖。

### 6.2 AnomalyCalculator

文件：`backend/analytics/anomaly.py`

职责：

- 计算历史均值、标准差和偏差。
- 应用异常类型方向与阈值。
- 判断严重等级。
- 返回确定性的检测结果。

禁止：查询数据库、读取快照、调用Service、创建ORM、管理事务或保存记录。

### 6.3 AnomalyRepository

文件：`backend/repositories/anomaly_repository.py`

计划接口：

- `replace_detection_records()`：按异常日期、算法版本和Drama范围替换本次检测结果。
- `paginate_anomalies()`：按日期、类型、等级、状态、Drama分页查询。
- `get_by_drama()`：查询单剧异常历史。
- `get_by_id()`：查询异常详情。
- `update_status()`：更新处置状态并`flush`。
- `get_summary()`：聚合异常数量、等级分布、趋势和短剧排行。

Repository只执行ORM查询、`add/add_all/delete/flush`，不计算异常，不调用其他Service，不创建Session，不`commit/rollback`。

### 6.4 AnomalyService

文件：`backend/services/anomaly_service.py`

职责：

1. 创建统一的检测上下文和`analysis_as_of`。
2. 通过AnalyticsService获取历史运营指标。
3. 通过DataQualityService获取同一截止点的数据可信状态。
4. 在需要时通过PredictionService获取已保存的预测对照，不触发新的预测计算。
5. 构造连续历史窗口并执行资格检查。
6. 调用AnomalyCalculator。
7. 将`ANOMALY`结果转换为异常记录并批量替换。
8. 记录一次`ANOMALY_DETECT`操作日志。
9. 统一提交或回滚事务。

Service可以组合多个模块的公开查询接口，但不能复制Composite Score、Data Quality、Prediction或异常算法。

### 6.5 与现有模块关系

#### AnalyticsService

提供按`analysis_as_of`可见的历史指标和平台聚合结果。Phase 4不重新建立运营事实表，不直接复制Analytics查询逻辑。

#### DataQualityService

提供当前质量评分或规则结果：

- 确定性ERROR或关键规则失败：该指标跳过检测，记为`DATA_QUALITY_BLOCKED`。
- WARNING：允许检测，但在Service返回摘要中记录质量风险。
- 质量数据不可用：采用明确策略跳过或标记，不默认视为“可信”。

V1质量结果只影响检测资格和说明，不自动关闭、删除或降级已保存异常。

#### PredictionService

提供已保存的最新预测结果，用于展示或作为辅助对照。V1主检测基线仍来自历史真实指标，不能以预测值替代真实历史均值。AnomalyService不得调用PredictionService重新计算预测，避免跨模块事务耦合。

### 6.6 Revision和时间语义

所有输入必须冻结到同一个`analysis_as_of`：

- `snapshot_time <= analysis_as_of`。
- revision满足`changed_at <= analysis_as_of`。
- 历史检测不得读取截止点之后产生的修订。
- 业务日期按Asia/Shanghai解释，数据库时间按UTC保存。

### 6.7 事务边界

一次检测事务包含：

```text
替换本次异常记录
    +
写入一次 operation_logs
    +
commit
```

任一持久化或日志失败时整体`rollback`。Repository不提交事务，Router也不控制事务。无异常命中时仍应清理同一检测身份的旧结果并记录一次成功日志，以保证重算语义正确。

## 7. API规划

统一前缀：`/api/v1/anomalies`。

### 7.1 执行检测

```http
POST /api/v1/anomalies/detect
```

权限：`ADMINISTRATOR`。

请求建议：

```json
{
  "analysis_date": "2026-09-19",
  "drama_id": 123
}
```

`drama_id`可选；为空时检测全部符合条件的短剧。客户端不能提交算法版本、窗口、阈值、严重等级或scope。

响应建议包括：`analysis_as_of`、`algorithm_version`、`detected_count`、`normal_count`、`skipped_count`和`skipped_reasons`。

### 7.2 异常列表

```http
GET /api/v1/anomalies
```

权限：已登录USER和ADMINISTRATOR。

查询参数：`start_date`、`end_date`、`anomaly_type`、`severity`、`status`、`drama_id`、`page`、`page_size`。Repository负责稳定排序：`anomaly_date DESC, severity DESC, anomaly_id DESC`；严重等级排序使用显式CASE或独立稳定序值，不能依赖字符串字典序。

### 7.3 单剧异常

```http
GET /api/v1/anomalies/{drama_id}
```

权限：已登录USER和ADMINISTRATOR。

返回指定短剧的分页异常历史。若未来增加`/summary`等静态路径，必须在`/{drama_id}`之前注册。

### 7.4 响应和错误

- 成功沿用`ResponseModel[T]`。
- 错误沿用`ErrorResponse`和现有全局异常处理。
- 匿名访问返回401，普通用户执行检测返回403。
- Router只处理参数、权限、Service调用和Schema转换，不访问Repository、ORM或Calculator。

## 8. Dashboard规划

新增`AnomalyAnalysis.vue`，路由建议为`/anomalies`，Dashboard只增加入口，不自动触发检测。

页面模块：

1. **异常概览卡**：异常总数、未处理数、高严重等级数量、涉及短剧数。
2. **严重等级分布**：LOW/MEDIUM/HIGH数量。
3. **异常趋势图**：按日期展示异常数量和类型变化。
4. **异常短剧排行**：按异常次数或高严重等级数量排序。
5. **异常列表与详情**：展示短剧、指标、类型、等级、异常日期、基线、实际值、偏差、算法版本和状态。
6. **管理员检测按钮**：调用`POST /detect`；普通用户隐藏。

前端禁止重新计算均值、Z-score、严重等级或异常类型。所有判断来自API。页面必须处理loading、error、empty和success状态，ECharts按现有规范执行resize和dispose。

## 9. 测试方案

### 9.1 Calculator测试

- 正常稳定数据返回`NORMAL`。
- 极端增长触发`PLAY_COUNT_SPIKE`。
- 极端下降触发`PLAY_COUNT_DROP`。
- 互动率高、低方向异常。
- 单日指标突变。
- 无历史、少于7个基线点、日期缺口。
- 阈值等于边界和边界前后值。
- 历史标准差为0的回退规则。
- 基线为0、播放量为0、负数和非有限数值。
- Decimal精度、ROUND_HALF_UP和结果确定性。
- 算法版本固定，输入顺序校验。

### 9.2 Repository测试

- 保存、批量替换和空结果清理。
- 唯一约束和Drama外键。
- 按日期、类型、等级、状态和Drama过滤。
- 稳定排序和分页。
- 单剧历史、详情和聚合统计。
- 状态更新。
- 空数据返回。
- 不commit、不rollback、不创建Session、不调用Calculator。

### 9.3 Service测试

- Analytics → Data Quality → Calculator → Repository → OperationLog完整流程。
- 数据质量ERROR阻断，WARNING保留风险说明。
- 历史不足、日期缺口和零播放量跳过。
- 同一`analysis_as_of`和revision过滤。
- 重复检测幂等替换，人工状态不被错误覆盖。
- 无异常时清理旧结果。
- Calculator、Repository和OperationLog异常整体回滚。
- 成功只commit一次，失败只rollback一次。
- Prediction只作查询对照，不触发重新预测。
- Service不复制检测公式、不直接执行SQL。

### 9.4 API测试

- OpenAPI路径和JWT Bearer声明。
- 匿名401、USER查询成功、USER检测403、ADMIN检测成功。
- 日期、Drama ID、分页和枚举参数校验。
- 禁止客户端提交算法版本、窗口和阈值。
- Service调用参数正确。
- 统一ResponseModel和ErrorResponse。
- 静态路径注册优先级。
- Router不访问Repository、ORM或Calculator。

### 9.5 Dashboard验证

- TypeScript类型检查：`vue-tsc --noEmit`。
- 生产构建：`npm run build`。
- 空数据、请求失败、加载和成功状态。
- 管理员按钮显示及普通用户隐藏。
- 图表数据全部来自API，resize和dispose正确。

## 10. Migration规划

### 10.1 迁移序列

当前正式迁移序列为V001—V010。Phase 4实现阶段计划新增：

```text
database/migrations/V011__create_data_anomaly_records.sql
```

V011只新增`data_anomaly_records`，不修改V001—V010，不修改`dramas`、snapshot、Data Quality、Score或Prediction表结构。

### 10.2 数据库规范

V011应遵循现有MySQL 8.x规范：

- `ENGINE=InnoDB`。
- `DEFAULT CHARSET=utf8mb4`。
- `COLLATE=utf8mb4_0900_ai_ci`。
- `BIGINT UNSIGNED`主键和外键。
- `DATETIME(6)` UTC时间。
- 外键`ON DELETE RESTRICT ON UPDATE RESTRICT`。
- 明确命名的UNIQUE、CHECK和INDEX约束。
- `created_at/updated_at`沿用项目统一默认值和更新时间规则。

### 10.3 实现前验证

进入V011前需要冻结：

1. `baseline_value/actual_value/deviation_value`的DECIMAL范围。
2. 严重等级和处置状态枚举。
3. 唯一约束身份是否满足重算和人工状态保留需求。
4. 零方差回退阈值和每个指标的最小绝对偏差。
5. Data Quality阻断规则与WARNING传播方式。

随后按以下顺序实现并分别提交：

1. V011 Migration + ORM +数据库约束测试。
2. Anomaly Calculator +纯计算测试。
3. Anomaly Repository +数据访问测试。
4. Anomaly Service +事务测试。
5. Anomaly API +权限/OpenAPI测试。
6. Anomaly Dashboard +TypeScript/生产构建验证。

## 11. 最终设计结论

- Phase 4独立回答“当前数据行为是否异常”，不替代Data Quality或Prediction。
- V1采用`Rule-based Detection V1.0`，使用连续历史基线、Z-score和零方差确定性回退。
- 异常结果以Drama级结构化记录保存，支持历史追溯、分页、状态和严重等级管理。
- `analysis_as_of`冻结快照与revision可见性，算法版本冻结检测语义。
- V1不会自动阻断现有Analytics、Score和Prediction流程。
- 设计完成后仍需进行架构审查并冻结阈值与唯一性语义，方可进入V011实现阶段。
