# Phase 2 Data Quality Service

## 1. 实现目标

本阶段实现`DataQualityService`，负责把规则加载、规则检查、纯计算、结果持久化和操作审计编排为一个完整且原子的业务流程：

```text
DataQualityRuleRepository
        ↓
registered Rule Evaluators
        ↓
Quality Calculator
        ↓
DataQualityScoreRepository
        ↓
DataQualityRuleResultRepository
        ↓
OperationLogRepository
```

实现文件：

```text
backend/services/data_quality_service.py
```

原占位`QualityService`已由统一公共名称`DataQualityService`替代，避免两个职责重叠的Service并存。

## 2. Service边界

`DataQualityService`负责：

- 解析评分日期和`analysis_as_of`。
- 加载当前有效规则。
- 根据`evaluator_key`调用已注册的V1规则Evaluator。
- 校验规则执行结果并转换为Calculator及Repository输入。
- 生成当前实际规则集合的确定性SHA-256。
- 调用Data Quality Calculator。
- 替换同日期、规则集和scope的Score。
- 批量保存Rule Result。
- 写入一次Operation Log。
- 成功时提交一次，任一步骤失败时回滚。

Service不负责：

- 直接执行SQL或访问ORM查询接口。
- 创建、关闭Session。
- 在Service中重复计算维度分、综合分或等级。
- 动态解释SQL/Python规则表达式。
- 允许用户在线创建或编辑规则。
- 修改来源数据或`data_quality_issues`。

## 3. 依赖与Session约束

构造依赖：

- `DataQualityRuleRepository`
- `DataQualityRuleResultRepository`
- `DataQualityScoreRepository`
- `OperationLogRepository`
- Rule Evaluator白名单映射
- Quality Calculator，可注入测试替身，默认使用`calculate_data_quality_score`

四个Repository必须共享Service的同一个Session。`BaseService`在构造阶段检查Session身份，不一致时立即拒绝启动业务流程。

### 3.1 Rule Evaluator边界

冻结设计包含`QualityEvidenceRepository / Rule Evaluator Registry`，但当前已完成的Repository阶段没有实现Quality Evidence Repository，且本任务禁止扩展Repository范围。

为避免Service直接查询ORM，本阶段采用显式Evaluator依赖：

```text
evaluator_key → RuleEvaluator(rule, QualityEvaluationContext)
```

Evaluator负责读取或持有其所需事实，并返回传输中立的`RuleExecutionResult`。Service只负责按规则白名单调用和校验结果。

缺少Evaluator、Evaluator抛错或返回非法结果时，统一抛出`DataQualityRuleExecutionError`并回滚。

这种设计保留了后续接入QualityEvidenceRepository的边界，不需要修改Service持久化流程，也不会让Service直接访问数据库。

## 4. 固定评分上下文

Phase 2 V1固定：

```text
score_scope_type = ALL
score_scope_id   = 0
rule_set_version = DQ Rules 1.0
algorithm_version = Quality Score V1.0
```

`rule_set_version`是当前V1有效规则集的业务版本。Service同时根据本次实际加载的规则生成`rule_set_hash`，避免业务版本标签相同但规则内容不同而失去技术追溯能力。

`analysis_as_of`规则与Phase 1保持一致：

- 当日评分使用当前时间。
- 历史评分使用指定日期在业务时区的结束时间。
- 存储前转换为UTC无时区`DATETIME(6)`语义。
- 未来日期在进入事务和Repository前拒绝。

## 5. 规则执行结果

Evaluator返回`RuleExecutionResult`：

| 字段 | 含义 |
|---|---|
| `status` | `PASS / FAIL / NOT_APPLICABLE` |
| `applicable_count` | 适用数量 |
| `passed_count` | 通过数量 |
| `failed_count` | 失败数量 |
| `rule_score` | BUCKET_AVERAGE规则的0—100分 |
| `not_applicable_reason` | N/A原因 |
| `evidence_summary` | 聚合证据说明 |

Service映射规则：

- PASS和FAIL写入数据库`result_status = APPLIED`。
- NOT_APPLICABLE写入数据库同名状态并从Calculator输入排除。
- PASS_RATE根据`passed_count / applicable_count × 100`生成规则分。
- BUCKET_AVERAGE必须由Evaluator提供0—100规则分。
- 所有计数必须是非负整数，且APPLIED满足总数恒等式。
- N/A必须具有零计数和非空原因。

Rule Result保存严格使用V009字段，不产生`actual_value / expected_value / message`等不存在的列。

## 6. 规则集Hash

Service按`rule_code`、`rule_version`和规则主键稳定排序，然后规范化以下字段：

- 规则编码和版本。
- 维度和目标实体类型。
- Evaluator键和计分方式。
- Decimal权重。
- JSON配置。

规范化JSON使用UTF-8编码并计算64字符小写SHA-256。同一规则集合不受Repository返回顺序影响，始终产生相同hash。

## 7. 原子计算流程

`calculate_quality_score()`执行：

1. 校验日期并创建固定scope上下文。
2. 在Service事务内加载`ACTIVE`有效规则。
3. 无规则时返回`NO_ACTIVE_RULE_SET`并回滚。
4. 生成规则集hash。
5. 按`evaluator_key`执行全部规则。
6. 生成Calculator输入和V009 Rule Result payload。
7. 调用纯Calculator生成四维分、总分和等级。
8. 调用`replace_scope_scores()`替换旧Score并取得新主键。
9. 调用`bulk_create()`保存全部Rule Result。
10. 写入一条`QUALITY_SCORE_CALCULATE`日志。
11. 全部成功后由Service执行一次commit。

Operation Log记录日期、算法版本、规则集版本、hash、固定scope、规则数量、适用/N/A数量、覆盖数量、总分和等级。不会为每条规则写一条操作日志。

`evaluated_entity_count`在当前传输结构中取各适用规则计数的最大值，避免把同一批对象在多条规则中重复相加。

`open_issue_count`在缺少QualityEvidenceRepository的本阶段保存为0；后续证据层接入时应提供真实快照值。

## 8. 事务与异常

事务包含：

```text
Score scope replacement
  + Rule Result bulk insert
  + Operation Log insert
```

行为：

- 成功：只调用一次`session.commit()`。
- 规则、Calculator或业务校验失败：调用`rollback()`并保留领域异常。
- Repository或Operation Log抛出SQLAlchemy错误：调用`rollback()`并转换为项目统一`PersistenceException`。
- Operation Log失败时，已经flush的Score和Rule Result仍会随事务回滚，不产生部分评分。

Repository仍然不commit、不rollback，Router未来也不得控制事务。

## 9. 查询方法

### `get_current_quality_score()`

使用固定scope、算法版本和规则集版本委托`DataQualityScoreRepository.get_current_score()`，不重新执行规则或计算评分。

### `get_quality_history()`

将日期范围和limit委托`DataQualityScoreRepository.list_history()`，不在Service中重新排序。

## 10. 测试覆盖

新增：

```text
backend/tests/test_data_quality_service.py
```

覆盖：

- 正常Rule → Evaluator → Calculator → Score → Rule Result → Log流程。
- 与真实Quality Calculator集成。
- 无有效规则集。
- Evaluator异常和非法规则结果。
- Calculator异常。
- Score与Rule Result Repository异常。
- Operation Log失败后的整体回滚。
- 同日重复计算使用相同替换身份。
- 固定`ALL / 0`作用域。
- NOT_APPLICABLE持久化并从Calculator排除。
- 规则集hash不受规则顺序影响。
- 当前评分和历史趋势纯委托。
- 未来日期提前拒绝。
- Service源码不导入ORM、不执行SQL。
- Service公共包导出同步。

当前验证结果：

| 测试 | 结果 |
|---|---|
| Data Quality Service专项pytest | **14 passed** |
| 当前完整工作区后端pytest | **228 passed** |
| 本次精确暂存快照后端pytest | **205 passed in 10.91s** |
| Python compileall | **passed** |

当前完整工作区包含用户尚未提交的其他功能。提交前已从Git暂存区导出独立快照执行后端回归，205项测试全部通过，确认本阶段文件可独立工作。

## 11. 阶段边界

本阶段没有实现或修改：

- API、Schema或Router
- Frontend或Dashboard
- V001—V009 Migration
- Data Quality ORM结构
- Repository接口
- Quality Calculator算法

后续API应仅负责参数、权限、Service调用和响应转换，不得绕过Service访问Repository或控制事务。
