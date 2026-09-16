# Phase 2 Data Quality Database Implementation

## 1. 实现目标

Phase 2 Step 1建立数据质量治理的持久化基础，只实现Migration、SQLAlchemy ORM和数据库约束测试，不包含Calculator、Repository、Service、API、Frontend或Dashboard。

新增三层模型：

```text
data_quality_rules
        1
        ↓
        N
data_quality_rule_results
        N
        ↓
        1
data_quality_scores
```

三层分别表达：

- 规则定义和单规则版本。
- 一次评价中的规则执行事实。
- 一次全局评价的四维与综合评分结果。

Phase 2 V1是全局数据治理评分，不是单剧评分。`data_quality_scores`使用固定作用域：

```text
score_scope_type = ALL
score_scope_id   = 0
```

数据库不增加`drama_id`、`platform_id`或`tag_id`，ORM也不建立Drama到DataQualityScore的关系。未来扩展其他scope必须使用新的Migration。

## 2. V009 Migration设计

Migration文件：

```text
database/migrations/V009__create_data_quality_tables.sql
```

V009仅新增三张表，不修改V001—V008及任何已有业务表。创建顺序为：

1. `data_quality_rules`
2. `data_quality_scores`
3. `data_quality_rule_results`

统一数据库规范：

- MySQL 8.x。
- InnoDB。
- `utf8mb4`。
- `utf8mb4_0900_ai_ci`。
- Migration会话时区设置为UTC。
- 主键使用`BIGINT UNSIGNED AUTO_INCREMENT`。
- 可变主记录使用`created_at`和`updated_at`。
- 规则执行事实只保存`created_at`，与冻结设计保持一致。
- 除Score到Rule Result的组合关系使用CASCADE外，外键使用RESTRICT。

### 2.1 `data_quality_rules`

规则表保存不可变规则版本，不保存可直接执行的SQL或Python表达式。

主要字段：

| 类别 | 字段 |
|---|---|
| 身份 | `quality_rule_id`、`rule_code`、`rule_version` |
| 展示 | `rule_name`、`description` |
| 分类 | `dimension`、`target_entity_type`、`severity` |
| 执行 | `evaluator_key`、`scoring_method`、`configuration` |
| 计分 | `weight` |
| 生命周期 | `status`、`valid_from`、`valid_to` |
| 审计时间 | `created_at`、`updated_at` |

约束与索引：

- `UNIQUE (rule_code, rule_version)`。
- 规则编码、版本、名称和执行器键不能为空白。
- 维度限定为Completeness、Accuracy、Consistency、Timeliness。
- 目标限定为Drama、Drama Platform、Snapshot、Import Job。
- 计分方式限定为PASS_RATE或BUCKET_AVERAGE。
- `0 < weight <= 1`。
- 状态、严重度和有效时间受到CHECK约束。
- 建立启用规则、目标维度和规则编码状态索引。

### 2.2 `data_quality_scores`

评分表保存一次全局质量评价快照，是Rule Result的父记录。

主要字段：

| 类别 | 字段 |
|---|---|
| 身份 | `quality_score_id`、`score_date` |
| 作用域 | `score_scope_type`、`score_scope_id` |
| 截止时间 | `analysis_as_of` |
| 四维评分 | `completeness_score`、`accuracy_score`、`consistency_score`、`timeliness_score` |
| 综合结果 | `total_score`、`quality_grade` |
| 版本追踪 | `algorithm_version`、`rule_set_version`、`rule_set_hash` |
| 覆盖快照 | `evaluated_entity_count`、`open_issue_count`、`source_watermark` |
| 审计时间 | `created_at`、`updated_at` |

业务唯一身份：

```text
UNIQUE (
  score_date,
  algorithm_version,
  rule_set_version,
  rule_set_hash,
  score_scope_type,
  score_scope_id
)
```

约束与索引：

- CHECK固定`ALL / 0`作用域。
- 四维分和总分限制在0—100。
- 等级限制为S/A/B/C。
- 算法版本和规则集版本不能为空白。
- 规则集hash长度必须为64。
- 覆盖实体数和开放问题数使用无符号整数并具有非负CHECK。
- 建立作用域日期、版本日期和等级日期索引，日期列使用降序索引。

### 2.3 `data_quality_rule_results`

规则结果表保存一次评分中一个具体规则版本的执行事实。

主要字段：

- `quality_rule_result_id`
- `quality_score_id`
- `quality_rule_id`
- `result_status`
- `applicable_count`
- `passed_count`
- `failed_count`
- `rule_score`
- `not_applicable_reason`
- `evidence_summary`
- `created_at`

关系：

- `quality_rule_id`引用`data_quality_rules`，删除和更新均为RESTRICT。
- `quality_score_id`引用`data_quality_scores`，更新为RESTRICT，删除为CASCADE。
- Score删除级联Rule Result仅用于同一身份重算时原子替换完整结果集合。

约束与索引：

- `UNIQUE (quality_score_id, quality_rule_id)`。
- `applicable_count = passed_count + failed_count`。
- `rule_score`为空或处于0—100。
- APPLIED必须有适用对象和规则分，且不能带N/A原因。
- NOT_APPLICABLE必须具有零计数、空规则分和非空原因。
- 建立评分状态、规则趋势和失败规则索引。

## 3. ORM映射

ORM文件：

```text
backend/models/data_quality.py
```

新增模型：

- `DataQualityRule`
- `DataQualityRuleResult`
- `DataQualityScore`

关系映射：

```text
DataQualityRule.results
    ↕
DataQualityRuleResult.rule

DataQualityScore.rule_results
    ↕
DataQualityRuleResult.score
```

Score到Rule Result配置为组合子关系，并使用`passive_deletes=True`配合数据库CASCADE。Rule到Rule Result不使用删除级联，被历史结果引用的规则版本由数据库RESTRICT保护。

ORM与V009在以下方面保持一致：

- 表名和全部字段。
- MySQL无符号整数、DECIMAL、DATETIME(6)和JSON类型。
- 字段可空性和服务器默认值。
- 主键、外键及删除/更新策略。
- 唯一约束和CHECK名称。
- 索引名称、列顺序和降序字段。

模型通过`backend/models/__init__.py`注册。未修改Drama ORM，也未建立任何业务实体scope关系。

## 4. 数据库约束测试

`database/tests/constraint_test.sql`已更新至V009，新增覆盖：

- 合法Rule、Score、APPLIED Result和NOT_APPLICABLE Result。
- 规则编码/版本唯一。
- 规则维度、目标、权重、执行器和有效时间。
- Score业务身份唯一、ALL/0作用域、分数范围、等级、算法版本和hash。
- Rule Result唯一性、计数恒等式、规则分范围、状态及APPLIED/N/A元组。
- Rule Result到Rule和Score的真实外键。
- 删除已引用Rule受到RESTRICT。
- 删除Score级联删除Rule Result。
- 测试事务回滚后无fixture残留。

ORM测试新增`backend/tests/test_data_quality_models.py`，验证：

- 三个模型完成注册。
- Rule、Rule Result、Score关系正确。
- Score包含`score_scope_type`和`score_scope_id`。
- Score不包含`drama_id`、`platform_id`或`tag_id`。
- JSON、无符号主键、CHECK、唯一约束和外键策略正确。
- Drama ORM不存在质量评分关系。

全局ORM metadata测试同步覆盖V009后的表、外键、CHECK、唯一约束、索引及唯一CASCADE外键。

## 5. 验证结果

### 5.1 隔离环境

| 项目 | 结果 |
|---|---|
| MySQL | Community Server 8.0.45 |
| 实例 | 独立临时数据目录和独立端口 |
| 业务数据库影响 | 无 |
| 清理 | MySQL正常关闭，临时目录已删除 |
| MySQL错误日志 | 无`[ERROR]`记录 |

### 5.2 Migration执行

在空白隔离实例中依次执行数据库引导和V001—V009，全部退出码为0：

| Migration | 结果 |
|---|---|
| V001 | PASS |
| V002 | PASS |
| V003 | PASS |
| V004 | PASS |
| V005 | PASS |
| V006 | PASS |
| V007 | PASS |
| V008 | PASS |
| V009 | PASS |

V009在MySQL 8.0.45中的执行耗时约123 ms。

### 5.3 最终数据库结构

| 检查项 | 预期 | 实际 | 结果 |
|---|---:|---:|---|
| 基础表 | 23 | 23 | PASS |
| 主键 | 23 | 23 | PASS |
| 外键 | 44 | 44 | PASS |
| CHECK | 92 | 92 | PASS |
| UNIQUE | 23 | 23 | PASS |
| RESTRICT/RESTRICT外键 | 43 | 43 | PASS |
| CASCADE/RESTRICT外键 | 1 | 1 | PASS |

V009新增三表均为InnoDB和`utf8mb4_0900_ai_ci`。23个V009 CHECK全部在information_schema中显示为`ENFORCED = YES`。

### 5.4 ORM一致性

使用SQLAlchemy Inspector将真实MySQL结构与ORM metadata逐项对比：

| 表 | 列 | 外键 | 唯一约束 | CHECK | 普通索引 | 差异 |
|---|---:|---:|---:|---:|---:|---:|
| `data_quality_rules` | 17 | 0 | 1 | 11 | 3 | 0 |
| `data_quality_scores` | 19 | 0 | 1 | 8 | 3 | 0 |
| `data_quality_rule_results` | 11 | 2 | 1 | 4 | 3 | 0 |

物理数据库与ORM差异数：**0**。

### 5.5 测试汇总

| 测试 | 结果 |
|---|---|
| 数据库约束回归 | **68 passed / 0 failed** |
| Data Quality ORM及全局metadata专项测试 | **7 passed** |
| 后端完整pytest | **161 passed in 11.58s** |
| 本次精确暂存快照后端pytest | **138 passed in 10.70s** |

完整工作区测试包含当前未提交的其他功能测试；为排除这些改动对结果的影响，提交前另从Git暂存区导出独立快照并执行全部后端测试，138项测试全部通过。

## 6. 阶段结论

Phase 2 Step 1数据库和ORM基础已完成：

- V009可以在V001—V008之后从空库安全执行。
- 三表结构符合冻结的V2三层模型。
- 全局作用域由数据库CHECK固定为`ALL / 0`。
- Rule、Rule Result、Score形成可追溯的规则版本和结果链。
- 数据库结构、SQLAlchemy ORM和约束行为一致。
- 现有后端测试未受影响。

本阶段未实现Calculator、Repository、Service、API、Frontend或Dashboard。
