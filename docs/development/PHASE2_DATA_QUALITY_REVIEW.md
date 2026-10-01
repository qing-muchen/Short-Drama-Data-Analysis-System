# Phase 2 Data Quality Governance 架构审查报告

> 审查范围：`PHASE2_DATA_QUALITY_DESIGN.md`及当前已提交的Import、Data Quality、Analytics、Composite Score架构。本文仅给出审查结论，不包含数据库、Migration、后端或前端实现。

## 1. 当前设计优点

### 1.1 模块定位正确

现有设计没有把数据质量治理简化为错误列表，而是形成了完整业务链路：

```text
数据采集/导入
  ↓
字段与业务校验
  ↓
质量规则检测
  ↓
四维质量评价
  ↓
历史趋势与Dashboard
  ↓
治理决策
```

这与软件著作权系统“数据采集—清洗—质量检测—指标计算—分析展示”的定位一致，能够与普通CRUD系统形成明显区分。

### 1.2 现有表职责划分基本清晰

- `import_jobs`负责一次导入任务的流程状态、行数结果、执行时间和来源追踪。
- `import_errors`负责某次导入中的行级/字段级拒绝原因，是导入阶段证据。
- `data_quality_issues`负责进入业务治理域后的持续性问题、严重度、重复发生和人工处置生命周期。
- `data_quality_rules`拟负责规则定义、版本、维度、权重和配置。
- `data_quality_scores`拟负责指定日期和算法版本下的综合质量评价结果。

以上对象分别表达“任务”“一次性错误”“持续问题”“规则定义”“评价结果”，不存在必须合并的同义实体。

### 1.3 评分结果独立持久化合理

质量评分是具有时间、算法版本和规则集版本的派生事实，不应写回Import任务、运营快照或问题表。独立保存可以支持：

- 历史趋势查询。
- 相同事实在不同算法版本下并存。
- 规则调整前后对比。
- Dashboard高频读取与计算过程解耦。
- 重算、审计和结果解释。

四维分数、综合分数和等级虽然存在计算关系，但它们属于一次评价输出快照，按结果事实保存不构成业务主数据冗余；公式一致性应由唯一的纯计算模块和测试保证。

### 1.4 规则模型具备安全边界

规则通过`evaluator_key`映射后端白名单计算器，并将阈值等参数放入结构化配置，而不是在数据库存储可执行SQL或Python代码。这一设计兼顾可配置性、可测试性和安全性。

### 1.5 Phase 2与Phase 1隔离意识明确

原设计明确不修改AnalyticsService、Composite Score计算器、ScoreRepository、ScoreService和`drama_scores`，也不让前端重新计算质量分。这符合已有分层方式，可以避免Phase 2改变已归档的Phase 1结果。

### 1.6 事务边界符合当前项目风格

由Service统一管理“评分结果写入 + 规则执行明细写入 + 单条操作日志”，Repository只执行数据库访问而不`commit`，与现有`BaseService`和`BaseRepository`契约一致。

## 2. 存在风险

### 2.1 两张表不足以支持规则通过率和历史解释

当前设计把分规则的适用数、通过数、失败数、N/A原因和规则版本放在`data_quality_scores.evaluation_detail` JSON中。如果JSON是唯一事实来源，会产生以下问题：

- 规则结果形成重复数组，不符合第三范式目标。
- Dashboard查询“失败最多规则”“规则通过率趋势”需要扫描和解析JSON。
- 无法使用外键保证评分明细引用真实且未删除的规则版本。
- 同一信息可能同时存在于规则表、评分聚合字段和JSON中，容易不一致。
- Repository分页、过滤、索引和数据库约束能力无法覆盖规则级结果。

如果Phase 2只展示一个总分，两张表可以工作；但既然需求包含规则通过率、问题趋势和历史追溯，当前两表方案不够。

### 2.2 `rule_set_version`的不可变规则尚未完全闭合

当前规则表同时具有`rule_set_version`、状态和有效时间。如果在同一个`rule_set_version`内直接启用、禁用或修改规则，规则集实际内容会变化：

- 同一个规则集版本可能对应多个`rule_set_hash`。
- 相同日期重算可能覆盖原结果，却使用了不同规则集合。
- 历史结果虽有hash，但版本名称不再具有稳定含义。

规则禁用不能只是把`ACTIVE`改为`INACTIVE`后继续沿用原规则集版本。规则集合、权重或配置发生变化时，必须发布新的`rule_set_version`。

### 2.3 `enabled`与`status`可能成为重复状态源

重点字段中提出了`enabled`，原设计已经使用`DRAFT/ACTIVE/INACTIVE`。如果同时保留布尔`enabled`和`status`，会出现`enabled = true`但`status = INACTIVE`等冲突组合。

V1只保留一个状态源即可。推荐保留`status`和有效时间，不再增加`enabled`字段；“规则禁用”即进入`INACTIVE`状态。

### 2.4 规则权重字段语义偏宽

原设计允许`weight > 0`且`<= 100`，同时计算公式又会对权重归一化。虽然可计算，但开发者难以判断该值是百分比、相对权重还是已经归一化的小数。

应统一为`DECIMAL(7,6)`且`0 < weight <= 1`，明确表示维度内相对权重。Service在规则集激活时校验每个维度至少有一条有效规则，并对实际可用规则权重再次归一化。

### 2.5 不同证据来源可能重复计分

同一缺陷可能先成为`import_error`，之后又以`data_quality_issue`出现。如果计算器按错误条数和问题条数直接相加，同一问题可能被重复扣分。严重度、发生次数和规则失败也可能形成多重惩罚。

每条规则必须明确：

- 评估对象和时间窗口。
- 适用分母。
- 主证据来源。
- 去重业务键。
- 是否产生持续性issue。

`severity`用于治理优先级，不再次参与扣分；`occurrence_count`也不应直接重复放大规则失败。

### 2.6 历史重算不能被描述为完全可重放

快照revision和导入错误具有较强历史性，但部分主数据不是双时态模型。`analysis_as_of`、规则版本和水位可以解释当时计算，但无法保证业务数据被后续修改后重新计算历史日期仍得到相同事实集合。

V1应承诺“持久化结果和规则证据可追溯”，不承诺“任意历史日期可完全重放”。严格重放需要独立事实快照或双时态设计，不应通过修改现有业务表临时实现。

### 2.7 操作日志缺少质量评分目标类型

当前`operation_logs`要求恰好一个目标，但没有`target_quality_score_id`。若V009严格只新增表，不扩展operation log，可沿用Phase 1批量评分约定：

```text
actor_user_id  = 当前管理员
target_user_id = 当前管理员
operation_type = QUALITY_SCORE_CALCULATE
```

该方案无需修改旧表，但`target_user_id`表达的是批量操作发起人而不是质量评分本身，语义不够理想。V1可以接受并在Service文档中明确；若以后需要评分实体级审计，再用独立Migration增加`target_quality_score_id`，不要在V009中扩大风险面。

### 2.8 当前已提交Migration序列存在编号缺口

审查时，Git HEAD中的已跟踪Migration为V001—V006和V008，未包含已跟踪的V007；工作区存在一个未跟踪的`V007__create_import_batches.sql`。这不是质量评分表设计本身的问题，但会影响“V009基于V001—V008”的发布前提。

在实现V009之前，必须先确认V007的归属、内容和提交状态，保证部署环境能够得到确定且连续的Migration序列。不能用V009掩盖现有编号缺口。

### 2.9 Service仅依赖两个Repository不足以取得评估事实

`RuleRepository`负责规则，`QualityScoreRepository`负责评分结果；两者都不应该顺便承担对Import、snapshot revision、drama platform和quality issue的复杂批量读取。

如果Service直接查询ORM会破坏分层，如果把这些查询塞进ScoreRepository又会使其职责过宽。因此还需要一个只读的`QualityEvidenceRepository`，专门批量构造质量评估事实。

### 2.10 API范围略大于V1必要范围

原设计同时规划规则创建、编辑、激活、停用、问题列表和多种评分查询。动态规则管理涉及规则集发布、并发启用、配置Schema和审计，可能使V1范围失控。

Phase 2 V1应优先完成规则可查看、评分可计算、结果可查询。规则可先由版本化数据Migration发布；在线规则编辑可以在评分闭环稳定后单独实施。

## 3. 需要调整项

### 3.1 必须调整

1. 新增`data_quality_rule_results`，不要把规则级结果只保存在`evaluation_detail` JSON。
2. 将`rule_set_version`定义为不可变规则集合版本；规则启用、禁用、权重或配置变化必须发布新规则集版本。
3. 规则表只保留`status`，不再新增重复的`enabled`布尔字段。
4. 明确每条规则的分母、证据来源、时间窗口和去重键，防止`import_errors`与`data_quality_issues`重复扣分。
5. 在进入V009前解决已跟踪Migration缺少V007的问题。
6. Data Quality V1只生成质量评价和治理证据，不阻断AnalyticsService、ScoreService或Score Dashboard。
7. 增加`QualityEvidenceRepository`，禁止Service直接查询数据库，也不污染Rule/Score Repository职责。

### 3.2 建议调整

1. `data_quality_scores`移除可由规则结果求和得到的`evaluated_check_count`、`passed_check_count`和`failed_check_count`，避免与明细重复；API层可聚合返回。
2. 将原`evaluation_detail`缩减为可选`source_watermark` JSON，只保存各来源最大ID、时间水位等不可自然关系化的追溯信息。
3. 将规则权重定义为`0—1`之间的小数，并在Service激活/加载规则集时校验维度覆盖。
4. `data_quality_scores`业务唯一键加入`rule_set_hash`作为防御性身份字段，或严格保证`rule_set_version`不可变后只使用版本字段。推荐同时保存并纳入唯一键。
5. V1先通过数据Migration发布内置规则，不开放规则写API，降低规则集生命周期复杂度。

### 3.3 可以保持不变

- Quality Score V1.0四维权重`30%/30%/25%/15%`。
- 四个维度和综合分数统一为0—100。
- 使用`ROUND_HALF_UP`保留两位小数。
- 单条规则`N/A`时排除该规则及其权重。
- 任一维度没有可评估规则时不生成误导性总分。
- V1固定`ALL / 0`全局作用域。
- 评分结果不保存操作人员，操作信息由`operation_logs`承担。
- Repository不提交事务，Router不控制事务。

## 4. 最终推荐架构

### 4.1 推荐数据库结构

Phase 2 V1推荐新增三张表，而不是两张表。

#### A. `data_quality_rules`

必须保存：

| 字段 | 说明 |
|---|---|
| `quality_rule_id` | 规则版本实体主键 |
| `rule_code` | 跨版本稳定编码 |
| `rule_version` | 单规则版本 |
| `rule_set_version` | 不可变规则集版本 |
| `rule_name` | 展示名称 |
| `dimension` | 四维归属 |
| `target_entity_type` | 评估对象类型 |
| `evaluator_key` | 后端白名单计算器键 |
| `weight` | 维度内相对权重，`0 < weight <= 1` |
| `severity` | 治理优先级，不直接重复扣分 |
| `configuration` | JSON规则参数，必须经过计算器专属Schema校验 |
| `status` | `DRAFT/ACTIVE/INACTIVE` |
| `valid_from/valid_to` | 生效区间 |
| `description` | 业务解释 |
| `created_at/updated_at` | 记录时间 |

关键约束与索引：

- `PRIMARY KEY (quality_rule_id)`。
- `UNIQUE (rule_code, rule_version)`。
- 检查维度、目标类型、严重度、状态、权重和生效区间。
- 索引`(rule_set_version, status, dimension)`。
- 索引`(target_entity_type, dimension, status)`。
- 同一规则编码的生效区间不得重叠，由Service事务校验。

不应保存：

- 可执行SQL/Python代码。
- 与`status`重复的`enabled`。
- 某次执行的通过数或失败数。
- Import原始错误行和质量issue副本。

#### B. `data_quality_scores`

必须保存：

| 字段 | 说明 |
|---|---|
| `quality_score_id` | 评分主键 |
| `score_date` | 业务评分日期 |
| `analysis_as_of` | 事实截止时间 |
| `quality_scope_type/id` | V1固定`ALL / 0` |
| 四维score | Completeness、Accuracy、Consistency、Timeliness |
| `total_score` | 综合质量分 |
| `quality_grade` | S/A/B/C |
| `algorithm_version` | `Quality Score V1.0` |
| `rule_set_version` | 规则集展示版本 |
| `rule_set_hash` | 精确规则集合摘要 |
| `evaluated_entity_count` | 去重后的覆盖对象数 |
| `open_issue_count` | 当时开放问题数量快照 |
| `source_watermark` | 可选JSON，只保存来源水位 |
| `created_at/updated_at` | 记录时间 |

关键约束与索引：

- `PRIMARY KEY (quality_score_id)`。
- `UNIQUE (score_date, algorithm_version, rule_set_version, rule_set_hash, quality_scope_type, quality_scope_id)`。
- 检查ALL/0作用域、分数范围、等级、hash长度和非负计数。
- 最新/趋势索引`(quality_scope_type, quality_scope_id, score_date DESC)`。
- 版本索引`(algorithm_version, rule_set_version, score_date DESC)`。

不应保存：

- 操作人员ID。
- 每条规则的重复名称、维度、权重或配置。
- 可从明细稳定求和的规则检查计数。
- Import错误或quality issue全文副本。

#### C. `data_quality_rule_results`

该表是一次质量评分与规则版本之间的执行事实。

| 字段 | 说明 |
|---|---|
| `quality_rule_result_id` | 主键 |
| `quality_score_id` | FK → `data_quality_scores` |
| `quality_rule_id` | FK → `data_quality_rules`中的具体版本 |
| `result_status` | `APPLIED/NOT_APPLICABLE` |
| `applicable_count` | 适用检查数 |
| `passed_count` | 通过数 |
| `failed_count` | 失败数 |
| `rule_score` | 0—100；N/A时为NULL |
| `not_applicable_reason` | N/A原因，APPLIED时为NULL |
| `evidence_summary` | 可选、有限长度的聚合证据，不复制原始行 |
| `created_at` | 创建时间 |

关键约束与索引：

- `UNIQUE (quality_score_id, quality_rule_id)`。
- 检查`applicable_count = passed_count + failed_count`。
- APPLIED要求`applicable_count > 0`且`rule_score`非空。
- NOT_APPLICABLE要求三个计数为0、`rule_score`为空且原因非空。
- `quality_rule_id`使用`ON DELETE RESTRICT`，规则版本不能删除。
- `quality_score_id`可使用`ON DELETE CASCADE`，因为规则结果完全从属于评分快照；评分替换仍必须由Service授权并处于同一事务。
- 索引`(quality_score_id, result_status)`和`(quality_rule_id, quality_score_id)`。

这三张表满足：规则定义与执行事实分离、总分与规则明细分离、规则级历史可查询，并避免把关系型明细藏在JSON中。

### 4.2 推荐评分模型

单规则分数：

```text
Rule Score = 100 × passed_count / applicable_count
```

维度分数：

```text
Dimension Score = Σ(rule_weight × rule_score) / Σ(applicable_rule_weight)
```

综合分数：

```text
Quality Score = 0.30 × Completeness
              + 0.30 × Accuracy
              + 0.25 × Consistency
              + 0.15 × Timeliness
```

权重审查结论：

- Completeness 30%合理：缺少关键数据会直接阻断后续指标计算。
- Accuracy 30%合理：错误数据比缺少数据更可能产生误导性结论，应与完整性同级。
- Consistency 25%合理：快照回退、引用冲突和跨表不一致会破坏趋势与增长分析。
- Timeliness 15%合理：时效重要，但不应让“新但错误”的数据获得过高质量分。

缺失处理：

- 缺失必需数据是Completeness规则失败，不是N/A。
- 规则对当前数据域不适用才是N/A，并从维度权重分母排除。
- 规则被禁用后不参与新规则集，历史评分继续引用旧规则版本。
- 一个维度没有任何APPLIED规则时，整体返回`INSUFFICIENT_QUALITY_DATA`，不保存伪总分。
- 四维和总分统一限制在0—100，最后一步使用`ROUND_HALF_UP`保留两位小数。

### 4.3 与现有分析模块的关系

Phase 2 V1选择A：只生成质量评价结果，不直接阻断Analytics计算。

```text
Import/Snapshot/Issue ──→ Data Quality评价 ──→ Quality Dashboard
          │
          └────────────→ AnalyticsService ──→ ScoreService ──→ Score Dashboard
```

两条链路并行读取同一事实数据，但互不调用、互不写入对方结果表：

- Data Quality不改变AnalyticsService的查询结果。
- ScoreService不读取`data_quality_scores`作为V1资格条件。
- Score Dashboard不显示前端计算的质量扣分。
- Quality Dashboard可以提示“当前分析数据可信度”，但只是决策辅助。

未来如需用质量分阻断或降低运营评分置信度，必须设计显式策略并发布新的Composite Score算法版本，不能静默改变`Composite Score V1.0`。

### 4.4 推荐Service架构

```text
Data Quality Router
        ↓
DataQualityService
        ├─ RuleRepository
        ├─ QualityEvidenceRepository
        ├─ QualityScoreRepository
        ├─ RuleResultRepository
        ├─ OperationLogRepository
        └─ QualityScoreCalculator（纯计算）
                    ↓
                 Database
```

职责：

- `RuleRepository`：加载指定时间和规则集的规则版本；不执行规则。
- `QualityEvidenceRepository`：批量读取Import、snapshot revision、release和issue证据；不计算总分。
- `QualityScoreRepository`：替换/查询质量评分、最新日期和历史趋势；不计算规则。
- `RuleResultRepository`：批量写入和查询规则执行明细；不判断通过或失败。
- `DataQualityService`：生成上下文、校验规则集、调用纯计算器、构造ORM对象、管理事务和单条操作日志。
- `QualityScoreCalculator`：规则结果、维度分数、总分、等级和N/A处理；无数据库副作用。

当前`backend/services/quality_service.py`已有占位`QualityService`。实现时应在该文件中形成一个明确的公共Service名称，不要同时保留职责重叠的`QualityService`与`DataQualityService`。推荐采用`DataQualityService`并同步依赖注册。

### 4.5 推荐Migration策略

V009只做增量创建：

```text
V009__create_data_quality_scoring_tables.sql
  ├─ data_quality_rules
  ├─ data_quality_scores
  └─ data_quality_rule_results
```

要求：

- 不编辑V001—V008文件。
- 不修改Import、snapshot、quality issue、Analytics或score表。
- 不使用Alembic。
- 建表顺序为rules → scores → rule_results。
- 初始规则使用独立数据Migration发布，避免结构Migration与规则内容混杂。
- V009实施前先解决当前Git迁移序列缺少V007的问题。

新增三张表足以完成V1核心评分、规则通过率和历史追溯。V1不需要新增`data_quality_rule_sets`；前提是`rule_set_version`被严格视为不可变发布版本。若以后出现规则版本跨多个规则集复用，再新增规则集主表和关联表。

### 4.6 推荐API

Phase 2 V1最小API：

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/v1/data-quality/calculate` | ADMINISTRATOR | 按日期计算全局质量分 |
| GET | `/api/v1/data-quality/score` | 登录用户 | 查询指定日期；不传日期时返回最新结果 |
| GET | `/api/v1/data-quality/rules` | 登录用户 | 分页查询当前或指定规则集 |
| GET | `/api/v1/data-quality/score/history` | 登录用户 | 查询质量分与四维趋势 |

计算请求只包含`score_date`，不允许客户端传入算法版本、规则集hash、scope或权重。Router只进行参数校验、权限、Service调用和Response转换。

V1不建议开放规则创建/编辑/启停API。初始规则由受审查的数据Migration发布，规则管理API可在评分闭环稳定后作为独立阶段实现。

### 4.7 推荐Dashboard

Dashboard应突出数据治理而不是规则CRUD：

- 综合质量分和质量等级。
- 四维评分雷达图/条形图。
- 规则通过率与适用数量。
- 失败规则Top 10。
- 质量问题总量及OPEN/CONFIRMED/RESOLVED/IGNORED趋势。
- 按严重度、来源和问题类型分布。
- 数据新鲜度和超时快照比例。
- 算法版本、规则集版本、分析截止时间、覆盖实体数。

管理员显示重新计算入口，普通用户只读。前端只展示API结果，不执行规则、标准化、加权或等级判断。

### 4.8 推荐测试门禁

必须覆盖：

- 规则版本变化后历史结果仍指向旧规则版本。
- 规则禁用通过新规则集版本生效，不污染旧评分。
- 缺失必需数据作为失败，真正不适用作为N/A。
- 规则全部N/A、某个维度无规则以及完全无数据。
- 负数、未来时间、累计回退、重复记录、未知引用和陈旧快照。
- 0—100边界、权重公式、等级边界和`ROUND_HALF_UP`。
- 同日期同身份重算无重复；不同算法/规则集/hash可以共存。
- 评分、规则明细和operation log同一事务提交。
- Score写入失败、Rule Result写入失败、日志失败均整体回滚。
- Repository不commit，Router不查询数据库。
- API 401/403/200、参数校验、分页、空数据和异常映射。
- 完整后端回归与前端生产构建，确认Analytics、ScoreService和Score Dashboard无回归。

## 5. 是否可以进入实现阶段

审查结论：有条件通过，当前设计不应原样直接进入实现。

进入实现前必须确认以下事项：

1. 接受新增第三张表`data_quality_rule_results`。
2. 确认规则集不可变语义及“禁用规则必须发布新规则集版本”。
3. 确认Phase 2 V1只评价、不阻断Analytics/Score。
4. 确认V1最小API和暂不开放在线规则编辑。
5. 处理当前Git中V007 Migration未跟踪导致的版本链缺口。

以上五项确认后，可以进入第一实现阶段：只实现V009、三张ORM模型、ORM注册和数据库约束测试。此后仍应按“纯计算 → Repository → Service → API → Dashboard”的顺序分阶段推进，不一次性实现全部模块。
