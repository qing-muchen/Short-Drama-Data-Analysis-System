# Phase 2 V007 Migration Recovery Review

> 审查范围：候选 `database/migrations/V007__create_import_batches.sql`、当前 Git HEAD、工作区内与批量导入相关的 ORM、Repository、Service、Router、Schema、测试及前端引用。本文只记录静态审查结论，不修改 V007 SQL、不执行 Migration、不创建 V009、不修改 ORM 或业务代码。

## 1. Candidate V007 Summary

### 1.1 文件信息

| 项目 | 审查结果 |
|---|---|
| 文件名 | `V007__create_import_batches.sql` |
| 相对路径 | `database/migrations/V007__create_import_batches.sql` |
| 文件大小 | 2915 bytes |
| 行数 | 46行 |
| 文件系统创建时间 | 2026-09-09 17:08:51 +08:00 |
| 文件系统最后修改时间 | 2026-09-09 17:08:51 +08:00 |
| SHA-256 | `8ABDF22EED6B9E635BB20D1DDCBA4EC37BCA4F6038F7E77C2D18FF5A1751005F` |
| Git工作区状态 | 未跟踪（`??`） |
| Git HEAD状态 | 不存在 |
| 全部可见Git历史 | 未发现该文件的提交记录 |

文件系统时间只能说明当前文件副本的本地元数据，不能证明创建者、评审过程、执行时间或发布状态。SHA-256仅用于标识本次审查所见的候选内容，不代表该内容已经获批。

### 1.2 创建内容概览

候选V007包含两个数据库动作：

1. 新建批量导入编排表`import_batches`，保存批次编码、状态、创建人、文件/行数统计以及验证、导入、完成时间。
2. 扩展既有`import_jobs`，增加批次归属、批次内顺序和批次文件类型，使多个单文件任务可以被一个批次编排。

其业务意图是保留现有单文件Import Job能力，并在其上增加四类CSV文件的批量、依赖顺序导入能力。

### 1.3 依赖前提

候选V007的直接前置依赖为：

- V001创建的`users`，供`import_batches.created_by_user_id`引用。
- V004创建的`import_jobs`，供V007执行`ALTER TABLE`。

V002、V003、V005和V006不是候选SQL的直接DDL依赖，但属于当前正式基线的一部分。候选SQL不引用V008创建的`drama_scores`。

## 2. SQL Analysis

### 2.1 `import_batches`表

#### 字段

| 字段 | 类型与空值 | 默认值 | 用途 |
|---|---|---|---|
| `import_batch_id` | `BIGINT UNSIGNED NOT NULL AUTO_INCREMENT` | 无 | 主键 |
| `batch_code` | `VARCHAR(64) NOT NULL` | 无 | 批次业务编码 |
| `status` | `VARCHAR(32) NOT NULL` | `CREATED` | 批次状态 |
| `created_by_user_id` | `BIGINT UNSIGNED NOT NULL` | 无 | 批次创建人 |
| `total_files` | `INT UNSIGNED NOT NULL` | `0` | 文件总数 |
| `total_rows` | `BIGINT UNSIGNED NOT NULL` | `0` | 总行数 |
| `valid_rows` | `BIGINT UNSIGNED NOT NULL` | `0` | 可导入行数 |
| `error_rows` | `BIGINT UNSIGNED NOT NULL` | `0` | 错误行数 |
| `imported_rows` | `BIGINT UNSIGNED NOT NULL` | `0` | 已导入行数 |
| `validation_started_at` | `DATETIME(6) NULL` | `NULL` | 验证开始时间 |
| `validated_at` | `DATETIME(6) NULL` | `NULL` | 验证结束时间 |
| `import_started_at` | `DATETIME(6) NULL` | `NULL` | 导入开始时间 |
| `completed_at` | `DATETIME(6) NULL` | `NULL` | 终态完成时间 |
| `created_at` | `DATETIME(6) NOT NULL` | 当前时间 | 创建时间 |
| `updated_at` | `DATETIME(6) NOT NULL` | 当前时间并自动更新 | 修改时间 |

#### 主键、外键与唯一约束

- 主键：`PRIMARY KEY (import_batch_id)`。
- 唯一约束：`uq_import_batches_code (batch_code)`。
- 外键：`fk_import_batches_user`，`created_by_user_id`引用`users.user_id`。
- 外键更新和删除策略均为`RESTRICT`，与当前项目外键风格一致。

#### CHECK约束

- `chk_import_batches_code`：批次编码去除首尾空格后必须非空。
- `chk_import_batches_status`：状态限定为`CREATED`、`UPLOADING`、`VALIDATING`、`READY`、`IMPORTING`、`COMPLETED`、`VALIDATION_FAILED`、`IMPORT_FAILED`。
- `chk_import_batches_row_totals`：`valid_rows + error_rows <= total_rows`，且`imported_rows <= valid_rows`。小于而非等于允许记录“已识别但跳过”的数据行，与当前批量导入响应中的`skipped_rows`定义一致。
- `chk_import_batches_validation_times`：存在`validated_at`时必须已记录`validation_started_at`。
- `chk_import_batches_completion_time`：存在`completed_at`时状态必须为三个终态之一。

#### 索引

- `idx_import_batches_status_created (status, created_at)`：支持按状态和创建时间查询批次。
- `idx_import_batches_user_created (created_by_user_id, created_at)`：支持按创建人查询批次历史。

### 2.2 对`import_jobs`的修改

#### 新增字段

| 字段 | 类型与空值 | 用途 |
|---|---|---|
| `import_batch_id` | `BIGINT UNSIGNED NULL` | 所属批次 |
| `batch_sequence` | `SMALLINT UNSIGNED NULL` | 批次内处理顺序 |
| `batch_file_type` | `VARCHAR(32) NULL` | 批次文件业务类型 |

三个字段均允许NULL，因此原有单文件Import Job可以继续保持三字段全部为NULL，不要求迁移旧数据。

#### 外键、唯一约束与CHECK约束

- `fk_import_jobs_batch`：`import_batch_id`引用`import_batches.import_batch_id`，更新和删除均为`RESTRICT`。
- `uq_import_jobs_batch_sequence`：同一批次内顺序唯一。
- `uq_import_jobs_batch_file_type`：同一批次内文件类型唯一。
- `chk_import_jobs_batch_fields`：要求三个批次字段要么全部为NULL，要么同时满足批次ID非NULL、顺序非NULL且大于0、文件类型属于`MASTER_DATA`、`DRAMA_TAGS`、`DRAMA_PLATFORMS`、`SNAPSHOT`。

MySQL唯一约束允许包含NULL的多行共存，因此既有单文件任务不会因两个新增唯一约束产生冲突。

#### 索引

- `idx_import_jobs_batch_status (import_batch_id, status)`：支持批次内按任务状态查询。

### 2.3 静态一致性判断

候选SQL与当前工作区ORM在以下项目上逐项一致：

- 表名、列名、MySQL无符号整数类型和可空性。
- 默认状态及全部批次状态枚举。
- 两个外键的名称、引用对象及`RESTRICT`策略。
- 三个唯一约束的名称和列顺序。
- 六个新增CHECK约束的名称和表达式语义。
- 三个新增索引的名称和列顺序。

现有批量导入Service把`SNAPSHOT`映射到既有`import_jobs.import_type = SNAPSHOT`，其余三种文件映射到`MASTER_DATA`，因此没有违反V004对`import_type`的限定。

### 2.4 静态风险与审查边界

- SQL是普通`CREATE TABLE`和`ALTER TABLE ADD`，不具备幂等性；任何环境若已手工执行过全部或部分内容，直接重放都会失败或形成部分状态。
- `total_files`和各行数统计是批次级物化汇总，数据库无法用当前约束自动保证它们始终等于子任务聚合值，完整一致性依赖Service事务。
- 状态和时间约束只验证部分必要关系，例如终态并未被反向要求必须具有`completed_at`。这与当前ORM一致，不属于SQL/ORM漂移，但应纳入数据库行为测试。
- V007没有修改`operation_logs`。当前V005只支持`target_import_job_id`，没有`target_import_batch_id`；当前批量导入Service也未注入`OperationLogRepository`。这是批量导入发布前需要单独确认的审计能力问题，不构成V008依赖，也不应在本次恢复审查中顺带修改V007。
- 本次禁止连接数据库和执行Migration，因此尚未验证MySQL 8.x上的实际DDL执行、CHECK执行行为、重复执行表现和既有数据兼容性。

## 3. Code Dependency Analysis

### 3.1 依赖矩阵

| 层次 | 相关文件或对象 | 与V007的关系 | 当前Git状态 |
|---|---|---|---|
| ORM Model | `backend/models/import_batch.py` / `ImportBatch` | 精确映射`import_batches` | 文件未跟踪 |
| ORM Model | `backend/models/import_job.py` / `ImportJob` | 使用三个新增字段、外键、唯一约束、CHECK和索引 | 已跟踪文件有未提交修改 |
| ORM关系 | `backend/models/user.py`、`backend/models/__init__.py` | 注册`ImportBatch`并建立User/ImportJob双向关系 | 已跟踪文件有未提交修改 |
| Repository | `ImportBatchRepository` | 按ID/编码读取批次并原子变更状态 | 已跟踪文件有未提交修改 |
| Repository | `ImportJobRepository.list_by_batch/get_batch_file` | 直接查询V007新增字段 | 已跟踪文件有未提交修改 |
| Service | `backend/services/batch_import_service.py` / `BatchImportService` | 创建批次、创建批次任务、验证、确认及更新统计/状态 | 文件未跟踪 |
| 批处理核心 | `backend/imports/batch.py` | 识别四类文件并按依赖顺序校验和写入 | 文件未跟踪 |
| Schema | `backend/schemas/import_batch.py` | 状态、文件类型和响应字段与V007对应 | 文件未跟踪 |
| Dependency | `get_batch_import_service` | 组装Batch Service及Repository | 已跟踪文件有未提交修改 |
| Router | `backend/routers/import_batches.py` | 暴露批次创建、上传、验证、确认和详情接口 | 文件未跟踪 |
| Router注册 | `backend/routers/__init__.py` | 注册`/api/v1/import/batches` | 已跟踪文件有未提交修改 |
| 测试 | `backend/tests/test_batch_import.py` | 覆盖识别、依赖顺序、Service流程、失败回滚和路由权限 | 文件未跟踪 |
| ORM测试 | `backend/tests/test_models_import.py` | 将`import_batches`加入20表元数据并更新约束/索引计数 | 已跟踪文件有未提交修改 |
| 前端 | Batch Import API、类型、页面和路由 | 消费批次接口及V007对应字段 | 新文件未跟踪，路由有未提交修改 |

### 3.2 业务调用对应关系

当前工作区内形成了以下依赖链：

```text
Batch Import Router
    ↓
BatchImportService
    ↓
ImportBatchRepository + ImportJobRepository
    ↓
import_batches + import_jobs(V007新增字段)
```

Service使用的状态与V007允许值一致：

```text
CREATED → UPLOADING → VALIDATING → READY → IMPORTING → COMPLETED
                               ↘ VALIDATION_FAILED
                                          ↘ IMPORT_FAILED
```

Service按上传顺序写入`batch_sequence`，按四类文件类型写入`batch_file_type`，并利用唯一约束防止同一批次中的顺序或文件类型重复。Repository查询和状态抢占直接依赖候选V007对象。因此，如果将当前工作区批量导入代码投入运行而未执行V007，ORM查询或写入会因表/列缺失而失败。

### 3.3 测试证据的有效范围

已有相关测试提供了两类证据：

- `test_models_import.py`验证SQLAlchemy元数据中包含`import_batches`，并验证整体外键、CHECK、唯一约束和索引数量变化。
- `test_batch_import.py`通过Fake Session和Fake Repository覆盖四类文件识别、依赖顺序、批次验证、确认、失败状态和事务回滚，并检查批次Router注册及管理员权限。

但这些测试没有创建真实MySQL schema，没有执行候选V007，也没有验证数据库实际拒绝非法值、唯一冲突或外键冲突。因此，它们证明了代码设计意图和ORM内部一致性，不能替代Migration集成测试。

### 3.4 正式版本与工作区的区别

当前Git HEAD中未发现`ImportBatch`、`import_batches`、`import_batch_id`、`batch_sequence`或`batch_file_type`的正式后端实现引用。HEAD中的`ImportBatchWriter`是原有单文件导入写入器的类名，不是V007的批次实体，不能作为V007已经正式发布的证据。

所以应分别判断：

- 当前正式HEAD：不依赖V007，缺失V007不会阻止现有V008评分功能部署。
- 当前未提交工作区：存在一套直接依赖V007的批量导入功能，若该功能计划发布，则必须先恢复并验证V007。

## 4. Migration History Judgment

### 4.1 与V008的关系

结论如下：

- **V008不依赖V007。** V008只创建`drama_scores`，唯一外键引用V001的`dramas`。
- **V008没有覆盖V007。** V008不创建`import_batches`，也不修改`import_jobs`。
- **V007不覆盖V008。** 候选V007不引用`drama_scores`或评分模块。
- **V007缺失不破坏V008的SQL执行。** 在V001—V006已完成的空白环境中，V008可独立创建评分表。
- **V007缺失会影响部署一致性。** 包含当前批量导入代码的部署必须具有V007 schema；此外，正式序列跳号会使后续V009的基线含义不确定。

### 4.2 A/B/C判断

| 可能性 | 支持证据 | 反向证据 | 判断 |
|---|---|---|---|
| A. 正式遗漏提交 | 候选SQL与ORM完全对应；Repository、Service、Router、Schema、测试、前端形成完整功能链；相关新文件的本地创建时间集中在同一开发时段；正式V008编号保留了V007位置；没有替代迁移 | SQL及整套批量导入功能均未进入Git历史；没有发布、评审或数据库执行记录 | **最符合现有证据，但只能判定为中等置信度** |
| B. 实验迁移 | 候选SQL和相关业务实现全部处于未提交状态；测试未覆盖真实MySQL；工作区混有多组未完成修改 | 设计已跨越全栈并与ORM精确对齐，不像孤立SQL草稿 | **仍有合理可能，正式确认前必须按候选版本管理** |
| C. 废弃迁移 | 未进入Git历史可能意味着未采纳 | 工作区仍存在大量主动引用；没有删除、替代、废弃说明或反向迁移 | **现有证据不支持，可能性最低** |

综合判断：候选V007**更可能是与批量导入功能共同开发、但遗漏正式归档的迁移**，而不是已被替代或明确废弃的迁移。但Git和文件系统都无法证明产品验收、代码评审或数据库验证已经完成，因此不能把“最可能为A”直接等同于“可以立即提交或执行”。

## 5. Recovery Recommendation

### 5.1 推荐恢复路径

建议保留当前文件名和版本号，将该候选作为V007唯一恢复候选；在获得后续实现授权后，按以下顺序处理：

1. 固定并复核本次候选hash，确认后续验证对象仍为`8ABDF22EED6B9E635BB20D1DDCBA4EC37BCA4F6038F7E77C2D18FF5A1751005F`。
2. 由项目负责人确认批量导入模块需要进入正式发布基线，排除“已废弃但遗留在工作区”的可能。
3. 对每个需保留的开发、测试、演示或生产数据库执行只读schema盘点，确认`import_batches`、三个新增列、外键、约束和索引是不存在、完整存在还是部分存在。
4. 在隔离MySQL 8.x数据库中验证`V001 → … → V006 → 候选V007 → V008`完整顺序，包括干净安装、既有单文件Import Job兼容、外键、唯一约束、CHECK约束和批次状态更新。
5. 确认批量导入操作审计策略：继续以Import Job作为日志目标，或在后续独立设计中增加批次级日志目标；不要在恢复V007时顺带扩展无关表。
6. 验证通过后，以独立提交恢复V007；不得与V009、Phase 2数据质量表或其他工作区修改混合提交。
7. V007进入Git正式历史且目标环境基线处理方案明确后，才允许创建V009。

### 5.2 不同数据库状态的处置原则

| 环境盘点结果 | 推荐处置 |
|---|---|
| 表、列及约束全部不存在 | 在隔离验证通过后按正式顺序执行V007 |
| 所有对象完整存在且与候选一致 | 不重复执行；建立人工基线记录并保存结构比对证据 |
| 仅存在部分对象 | 停止执行，制定一次性修复方案；不得直接重放非幂等V007 |
| 对象存在但定义不同 | 停止恢复，先完成差异审查和数据影响评估 |
| 无法访问或确认环境 | 该环境不得宣称已完成V007恢复 |

### 5.3 不推荐方案

- 不应把V008重编号为V007。V008已正式归档，且业务职责与V007不同。
- 不应在V009中复制V007内容或绕过缺口，这会使不同环境得到不可比较的基线。
- 不应直接创建空V007。当前存在完整的批量导入依赖证据；只有产品明确废弃该模块且所有环境确认未执行候选SQL时，空迁移才可重新评估。
- 不应因为关联代码“看起来完整”就直接执行候选SQL；真实MySQL验证和环境盘点不可省略。

## 6. Final Decision

### 6.1 是否允许恢复V007

最终结论：**允许有条件恢复V007；当前不允许直接恢复。**

“允许有条件恢复”表示：

- 静态架构审查未发现V007与V001—V006、V008或对应ORM之间的职责冲突。
- V007补充的是独立、可解释且被当前批量导入实现直接引用的schema能力。
- 当前候选是恢复正式V007的首选内容，不需要通过重编号V008解决序列问题。

“当前不允许直接恢复”表示：

- 尚未确认批量导入功能的正式发布决策。
- 尚未检查任何实际数据库是否已执行全部或部分候选内容。
- 尚未在隔离MySQL 8.x中执行并验证V001—V008完整序列。
- 尚无证据证明候选SQL已通过正式评审或发布验收。

因此，本审查批准候选V007**进入独立恢复验证阶段**，不批准在本任务中执行`git add`、提交或运行该迁移。

### 6.2 对V009的决定

**V009继续保持阻塞。** 只有同时满足以下条件后才可解除：

1. 批量导入模块确认保留。
2. 候选V007通过隔离MySQL验证。
3. 各目标数据库完成schema盘点并形成对应处置方案。
4. V007以独立提交进入正式Git历史。
5. 正式迁移序列确认为`V001 → V002 → V003 → V004 → V005 → V006 → V007 → V008`。

在此之前，不创建、不执行Phase 2 V009。
