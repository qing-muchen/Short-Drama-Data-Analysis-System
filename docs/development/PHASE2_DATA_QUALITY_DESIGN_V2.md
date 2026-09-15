# Phase 2 数据质量治理最终设计方案 V2

> 文档状态：最终设计依据。当前仅完成架构设计，不创建数据库、不执行Migration、不实现后端或前端代码。

## 1. 设计背景

### 1.1 建设目标

Phase 2在现有数据采集与导入能力之上建立数据质量治理闭环，使系统能够回答三个不同层次的问题：

1. 系统采用了哪些质量规则，规则内容和版本是什么。
2. 每条规则在一次评估中检查了多少数据、通过多少、失败多少、得到多少分。
3. 全部规则汇总后，整体数据质量及四个维度分别处于什么水平。

业务链路为：

```text
数据采集/Import
  ↓
数据清洗与基础校验
  ↓
Quality Rule Execute
  ↓
Rule Result
  ↓
Quality Score
  ↓
Quality Dashboard
  ↓
数据治理决策
```

这使系统从错误记录工具升级为具备规则管理、检测证据、指标计算、历史评价和分析展示能力的数据治理平台。

### 1.2 为什么采用三层模型

V2采用三层数据模型：

```text
data_quality_rules
        ↓ 1:N
data_quality_rule_results
        N:1 ↓
data_quality_scores
```

- `data_quality_rules`是规则定义层，保存规则含义、版本、维度、权重和受控配置。
- `data_quality_rule_results`是规则执行事实层，保存某次评分中每条规则的适用量、通过量、失败量和标准化分数。
- `data_quality_scores`是综合评价层，保存评分日期、四维得分、总分、等级、算法版本和规则集身份。

三层分离的原因：

- 避免把规则级重复数据塞入评分表JSON，符合第三范式方向。
- 规则定义只保存一次，执行结果通过外键引用具体规则版本。
- Dashboard可以使用普通SQL查询规则通过率、失败Top规则和历史趋势。
- 总分、维度分和规则分都具有独立且明确的业务含义。
- 规则版本变化不会覆盖历史执行结果。
- 数据库可以约束规则结果与评分、规则版本之间的引用关系。

### 1.3 与现有质量数据的职责边界

| 对象 | 职责 |
|---|---|
| `import_jobs` | 一次导入任务的状态、行数、时间和来源 |
| `import_errors` | 导入阶段的行级/字段级拒绝证据 |
| `data_quality_issues` | 需要持续跟踪和人工处置的数据质量问题 |
| `data_quality_rules` | 可版本化质量规则定义 |
| `data_quality_rule_results` | 一次评估中的单规则执行事实 |
| `data_quality_scores` | 一次评估的四维与综合质量结果 |

规则执行结果不替代Import错误，也不替代问题台账。Import错误回答“本次导入为什么失败”，quality issue回答“当前需要治理什么”，rule result回答“某条规则执行效果如何”，quality score回答“整体质量水平如何”。

## 2. 数据库设计

### 2.1 通用设计原则

- 使用新增SQL Migration，不修改V001—V008文件，不使用Alembic。
- 新表使用MySQL 8.x、InnoDB、`utf8mb4_0900_ai_ci`。
- 主键统一使用`BIGINT UNSIGNED AUTO_INCREMENT`。
- 时间统一使用`DATETIME(6)`，业务评分日使用`DATE`。
- 分数统一使用`DECIMAL(5,2)`，范围0—100。
- 历史规则和评分结果不物理删除。
- 评分结果表不保存操作人员，操作主体由`operation_logs`负责。
- Repository只执行数据库访问和`flush`，不`commit`；事务由Service统一管理。

Phase 2 V1评分作用域固定为：

```text
quality_scope_type = ALL
quality_scope_id   = 0
```

V1不使用多态业务外键。未来扩展DRAMA、PLATFORM或IMPORT_JOB作用域时，应通过新Migration增加明确外键并发布新的评分算法版本。

### 2.2 `data_quality_rules`

#### 2.2.1 表职责

保存不可变的质量规则版本。数据库不保存可直接执行的SQL或Python代码，`evaluator_key`只能映射后端注册表中的白名单计算器。

#### 2.2.2 字段设计

| 字段 | 类型 | 空值/默认 | 说明 |
|---|---|---|---|
| `quality_rule_id` | `BIGINT UNSIGNED` | PK，自增 | 规则版本实体ID |
| `rule_code` | `VARCHAR(64)` | NOT NULL | 跨版本稳定业务编码 |
| `rule_version` | `VARCHAR(32)` | NOT NULL | 单规则版本，例如`1.0` |
| `rule_name` | `VARCHAR(200)` | NOT NULL | 规则展示名称 |
| `dimension` | `VARCHAR(32)` | NOT NULL | 四维归属 |
| `target_entity_type` | `VARCHAR(32)` | NOT NULL | 评估对象类型 |
| `evaluator_key` | `VARCHAR(64)` | NOT NULL | 后端白名单执行器键 |
| `scoring_method` | `VARCHAR(32)` | NOT NULL | `PASS_RATE/BUCKET_AVERAGE` |
| `weight` | `DECIMAL(7,6)` | NOT NULL | 维度内相对权重，`0 < weight <= 1` |
| `severity` | `VARCHAR(16)` | NOT NULL | `INFO/WARNING/ERROR` |
| `configuration` | `JSON` | NOT NULL | 字段、阈值、窗口、分段等参数 |
| `status` | `VARCHAR(16)` | NOT NULL，默认`DRAFT` | `DRAFT/ACTIVE/INACTIVE` |
| `valid_from` | `DATETIME(6)` | NOT NULL | 生效时间 |
| `valid_to` | `DATETIME(6)` | NULL | 失效时间 |
| `description` | `TEXT` | NULL | 规则业务解释 |
| `created_at` | `DATETIME(6)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(6)` | NOT NULL | 更新时间 |

`dimension`取值：

```text
COMPLETENESS
ACCURACY
CONSISTENCY
TIMELINESS
```

`target_entity_type`取值：

```text
DRAMA
DRAMA_PLATFORM
SNAPSHOT
IMPORT_JOB
```

规则只使用`status`表达生命周期，不增加与其含义重复的`enabled`字段。规则禁用即状态变为`INACTIVE`。

#### 2.2.3 主键、索引和约束

- 主键：`PRIMARY KEY (quality_rule_id)`。
- 唯一约束：`UNIQUE (rule_code, rule_version)`。
- 规则加载索引：`(status, dimension, valid_from, valid_to)`。
- 目标规则索引：`(target_entity_type, dimension, status)`。
- 编码状态索引：`(rule_code, status)`。
- 检查`rule_code`、`rule_version`、`rule_name`和`evaluator_key`去空格后非空。
- 检查`dimension`、`target_entity_type`、`scoring_method`、`severity`和`status`取值范围。
- 检查`weight > 0 AND weight <= 1`。
- 检查`valid_to IS NULL OR valid_to > valid_from`。
- MySQL JSON列保证配置是合法JSON；Service还必须使用对应evaluator的Schema校验JSON结构。

同一`rule_code`的有效时间不能重叠。MySQL难以使用通用条件唯一索引表达该规则，由`RuleRepository`查询配合`DataQualityService`事务锁定校验。

#### 2.2.4 更新规则

- DRAFT规则可以修改。
- ACTIVE或曾参与评分的规则版本不得原地修改`dimension`、执行器、计分方法、权重或配置。
- 业务规则变化时创建新的`rule_version`，旧版本转为INACTIVE并保留。
- 规则名称和描述如需修正，也应优先创建新版本，确保历史展示完全稳定。

### 2.3 `data_quality_scores`

#### 2.3.1 表职责

保存一次全局数据质量评价的结果快照。该表是规则执行结果的父记录，也是Quality Dashboard的总览和趋势数据源。

#### 2.3.2 字段设计

| 字段 | 类型 | 空值/默认 | 说明 |
|---|---|---|---|
| `quality_score_id` | `BIGINT UNSIGNED` | PK，自增 | 质量评分ID |
| `score_date` | `DATE` | NOT NULL | 评分业务日期 |
| `quality_scope_type` | `VARCHAR(16)` | NOT NULL，默认`ALL` | V1固定ALL |
| `quality_scope_id` | `BIGINT UNSIGNED` | NOT NULL，默认0 | V1固定0 |
| `analysis_as_of` | `DATETIME(6)` | NOT NULL | 事实数据截止时间 |
| `completeness_score` | `DECIMAL(5,2)` | NOT NULL | 完整性评分 |
| `accuracy_score` | `DECIMAL(5,2)` | NOT NULL | 准确性评分 |
| `consistency_score` | `DECIMAL(5,2)` | NOT NULL | 一致性评分 |
| `timeliness_score` | `DECIMAL(5,2)` | NOT NULL | 及时性评分 |
| `total_score` | `DECIMAL(5,2)` | NOT NULL | 综合质量评分 |
| `quality_grade` | `CHAR(1)` | NOT NULL | `S/A/B/C` |
| `algorithm_version` | `VARCHAR(64)` | NOT NULL | 例如`Quality Score V1.0` |
| `rule_set_version` | `VARCHAR(64)` | NOT NULL | 不可变规则集发布版本 |
| `rule_set_hash` | `CHAR(64)` | NOT NULL | 本次实际规则集合SHA-256 |
| `evaluated_entity_count` | `BIGINT UNSIGNED` | NOT NULL，默认0 | 去重后的覆盖对象数 |
| `open_issue_count` | `BIGINT UNSIGNED` | NOT NULL，默认0 | 截止时间开放问题数快照 |
| `source_watermark` | `JSON` | NULL | 各证据源最大ID/时间水位 |
| `created_at` | `DATETIME(6)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(6)` | NOT NULL | 更新时间 |

规则检查总数、通过总数和失败总数不在score表重复保存，由`data_quality_rule_results`按需聚合。`source_watermark`只保存不能自然关系化的来源水位，不保存规则明细、原始导入行或issue全文。

#### 2.3.3 主键、索引和约束

- 主键：`PRIMARY KEY (quality_score_id)`。
- 业务唯一约束：

```text
UNIQUE (
  score_date,
  algorithm_version,
  rule_set_version,
  rule_set_hash,
  quality_scope_type,
  quality_scope_id
)
```

- 最新/趋势索引：`(quality_scope_type, quality_scope_id, score_date DESC)`。
- 版本趋势索引：`(algorithm_version, rule_set_version, score_date DESC)`。
- 等级日期索引：`(quality_grade, score_date DESC)`。
- 检查V1必须满足`quality_scope_type = 'ALL' AND quality_scope_id = 0`。
- 检查四个维度和`total_score`均在0—100。
- 检查`quality_grade IN ('S', 'A', 'B', 'C')`。
- 检查算法版本和规则集版本去空格后非空。
- 检查`CHAR_LENGTH(rule_set_hash) = 64`。
- 计数字段使用UNSIGNED，并检查非负语义。

综合分和等级由纯计算模块生成。Repository、Service和Router不得重复计算或重新判断等级。

### 2.4 `data_quality_rule_results`

#### 2.4.1 表职责

保存一次质量评分中每个具体规则版本的执行事实。它是规则通过率、失败规则排行和历史解释的权威来源。

#### 2.4.2 字段设计

| 字段 | 类型 | 空值/默认 | 说明 |
|---|---|---|---|
| `quality_rule_result_id` | `BIGINT UNSIGNED` | PK，自增 | 规则结果ID |
| `quality_score_id` | `BIGINT UNSIGNED` | NOT NULL，FK | 所属质量评分 |
| `quality_rule_id` | `BIGINT UNSIGNED` | NOT NULL，FK | 执行的具体规则版本 |
| `result_status` | `VARCHAR(24)` | NOT NULL | `APPLIED/NOT_APPLICABLE` |
| `applicable_count` | `BIGINT UNSIGNED` | NOT NULL，默认0 | 适用检查数 |
| `passed_count` | `BIGINT UNSIGNED` | NOT NULL，默认0 | 通过数 |
| `failed_count` | `BIGINT UNSIGNED` | NOT NULL，默认0 | 失败数 |
| `rule_score` | `DECIMAL(5,2)` | NULL | 标准化规则分，0—100 |
| `not_applicable_reason` | `VARCHAR(255)` | NULL | N/A原因 |
| `evidence_summary` | `VARCHAR(1000)` | NULL | 聚合证据摘要，不复制原始数据 |
| `created_at` | `DATETIME(6)` | NOT NULL | 创建时间 |

#### 2.4.3 外键关系

- `quality_score_id` → `data_quality_scores.quality_score_id`。
  - `ON UPDATE RESTRICT`。
  - `ON DELETE CASCADE`。规则结果完全从属于评分快照，相同身份重算替换父结果时允许原子删除子结果。
- `quality_rule_id` → `data_quality_rules.quality_rule_id`。
  - `ON UPDATE RESTRICT`。
  - `ON DELETE RESTRICT`。被历史结果引用的规则版本不能删除。

#### 2.4.4 索引和约束

- 主键：`PRIMARY KEY (quality_rule_result_id)`。
- 唯一约束：`UNIQUE (quality_score_id, quality_rule_id)`，同一次评分每个规则版本只执行一次。
- 评分明细索引：`(quality_score_id, result_status)`。
- 规则趋势索引：`(quality_rule_id, quality_score_id)`。
- 失败规则索引：`(quality_score_id, failed_count DESC)`。
- 检查`applicable_count = passed_count + failed_count`。
- 检查`rule_score IS NULL OR rule_score BETWEEN 0 AND 100`。
- APPLIED必须满足：
  - `applicable_count > 0`。
  - `rule_score IS NOT NULL`。
  - `not_applicable_reason IS NULL`。
- NOT_APPLICABLE必须满足：
  - 三个计数均为0。
  - `rule_score IS NULL`。
  - `not_applicable_reason`去空格后非空。

规则名称、版本、维度、权重和配置不在结果表重复保存，通过`quality_rule_id`关联不可变规则版本取得。

### 2.5 第三范式与必要的结果持久化

三张表分别以规则ID、规则结果ID和评分ID为主键，非主属性只描述各自主体：

- 规则属性只依赖`quality_rule_id`。
- 单规则执行属性只依赖`quality_rule_result_id`。
- 综合评分属性只依赖`quality_score_id`。

`total_score`和`quality_grade`虽然可以从维度分数推导，但它们是一次算法执行的正式输出，需要与算法版本一起保存，属于结果快照而非主数据冗余。

不应保存：

- Score表中的操作人ID。
- Score表中的规则执行数组JSON。
- Rule Result表中的规则名称、版本、维度、权重或配置副本。
- Import原始错误行和`data_quality_issues`全文副本。
- 可执行SQL、Python表达式或前端公式。

## 3. 规则版本管理

### 3.1 `rule_version`

`rule_version`描述单条规则内容版本，与稳定的`rule_code`共同形成唯一身份：

```text
(rule_code, rule_version)
```

以下任一内容发生变化都必须创建新规则版本：

- 维度归属。
- 评估目标。
- evaluator或计分方法。
- 权重。
- 配置参数、阈值和时间窗口。
- 会改变历史解释的规则业务含义。

历史规则不删除、不覆盖。

### 3.2 `rule_set_version`

`rule_set_version`描述一次发布的不可变规则集合，例如`DQ Rules 1.0`。V1不新增规则集主表，规则集成员由某次评分下的`data_quality_rule_results`精确记录。

规则集发布原则：

- 启用、禁用、增加或移除规则时发布新的`rule_set_version`。
- 改变规则权重或配置时先创建新`rule_version`，再发布新规则集版本。
- 已用于评分的规则集版本名称不得复用到另一套规则集合。
- Phase 2 V1规则由受审查的数据Migration发布，不开放在线规则写接口。

### 3.3 `rule_set_hash`

DataQualityService对本次实际规则集合生成确定性SHA-256：

1. 按`rule_code`、`rule_version`排序。
2. 对每条规则序列化以下字段：规则编码、版本、维度、目标类型、evaluator、计分方法、权重和规范化JSON配置。
3. 使用UTF-8编码连接规范化结果。
4. 计算64字符小写十六进制SHA-256。

相同规则集合必须得到相同hash。hash与`rule_set_version`同时保存：版本用于业务沟通，hash用于技术校验。

### 3.4 历史追溯

历史评分通过以下关系还原：

```text
data_quality_scores
  ├─ algorithm_version
  ├─ rule_set_version
  ├─ rule_set_hash
  ├─ analysis_as_of
  └─ data_quality_rule_results
       └─ data_quality_rules(rule_code + rule_version + configuration)
```

`source_watermark`保存事实来源水位，rule result保存规则执行汇总。由于部分现有主数据不是双时态表，V1保证“已保存结果和执行证据可追溯”，不承诺数据修正后对任意历史日期进行完全一致的事实重放。

### 3.5 重算策略

- 相同日期、算法版本、规则集版本、hash和作用域视为同一评分身份。
- 重算由Service在单一事务中替换父Score和全部Rule Results。
- 不同算法版本、规则集版本或hash可以并存。
- Repository不提交事务。
- 规则结果、综合评分或operation log任一步骤失败时全部回滚。

## 4. 评分模型

### 4.1 规则分标准化

所有规则执行器输出0—100的`rule_score`。

#### PASS_RATE

用于完整性、准确性和多数一致性规则：

```text
Rule Score = 100 × passed_count / applicable_count
```

#### BUCKET_AVERAGE

用于及时性等分段规则：先将每个适用对象映射到0—100分，再计算平均值。`passed_count`表示达到规则配置中`pass_threshold`的对象数，`failed_count`表示未达到阈值的对象数。

规则对当前数据域真正不适用时返回NOT_APPLICABLE；缺失必需数据属于规则失败，不能作为N/A绕过扣分。

### 4.2 维度分数

仅使用`result_status = APPLIED`的规则：

```text
Dimension Score =
  Σ(rule.weight × rule_result.rule_score)
  / Σ(applied rule.weight)
```

- N/A规则及其权重从分母排除。
- 被禁用规则不进入新规则集，但历史结果仍关联旧规则。
- 任一维度没有APPLIED规则时，本次计算返回`INSUFFICIENT_QUALITY_DATA`，不持久化误导性总分。
- 各维度使用`ROUND_HALF_UP`保留两位小数。

### 4.3 四维定义

#### Completeness 30%

衡量分析所需数据是否齐备，包括：

- 短剧必填主数据。
- ONLINE发布关系的上线时间。
- 快照当前revision。
- 非VOID revision的必要运营指标。
- Import任务已处理行覆盖情况。

#### Accuracy 30%

衡量数据是否满足字段、范围和业务语义，包括：

- 累计指标非负。
- 排名大于0或为空。
- 快照时间不在允许范围之外。
- 日期、数值和枚举可正确解析。
- Import窗口中的类型、字段、负值和时间错误。

#### Consistency 25%

衡量跨时间、跨表和业务键的一致性，包括：

- 快照业务键唯一。
- revision链和当前revision归属正确。
- 累计指标无不合理回退。
- 发布状态与上线时间一致。
- 短剧、平台和发布关系引用有效。

#### Timeliness 15%

衡量运营数据更新时效，不评价短剧生命周期，也不预测未来表现。建议按“最新有效快照年龄 / 期望更新间隔”映射：

| 比例 | 分数 |
|---|---:|
| `<= 1` | 100 |
| `> 1`且`<= 2` | 80 |
| `> 2`且`<= 3` | 60 |
| `> 3`且`<= 7` | 40 |
| `> 7` | 20 |
| 无有效快照 | 0 |

### 4.4 综合评分

```text
Quality Score = 0.30 × Completeness
              + 0.30 × Accuracy
              + 0.25 × Consistency
              + 0.15 × Timeliness
```

权重依据：

- 完整性和准确性决定数据能否用于分析，权重最高。
- 一致性直接影响增长与趋势判断。
- 及时性影响决策时效，但不能掩盖错误或缺失数据。

总分使用`ROUND_HALF_UP`保留两位小数，并限制为0—100。

### 4.5 等级划分

| 等级 | 分数范围 |
|---|---|
| S | `>= 90` |
| A | `>= 75`且`< 90` |
| B | `>= 60`且`< 75` |
| C | `< 60` |

调整四维权重、等级边界、标准化方法或N/A策略时必须发布新的`algorithm_version`。

### 4.6 防止重复扣分

每条规则配置必须明确：

- 评估对象。
- 统计时间窗口。
- 适用分母。
- 主证据来源。
- 去重业务键。
- 是否产生持续性quality issue。

同一缺陷不能同时按`import_errors`和`data_quality_issues`重复计入同一规则。`severity`用于治理优先级，不再次乘以扣分；`occurrence_count`用于问题趋势，不直接放大规则失败。

## 5. 数据流程

```text
Import
  ↓
现有解析、字段校验、引用校验、重复检查
  ├─ 失败行 → import_errors
  └─ 有效数据 → 业务表 / drama_metric_snapshots / revisions
                                ↓
QualityEvidenceRepository读取事实和data_quality_issues
                                ↓
data_quality_rules → Quality Rule Execute
                                ↓
data_quality_rule_results
                                ↓
四维聚合 + Quality Score V1.0
                                ↓
data_quality_scores + operation_logs
                                ↓
Data Quality API
                                ↓
Quality Dashboard
```

计算流程：

1. 管理员指定`score_date`。
2. Service生成`analysis_as_of`；当日使用当前时间，历史日期使用指定日期结束时间。
3. RuleRepository加载本次规则集，并验证四个维度覆盖、版本和配置。
4. QualityEvidenceRepository按规则需求批量读取Import、snapshot revision、release和issue事实，避免N+1查询。
5. 纯计算模块执行规则、生成Rule Result、计算维度分、总分和等级。
6. Service构造一个DataQualityScore及对应Rule Result集合。
7. 在同一事务中替换相同身份结果并记录一次`QUALITY_SCORE_CALCULATE`操作日志。
8. API和Dashboard读取持久化结果，不重新计算。

评分计算默认不创建、关闭或修改`data_quality_issues`。自动问题检测与合并应作为独立Quality Check操作，避免“重算评分”产生隐藏副作用。

## 6. 与现有模块关系

### 6.1 Import模块

- 不修改现有解析、校验、暂存、确认和错误定位流程。
- 只读使用`import_jobs`和`import_errors`作为质量证据。
- 不把每个Import Error机械复制成quality issue。
- Import错误保留一次导入上下文，持续性业务缺陷继续由`data_quality_issues`管理。

### 6.2 AnalyticsService

- 不修改AnalyticsService接口、查询或指标算法。
- Data Quality通过自己的Evidence Repository读取质量事实。
- Phase 2 V1质量结果不直接阻断Analytics计算。

### 6.3 ScoreService与Score Dashboard

- 不修改Composite Score计算核心、ScoreRepository、ScoreService或`drama_scores`。
- ScoreService不读取`data_quality_scores`作为Composite Score V1.0资格条件。
- Score Dashboard不增加前端质量扣分或重新计算逻辑。
- Quality Dashboard可以展示数据可信度，但与运营价值评分保持独立。

如果未来需要用质量结果阻断运营评分或生成置信度，必须发布新的Composite Score算法版本并进行单独架构评审，不得静默改变Phase 1结果。

## 7. Service架构

### 7.1 调用结构

```text
Data Quality Router
        ↓
DataQualityService
        ├─ RuleRepository
        ├─ RuleResultRepository
        ├─ QualityScoreRepository
        ├─ QualityEvidenceRepository
        ├─ OperationLogRepository
        └─ QualityScoreCalculator / Rule Evaluator Registry
                    ↓
                 Database
```

### 7.2 Repository职责

#### RuleRepository

- 按规则集、状态和生效时间加载规则。
- 查询规则版本和规则列表。
- 检测同编码规则有效期冲突。
- 不执行规则、不计算分数、不提交事务。

#### RuleResultRepository

- 批量写入某个Score的规则结果。
- 查询Score规则明细、规则通过率和失败排行。
- 查询单规则历史趋势。
- 不判断规则是否通过、不提交事务。

#### QualityScoreRepository

- 替换相同身份的Quality Score及其从属结果。
- 查询指定日期、最新结果和历史趋势。
- 不计算四维分数、总分或等级。
- 不提交事务。

#### QualityEvidenceRepository

- 批量读取规则所需的Import、snapshot revision、release和issue证据。
- 生成传输中立的评估事实结构。
- 负责查询优化和避免N+1，不决定规则结果。
- 不修改来源数据、不提交事务。

#### OperationLogRepository

- 在批量计算中只写一条日志。
- 日志detail包含日期、算法版本、规则集版本、hash、规则数、覆盖数、成功状态和失败原因。
- V1可沿用Phase 1批量评分约定，以当前管理员同时作为actor和target user，避免在V009修改`operation_logs`结构。

### 7.3 DataQualityService职责

`calculate_quality_score()`负责：

1. 校验评分日期并创建固定作用域上下文。
2. 解析`analysis_as_of`。
3. 加载并校验规则集。
4. 生成规则集hash。
5. 批量获取评估证据。
6. 调用纯计算模块。
7. 创建Score与Rule Result ORM对象。
8. 调用Repository原子替换结果。
9. 写入一次operation log。
10. 成功提交，任一步骤失败全部回滚。

查询方法只调用对应Repository，不重新计算或排序。

当前`backend/services/quality_service.py`只有占位`QualityService`。实现时采用一个统一公共名称`DataQualityService`，不要并存两个职责重叠的Service。

## 8. Migration规划

### 8.1 实施前置检查

在创建V009前必须确认V001—V008迁移序列：

- 文件编号连续且均已纳入Git版本。
- 数据库实际已执行版本与仓库一致。
- V007的归属和内容已经确认。
- V008在目标MySQL 8.x数据库中可正常执行。

当前审查发现Git HEAD的已跟踪Migration缺少V007，而工作区存在未跟踪的`V007__create_import_batches.sql`。该问题必须先独立处理，不能在V009中顺带提交或绕过。

### 8.2 V009内容

建议Migration：

```text
database/migrations/V009__create_data_quality_scoring_tables.sql
```

V009只新增：

1. `data_quality_rules`。
2. `data_quality_scores`。
3. `data_quality_rule_results`。
4. 三张表内部的主键、唯一约束、检查约束、索引和外键。

创建顺序：

```text
data_quality_rules
  ↓
data_quality_scores
  ↓
data_quality_rule_results
```

V009不执行：

- 修改V001—V008脚本。
- 修改已有业务表结构。
- 修改Analytics、Score或Import数据。
- 写入运行时评分结果。
- 执行Alembic命令。

初始规则建议在V009结构通过测试后，以独立版本化数据Migration发布，便于结构与规则内容分别审查。

## 9. API规划

统一前缀：`/api/v1/data-quality`。

### 9.1 Phase 2 V1接口

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| `POST` | `/api/v1/data-quality/calculate` | ADMINISTRATOR | 计算指定日期质量评分 |
| `GET` | `/api/v1/data-quality/score` | 登录用户 | 查询指定日期；未传日期时查询最新结果 |
| `GET` | `/api/v1/data-quality/score/history` | 登录用户 | 查询总分和四维历史趋势 |
| `GET` | `/api/v1/data-quality/rules` | 登录用户 | 分页查询规则及版本 |

V1暂不开放规则创建、编辑、启用和停用API。初始规则通过受审查的数据Migration管理，在线规则管理作为后续独立阶段。

### 9.2 请求边界

计算请求只允许：

```json
{
  "score_date": "2026-09-15"
}
```

客户端不能传入：

- `algorithm_version`。
- `rule_set_version`。
- `rule_set_hash`。
- `quality_scope_type`或`quality_scope_id`。
- 维度权重、规则权重或等级。

### 9.3 Response规划

继续使用项目统一`ResponseModel[T]`、分页Schema、JWT Bearer和异常处理。

Score Response包含：

- 评分日期和`analysis_as_of`。
- 四维分数、总分和等级。
- 算法版本、规则集版本和hash。
- 覆盖实体数、开放问题数。
- 规则总数、通过/失败汇总及规则明细。

规则结果通过后端JOIN和聚合返回，客户端不解析数据库JSON来重建规则结果。

Router只负责参数校验、权限、Service调用和Response转换，不允许直接访问Repository、执行规则、计算分数、判断等级或控制事务。

## 10. Dashboard规划

Quality Dashboard应体现数据治理价值，而不是规则CRUD列表：

- 综合质量分和S/A/B/C等级。
- Completeness、Accuracy、Consistency、Timeliness四维雷达图或条形图。
- 规则通过率、适用数量和失败数量。
- 失败规则Top 10。
- 综合分及四维历史趋势。
- OPEN/CONFIRMED/RESOLVED/IGNORED问题趋势。
- 按严重度、来源和问题类型分布。
- 数据新鲜度与超时发布关系比例。
- 算法版本、规则集版本、分析截止时间和覆盖量。

管理员显示重新计算入口，普通用户只读。前端不得执行质量规则、标准化、加权或等级判断。

## 11. 测试与实施门禁

### 11.1 数据库测试

- 三张表、ORM注册、字段类型、索引和外键正确。
- 规则编码版本唯一、权重、枚举和时间约束生效。
- Score业务唯一键、ALL/0、分数和等级约束生效。
- Rule Result父子关系、唯一性、计数恒等式和N/A元组约束生效。
- 删除规则被RESTRICT，授权替换Score时子结果CASCADE。

### 11.2 纯计算测试

- PASS_RATE和BUCKET_AVERAGE标准化。
- 四维权重和综合公式。
- S/A/B/C边界和`ROUND_HALF_UP`。
- 缺失必需数据、真正N/A、单维度无规则和完全无数据。
- 负数、未来时间、累计回退、重复引用和陈旧快照。
- 不同证据来源去重。

### 11.3 Repository与Service测试

- 规则版本变化、规则禁用和新规则集发布。
- Score与Rule Result批量插入和原子替换。
- 同身份重算无重复，不同版本/hash可共存。
- 最新评分、历史趋势、规则通过率和失败排行。
- Repository无commit。
- Score写入、Rule Result写入或日志失败全部回滚。
- AnalyticsService、ScoreService和Import Service不被调用或修改。

### 11.4 API与回归测试

- OpenAPI、JWT、管理员计算、登录用户查询。
- 401/403/200、日期、分页、空数据和异常映射。
- 使用dependency overrides与Fake DataQualityService，不连接真实数据库。
- 完整后端回归测试和前端`npm run build`通过。
- Phase 1 Score API与Score Dashboard保持稳定。

## 12. 分阶段实施顺序

设计确认后按以下顺序推进，每阶段独立评审：

1. 处理并确认V001—V008迁移序列。
2. V009、三张ORM模型、ORM注册和数据库约束测试。
3. 纯规则执行与Quality Score计算模块。
4. 四个Data Quality Repository。
5. DataQualityService与事务测试。
6. Schema、Router、Dependency和API测试。
7. Quality Dashboard与生产构建验证。

本设计确认前以及V001—V008迁移序列确认前，不进入Phase 2代码实现。
