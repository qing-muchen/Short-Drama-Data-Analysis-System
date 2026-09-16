# Phase 2 Data Quality Calculator

## 1. 实现目标

本阶段实现Data Quality Score V1.0纯计算核心，将已经产生的规则PASS/FAIL结果转换为四维质量评分、综合质量分和S/A/B/C等级。

实现文件：

```text
backend/analytics/data_quality.py
```

Calculator只负责确定性计算，不负责：

- 查询数据库或规则。
- 构造SQLAlchemy ORM对象。
- 保存评分或规则结果。
- 管理Session或事务。
- 调用Repository、Service或API。

因此同一输入在任意执行环境中都会得到相同结果，也便于后续Service复用和独立测试。

## 2. 输入与输出

### 2.1 规则结果

`QualityRuleResult`表示一个已经执行完成的二元规则结果：

| 字段 | 含义 |
|---|---|
| `dimension` | `COMPLETENESS/ACCURACY/CONSISTENCY/TIMELINESS` |
| `status` | `PASS/FAIL` |
| `weight` | 维度内部相对权重 |

Calculator不会查询规则表。调用方需要在进入纯计算模块前，将规则定义中的维度、权重和执行结果组合成输入对象。

`calculate_rule_pass_rate()`独立计算规则通过率：

```text
Rule Pass Rate = pass_count / total_count × 100
```

该函数校验计数类型、总数和0—100范围，并使用`ROUND_HALF_UP`保留两位小数。

### 2.2 评分结果

`DataQualityScoreResult`输出：

- `completeness_score`
- `accuracy_score`
- `consistency_score`
- `timeliness_score`
- `total_score`
- `quality_grade`
- `algorithm_version`
- `rule_set_version`

`algorithm_version`固定为`Quality Score V1.0`。`rule_set_version`由调用方传入、去除首尾空格后原样输出，用于历史追踪。

## 3. 计算规则

### 3.1 维度内评分

同一维度内按照规则权重计算加权通过率：

```text
Dimension Score =
  Σ(PASS rule weight)
  / Σ(all rule weight)
  × 100
```

- PASS规则的权重进入分子和分母。
- FAIL规则的权重只进入分母。
- 每个维度至少需要一条规则结果。
- 权重必须存在、有限、处于0—1，并且每条规则最终必须大于0。
- 维度权重总和为0时返回稳定错误，不执行除零。
- 维度分使用`ROUND_HALF_UP`保留两位小数。

### 3.2 综合评分

四维固定权重：

| 维度 | 权重 |
|---|---:|
| Completeness | 30% |
| Accuracy | 30% |
| Consistency | 25% |
| Timeliness | 15% |

综合公式：

```text
Quality Score = 0.30 × Completeness
              + 0.30 × Accuracy
              + 0.25 × Consistency
              + 0.15 × Timeliness
```

综合分限制在0—100，并使用`ROUND_HALF_UP`保留两位小数。计算过程中使用局部高精度Decimal上下文，避免二进制浮点误差影响边界结果。

### 3.3 等级

| 等级 | 范围 |
|---|---|
| S | `>= 90` |
| A | `>= 75`且`< 90` |
| B | `>= 60`且`< 75` |
| C | `< 60` |

等级以已经按两位小数舍入的综合分为依据。

## 4. 核心接口

| 接口 | 职责 |
|---|---|
| `calculate_rule_pass_rate()` | 根据通过数和总数计算规则通过率 |
| `calculate_dimension_score()` | 计算单一维度的规则权重通过率 |
| `calculate_data_quality_score()` | 计算四维分、综合分、等级和版本信息 |
| `determine_quality_grade()` | 对0—100分进行S/A/B/C分类 |
| `round_half_up()` | 统一Decimal两位小数舍入 |

完整评分要求四个维度均存在规则结果。任何维度缺失时返回`INSUFFICIENT_QUALITY_DATA`，不生成误导性的总分。单维度分析可以直接调用`calculate_dimension_score()`。

## 5. 异常模型

所有业务校验错误使用`DataQualityCalculationError`，并提供稳定的`code`：

| 错误码 | 场景 |
|---|---|
| `EMPTY_RULE_RESULTS` | 没有规则结果 |
| `MISSING_RULE_WEIGHT` | 权重为空 |
| `ZERO_WEIGHT_SUM` | 维度权重总和为0 |
| `INVALID_RULE_WEIGHT` | 权重为负、超过1或单条权重为0 |
| `UNKNOWN_DIMENSION` | 未知维度 |
| `INVALID_RULE_STATUS` | 非PASS/FAIL状态 |
| `MIXED_DIMENSION_RESULTS` | 单维度接口收到其他维度结果 |
| `INVALID_RULE_COUNTS` | 通过数或总数类型/范围非法 |
| `RULE_SCORE_OUT_OF_RANGE` | 计数会产生0—100之外的规则分 |
| `INSUFFICIENT_QUALITY_DATA` | 完整计算缺少一个或多个维度 |
| `TOTAL_SCORE_OUT_OF_RANGE` | 综合分超出0—100 |
| `INVALID_RULE_SET_VERSION` | 规则集版本为空 |
| `INVALID_NUMERIC_VALUE` | 数值非有限Decimal |

错误模型不依赖HTTP状态码或持久化层，后续Service/API可以在边界层完成映射。

## 6. 测试结果

测试文件：

```text
backend/tests/test_data_quality_calculator.py
```

覆盖范围：

- 四维固定权重和综合公式。
- 单维度及不同规则权重。
- PASS/FAIL上下界。
- 规则通过率。
- S/A/B/C等级边界。
- `ROUND_HALF_UP`和Decimal精度。
- 空结果、缺失维度和空规则集版本。
- 缺失、零、负数、超范围及非有限权重。
- 未知维度、非法状态和混合维度。
- 非法计数及超过0—100的规则分。
- 规则集版本传递。
- 生成器输入和不同输入顺序的确定性。

验证结果：

| 测试 | 结果 |
|---|---|
| Calculator专项pytest | **35 passed** |
| 当前完整工作区后端pytest | **196 passed** |
| 本次精确暂存快照后端pytest | **173 passed in 10.53s** |
| Python compileall | **passed** |

完整工作区包含用户当前未提交的其他功能。提交前已从Git暂存区导出独立快照执行后端回归，173项测试全部通过，确认本次三个新增文件可独立工作。

## 7. 阶段边界

本阶段没有实现或修改：

- Repository
- Service
- Router或API
- Frontend或Dashboard
- V001—V009 Migration
- 数据库Session及事务

后续Repository和Service应消费Calculator输出，不得重复计算维度分、综合分或等级。
