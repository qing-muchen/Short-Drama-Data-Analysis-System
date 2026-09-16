# Phase 2 Data Quality Repository

## 1. 实现目标

本阶段在V009三表ORM之上实现Data Quality持久化访问层，保持项目既有分层：

```text
Router
  ↓
Service
  ↓
Repository
  ↓
SQLAlchemy ORM
  ↓
MySQL
```

实现文件：

```text
backend/repositories/data_quality_repository.py
```

三个Repository放在同一文件中，原因是它们共同服务于一个质量评分快照聚合，且当前项目已经采用在单个Repository模块内组织紧密相关实体的方式。

Repository只构造查询、添加对象和执行`flush`，不负责质量规则执行、权重计算、等级判断、Session创建、`commit`或`rollback`。

## 2. V009字段边界

本实现严格以已提交的V009和`backend/models/data_quality.py`为持久化契约，没有修改Migration或ORM。

任务描述中的以下字段不属于V009：

```text
actual_value
expected_value
message
```

因此Repository不会虚构这些列，也不会将其隐式塞入其他字段。V009的规则结果字段为：

- `quality_rule_id`
- `quality_score_id`
- `result_status`
- `applicable_count`
- `passed_count`
- `failed_count`
- `rule_score`
- `not_applicable_reason`
- `evidence_summary`

如未来确实需要结构化的实际值、期望值和消息，必须先通过新Migration和ORM变更明确数据类型及历史兼容策略。

同样，`data_quality_rules`没有`rule_set_version`列。V2设计规定规则集成员由已持久化Score下的Rule Result关系精确记录，所以历史规则集查询通过：

```text
data_quality_scores.rule_set_version
  ↓
data_quality_rule_results
  ↓
data_quality_rules
```

完成，不把规则集版本错误等同于单条规则的`rule_version`。

## 3. DataQualityRuleRepository

### 3.1 `list_effective_rules()`

按指定时间查询有效规则：

- `status`过滤，默认`ACTIVE`。
- `valid_from <= as_of`。
- `valid_to IS NULL OR valid_to > as_of`。
- 可选`dimension`过滤。
- 可选单规则`rule_version`过滤。
- 按`rule_code ASC, rule_version ASC, quality_rule_id ASC`稳定排序。

返回完整Rule ORM对象，因此调用方可以直接读取`dimension`和`weight`，Repository不解释或计算权重。

### 3.2 `list_by_rule_set_version()`

通过Score和Rule Result关系查询某个已经持久化的`rule_set_version`实际包含的规则版本。使用`DISTINCT`去除同一规则集在多次评分中的重复引用，并支持`status`和`dimension`过滤。

该接口用于历史追溯。尚未执行过的未来规则集没有成员关系记录，其发布与组装属于后续Service职责。

### 3.3 `list_rule_versions()`

按`rule_code`查询所有版本，可选状态过滤，按有效时间、版本和主键倒序返回，为未来规则版本审阅提供基础查询。

## 4. DataQualityRuleResultRepository

### 4.1 `bulk_create()`

接收一个`quality_score_id`和规则结果集合：

1. 将父Score ID覆盖写入每个payload。
2. 使用BaseRepository列白名单拒绝非V009字段和主键注入。
3. 构造`DataQualityRuleResult`对象集合。
4. 使用`session.add_all()`批量加入Session。
5. 使用`session.flush()`触发主键、唯一约束、外键和CHECK校验。

方法不提交或回滚。任何`IntegrityError`原样向上传递，由Service统一回滚事务。

### 4.2 `list_by_score_id()`

根据`quality_score_id`查询全部规则结果，并在同一SQL中JOIN及预加载Rule：

```text
Rule Result JOIN Rule
```

结果按`rule_code`、`rule_version`和Rule Result主键稳定排序。Rule元数据已随一次查询加载，后续访问不会对每条结果产生N+1查询。

## 5. DataQualityScoreRepository

### 5.1 `save_score()`

保存并flush单个DataQualityScore，不提交事务。

### 5.2 `replace_scope_scores()`

按照已确认的替换身份删除旧集合：

```text
score_date
+ rule_set_version
+ score_scope_type
+ score_scope_id
```

随后将相同身份字段覆盖到新payload，执行`add_all()`和`flush()`。空集合仍会执行DELETE和flush，从而支持清理指定作用域。

Phase 2 V1由数据库CHECK保证作用域只能是：

```text
ALL / 0
```

Repository保留scope参数是为了生成明确SQL并与未来Migration扩展兼容，不在Repository中复制CHECK业务判断。

删除Score时，V009外键会CASCADE删除其Rule Result。替换父Score和重新写入子结果必须由后续Service放在同一事务中编排。

### 5.3 查询接口

| 方法 | 用途 |
|---|---|
| `get_latest_score_date()` | 获取scope及可选算法/规则集版本的最新日期 |
| `get_current_score()` | 获取最近Score及完整Rule Result → Rule图 |
| `list_history()` | 获取最近N条趋势并按时间正序返回 |
| `get_grade_distribution()` | 统计持久化的S/A/B/C数量 |

`get_current_score()`使用一次JOIN eager-load加载Score、Rule Results和Rules，避免详情读取产生N+1。

历史趋势先在子查询中按日期、分析截止时间和主键倒序选出最近N条，再在外层按相同字段正序返回，兼顾“最近窗口”和图表时间顺序。

等级分布只聚合数据库中的`quality_grade`，不会重新计算分数或判断等级；无数据时返回四个等级均为0。

## 6. 事务边界

所有Repository遵守：

- Session由调用方注入。
- 写入使用`add`、`add_all`和`flush`。
- 不调用`commit`。
- 不调用`rollback`。
- 不创建或关闭Session。
- 数据库约束错误向上传递。

未来DataQualityService负责把Score替换、Rule Result批量写入和Operation Log写入放入同一事务。

## 7. 测试设计

新增：

```text
backend/tests/test_data_quality_repository.py
```

更新Repository包导出测试，使三个新Repository纳入公共接口检查。

覆盖内容：

- 有效规则时间窗口、状态、维度和版本过滤。
- 历史`rule_set_version`关系查询。
- 单规则未来版本查询。
- Rule Result批量写入、空集合和父Score ID覆盖。
- 拒绝不存在的非V009字段。
- Rule Result单查询预加载Rule及稳定排序。
- Score单条保存。
- scope集合替换及空集合清理。
- 最新日期和无数据场景。
- 当前评分完整关系图单查询加载。
- 最近历史窗口及正序返回。
- S/A/B/C分布及缺失等级补零。
- Score业务唯一约束、Rule Result唯一约束和两个外键定义。
- flush产生的唯一/外键`IntegrityError`不被Repository吞掉。
- 所有写操作均不调用commit或rollback。

V009阶段的隔离MySQL约束回归已经验证真实唯一约束和外键行为；本阶段Repository测试进一步确认约束元数据与写入身份一致，并确认数据库错误会传播给Service事务边界。

此外，本阶段在独立临时MySQL 8.0.45实例中重新执行V001—V009，并通过Repository真实执行以下验证：

- Rule、Score和Rule Result写入及flush成功。
- 重复Score/Rule组合触发UNIQUE约束错误。
- 不存在的Score ID触发外键约束错误。
- scope替换删除旧Score并级联清理Rule Result。
- `list_by_score_id()`加载结果及关联Rule只执行一条SQL。
- Service拥有的rollback后，三张质量表均无测试数据残留。

临时实例使用独立端口和数据目录，验证结束后已关闭并删除，不影响现有数据库。

## 8. 验证结果

| 测试 | 结果 |
|---|---|
| Data Quality Repository专项pytest | **18 passed** |
| 当前完整工作区后端pytest | **214 passed** |
| 本次精确暂存快照后端pytest | **191 passed in 8.13s** |
| MySQL 8.0.45 Repository集成验证 | **passed** |
| Python compileall | **passed** |

当前完整工作区包含用户尚未提交的其他功能。提交前已从Git暂存区导出独立快照运行后端测试，191项测试全部通过，排除了这些改动对本阶段结果的影响。

## 9. 阶段边界

本阶段没有实现或修改：

- DataQualityService
- Router或API
- Frontend或Dashboard
- Calculator算法
- V001—V009 Migration
- ORM表结构

后续Service应组合三个Repository，但不得将事务控制下沉到Repository。
