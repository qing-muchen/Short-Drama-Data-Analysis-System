# Phase 4 Anomaly Detection Database

## 1. 实施范围

本阶段只完成Phase 4异常检测的数据库结构和ORM映射：

- V011 Migration：`data_anomaly_records`。
- SQLAlchemy `DataAnomalyRecord`模型。
- `Drama`到异常记录的一对多关系。
- ORM metadata、MySQL DDL和数据库约束测试。

本阶段未实现Calculator、Repository、Service、Router、API或Dashboard。

异常表保存的是规则检测得到的`anomaly finding`，不是原始运营事实、Data Quality结果或Prediction结果。原始指标仍来自既有snapshot/revision表，未来计算模块通过`analysis_as_of`重建检测输入。

## 2. V011 Migration

文件：

```text
database/migrations/V011__create_data_anomaly_records.sql
```

V011不修改V001–V010，也不重编号既有Migration。表使用项目统一规范：

- MySQL 8.x / InnoDB。
- `utf8mb4`与`utf8mb4_0900_ai_ci`。
- `DATETIME(6)`保存UTC时间。
- `BIGINT UNSIGNED`自增主键。
- `drama_id`外键使用`ON DELETE RESTRICT ON UPDATE RESTRICT`。
- `created_at`和`updated_at`使用项目统一时间默认值。

V010完成后为24张表，V011新增1张表，最终为25张表。

## 3. `data_anomaly_records`表结构

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `anomaly_id` | `BIGINT UNSIGNED` | PK、AUTO_INCREMENT |
| `drama_id` | `BIGINT UNSIGNED` | NOT NULL，外键到`dramas.drama_id` |
| `metric_type` | `VARCHAR(32)` | `PLAY_COUNT`或`ENGAGEMENT_RATE` |
| `anomaly_type` | `VARCHAR(64)` | 四种Phase 4 V1异常类型 |
| `severity` | `CHAR(1)` | V1存储`A/B/C`，等级含义由Calculator冻结 |
| `status` | `VARCHAR(16)` | `OPEN/ACKNOWLEDGED/RESOLVED/IGNORED`，默认`OPEN` |
| `analysis_as_of` | `DATETIME(6)` | 历史输入和revision截止时间 |
| `detected_at` | `DATETIME(6)` | 检测生成时间 |
| `algorithm_version` | `VARCHAR(64)` | V1为`Rule-based Detection V1.0` |
| `baseline_value` | `DECIMAL(18,4)` | 历史基准，可为空 |
| `actual_value` | `DECIMAL(18,4)` | 检测窗口实际值，可为空 |
| `deviation_value` | `DECIMAL(18,4)` | 实际值与基准差异，可为空 |
| `evidence_summary` | `TEXT` | 非空解释性证据摘要 |
| `created_at` | `DATETIME(6)` | 非空创建时间 |
| `updated_at` | `DATETIME(6)` | 非空更新时间 |

表不保存：

- `drama_name`。
- `platform_name`。
- 原始snapshot数组或revision副本。
- Prediction结果副本。
- Data Quality结果副本。

### 3.1 V1异常字典

`metric_type`：

- `PLAY_COUNT`
- `ENGAGEMENT_RATE`

`anomaly_type`：

- `PLAY_COUNT_GROWTH_ANOMALY`
- `PLAY_COUNT_DROP_ANOMALY`
- `ENGAGEMENT_RATE_ANOMALY`
- `DATA_SPIKE_ANOMALY`

`severity`：

- `A`：严重等级编码，具体方向和阈值由Calculator定义。
- `B`：中等级编码。
- `C`：低等级编码。

数据库只负责字典约束，不实现异常算法和等级判断。

## 4. 唯一约束、CHECK与索引

### 4.1 历史唯一性

唯一约束：

```text
uq_data_anomaly_records_identity(
  drama_id,
  metric_type,
  anomaly_type,
  analysis_as_of,
  algorithm_version
)
```

相同短剧、指标、异常类型、历史截止点和算法版本重复检测时不能产生重复记录；不同`analysis_as_of`表示不同历史检测快照，允许并存。

### 4.2 CHECK约束

V011包含5个命名CHECK：

- `chk_data_anomaly_records_metric_type`
- `chk_data_anomaly_records_anomaly_type`
- `chk_data_anomaly_records_severity`
- `chk_data_anomaly_records_status`
- `chk_data_anomaly_records_algorithm_version`

约束内容覆盖指标字典、异常类型字典、A/B/C等级、状态字典和算法版本非空。`baseline_value`、`actual_value`和`deviation_value`允许NULL，以支持不适用或缺少可计算基准的检测结果；数值计算规则由后续Calculator和Service负责。

### 4.3 索引

- `idx_anomaly_query(analysis_as_of, status, severity, metric_type)`：Dashboard筛选和历史截止点查询。
- `idx_anomaly_trend(drama_id, analysis_as_of)`：单剧异常趋势和历史快照查询。

唯一键同时支撑检测幂等性，不额外保存冗余业务名称。

## 5. ORM映射

文件：`backend/models/anomaly.py`。

`DataAnomalyRecord`继承项目统一的`CreatedUpdatedAtMixin`和`Base`，完整映射V011字段、外键、CHECK、UNIQUE和INDEX定义。

关系：

```text
Drama 1 ───── N DataAnomalyRecord
```

`Drama.anomaly_records`与`DataAnomalyRecord.drama`使用`back_populates`双向关系。该关系只表达异常记录归属，不把异常检测逻辑放入Drama模型，也不增加平台或标签作用域。

`backend/models/__init__.py`已注册`DataAnomalyRecord`，metadata导入后包含25张表。

## 6. 约束测试

新增：

```text
backend/tests/test_anomaly_models.py
```

覆盖：

- ORM导入和Mapper配置。
- Drama双向关系。
- 字段集合、主键、自增和类型精度。
- DATETIME(6)、DECIMAL(18,4)、CHAR(1)。
- 外键目标及RESTRICT行为声明。
- CHECK、UNIQUE和两个索引的列顺序。
- MySQL方言DDL编译。

更新：

```text
backend/tests/test_models_import.py
```

同步验证25张表、25个模型导出项、46个外键、100个CHECK、25个UNIQUE和64个索引，并确认Drama异常关系注册。

更新：

```text
database/tests/constraint_test.sql
```

增加有效异常插入、重复身份、指标类型、异常类型、A/B/C等级、状态、空算法版本和孤儿Drama外键约束测试。

## 7. 验证结果

### 7.1 Backend pytest

```text
290 tests collected and passed
```

其中包括4项新增`test_anomaly_models.py`测试以及更新后的全局metadata测试。

### 7.2 MySQL 8.0.45隔离迁移

在临时隔离数据库中依次执行V001–V011，验证结果：

| 项目 | 结果 |
|---|---:|
| 最终表数量 | 25 |
| 外键约束 | 46 |
| CHECK约束 | 100 |
| UNIQUE约束 | 25 |
| `data_anomaly_records`存在 | 1 |
| V001–V011执行 | 成功 |

验证完成后临时数据库已删除，未修改现有`short_drama_analysis`业务库。

### 7.3 约束回归

`database/tests/constraint_test.sql`在MySQL 8.0.45隔离库执行：

```text
82 passed / 0 failed
```

## 8. 后续阶段边界

后续实现必须遵循以下边界：

- Calculator只负责基线、偏差、Z-score/回退和等级计算。
- Repository只负责异常记录访问，不计算、不提交事务。
- Service负责as-of数据准备、Data Quality协同、事务和OperationLog。
- Router/API负责权限、参数和响应转换。
- Dashboard只展示API结果，不在前端重新判断异常。

本阶段不实现上述业务模块。
