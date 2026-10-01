# TASK-PHASE6-02-C Import 系统真实导入与 MySQL 验证报告

- 日期：2026-09-08
- 数据源：`simulation/output/injected/`（Simulation Dataset V1 + 异常注入）
- 后端：FastAPI（本地 venv Python 3.12.14，`uvicorn main:app --port 8000`）
- 数据库：本机 MySQL Community Server 8.0.45（`short_drama_analysis`，18 张物理表）
- 凭证：仅写入 `backend/.env`（gitignored，未提交，未写入示例文件或任何源码/报告）

## 1. MySQL 环境

- 连接验证：`mysql --host=127.0.0.1 --port=3306 --user=root` 成功，`VERSION() = 8.0.45`
- 通过 `database/ddl/001_create_database.sql` ~ `007_create_indexes.sql` 建库建表（7 个文件全部执行成功，18 张表就绪）
- 引导账号：`users` 表手工插入 ADMINISTRATOR 用户（bcrypt 哈希由 backend `auth.password.hash_password` 生成；密码仅存于 `backend/.env`）

## 2. Import 流程（真实 API）

使用已有 Import System，未修改 backend/imports 任何代码：

| Job | 文件 | 类型 | 结果 |
| --- | --- | --- | --- |
| 1 | master_data.csv（702 行） | MASTER_DATA | READY → COMPLETED，导入 702 |
| 2 | snapshots_part1.csv（50,000 行） | SNAPSHOT | READY → COMPLETED_WITH_ERRORS，导入 47,450，错误 2,550 |
| 3 | snapshots_part2.csv（21,856 行） | SNAPSHOT | READY → COMPLETED_WITH_ERRORS，导入 16,673，错误 5,183 |
| 4 | future_timestamp_validation.csv（2 行，2027 年未来时间） | SNAPSHOT | VALIDATION_FAILED，错误 2（INVALID_TIMESTAMP） |

说明：Import Service 的确认事务在真实 MySQL 上逐行写入，Job 2 的 47,450 行确认耗时超过 HTTP 客户端默认 120s 超时（服务端事务最终成功提交）。后续 Job 3 使用 600s 超时正常完成。

## 3. ImportJob 结果

| import_job_id | import_type | status | total_rows | valid_rows | error_rows | imported_rows |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 1 | MASTER_DATA | COMPLETED | 702 | 702 | 0 | 702 |
| 2 | SNAPSHOT | COMPLETED_WITH_ERRORS | 50,000 | 47,450 | 2,550 | 47,450 |
| 3 | SNAPSHOT | COMPLETED_WITH_ERRORS | 21,856 | 16,673 | 5,183 | 16,673 |
| 4 | SNAPSHOT | VALIDATION_FAILED | 2 | 0 | 2 | 0 |

## 4. ImportError 验证

总错误数：7,733（Job 2/3）+ 2（Job 4）= 7,735。

| error_code | 数量 | 来源 |
| --- | ---: | --- |
| INACTIVE_REFERENCE | 6,726 | INACTIVE 短剧的历史快照（Import 校验按设计拒绝当前非活跃引用） |
| MISSING_REQUIRED_DATA | 463 | 缺失互动指标注入（部分缺失行因命中 INACTIVE_REFERENCE 优先计为该类） |
| INVALID_RANKING | 182 | ranking=0/-1/9999 注入（部分行同受 INACTIVE_REFERENCE 优先） |
| CONFLICTING_SNAPSHOT | 273 | 跨文件重复快照（part2 重复行与 part1 已导入键冲突） |
| DUPLICATE_RECORD | 89 | 同文件内重复快照注入 |
| INVALID_TIMESTAMP | 2 | 独立未来时间验证文件（2027-01-01） |

发现（真实记录）：注入的 200 条 `future_timestamp`（2026-09-08T00:00~03:19+08:00）相对 `simulation_as_of` 是未来时间，但真实导入发生在本机时间 2026-09-08 晚些时候，Import 校验以 `received_at` 为准，因此这些行被当作有效行导入。为验证 `INVALID_TIMESTAMP` 错误路径，额外用 2027 年时间创建 Job 4，得到 2 条 INVALID_TIMESTAMP 错误。后续 Analytics as-of 语义若与导入时刻存在偏差，需要在 Analytics 阶段记录。

## 5. Snapshot 验证

- `drama_metric_snapshots` 总数：64,123
- `drama_metric_snapshot_revisions` 总数：64,123，全部为 `INITIAL`（`version_no=1`，`previous_revision_id IS NULL`）
- 说明：Observation Slot + Revision 模型下，Import 确认写入为每个快照创建一条 INITIAL revision，符合冻结 Schema。

## 6. DataQuality 验证

- `data_quality_issues` 表存在，导入后行数：**0**
- 原因：Import System 只负责 Stage 1 校验与正式写入，不生成 DataQualityIssue；数据质量治理（CUMULATIVE_REGRESSION、STATISTICAL_SPIKE 等 WARNING）由 Analytics/Quality 服务在分析读取阶段计算。本 Task 按要求不进入 Dashboard/Analytics 验证，因此质量治理留待后续阶段。

## 7. 数据库结果（导入后计数）

| 表 | 行数 |
| --- | ---: |
| dramas | 100 |
| actors | 400 |
| directors | 100 |
| companies | 70 |
| platforms | 8 |
| tags | 24 |
| drama_platforms | 215 |
| drama_tags | 264 |
| drama_actors | 792 |
| drama_directors | 110 |
| drama_companies | 251 |
| drama_metric_snapshots | 64,123 |
| drama_metric_snapshot_revisions | 64,123（全部 INITIAL） |
| import_jobs | 4 |
| import_errors | 7,735 |
| data_quality_issues | 0（待 Analytics 阶段） |

## 8. 测试结果

- MySQL 连接：PASS
- backend 启动与 /health：PASS
- MASTER_DATA 导入：PASS（702/702）
- SNAPSHOT 导入（含异常）：PASS（64,123 有效行写入，7,733 行按设计被 ImportError 拦截）
- ImportJob 状态流转：PASS（READY → COMPLETED / COMPLETED_WITH_ERRORS；Job 4 VALIDATION_FAILED 验证纯错误文件）
- ImportError 记录：PASS（6 类错误码均来自异常注入或冻结的 INACTIVE_REFERENCE 规则）
- Snapshot INITIAL Revision：PASS（64,123/64,123）
- DataQualityIssue：按设计延后（导入阶段不生成）

## 9. 发现的问题

1. 大文件确认事务耗时超过 120s（Job 2 客户端超时但服务端成功提交）——后续验证脚本应使用更长 HTTP 超时；这属于验证工具问题，不是后端缺陷。
2. 注入的 `future_timestamp` 相对 `simulation_as_of` 为未来，但相对真实导入 `received_at` 不是未来，未触发 INVALID_TIMESTAMP；已用 2027 年样例文件（Job 4）补齐该错误路径验证。后续若需要，可将 future_timestamp 注入改为相对真实运行时刻的未来时间。
3. INACTIVE_REFERENCE 优先于字段级校验，导致部分 missing/ranking 注入在 INACTIVE 短剧上表现为 INACTIVE_REFERENCE；这是 Import 校验顺序的既有行为，非错误。
4. DataQualityIssue 不在此阶段生成，需 Analytics/Quality 阶段验证。

## 10. Git 状态

- 本阶段未提交 Git（等待统一提交）。
- `backend/.env` 已确认被 gitignore 忽略。
