# Phase 2 数据质量治理设计方案

> 文档状态：设计稿，尚未创建数据库表、ORM、Service、API或前端页面。

## 1. 当前数据质量体系分析

### 1.1 已有能力

当前系统已经具备数据质量治理的基础数据结构和部分执行入口。

#### `import_jobs`

- 记录单次CSV/XLSX导入任务、发起人、文件摘要、任务状态和处理时间。
- 保存`total_rows`、`valid_rows`、`error_rows`、`imported_rows`，能够描述导入批次的处理结果。
- 通过状态约束和行数约束保证导入任务自身数据基本一致。
- 与运营快照的`source_import_job_id`建立来源关系，可追踪已写入快照的导入任务。

#### `import_errors`

- 记录导入任务中的行级或字段级错误。
- 保存来源行号、字段名、错误编码、错误描述和原始值。
- 已覆盖缺少必填值、类型错误、负数指标、非法时间、未知引用、重复记录、快照冲突等校验场景。
- 通过`import_job_id + source_row_number`和`import_job_id + error_code`索引支持错误定位和分类统计。

#### `data_quality_issues`

- 保存进入业务数据域后的持续性质量问题，而不仅是一次导入失败。
- 支持快照revision、短剧平台关系、短剧三类互斥目标，并由数据库保证恰好存在一个目标。
- 记录问题类型、严重级别、来源、规则编码、证据、首次/最近发现时间和重复发生次数。
- 支持`OPEN → CONFIRMED → RESOLVED/IGNORED`处置状态以及处理人、处理时间、处理说明。
- 已为状态、严重级别、目标、规则类型和处理时间建立查询索引。

#### 现有执行边界

- Import模块已经执行文件解析、字段校验、业务引用校验、重复检查和错误持久化。
- `QualityService`当前仅为结构入口，尚未形成规则加载、批量检查、评分计算和结果查询流程。
- 已有`operation_logs`可以承担质量评分计算、规则启停和问题处置的审计职责。

### 1.2 当前不足

1. 质量校验规则分散在导入校验器、数据库约束和业务代码中，没有统一、可查询、可版本化的规则目录。
2. `import_errors`回答“某次导入哪里出错”，`data_quality_issues`回答“当前有哪些待治理问题”，但都不能给出整体质量水平。
3. 缺少完整性、准确性、一致性、及时性四个维度的统一计算口径。
4. 缺少按日期保存的质量评分历史，无法观察治理前后趋势或复核过去结果。
5. 缺少规则版本与评分结果之间的绑定，规则调整后难以解释历史分数。
6. 缺少质量概览、维度对比、问题结构、失败规则和趋势等决策展示。
7. 现有数据库约束可以阻止部分非法数据写入，但不能替代跨时间、跨表和统计型质量检查。

### 1.3 Phase 2边界

Phase 2建立“规则目录—质量检查—质量评分—历史结果—分析展示”闭环。它复用现有事实表和问题台账，不重写Import校验，不修改Analytics或Composite Score算法。

V1评分作用域建议固定为：

```text
quality_scope_type = ALL
quality_scope_id   = 0
```

即先生成系统级每日质量画像。后续若需要按短剧、平台或导入任务评分，应新增明确外键和新算法版本，不在Phase 2 V1中使用无法由数据库校验的多态目标ID。

## 2. 数据库设计

### 2.1 设计结论

建议新增：

- `data_quality_rules`：版本化质量规则目录。
- `data_quality_scores`：按日期持久化的综合质量评分结果。

采用新增SQL Migration，建议文件为`V009__create_data_quality_scoring_tables.sql`；不修改V001—V008，不使用Alembic，不改变已有业务表字段或约束。初始规则数据建议使用后续独立的数据Migration维护，以便表结构和规则版本分别审查。

### 2.2 `data_quality_rules`

该表保存规则元数据和执行参数，不保存可直接执行的SQL或Python表达式。实际算法由后端受控的`evaluator_key`注册表实现，避免配置内容变成任意代码执行入口。

| 字段 | 建议类型 | 约束/说明 |
|---|---|---|
| `quality_rule_id` | `BIGINT UNSIGNED` | 主键，自增 |
| `rule_code` | `VARCHAR(64)` | 稳定业务编码，非空、去空格后非空 |
| `rule_version` | `VARCHAR(32)` | 单条规则版本，例如`1.0` |
| `rule_set_version` | `VARCHAR(64)` | 所属规则集，例如`DQ Rules 1.0` |
| `rule_name` | `VARCHAR(200)` | 中文可读名称 |
| `dimension` | `VARCHAR(32)` | `COMPLETENESS/ACCURACY/CONSISTENCY/TIMELINESS` |
| `target_entity_type` | `VARCHAR(32)` | `DRAMA/DRAMA_PLATFORM/SNAPSHOT/IMPORT_JOB` |
| `evaluator_key` | `VARCHAR(64)` | 映射后端白名单计算器 |
| `weight` | `DECIMAL(7,4)` | 维度内权重，`> 0`且`<= 100` |
| `severity` | `VARCHAR(16)` | `INFO/WARNING/ERROR`，用于问题治理优先级 |
| `parameters_json` | `JSON` | 阈值、字段列表、时间窗口等结构化参数 |
| `status` | `VARCHAR(16)` | `DRAFT/ACTIVE/INACTIVE` |
| `valid_from` | `DATETIME(6)` | 生效时间 |
| `valid_to` | `DATETIME(6) NULL` | 失效时间，必须晚于`valid_from` |
| `description` | `TEXT NULL` | 规则业务解释 |
| `created_at` | `DATETIME(6)` | 创建时间 |
| `updated_at` | `DATETIME(6)` | 更新时间 |

主键、索引和约束建议：

- 主键：`PRIMARY KEY (quality_rule_id)`。
- 唯一约束：`UNIQUE (rule_code, rule_version)`，历史版本不覆盖。
- 规则集查询索引：`(rule_set_version, status, dimension)`。
- 生效规则索引：`(status, valid_from, valid_to)`。
- 目标规则索引：`(target_entity_type, dimension, status)`。
- 检查`dimension`、`target_entity_type`、`severity`和`status`枚举范围。
- 检查规则权重范围、时间区间和非空文本。
- MySQL不具备通用的条件唯一索引；“同一`rule_code`同一时间只能有一个ACTIVE版本”由Service在事务中加锁校验。

已用于评分的ACTIVE规则版本不允许原地修改业务字段。调整阈值、权重或计算器时创建新`rule_version`，旧版本转为INACTIVE并保留。

### 2.3 `data_quality_scores`

该表保存质量评分结果快照，不保存计算操作人员；操作主体继续由`operation_logs`记录。

| 字段 | 建议类型 | 约束/说明 |
|---|---|---|
| `quality_score_id` | `BIGINT UNSIGNED` | 主键，自增 |
| `score_date` | `DATE` | 质量评分业务日期 |
| `quality_scope_type` | `VARCHAR(16)` | Phase 2 V1固定`ALL` |
| `quality_scope_id` | `BIGINT UNSIGNED` | Phase 2 V1固定`0` |
| `analysis_as_of` | `DATETIME(6)` | 实际统计截止时间 |
| `completeness_score` | `DECIMAL(5,2)` | 完整性，0—100 |
| `accuracy_score` | `DECIMAL(5,2)` | 准确性，0—100 |
| `consistency_score` | `DECIMAL(5,2)` | 一致性，0—100 |
| `timeliness_score` | `DECIMAL(5,2)` | 及时性，0—100 |
| `total_score` | `DECIMAL(5,2)` | 综合质量评分，0—100 |
| `quality_grade` | `CHAR(1)` | `S/A/B/C` |
| `algorithm_version` | `VARCHAR(64)` | 例如`Quality Score V1.0` |
| `rule_set_version` | `VARCHAR(64)` | 本次采用的规则集版本 |
| `rule_set_hash` | `CHAR(64)` | 活跃规则编码、版本、权重和参数的SHA-256摘要 |
| `evaluated_entity_count` | `BIGINT UNSIGNED` | 纳入评估的业务对象数 |
| `evaluated_check_count` | `BIGINT UNSIGNED` | 实际执行的规则检查数 |
| `passed_check_count` | `BIGINT UNSIGNED` | 通过检查数 |
| `failed_check_count` | `BIGINT UNSIGNED` | 失败检查数 |
| `open_issue_count` | `BIGINT UNSIGNED` | 截止分析时间仍开放的问题数 |
| `evaluation_detail` | `JSON` | 分规则分母、通过数、失败数、N/A原因和使用的规则ID/版本 |
| `created_at` | `DATETIME(6)` | 创建时间 |
| `updated_at` | `DATETIME(6)` | 更新时间 |

主键、索引和约束建议：

- 主键：`PRIMARY KEY (quality_score_id)`。
- 业务唯一约束：`UNIQUE (score_date, algorithm_version, rule_set_version, quality_scope_type, quality_scope_id)`。
- 最新结果索引：`(quality_scope_type, quality_scope_id, score_date DESC)`。
- 版本趋势索引：`(algorithm_version, rule_set_version, score_date DESC)`。
- 等级趋势索引：`(score_date, quality_grade)`，为后续扩展多作用域统计保留。
- 检查V1作用域必须为`ALL / 0`。
- 检查四维分数和综合分数均在0—100之间。
- 检查等级范围、算法版本/规则集版本非空、`rule_set_hash`长度为64。
- 检查`evaluated_check_count = passed_check_count + failed_check_count`。

V1只有全局作用域，因此`data_quality_scores`不增加业务实体外键。`data_quality_rules`与现有`data_quality_issues.rule_code`保持逻辑关联，不给旧表新增外键，避免规则停用或版本升级影响历史问题记录。

### 2.4 历史保存与重算

- 不覆盖不同日期、算法版本或规则集版本的结果。
- 相同业务唯一键重复计算时，由Repository先删除后批量写入或使用等价的原子替换策略，但Repository不提交事务。
- `QualityScoreService`在一个事务中完成评分替换和一次操作日志写入；任一步骤失败整体回滚。
- `analysis_as_of`确定事实数据截止点，`rule_set_hash`和`evaluation_detail`确定规则输入，两者共同支持结果解释和审计。
- `evaluation_detail`同时保存各事实来源的最大ID/时间水位。由于部分主数据不是双时态表，V1保证“已保存结果可追溯”，但不承诺在业务数据后续修正后重算历史日期仍得到完全相同的事实集合；需要严格重放时应另行设计事实快照，不修改现有业务表来模拟历史。
- 规则版本记录不可物理删除；只允许停用。若未来需要严格的规则集实体和多对多明细，可在后续版本增加`data_quality_rule_sets`及关联表，不在V1提前扩表。

## 3. 评分模型设计

### 3.1 统一计算方法

每条规则`r`在指定`analysis_as_of`下得到：

- `N_r`：适用记录数。
- `P_r`：通过记录数。
- `F_r`：失败记录数，满足`N_r = P_r + F_r`。
- `RuleScore_r = 100 × P_r / N_r`。

当`N_r = 0`时，该规则记为`N/A`并排除出当前维度分母，同时在`evaluation_detail`记录原因，不按100分处理。

维度分数采用规则权重归一化：

```text
DimensionScore = Σ(weight_r × RuleScore_r) / Σ(weight_r)
```

如果某个维度没有任何可评估规则，则本次整体评分返回`INSUFFICIENT_QUALITY_DATA`，不持久化一个具有误导性的完整分数，并记录失败操作日志。

`severity`用于问题展示和治理优先级，不再次直接扣分；规则失败已经进入通过率，避免同一问题被重复惩罚。规则的重要程度由`weight`表达。

### 3.2 完整性评分 Completeness

衡量完成运营分析所需数据是否齐备。

建议V1规则：

- 短剧必填主数据存在且非空，例如编号、名称、状态。
- ONLINE短剧平台关系具有`online_at`。
- 运营快照存在有效`current_revision_id`。
- 非VOID当前revision具备播放量等必需指标。
- 导入任务行数统计完整，`valid_rows + error_rows`覆盖已处理行。

示例：某规则适用于100条在线发布关系，其中95条拥有有效当前快照，则该规则得分为95。

### 3.3 准确性评分 Accuracy

衡量数据是否满足字段、范围和业务语义要求。

建议V1规则：

- 播放、点赞、评论、收藏和分享等累计指标非负。
- 排名为空或大于0。
- 快照时间不晚于允许的未来偏差。
- 日期、数值和枚举字段能够按定义解析。
- Import窗口内的`FIELD_VALIDATION`、`TYPE_ERROR`、`INVALID_NEGATIVE_VALUE`、`INVALID_TIMESTAMP`等错误进入失败检查统计。

数据库已经拒绝的非法写入仍通过`import_errors`进入该维度，避免只检查已成功落库数据而产生虚高分数。

### 3.4 一致性评分 Consistency

衡量跨时间、跨表和同一业务键的数据是否保持一致。

建议V1规则：

- 同一短剧平台与快照时间只有一个观察槽位。
- revision链版本连续，当前revision属于对应snapshot。
- 累计播放和互动指标相较前一有效快照不应无理由回退。
- ONLINE/OFFLINE状态与上线时间满足业务约束。
- 导入引用的短剧、平台和发布关系存在且状态可用。
- `DUPLICATE_RECORD`、`CONFLICTING_SNAPSHOT`、`UNKNOWN_REFERENCE`、`CUMULATIVE_REGRESSION`等错误或开放问题进入失败检查统计。

统计型突增/突降先作为可配置规则产生问题证据；除非规则明确标记为一致性失败，否则不因单个异常值重复扣分。

### 3.5 及时性评分 Timeliness

衡量运营数据是否在期望时间内更新，而不是评价短剧生命周期或预测未来热度。

对每个ONLINE发布关系，读取截至`analysis_as_of`的最新有效快照，并以规则参数`expected_interval_hours`计算数据年龄比例。V1建议阶段分值：

| 最新快照年龄 / 期望更新间隔 | 分数 |
|---|---:|
| `<= 1` | 100 |
| `> 1`且`<= 2` | 80 |
| `> 2`且`<= 3` | 60 |
| `> 3`且`<= 7` | 40 |
| `> 7` | 20 |
| 无任何有效快照 | 0 |

各发布关系分值再按对应规则权重汇总。缺少快照同时影响完整性和及时性是有意设计：前者表示数据不存在，后者表示运营观测不可用，两个维度表达不同风险。

### 3.6 综合质量评分

Quality Score V1.0建议权重：

```text
Quality Score = 0.30 × Completeness
              + 0.30 × Accuracy
              + 0.25 × Consistency
              + 0.15 × Timeliness
```

完整性与准确性直接决定数据能否用于分析，权重最高；一致性影响趋势与增长判断；及时性影响决策时效，但不应掩盖数据正确性问题。

所有维度和综合评分使用`ROUND_HALF_UP`保留两位小数。建议质量等级：

| 等级 | 分数范围 |
|---|---|
| S | `>= 90` |
| A | `>= 75`且`< 90` |
| B | `>= 60`且`< 75` |
| C | `< 60` |

调整维度权重、等级边界或N/A策略必须升级`algorithm_version`；调整具体规则阈值或维度内权重必须升级规则版本及`rule_set_version`。

## 4. 数据流程

```text
Import
  ↓
字段/引用/重复校验
  ├─ 失败行 → import_errors
  └─ 有效行 → 业务表与运营快照
                  ↓
Quality Check ← data_quality_rules
  ├─ 持续性问题 → data_quality_issues
  └─ 规则评估结果
                  ↓
Quality Score V1.0
                  ↓
data_quality_scores + operation_logs
                  ↓
Quality API
                  ↓
Quality Dashboard
```

建议计算流程：

1. 管理员传入`score_date`，Service生成当日当前时间或历史日期结束时刻作为`analysis_as_of`。
2. 加载该时间点有效的ACTIVE规则并验证规则集完整性。
3. Repository批量读取规则所需事实数据、导入统计、导入错误和开放质量问题；避免逐规则N+1查询。
4. 纯计算模块执行规则评估、维度汇总、综合评分和等级划分。
5. 构造`DataQualityScore`结果并按固定作用域替换同一结果集合。
6. 写入一条`QUALITY_SCORE_CALCULATE`操作日志，detail包含日期、算法版本、规则集版本、规则摘要、评估数量和失败原因。
7. Service提交事务；规则加载、评分保存或日志写入任一步骤失败时整体回滚。

评分计算默认只读取已有`import_errors`和`data_quality_issues`。自动创建或合并质量问题应作为独立的Quality Check事务，避免“查看/重算分数”意外改变问题台账。

## 5. 与现有模块关系

### 5.1 Import模块

- 不修改现有解析、校验、暂存、确认和错误定位流程。
- 读取`import_jobs`汇总与`import_errors`作为质量证据，不改变其状态或错误记录。
- 不把每条`import_error`机械复制为`data_quality_issue`；只有进入业务域并需要持续跟踪的问题才进入问题台账。

### 5.2 AnalyticsService

- 不修改AnalyticsService接口或指标算法。
- Quality模块直接通过自己的Repository读取质量评估所需事实，不把质量规则塞入运营分析服务。
- Analytics可以在未来只读展示质量标签，但该集成不属于Phase 2 V1。

### 5.3 Composite Score模块

- 不修改`drama_scores`、Composite Score计算器、ScoreRepository或ScoreService。
- Phase 2质量评分与短剧运营价值评分是两个独立结果域：前者评价数据可信度，后者评价作品运营表现。
- 不在现有Composite Score V1.0中自动扣除质量分。未来若质量评分参与运营评分资格或置信度，必须发布新的Composite Score算法版本并单独评审。

### 5.4 审计与事务

- 规则创建、启用、停用和质量评分计算均写`operation_logs`。
- `data_quality_scores`不保存操作人员字段，避免与审计表职责重复。
- Repository继续遵循不`commit`原则，事务由Quality Service管理，Router不控制事务。

## 6. API和Dashboard规划

### 6.1 API规划

统一前缀建议为`/api/v1/data-quality`，继续使用`ResponseModel[T]`、统一分页Schema、JWT Bearer和现有异常映射。

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| `GET` | `/rules` | 登录用户 | 分页查询规则及版本 |
| `POST` | `/rules` | 管理员 | 创建DRAFT规则版本 |
| `PUT` | `/rules/{quality_rule_id}` | 管理员 | 修改尚未启用的DRAFT规则 |
| `POST` | `/rules/{quality_rule_id}/activate` | 管理员 | 激活规则版本并关闭冲突版本 |
| `POST` | `/rules/{quality_rule_id}/deactivate` | 管理员 | 停用规则版本 |
| `POST` | `/scores/calculate` | 管理员 | 计算指定日期全局质量评分 |
| `GET` | `/scores/latest` | 登录用户 | 获取最新完整质量评分 |
| `GET` | `/scores/history` | 登录用户 | 按日期范围查询质量趋势 |
| `GET` | `/scores/{score_date}` | 登录用户 | 查看指定日期维度和规则明细 |
| `GET` | `/issues` | 登录用户 | 按状态、严重度、维度和规则查询问题 |

静态路径`/latest`和`/history`必须在动态`/{score_date}`之前注册。Phase 2 V1计算请求只允许客户端传入`score_date`，不允许传入算法版本、规则集摘要或作用域。

Router只负责参数校验、鉴权、Service调用和响应转换；不得直接查询Repository、执行规则、计算分数或提交事务。

### 6.2 Dashboard规划

新增“数据质量治理”页面，建议包含：

- 综合质量分与S/A/B/C等级。
- Completeness、Accuracy、Consistency、Timeliness四维雷达图或横向条形图。
- 历史质量趋势及各维度趋势。
- OPEN/CONFIRMED/RESOLVED/IGNORED问题数量。
- 按严重度、问题类型、规则和数据来源统计。
- 失败次数最高的规则Top 10。
- 快照新鲜度分布和超时发布关系列表。
- 规则版本、算法版本、分析截止时间和评估覆盖量。

管理员显示“重新计算”和规则管理入口；普通登录用户只读。前端不得重新执行质量规则、加权、等级判断或问题严重度判断，所有结果来自API。

## 7. 测试方案

### 7.1 数据库与ORM测试

- Migration可在现有V001—V008数据库上增量执行，不修改已有表。
- 两张新表、字段类型、默认值、ORM注册和关系映射正确。
- 规则编码+版本唯一约束、枚举约束、权重范围、有效期约束生效。
- 评分业务唯一约束、ALL/0作用域、0—100分数范围、等级和计数恒等式约束生效。
- 同日期不同算法或规则集版本可以共存，相同身份不能重复。
- 非法JSON、空版本、非法hash和负计数被拒绝。

### 7.2 纯计算测试

- 四个维度正常计算及维度内加权公式。
- 综合权重公式与`ROUND_HALF_UP`两位小数。
- S/A/B/C等级边界。
- N/A规则不进入分母，整个维度无数据时返回不足数据。
- 及时性所有时间阶段边界、未来时间和缺失快照。
- 零记录、全通过、全失败、极大计数、重复问题和跨时区边界。
- 严重度不重复扣分，规则权重和规则版本变更可复现。

### 7.3 Repository测试

- 生效规则按`analysis_as_of`和规则集版本正确加载。
- 批量质量事实查询没有N+1访问。
- 同一作用域结果插入、替换、最新查询、历史分页和趋势排序正确。
- 空数据返回稳定结构。
- Repository不调用`commit`。

### 7.4 Service测试

- 完整调用顺序：规则加载→事实读取→纯计算→结果替换→单条操作日志。
- 相同日期重复计算不产生重复结果。
- 规则集不完整、某维度无数据、事实读取异常的错误映射。
- 部分规则N/A时的覆盖量和detail汇总。
- Repository异常、规则计算异常、operation log异常均整体回滚。
- Import、Analytics和Composite Score服务不被调用或修改。

### 7.5 API测试

- OpenAPI路径、Schema、JWT Bearer和统一Response/Error结构。
- 计算与规则管理接口的401、403、200；查询接口的401、200。
- 日期、分页、维度、等级、规则状态和错误参数校验。
- 使用`dependency_overrides`和Fake Quality Service，不连接真实数据库。
- 静态路由优先级、无结果404或空列表语义、Service异常映射。

### 7.6 集成与回归测试

- 构造包含有效行、缺失值、非法值、未知引用、重复快照和陈旧快照的导入数据，验证其分别进入`import_errors`、`data_quality_issues`和质量评分明细。
- 验证质量评分计算不会改变Import任务、运营快照、Analytics结果和`drama_scores`。
- 执行完整后端回归测试和前端`npm run build`，确保Phase 1评分闭环保持稳定。

## 8. 建议实施顺序

1. 确认Quality Score V1.0权重、初始规则清单和规则参数Schema。
2. 新增Migration、ORM及数据库约束测试。
3. 实现无数据库副作用的规则计算与质量评分核心。
4. 实现Rule/QualityScore Repository，保持无事务提交。
5. 扩展Quality Service完成规则生命周期、评分编排和审计事务。
6. 实现Schema、Router和Fake Service API测试。
7. 实现Quality Dashboard及生产构建验证。

每个阶段独立评审和提交；在设计确认前不进入任何Phase 2代码实现。
