# Phase 2 V007 Recovery Validation

> 验证对象：`database/migrations/V007__create_import_batches.sql`
>
> 候选文件SHA-256：`8ABDF22EED6B9E635BB20D1DDCBA4EC37BCA4F6038F7E77C2D18FF5A1751005F`
>
> 验证范围：SQL静态规范、隔离MySQL 8.x完整迁移链、数据库物理结构与约束、SQLAlchemy ORM一致性、现有后端测试。
>
> 本次未修改或提交V007，未创建V009，未修改ORM和业务代码。

## 1. 验证环境

### 1.1 环境信息

| 项目 | 实际结果 | 状态 |
|---|---|---|
| MySQL Server | MySQL Community Server 8.0.45，Win64 x86_64 | PASS |
| 最低版本要求 | MySQL 8.x | PASS |
| 临时实例地址 | `127.0.0.1:33317` | PASS |
| 临时schema | `short_drama_analysis` | PASS |
| 默认存储引擎 | InnoDB | PASS |
| Server字符集 | utf8mb4 | PASS |
| Server排序规则 | utf8mb4_0900_ai_ci | PASS |
| Python测试环境 | 项目`backend/.venv` | PASS |

### 1.2 隔离方式

本次没有连接或修改当前项目正在使用的MySQL服务和业务数据库，验证过程如下：

1. 使用MySQL 8.0.45的`mysqld --initialize-insecure`创建一次性空数据目录。
2. 通过独立端口33317和`127.0.0.1`启动临时实例。
3. 在空实例内创建固定名称`short_drama_analysis`，使迁移文件中的`USE short_drama_analysis`只作用于临时实例。
4. 严格按顺序执行数据库引导、V001至V008。
5. 完成结构、约束和ORM检查后，通过`mysqladmin shutdown`正常关闭实例。
6. 验证MySQL进程退出后删除临时数据目录。

隔离实例错误日志中未发现`[ERROR]`记录。实例关闭成功，临时目录清理成功。因此，本次验证未影响现有数据库，也没有遗留测试schema或临时MySQL进程。

### 1.3 SQL静态检查

| 检查项 | 结果 | 说明 |
|---|---|---|
| SQL语法 | PASS | 候选SQL在MySQL 8.0.45中完整执行，退出码为0 |
| schema选择 | PASS | 与V001—V008一致使用`short_drama_analysis` |
| 字符集 | PASS | 新表使用`utf8mb4` |
| 排序规则 | PASS | 新表使用`utf8mb4_0900_ai_ci` |
| 存储引擎 | PASS | 新表使用InnoDB |
| 时区规范 | PASS | 文件开头执行`SET time_zone = '+00:00'` |
| 时间字段 | PASS | 业务时间和审计时间统一为`DATETIME(6)`；创建/更新时间默认值与现有表一致 |
| 主键设计 | PASS | `BIGINT UNSIGNED AUTO_INCREMENT`单列主键，与现有业务表一致 |
| 外键设计 | PASS | 两个外键均使用显式名称及`ON DELETE/UPDATE RESTRICT` |
| 唯一约束 | PASS | 批次编码、批次内顺序、批次内文件类型均具有显式唯一约束 |
| CHECK约束 | PASS | 批次状态、行数、时间及Import Job批次字段完整性均有命名约束 |
| 索引设计 | PASS | 批次状态/创建人查询和批次任务状态查询均有匹配索引 |
| 命名规范 | PASS | 使用项目既有`pk/fk/uq/chk/idx`语义及表名命名方式，无重名冲突 |

## 2. Migration执行结果

在空白隔离实例中先执行数据库引导文件，再执行正式顺序中的每个迁移候选：

```text
Database Bootstrap
    ↓
V001 → V002 → V003 → V004 → V005 → V006 → V007 → V008
```

| 步骤 | 文件 | 退出码 | 耗时 | 结果 |
|---|---|---:|---:|---|
| Database Bootstrap | `database/ddl/001_create_database.sql` | 0 | 90 ms | PASS |
| V001 | `V001__create_core_tables.sql` | 0 | 163 ms | PASS |
| V002 | `V002__create_relation_tables.sql` | 0 | 143 ms | PASS |
| V003 | `V003__create_snapshot_tables.sql` | 0 | 130 ms | PASS |
| V004 | `V004__create_import_quality_tables.sql` | 0 | 142 ms | PASS |
| V005 | `V005__create_operation_log.sql` | 0 | 106 ms | PASS |
| V006 | `V006__create_indexes.sql` | 0 | 711 ms | PASS |
| V007 | `V007__create_import_batches.sql` | 0 | 129 ms | PASS |
| V008 | `V008__create_drama_scores.sql` | 0 | 72 ms | PASS |

全部SQL执行成功。V007可以在V001—V006之后正常创建批次表并扩展`import_jobs`；V008可以在V007之后继续正常创建`drama_scores`，未发现迁移间对象、约束或命名冲突。

## 3. 数据库验证结果

### 3.1 最终表结构

| 验证项 | 预期 | 实际 | 结果 |
|---|---:|---:|---|
| 基础表数量 | 20 | 20 | PASS |
| 单列主键数量 | 20 | 20 | PASS |
| 外键数量 | 42 | 42 | PASS |
| 外键使用RESTRICT | 42 | 42 | PASS |
| CHECK约束数量 | 69 | 69 | PASS |
| 唯一约束数量 | 20 | 20 | PASS |
| 表存储引擎为InnoDB | 20 | 20 | PASS |
| 表排序规则为utf8mb4_0900_ai_ci | 20 | 20 | PASS |

最终表包括：

```text
actors
companies
data_quality_issues
directors
drama_actors
drama_companies
drama_directors
drama_metric_snapshot_revisions
drama_metric_snapshots
drama_platforms
drama_scores
drama_tags
dramas
import_batches
import_errors
import_jobs
operation_logs
platforms
tags
users
```

`import_batches`、`import_jobs`、`import_errors`及`drama_scores`均存在，V007和V008的业务对象同时可用。

### 3.2 V007字段验证

`import_batches`实际创建15个字段：

- `import_batch_id`为`BIGINT UNSIGNED AUTO_INCREMENT`。
- `batch_code`、`status`、`created_by_user_id`符合候选SQL定义。
- 文件及行数统计使用无符号`INT/BIGINT`并默认0。
- 四个阶段时间字段均为可空`DATETIME(6)`。
- `created_at`和`updated_at`均为`DATETIME(6)`；`updated_at`具有`ON UPDATE CURRENT_TIMESTAMP(6)`。

`import_jobs`成功增加：

- `import_batch_id BIGINT UNSIGNED NULL`
- `batch_sequence SMALLINT UNSIGNED NULL`
- `batch_file_type VARCHAR(32) NULL`

三个字段均为NULL的既有单文件Import Job插入成功；三个字段完整且合法的批次Import Job插入成功，证明迁移保持向后兼容。

### 3.3 外键验证

| 外键 | 源字段 | 目标 | UPDATE | DELETE | 结果 |
|---|---|---|---|---|---|
| `fk_import_batches_user` | `import_batches.created_by_user_id` | `users.user_id` | RESTRICT | RESTRICT | PASS |
| `fk_import_jobs_batch` | `import_jobs.import_batch_id` | `import_batches.import_batch_id` | RESTRICT | RESTRICT | PASS |
| `fk_import_errors_job` | `import_errors.import_job_id` | `import_jobs.import_job_id` | RESTRICT | RESTRICT | PASS |
| `fk_drama_scores_drama` | `drama_scores.drama_id` | `dramas.drama_id` | RESTRICT | RESTRICT | PASS |

专项行为验证确认：孤立批次创建人、孤立Import Batch引用、删除被引用批次和删除被引用创建人均被数据库拒绝。

### 3.4 索引与唯一约束验证

| 表 | 名称 | 列顺序 | 类型 | 结果 |
|---|---|---|---|---|
| `import_batches` | `PRIMARY` | `import_batch_id` | 主键 | PASS |
| `import_batches` | `uq_import_batches_code` | `batch_code` | 唯一 | PASS |
| `import_batches` | `idx_import_batches_status_created` | `status, created_at` | 普通索引 | PASS |
| `import_batches` | `idx_import_batches_user_created` | `created_by_user_id, created_at` | 普通索引 | PASS |
| `import_jobs` | `uq_import_jobs_batch_sequence` | `import_batch_id, batch_sequence` | 唯一 | PASS |
| `import_jobs` | `uq_import_jobs_batch_file_type` | `import_batch_id, batch_file_type` | 唯一 | PASS |
| `import_jobs` | `idx_import_jobs_batch_status` | `import_batch_id, status` | 普通索引 | PASS |

同一批次的重复顺序和重复文件类型均被数据库拒绝；不同单文件任务的NULL批次字段可正常共存。

### 3.5 CHECK约束验证

information_schema确认以下V007约束均存在且`ENFORCED = YES`：

- `chk_import_batches_code`
- `chk_import_batches_status`
- `chk_import_batches_row_totals`
- `chk_import_batches_validation_times`
- `chk_import_batches_completion_time`
- `chk_import_jobs_batch_fields`

V007专项数据库行为用例结果：

| 类别 | 覆盖内容 | 通过数 |
|---|---|---:|
| CHECK | 空白批次编码、非法状态、非法行数、非法验证时间、非法完成状态、批次字段不完整、顺序非正数、非法文件类型 | 8/8 |
| UNIQUE | 重复批次编码、重复批次顺序、重复批次文件类型 | 3/3 |
| FOREIGN KEY / RESTRICT | 孤立创建人、孤立批次引用、删除被引用批次、删除被引用创建人 | 4/4 |
| 合计 | V007专项约束行为 | **15/15** |

项目已有`database/tests/constraint_test.sql`也在V001—V008完整schema上执行成功：

```text
42 passed / 0 failed
```

测试事务回滚后，约束测试用户和短剧fixture持久化数量均为0。

## 4. ORM一致性结果

### 4.1 自动对比范围

通过SQLAlchemy Inspector读取隔离MySQL的真实结构，并与当前SQLAlchemy metadata逐项比较：

- 列集合
- MySQL列类型
- 可空性
- 主键列
- 外键名称、列、目标表/字段及RESTRICT规则
- 唯一约束名称和列顺序
- CHECK约束名称
- 普通索引名称和列顺序
- `import_batches`默认状态及统计字段默认值

### 4.2 对比结果

| 表 | 列 | 主键 | 外键 | 唯一约束 | CHECK | 普通索引 | 差异 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `import_batches` | 15 | 1 | 1 | 1 | 5 | 2 | 0 |
| `import_jobs` | 18 | 1 | 2 | 2 | 7 | 4 | 0 |
| `import_errors` | 8 | 1 | 1 | 0 | 3 | 2 | 0 |

结论：V007创建和修改的数据库结构与`ImportBatch`、`ImportJob` ORM完全一致；既有`ImportError`结构未被V007改变，且仍与ORM一致。

### 4.3 测试结果

| 测试 | 结果 |
|---|---|
| ORM metadata专项测试：`pytest tests/test_models_import.py` | **3 passed in 0.38s** |
| 后端完整测试：`pytest` | **157 passed in 6.10s** |

现有后端测试未受V007完整schema验证影响。本次没有修改测试代码，也没有将测试缓存加入Git。

## 5. 最终建议

### 5.1 是否允许提交V007

最终验证结论：**允许将当前候选V007恢复并提交为正式Migration。**

批准对象必须是本次验证的原始文件：

```text
database/migrations/V007__create_import_batches.sql
SHA-256: 8ABDF22EED6B9E635BB20D1DDCBA4EC37BCA4F6038F7E77C2D18FF5A1751005F
```

依据如下：

1. SQL静态规范与V001—V008现有风格一致。
2. 空白MySQL 8.0.45实例中V001—V008完整迁移链全部成功。
3. 最终表、字段、外键、索引和CHECK约束符合候选设计。
4. V007专项数据库行为验证15/15通过。
5. 项目既有数据库约束回归42/42通过。
6. 数据库物理结构与三个Import相关ORM表0差异。
7. ORM metadata测试和完整后端pytest全部通过。
8. V007与V008不存在覆盖或执行顺序冲突。

### 5.2 恢复提交要求

下一阶段如获得明确授权，应：

- 仅暂存当前hash对应的`V007__create_import_batches.sql`。
- 使用独立Git提交恢复V007，不混入批量导入代码、V009或其他工作区修改。
- 提交前再次校验SHA-256，防止候选内容在验证后发生变化。
- 提交后确认正式序列为V001—V008连续编号。

### 5.3 部署边界

本结论批准V007进入Git正式历史，并证明其可以安全用于空白MySQL 8.x实例的完整初始化。由于V007使用非幂等`CREATE TABLE`和`ALTER TABLE ADD`，对任何已有数据库执行前仍必须进行只读schema盘点：

- 对象全部不存在：可按正式顺序执行V007。
- 对象完整存在且定义一致：不得重复执行，应建立基线记录。
- 对象部分存在或定义不同：停止执行并制定单独修复方案。

V007正式提交完成前仍不创建V009；本次验证任务本身不提交V007。
