# Phase 4 Anomaly Detection Architecture Review

> 审查范围：仅审查`PHASE4_ANOMALY_DETECTION_DESIGN.md`，不修改代码、数据库、Migration、ORM、API或Frontend。

## 1. 审查结论摘要

Phase 4总体分层方向正确，已经明确了数据质量、趋势预测和异常检测的业务边界，也采用了适合当前数据规模的可解释规则模型。但设计还不能直接进入V011实现，主要原因是：

1. 异常检测的最小播放量门槛和零方差回退阈值尚未冻结。
2. 累计播放量回退、运营下降和数据缺失之间需要更严格的结果优先级。
3. `analysis_as_of`虽然已设计，但重算唯一性会覆盖历史结果，存在追溯风险。
4. 异常证据保存不足，无法仅凭当前字段完整解释当次阈值和基线计算。
5. Data QualityService当前以全局评分为主，不能直接作为单指标阻断依据。
6. 状态字段已有生命周期设计，但API没有状态更新接口，职责尚未闭合。

结论：**有条件通过设计审查，不允许立即创建V011；完成本审查中的必须修改项并冻结字段、阈值、重算和状态策略后，方可进入实现阶段。**

## 2. 设计通过项

### 2.1 模块边界通过

当前设计对三类能力的定位清晰：

| 模块 | 责任 | 审查结论 |
|---|---|---|
| Data Quality | 判断数据完整、准确、一致、及时，回答“数据是否可信” | 通过 |
| Prediction | 基于历史数据预测未来趋势，回答“未来如何变化” | 通过 |
| Anomaly | 判断当前行为是否偏离历史常态 | 通过 |

设计没有把预测值直接当作异常结论，也没有把异常结果回写为质量问题。以历史真实指标作为主要基线、Prediction只作为可选展示对照，这个边界是正确的。

### 2.2 分层架构通过

设计保持：

```text
Router → AnomalyService → AnomalyRepository → ORM
                         ↘ AnomalyCalculator
```

Calculator只处理已准备好的数值序列；Repository只负责持久化和查询；Service负责数据获取、资格检查、事务和日志，符合现有项目的分层风格。Repository不计算、不创建Session、不提交事务的约束应保留。

### 2.3 版本化和时间截点通过

固定`Rule-based Detection V1.0`并要求`analysis_as_of`过滤snapshot和revision，能够避免当前修订污染历史检测。这与Phase 3的历史追溯原则一致，也是异常结果具有软件系统审计价值的基础。

### 2.4 数据库范式方向通过

`data_anomaly_records`只保存`drama_id`外键和检测结果，不保存`drama_name`、`platform_name`或快照数组，符合第三范式和事实数据与派生结果分离的原则。V1不增加平台scope，也避免了过早扩展。

### 2.5 V1规则模型通过

滚动历史基线、Z-score和零方差回退比机器学习模型更容易解释、测试和审计，适合当前历史数据量及软件著作权展示目标。V1不引入训练、模型文件或自动调参，方向正确。

## 3. 发现的问题和风险

### 3.1 播放量累计语义需要在实现契约中再次冻结

`play_count`是累计播放量，不能直接对累计值做异常均值判断。检测输入必须是：

```text
累计播放量日点 → 相邻差分 → 日增量序列 → 历史基线
```

设计已部分表达这一点，但`PLAY_COUNT_SPIKE`、`PLAY_COUNT_DROP`、`DATA_MUTATION`三个类型仍可能使用不同的“当前值”定义。若没有统一的`actual_value`语义，数据库中的结果无法解释。

必须在Calculator契约中明确：

- `PLAY_COUNT_SPIKE/DROP`的`actual_value`是当前日增量，不是累计总量。
- `DATA_MUTATION`的`actual_value`是指定指标当前日增量或日变化值。
- 互动率异常的`actual_value`是当前日互动率。

### 3.2 运营下降与数据缺失/回退可能混淆

连续累计播放量出现负差分通常表示修订、删除、口径变化或数据错误，不能直接解释为运营下降。设计已经倾向于用`DATA_QUALITY_BLOCKED`阻断，但必须定义优先级：

1. 先检查日期连续性和revision有效性。
2. 发现累计值回退或确定性质量错误时，跳过普通异常检测。
3. 只有非负日增量显著低于历史基线时，才生成`PLAY_COUNT_DROP`。

否则同一输入可能同时产生质量问题和下降异常，运营人员会误以为下降结果可信。

### 3.3 互动率缺少最小播放量门槛

当播放量很小或接近0时，单次点赞、评论或分享会产生极大的比率波动。仅使用：

```text
(like + comment + favorite + share) / play_count
```

会产生大量低样本误报。必须增加V1资格规则：

- `play_count = 0`：跳过，返回`ZERO_PLAY_COUNT`。
- `play_count < MIN_PLAY_COUNT_FOR_ENGAGEMENT`：跳过或标记低置信度，不生成普通互动率异常。
- 门槛必须是算法版本固定常量，不能由客户端提交。

门槛具体数值应在样本回放后冻结，并写入Calculator测试和算法文档。

### 3.4 七个基线点对Z-score偏差敏感

七个样本可以实现V1，但标准差对单个历史异常值敏感，且样本量不足以支持稳定统计推断。这里的Z-score应被描述为“规则偏差分”，不能解释为统计显著性或概率。

建议保留7个点以与Phase 3窗口和系统成本一致，同时增加：

- 至少7个连续有效基线点。
- 当前值不参与基线计算。
- 统一的最小绝对偏差门槛。
- 零方差时使用确定性绝对/相对阈值，不使用无穷Z-score。

若后续需要更稳定的统计模型，应升级算法版本，不在V1隐式改变窗口。

### 3.5 异常类型之间存在重复命中风险

同一个突增日可能同时命中`PLAY_COUNT_SPIKE`和`DATA_MUTATION`；互动率变化也可能由播放量突变引起。当前设计没有明确去重和优先级。

V1建议：

- `DATA_MUTATION`只表示指标级单日突变，不替代播放量方向异常。
- 允许同一业务日保存不同`anomaly_type`，但必须在响应中说明它们是独立信号。
- 若同一指标、同一方向、同一日重复命中完全相同规则，应由Calculator去重。
- 对累计值回退，质量阻断优先，不生成`PLAY_COUNT_DROP`。

### 3.6 异常证据字段不足

当前字段有`baseline_value`、`actual_value`、`deviation_value`和可选`deviation_score`，但无法完整重现：

- 使用了多少历史点。
- 基线标准差是多少。
- 触发阈值是多少。
- 使用了哪一个零方差回退分支。
- 互动率的分子、分母是否满足门槛。

这会降低异常详情的解释能力和历史审计价值。V1至少应增加结构化的不可变证据字段之一：

**推荐方案：**增加`evidence_detail JSON`，仅保存算法输入摘要和阈值元数据，例如`window_size`、`baseline_std`、`threshold_value`、`minimum_play_count`、`fallback_mode`，不保存短剧名称、平台名称或完整快照副本。

如果项目要求完全关系化，则新增`data_anomaly_evidences`明细表，以`anomaly_id`外键保存键值化证据。不能把历史日点数组或业务实体快照冗余写入异常主表。

### 3.7 唯一约束会影响历史追溯

设计中的唯一键：

```text
(drama_id, metric_type, anomaly_type, anomaly_date, algorithm_version)
```

如果同一业务日以新的`analysis_as_of`重算，该键会覆盖旧记录，导致历史检测结果和原始截止时间丢失。仅保存最新结果不满足严格历史追溯要求。

实现前必须二选一：

- **方案A（V1推荐）**：把`analysis_as_of`纳入检测身份唯一键，重复使用同一截止点时幂等，新的截止点产生新的检测快照；查询“当前异常”时取每个业务身份最新快照。
- **方案B**：新增检测批次表，以`detection_run_id`标识一次检测，并让异常记录关联批次；适合未来批量审计，但V1结构更复杂。

若坚持方案A，需增加`SUPERSEDED`或查询层的最新快照语义，避免历史记录和当前列表混淆。

### 3.8 状态字段与API不闭合

设计包含`OPEN/ACKNOWLEDGED/RESOLVED/IGNORED`，Repository也规划了`update_status()`，但API规划没有状态更新接口。这样状态要么只能由数据库直接修改，要么无法完成生命周期闭环。

V1应明确选择：

- 暂不提供状态变更：只保存`OPEN`，删除`update_status()`和处置状态承诺；或
- 增加受权限保护的`PATCH /api/v1/anomalies/{anomaly_id}/status`，并补充Service、API和审计测试。

不能在没有接口和权限的情况下宣称支持完整状态管理。

### 3.9 Data Quality全局评分不能直接阻断单指标

Phase 2的`data_quality_scores`是全局质量评分，不能直接说明某一天的播放量或互动率一定不可用。AnomalyService如果只读取全局等级就阻断所有指标，可能误删有效异常；如果完全忽略规则结果，又会让质量模块失去边界。

必须定义只读质量输入协议：

- 只对与当前指标、业务日期和`analysis_as_of`对应的确定性失败规则执行阻断。
- 全局质量分只作为摘要和风险提示，不单独作为指标阻断条件。
- WARNING允许检测但必须传播质量标记。
- 质量结果不可用时采用显式策略（跳过或允许并标记），不能静默当作可信。

### 3.10 AnalyticsService需要as-of查询能力

设计要求AnomalyService读取历史指标并按revision截止点过滤，但现有AnalyticsService是否已经提供等价的、可传入`analysis_as_of`的只读接口需要在实现前确认。若没有，不能在AnomalyService复制snapshot查询和平台聚合逻辑。

准入条件是新增或复用一个明确的历史指标读取契约，而不是让异常模块绕过AnalyticsService访问ORM。

## 4. 各异常类型审查结论

| 异常类型 | 输入 | V1算法 | 输出 | 审查结论 |
|---|---|---|---|---|
| `PLAY_COUNT_SPIKE` | 当前日非负播放增量、前7日增量 | 当前值高于均值，且满足Z-score与最小绝对偏差 | `actual_value`=当前日增量，正`deviation_value`，等级 | 通过，需冻结门槛和实际值语义 |
| `PLAY_COUNT_DROP` | 当前日非负播放增量、前7日增量 | 当前值低于均值，且满足负向阈值 | `actual_value`=当前日增量，负`deviation_value`，等级 | 有条件通过，负差分必须先被质量阻断 |
| `ENGAGEMENT_RATE_ANOMALY` | 当前互动率、前7日互动率、当前播放量 | 正负方向Z-score或零方差回退 | 当前互动率、偏差和方向 | 有条件通过，必须增加最小播放量门槛 |
| `DATA_MUTATION` | 指标当前日变化、前7日变化 | 单日变化偏离滚动基线 | 指标值、偏差、等级和证据 | 有条件通过，需定义与Spike/Drop去重优先级 |

每类规则都必须在Calculator中具有稳定的输入结构、算法分支、输出字段和解释文本，Router和Frontend不得重新解释。

## 5. 数据库调整建议

### 5.1 必须调整

在V011冻结前：

1. 明确`anomaly_date`字段；仅有`detected_at`不足以表达异常发生日。
2. 将`analysis_as_of`纳入唯一性或引入`detection_run_id`，避免重算覆盖历史。
3. 增加异常证据摘要（推荐`evidence_detail JSON`，或独立证据表）。
4. 冻结`baseline_value`、`actual_value`的业务语义和DECIMAL范围。
5. 明确累计值回退、质量阻断和普通下降异常的存储策略。
6. 处理状态字段与状态更新API的闭环问题。

### 5.2 可以保留

- `drama_id`外键和不保存名称的设计。
- `metric_type`、`anomaly_type`、`severity`、`status`枚举化设计。
- `algorithm_version`用于规则版本追踪。
- `baseline_value`、`actual_value`、`deviation_value`保存当次派生结果。
- Drama级V1结果，不提前增加平台或标签scope。
- RESTRICT外键、UTC时间、InnoDB、utf8mb4和索引分层设计。

### 5.3 rule_id和rule_version判断

V1不需要`rule_id`或独立`rule_version`：当前规则不是用户可编辑规则集，异常类型加`algorithm_version`已经能够标识检测语义。

未来若支持动态阈值、启停规则、规则配置审计，应新增`data_anomaly_rules`及`rule_version/rule_set_version`，并在结果中保存规则版本。不能在V1先加无实际来源的外键或伪版本字段。

## 6. 算法调整建议

### 6.1 必须冻结的参数

- 历史窗口长度（建议7个完整基线点）。
- 最小有效历史点数。
- LOW/MEDIUM/HIGH的Z-score阈值。
- 每个指标的最小绝对偏差。
- 互动率最小播放量门槛。
- 零方差回退公式和阈值。
- 日期缺失、负差分、非有限值处理。
- 多规则同时命中时的去重和优先级。

### 6.2 Z-score与历史均值偏差的选择

建议保留“均值偏差 + Z-score”的组合，而不是二选一：

- 均值和绝对偏差给出稳定、易解释的业务基线。
- Z-score用于考虑历史波动尺度。
- 当标准差为0或样本过少时，回退到绝对/相对阈值。

V1不得将Z-score表述为概率、置信度或机器学习模型输出。若未来改用EWMA、MAD或分位数，应升级算法版本并保留旧结果语义。

## 7. Repository / Service边界审查

### 7.1 Calculator

通过：只计算数值、阈值、方向、等级和证据摘要；不访问数据库和事务。

### 7.2 Repository

通过：只负责记录保存、幂等更新、分页、过滤、状态和统计查询；不读取Analytics、Prediction或Data Quality，不计算异常。

### 7.3 Service

有条件通过：负责数据获取、as-of过滤、质量资格检查、平台聚合、Calculator编排、事务和日志。实现前必须使用AnalyticsService的历史指标契约，并以指标级质量结果而非全局质量分独立判断。

### 7.4 OperationLog

检测批次只记录一次`ANOMALY_DETECT`日志，包含`analysis_as_of`、算法版本、检测数量、正常数量、跳过原因和异常类型摘要，不为每个异常生成一条操作日志。

## 8. API审查

### 8.1 现有规划通过项

- `POST /api/v1/anomalies/detect`仅管理员。
- `GET /api/v1/anomalies`和`GET /api/v1/anomalies/{drama_id}`允许登录用户查询。
- Router不访问Repository、ORM或Calculator。
- 使用统一`ResponseModel[T]`和`ErrorResponse`。

### 8.2 必须补充

1. 检测请求应支持可选的完整`analysis_as_of`时间，而不只接收日期；日期输入必须明确映射到业务日结束时间。
2. 客户端不能提交窗口、阈值、规则版本或严重等级。
3. 列表响应需返回`analysis_as_of`、`algorithm_version`、`baseline_value`、`actual_value`、`deviation_value`和证据摘要，避免详情无法解释。
4. 若保留状态生命周期，增加受保护的状态更新API并记录审计；否则V1只声明`OPEN`。
5. 列表分页必须有稳定排序，异常等级不能依赖字符串字典序。

## 9. Dashboard审查

展示异常数量、严重等级、趋势、短剧排行和详情的方向通过。前端不应重新计算均值、Z-score、严重等级、异常类型或质量阻断。

详情至少展示：异常日期、指标、类型、等级、实际值、基线值、偏差、算法版本、分析截止时间、质量风险标记和证据摘要。若没有证据摘要，页面只能显示结论，无法满足运营复核需求，因此数据库证据调整是Dashboard实现的前置条件。

## 10. 测试方案审查

### 10.1 Calculator必须补充

- 累计播放量差分语义和负差分阻断。
- 互动率最小播放量门槛。
- 七点基线、缺失日期和当前点不参与基线。
- Z-score边界、最小绝对偏差和零方差回退。
- Spike/Drop/Mutation重复命中与优先级。
- 证据摘要确定性、Decimal精度和算法版本传递。

### 10.2 Service必须补充

- `analysis_as_of`过滤snapshot和revision。
- 全局质量分不直接阻断单指标；确定性规则失败才阻断。
- 预测只读查询，不触发重新计算。
- 无效累计回退不生成普通下降异常。
- 重算幂等、历史快照不被覆盖、人工状态保留。
- 无命中时旧OPEN结果清理策略。
- 一次commit、失败整体rollback和一次批量OperationLog。

### 10.3 Repository必须补充

- 唯一键包含`analysis_as_of`或检测批次身份。
- 分页、过滤、稳定排序、状态更新。
- 证据摘要保存和读取。
- 空结果、外键、枚举CHECK和重复检测行为。
- 不创建Session、不commit、不rollback、不调用Calculator。

### 10.4 API必须补充

- 401、USER读取成功、USER检测403、ADMIN检测成功。
- `analysis_as_of`格式和范围校验。
- 客户端禁止覆盖算法参数。
- ResponseModel中异常证据和时间截点字段。
- 状态更新API（若纳入V1）。
- OpenAPI路径、Schema和静态路径优先级。

## 11. 实现准入结论

当前结论：**暂不允许进入V011 Migration。**

允许进入的前置条件：

1. 冻结四种异常的`actual_value`语义和规则优先级。
2. 冻结互动率最小播放量门槛、窗口长度、Z-score/绝对阈值及零方差回退。
3. 决定历史重算采用`analysis_as_of`唯一快照还是`detection_run_id`批次模型，确保历史不被覆盖。
4. 增加可解释证据摘要或证据明细设计。
5. 明确Data Quality的指标级阻断协议，禁止直接使用全局质量分替代规则结果。
6. 确认AnalyticsService提供as-of历史指标读取契约。
7. 闭合状态字段与API权限设计，或明确V1仅保存OPEN。
8. 将上述决定补入V011数据库、Calculator、Service和API测试计划。

完成以上调整后，建议按以下顺序实现并分别提交：

1. V011 Migration、ORM和约束测试。
2. AnomalyCalculator和纯计算测试。
3. AnomalyRepository和数据访问测试。
4. AnomalyService、质量过滤、重算和事务测试。
5. Anomaly API、权限和OpenAPI测试。
6. Anomaly Dashboard、类型检查和生产构建验证。

本审查不否定Phase 4方向；它要求先把可解释性、历史追溯和指标级质量边界冻结，再进入实现阶段。
