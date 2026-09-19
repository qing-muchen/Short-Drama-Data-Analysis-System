# Phase 4 Anomaly Detection Repository

## 1. 实现目标与职责边界

本阶段在V011 `data_anomaly_records`与`DataAnomalyRecord` ORM之上增加异常记录数据访问层：

```text
未来 AnomalyService
        ↓
AnomalyRepository
        ↓
DataAnomalyRecord ORM
        ↓
data_anomaly_records
```

`AnomalyRepository`只负责异常记录的保存、查询、分页、聚合与状态持久化。它不执行Z-score、异常等级判断、规则选择、snapshot revision筛选或平台聚合，也不调用异常Calculator。

Repository接收外部注入的SQLAlchemy `Session`，不创建、提交、回滚或关闭Session。写操作仅执行`flush()`，事务由后续`AnomalyService`统一管理。

## 2. Repository接口

### 2.1 `save_anomalies`

接收`AnomalyFinding`集合，批量转换为`DataAnomalyRecord`：

- `status`固定初始化为`OPEN`；
- 同一批记录共享一个`detected_at`；调用方可显式传入，未传入时使用当前UTC时间；
- Calculator输出中的`analysis_as_of`保持不变，用于历史追溯；
- 使用`session.add_all()`和`session.flush()`，不提交事务；
- 数据库外键、唯一约束或CHECK失败时，异常原样向Service传播。

### 2.2 `get_anomalies`

提供全局分页列表，支持以下可选过滤：

- `analysis_as_of`
- `status`
- `severity`
- `metric_type`
- `anomaly_type`

固定排序为：

```text
severity DESC
detected_at DESC
anomaly_id DESC
```

查询通过`joinedload(DataAnomalyRecord.drama)`预加载短剧，避免列表展示短剧信息时产生N+1查询。返回项目统一的`Page[DataAnomalyRecord]`。

### 2.3 `get_by_drama`

按`drama_id`读取单剧异常历史，可选`limit`，固定排序为：

```text
analysis_as_of DESC
detected_at DESC
anomaly_id DESC
```

同样使用`joinedload`预加载Drama。

### 2.4 `get_latest_anomalies`

先通过`MAX(analysis_as_of)`确定最近一次全局检测截止点，再一次性返回该截止点的全部异常记录。无数据时返回空列表，不执行第二次列表查询。

### 2.5 `get_trend`

使用数据库侧`DATE(analysis_as_of)`和`COUNT(anomaly_id)`按日聚合异常数量。支持起止截止时间、短剧、指标、等级和状态过滤，按日期升序返回`AnomalyTrendPoint`，供Dashboard趋势图使用。

### 2.6 `update_status`

按主键获取异常记录，将状态更新为调用方给出的值并flush；记录不存在时返回`None`。Repository不重复实现V011的状态CHECK，状态流转授权与业务校验属于未来Service。

### 2.7 `get_statistics`

在数据库侧分别统计：

- 总异常数；
- A/B/C等级分布；
- OPEN/ACKNOWLEDGED/RESOLVED/IGNORED状态分布；
- PLAY_COUNT/ENGAGEMENT_RATE指标分布。

没有记录的固定枚举项补0。Repository只统计已经持久化的事实，不重新判断异常或等级。

## 3. SQLAlchemy查询设计

实现全部采用SQLAlchemy ORM表达式，没有原生SQL：

- 列表和单剧历史使用`select(DataAnomalyRecord)`；
- Dashboard分页沿用`BaseRepository.paginate()`，总数和数据页均在数据库侧处理；
- Drama关联使用`joinedload`，避免循环访问触发额外查询；
- 最新检测使用`func.max(analysis_as_of)`；
- 趋势和统计使用`func.date()`、`func.count()`与`GROUP BY`；
- 状态更新修改已加载ORM对象后flush。

数据库CHECK继续作为`metric_type`、`anomaly_type`、`severity`和`status`的最终一致性边界，Repository不复制Calculator规则。

## 4. 事务边界

Repository遵守以下约束：

- Session由调用方注入；
- 保存和状态更新只调用`flush()`；
- 不调用`commit()`或`rollback()`；
- 不调用`sessionmaker()`，也不创建或关闭Session；
- 约束异常向上传递，不在Repository内吞掉或转换。

后续`AnomalyService`应把异常记录写入、Operation Log及重算清理放在同一Session事务内，成功时一次提交，失败时整体回滚。

## 5. 测试结果

新增`backend/tests/test_anomaly_repository.py`，覆盖：

- 单条和批量保存、统一检测时间、空集合及flush；
- Repository不commit、不rollback、不关闭Session；
- 列表五类过滤、分页参数和固定排序语句；
- Drama eager loading，避免N+1；
- 单剧历史与limit；
- 最近检测结果和无数据；
- 按日趋势聚合；
- 状态更新及不存在记录；
- 总数、等级、状态和指标分布及缺失项补0。

`backend/tests/test_repositories.py`同步验证公共包导出。

验证结果：

```text
定向测试：21 passed
完整后端测试：319 passed
```

测试使用注入的Session mock，不连接真实数据库；V011表结构、外键、UNIQUE、CHECK和索引已在Phase 4 Database阶段完成验证。

## 6. 与Calculator及未来Service的边界

```text
Anomaly Calculator：历史指标序列 → 纯规则计算 → AnomalyFinding
Anomaly Repository：AnomalyFinding → ORM持久化/查询
未来 AnomalyService：数据准备、质量协同、Calculator调用、重算策略、事务与日志
```

Repository不会读取Analytics、Data Quality或Prediction模块，也不会把预测结果误作异常输入。状态更新仅持久化Service已经授权的目标状态，业务状态流转规则仍由Service负责。
