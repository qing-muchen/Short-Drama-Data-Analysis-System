# Phase 3 Prediction Database Implementation

## 1. 实现目标

Phase 3数据库阶段为短剧运营趋势预测建立独立、可追溯的结果存储。本阶段只实现V010 Migration、SQLAlchemy ORM和数据库约束测试，不包含Calculator、Repository、Service、API、Frontend或Dashboard。

Phase 3 V1预测目标为下一日累计播放量。算法身份固定为`Moving Average V1.0`，但算法计算过程和日增量中间值不进入本阶段数据库模型。

## 2. V010 Migration设计

Migration文件：

```text
database/migrations/V010__create_prediction_results.sql
```

V010在V001—V009之后新增`prediction_results`，不修改任何已有表。统一数据库规范为：

- MySQL 8.x、InnoDB。
- `utf8mb4`和`utf8mb4_0900_ai_ci`。
- Migration会话时区为UTC。
- 主键使用`BIGINT UNSIGNED AUTO_INCREMENT`。
- 审计时间使用`DATETIME(6)`和数据库服务器默认值。
- Drama外键删除、更新策略均为RESTRICT。

### 2.1 字段

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `prediction_id` | `BIGINT UNSIGNED` | PK、AUTO_INCREMENT | 预测结果主键 |
| `drama_id` | `BIGINT UNSIGNED` | NOT NULL、FK | 所属短剧 |
| `metric_type` | `VARCHAR(32)` | NOT NULL、非空白CHECK | V1业务值为`PLAY_COUNT` |
| `prediction_date` | `DATE` | NOT NULL | 预测生成业务日期 |
| `target_date` | `DATE` | NOT NULL | 预测目标日期 |
| `predicted_value` | `DECIMAL(20,2)` | NOT NULL、非负CHECK | 下一日累计播放量预测值 |
| `algorithm_version` | `VARCHAR(64)` | NOT NULL、非空白CHECK | V1为`Moving Average V1.0` |
| `analysis_as_of` | `DATETIME(6)` | NOT NULL | 历史输入和revision截止时刻 |
| `created_at` | `DATETIME(6)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(6)` | NOT NULL | 更新时间 |

未增加`scope_type`、`scope_id`、`confidence`、`actual_value`、`prediction_error`、`input_window`或`predicted_increment`。预测结果天然归属于`drama_id`；窗口和预测增量属于后续Calculator内部过程。

### 2.2 约束

业务唯一身份为：

```text
UNIQUE (
  drama_id,
  metric_type,
  target_date,
  algorithm_version
)
```

该约束防止同一短剧、指标、目标日期和算法版本产生重复结果。`prediction_date`和`analysis_as_of`是结果属性，不参与本阶段冻结的唯一身份。

外键：

```text
prediction_results.drama_id
    → dramas.drama_id
    ON DELETE RESTRICT
    ON UPDATE RESTRICT
```

CHECK约束：

- `metric_type`去除首尾空格后长度大于0。
- `predicted_value >= 0`。
- `algorithm_version`去除首尾空格后长度大于0。

V1只由后续Service产生`PLAY_COUNT`和`Moving Average V1.0`；数据库保留版本化结果所需的字符串字段，不静默覆盖历史算法结果。

### 2.3 索引

| 索引 | 列顺序 | 用途 |
|---|---|---|
| `idx_prediction_results_drama_metric_target` | `drama_id, metric_type, target_date` | 单剧最新预测和历史趋势 |
| `idx_prediction_results_metric_target` | `metric_type, target_date` | 指标维度的目标日期趋势 |

## 3. ORM映射

ORM文件：

```text
backend/models/prediction.py
```

新增`PredictionResult`，使用项目现有`Base`和`CreatedUpdatedAtMixin`。ORM与V010保持以下一致：

- 表名、字段名、类型、精度和可空性。
- MySQL无符号主键、`DECIMAL(20,2)`和`DATETIME(6)`。
- 外键名称及RESTRICT策略。
- UNIQUE、CHECK及索引名称和列顺序。
- 不包含任何V1禁止字段。

建立双向关系：

```text
Drama.predictions
    1
    ↓
    N
PredictionResult.drama
```

该关系只扩展ORM映射，不修改`dramas`物理表结构。模型通过`backend/models/__init__.py`注册。

## 4. 测试设计

### 4.1 ORM测试

`backend/tests/test_prediction_models.py`覆盖：

- 模型导入、metadata注册及Mapper配置。
- Drama与PredictionResult双向关系。
- 精确字段集合及禁止字段缺失。
- 无符号主键、DECIMAL精度和DATETIME(6)。
- 外键、UNIQUE、CHECK和索引。
- 使用SQLAlchemy MySQL dialect编译建表SQL。

全局metadata测试同步覆盖V010后的表数、外键、CHECK、UNIQUE和索引总数。

### 4.2 数据库约束测试

`database/tests/constraint_test.sql`更新至V010，新增覆盖：

- 合法PredictionResult插入。
- 唯一身份冲突，即使`prediction_date`不同也会拒绝。
- 空白`metric_type`。
- 负数`predicted_value`。
- 空白`algorithm_version`。
- 孤立`drama_id`外键。

全部fixture位于事务内，测试结束后回滚。

## 5. 验证结果

### 5.1 MySQL 8.0隔离验证

使用MySQL Community Server 8.0.45、独立临时数据目录和随机本地端口进行验证。未连接或修改现有业务数据库；验证完成后实例已关闭，临时目录已清理。

数据库引导及V001—V010全部执行成功。最终结构：

| 检查项 | 实际结果 |
|---|---:|
| 基础表 | 24 |
| 外键 | 45 |
| CHECK | 95 |
| ENFORCED CHECK | 95 |
| UNIQUE | 24 |

`prediction_results`实际为InnoDB和`utf8mb4_0900_ai_ci`。V010的3个CHECK均为`ENFORCED = YES`，Drama外键为RESTRICT/RESTRICT，唯一约束和两组普通索引的列顺序均符合Migration。

数据库约束回归结果：

```text
74 passed / 0 failed
```

### 5.2 后端测试

| 测试范围 | 结果 |
|---|---|
| Prediction ORM及全局metadata专项 | 7 passed |
| 当前完整工作区pytest | 242 passed |
| 本次精确暂存快照完整pytest | 219 passed |

当前完整工作区包含既有未提交功能测试。精确暂存快照测试证明，本次提交不依赖这些无关工作区修改。

## 6. 阶段边界

本阶段已完成：

- V010 Migration。
- PredictionResult ORM及Drama 1:N关系。
- ORM、DDL编译和数据库约束测试。
- MySQL 8.0.45空库迁移链验证。

本阶段未实现Calculator、Repository、Service、API、Frontend或Dashboard。后续Calculator必须继续遵循设计V2的“8个累计日点→7个日增量→下一日累计播放量”规则。
