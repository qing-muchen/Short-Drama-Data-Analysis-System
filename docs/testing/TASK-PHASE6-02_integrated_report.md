# TASK-PHASE6-02 综合报告（Integrated Report V1.0）

本报告整合 TASK-PHASE6-02 三个阶段（A/B/C）的完整结果：

- A：Simulation Dataset Generator + Clean Base Dataset
- B：异常注入与数据质量场景生成
- C：Import 系统真实导入与 MySQL 验证

## 1. 阶段 A — Clean Base Dataset

- 固定 seed：`20260907`
- `simulation_as_of`：`2026-09-07T22:00:00+08:00`
- 时间窗口：连续 90 天（2026-06-10 ~ 2026-09-07），每日 4 时点（08:00/12:00/18:00/22:00）
- 生成器：`simulation/generators/clean_base_generator.py`
- Profile：`simulation/profiles/development_demo.json`

Clean Base 实测规模：

| 对象 | 数量 | 冻结目标 |
| --- | ---: | --- |
| Drama | 100 | 100 |
| Actor | 400 | 约 400 |
| Director | 100 | 100 |
| Company | 70 | 70 |
| Platform | 8 | 8 |
| Tag | 24 | 24 |
| DramaPlatform | 215 | 约 205～215 |
| DramaTag | 264 | 约 250～350 |
| DramaActor | 792 | 约 700～900 |
| DramaDirector | 110 | 约 110～120 |
| DramaCompany | 251 | 约 200～300 |
| Snapshot | 71,456 | 70,000～80,000 |

- Drama 状态：DRAFT 5 / SERIALIZING 25 / COMPLETED 60 / INACTIVE 10
- 增长曲线：爆发 14（约15%）/ 稳定 43（约45%）/ 衰退 19（20%）/ 低迷 19（20%）
- 分层：头部 10 / 中腰部 30 / 长尾 60
- 确定性：同 seed 重复生成，全部 CSV SHA-256 一致

## 2. 阶段 B — 异常注入

- 注入器：`simulation/injectors/injector.py`（配置 `config.py`）
- 原则：从 Clean Base 注入，不覆盖 Clean Base，输出到 `simulation/output/injected/`
- 固定 seed：`20260907`

| 异常类型 | 数量 | 注入规则 |
| --- | ---: | --- |
| duplicate_snapshot | 400 | 追加完全相同的 `(drama_code, platform_name, snapshot_time)` 行 |
| missing_engagement | 500 | `like_count`/`comment_count` 或 `favorite_count`/`share_count` 置 NULL |
| invalid_ranking | 300 | `ranking` 置 0(100) / -1(100) / 9999 超平台数量(100) |
| future_timestamp | 200 | `snapshot_time` 移到 2026-09-08（晚于 simulation_as_of，每行唯一） |
| abnormal_growth | 300 | 相对同 DramaPlatform 前一条快照异常拉高 play/互动 |

- 受影响行数：1,700 / 71,456 = **2.38%**（目标 1%–3%，上限 5%）
- 注入后快照行数：71,856（+400 重复行）
- 确定性：重复运行注入器，`injected/` 输出逐文件一致；Clean Base 注入前后逐文件一致
- 清单：`simulation/output/injected/inject_manifest.json`（类型、数量、比例、受影响记录 business key 与规则）

## 3. 阶段 C — Import 真实导入与 MySQL 验证

- 数据库：本机 MySQL Community Server 8.0.45（`short_drama_analysis`，通过 DDL 001~007 建库建表，18 表就绪）
- backend：venv Python 3.12.14 + `uvicorn main:app --port 8000`，`/health` 200
- 凭证：仅写入 `backend/.env`（gitignored，未提交、未写入任何源码/报告/example）
- 引导 ADMINISTRATOR 用户：bcrypt 哈希由 backend `auth.password.hash_password` 生成并手工 INSERT

ImportJob 结果：

| Job | 文件 | 类型 | 状态 | total | valid | error | imported |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | master_data.csv | MASTER_DATA | COMPLETED | 702 | 702 | 0 | 702 |
| 2 | snapshots_part1.csv | SNAPSHOT | COMPLETED_WITH_ERRORS | 50,000 | 47,450 | 2,550 | 47,450 |
| 3 | snapshots_part2.csv | SNAPSHOT | COMPLETED_WITH_ERRORS | 21,856 | 16,673 | 5,183 | 16,673 |
| 4 | future_timestamp_validation.csv | SNAPSHOT | VALIDATION_FAILED | 2 | 0 | 2 | 0 |

ImportError 汇总（7,733 + 2）：

| error_code | 数量 | 来源 |
| --- | ---: | --- |
| INACTIVE_REFERENCE | 6,726 | INACTIVE 短剧历史快照（Import 校验按设计拒绝） |
| MISSING_REQUIRED_DATA | 463 | 缺失互动指标注入 |
| INVALID_RANKING | 182 | ranking=0/-1/9999 注入 |
| CONFLICTING_SNAPSHOT | 273 | 跨文件重复键冲突 |
| DUPLICATE_RECORD | 89 | 同文件重复快照注入 |
| INVALID_TIMESTAMP | 2 | 独立 2027 年未来时间验证文件 |

数据库结果（导入后）：

| 表 | 行数 |
| --- | ---: |
| dramas / actors / directors / companies / platforms / tags | 100 / 400 / 100 / 70 / 8 / 24 |
| drama_platforms | 215 |
| drama_tags / drama_actors / drama_directors / drama_companies | 264 / 792 / 110 / 251 |
| drama_metric_snapshots | 64,123 |
| drama_metric_snapshot_revisions | 64,123（全部 INITIAL） |
| import_jobs / import_errors | 4 / 7,735 |
| data_quality_issues | 0（待 Analytics 阶段生成） |

## 4. 关键验证结论

- Clean Base 生成可复现（SHA-256 一致）→ PASS
- 异常注入可复现、比例 2.38% → PASS
- ImportJob 状态流转（READY → COMPLETED / COMPLETED_WITH_ERRORS / VALIDATION_FAILED）→ PASS
- ImportError 六类错误码均有真实来源 → PASS
- Snapshot INITIAL Revision 正常生成（64,123/64,123）→ PASS
- DataQualityIssue：导入阶段不生成，需 Analytics/Quality 阶段（按指令未进入）→ 记录延后

## 5. 发现的问题（真实记录）

1. 大文件确认事务耗时超过 120s：Job 2 客户端超时但服务端事务最终提交成功；后续脚本改用 600s 超时。
2. 注入的 future_timestamp 相对 `simulation_as_of` 为未来，但相对真实导入 `received_at` 不是未来，未触发 INVALID_TIMESTAMP；已用 2027 年样例（Job 4）补齐该错误路径。
3. INACTIVE_REFERENCE 在 Import 校验中优先于字段级校验，部分 missing/ranking 注入在 INACTIVE 短剧上表现为 INACTIVE_REFERENCE。
4. DataQualityIssue 不在 Import 阶段生成，留待 Analytics/Quality 阶段。

## 6. 文件清单

- `simulation/generators/clean_base_generator.py`（阶段 A）
- `simulation/profiles/development_demo.json`（阶段 A）
- `simulation/output/*.csv` + `dataset_manifest.json`（阶段 A 输出）
- `simulation/injectors/config.py`、`injector.py`、`README.md`（阶段 B）
- `simulation/output/injected/*`（阶段 B 输出，含 `inject_manifest.json`）
- `simulation/import_prep.py`、`run_import_flow.py`（阶段 C 准备/执行脚本）
- `docs/testing/full_flow_validation_report.md`、`full_flow_validation_report.json`（阶段 C 报告）
- `backend/.env`（本地配置，gitignored，未提交）

## 7. Git 状态

- 未提交 Git（等待统一提交）。
- 未跟踪：`simulation/`、`docs/testing/full_flow_validation_report.*`、`reasonix.toml`、`.reasonix/`。
- `backend/.env` 已确认被 gitignore 忽略。
