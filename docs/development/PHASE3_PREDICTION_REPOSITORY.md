# Phase 3 Prediction Repository

## 1. 职责边界

`PredictionRepository`只负责`prediction_results`的数据访问，位于：

```text
PredictionService
        ↓
PredictionRepository
        ↓
PredictionResult ORM
        ↓
prediction_results
```

Repository不计算移动平均、不读取snapshot或revision、不选择历史revision、不聚合平台数据、不判断数据质量，也不调用`PredictionCalculator`。

Repository接收外部注入的SQLAlchemy `Session`，不创建Session、不`commit()`、不`rollback()`，只在写操作完成后`flush()`。事务由后续PredictionService统一管理。

## 2. 接口

### `save_prediction`

保存单条`PredictionResult` ORM对象或映射值，调用`session.add()`和`session.flush()`后返回对象。

### `replace_prediction`

按`drama_id`、`metric_type`、`algorithm_version`和`target_date`删除同一目标日期旧结果，再插入新对象并flush。这样支持同一目标日期的重算，同时保留不同目标日期的历史预测。

### `get_latest_prediction`

按短剧、指标和算法版本过滤，数据库排序为：

```text
analysis_as_of DESC
created_at DESC
prediction_id DESC
```

返回最近一次有效预测或`None`。

### `get_predictions_by_drama`

按短剧、指标和算法版本过滤，使用调用方提供的`limit`限制结果，按`target_date ASC, prediction_id ASC`返回历史列表。

### `get_prediction_range`

按短剧和闭区间`target_date`过滤，可选指标和算法版本过滤，按目标日期升序返回。起止日期倒置时在查询前抛出`ValueError`。

### `delete_prediction_scope`

删除指定短剧、指标和算法版本的全部预测，flush后返回数据库删除行数。

## 3. SQLAlchemy查询方式

所有查询均使用SQLAlchemy ORM `select()`和`delete()`：

- 最新预测使用`Session.scalar(select(...).limit(1))`。
- 历史和日期范围使用`Session.scalars(select(...)).all()`。
- 替换和删除使用带条件的SQLAlchemy `delete()`。
- 未使用原生SQL。
- 当前查询只返回PredictionResult，不需要关联Drama，因此没有引入额外JOIN；未来若返回Drama信息，应使用`joinedload`或`selectinload`避免N+1。

## 4. 唯一性与事务

V010数据库唯一约束为：

```text
(drama_id, metric_type, target_date, algorithm_version)
```

Repository不吞掉唯一约束或外键异常，`flush()`产生的`IntegrityError`向Service传播，由Service决定回滚和错误响应。

Repository自身不提交事务，因此“删除旧结果—插入新结果”仍处于Service控制的同一事务中；任何后续失败都可以整体回滚。

## 5. 测试结果

`backend/tests/test_prediction_repository.py`覆盖：

- 单条保存、ORM对象保存和flush。
- 同目标日期替换。
- 最新预测排序。
- 历史列表排序及limit。
- 日期范围过滤、空结果和日期参数校验。
- 指定Scope删除和删除行数。
- V010唯一约束字段。
- flush异常传播。
- 不commit、不rollback。

`backend/tests/test_repositories.py`同步验证Repository包导出`PredictionRepository`。

测试使用注入的Session mock，不连接真实数据库；V010数据库约束已经在Phase 3 Database阶段通过MySQL 8.0验证。

## 6. 与Calculator和未来Service的边界

Calculator负责：

```text
累计播放量序列 → 日增量 → Moving Average V1.0 → 预测结果
```

Repository只负责保存和查询Calculator输出。未来PredictionService负责读取已按`analysis_as_of`筛选并完成多平台聚合的输入，调用Calculator，构造PredictionResult，组织Repository写入和OperationLog事务；不得把这些业务职责下沉到Repository。
