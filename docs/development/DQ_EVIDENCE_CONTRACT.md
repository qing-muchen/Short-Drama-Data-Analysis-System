# Data Quality Evidence 与规则初始化契约候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.2 |
| 适用软件版本 | V1.0 maintenance baseline |
| Git 基线 | `15b161c09f78b804c42802bc76108613e77d9508` |
| 设计状态 | **STATUS: PROPOSED — USER APPROVAL REQUIRED** |

## 1. 分层与接口

Design V2 `:506-515, 561-583` 要求 Evidence Repository 批量读取事实，Evaluator 保持纯计算；现有 `RuleEvaluator(rule, context)`（`backend/services/data_quality_service.py:62-70`）尚未接收 evidence。

候选接口：

```text
QualityEvidenceRequest
  score_date, analysis_as_of, scope_type, scope_id
  rule_requirements[]  # 已批准配置的并集，不含可执行代码

QualityEvidenceBundle
  analysis_as_of, source_watermark
  dramas[], releases[], snapshots[], snapshot_revisions[]
  import_jobs[], import_errors[], quality_issues[]
  source_refs[] = {source_type, table_name, primary_key, changed_at/version}
  limitations[]

RuleEvaluator(rule_definition, evaluation_context, evidence_view)
  -> RuleExecutionResult
```

- Repository：只负责一次/少量批量查询、as-of 修订选择和持久化 DTO 映射；不判断 PASS/FAIL，不 commit。
- Service：加载并验证完整规则集、请求 Evidence、调用 evaluator/Calculator、拥有唯一事务和错误映射。
- Evaluator/Analytics：只接受不可变 DTO，确定性计算，不访问 Session/Repository/当前时间。
- 输出：已有 `RuleExecutionResult` 的 status、三计数、rule_score、N/A reason、受控 evidence summary；B2 应增加结构化 `source_refs` 供解释/审计，而不是只保存自由文本。

## 2. 权威来源映射

| 事实 | 表/主键 | as-of/版本规则 | 限制 |
|---|---|---|---|
| 短剧主数据 | `dramas.drama_id` | 只纳入 `created_at <= analysis_as_of`（如字段存在） | 主数据并非完整双时态；不能保证修正后的历史重放 |
| 发布关系 | `drama_platforms` 的关系主键 | 只纳入截点前可见关系 | 更新历史是否可重放需按实际时间字段验证 |
| 快照槽位 | `drama_metric_snapshots.snapshot_id` | `snapshot_time <= analysis_as_of` | `current_revision_id` 只能代表当前，不可直接用于历史 as-of |
| 快照修订 | `drama_metric_snapshot_revisions.snapshot_revision_id` | 每个 snapshot 选 `changed_at <= analysis_as_of` 的最大 `(changed_at, revision_id)` | 若可见最新修订为 VOID，该槽位无有效值，禁止回退到更老 revision；规则仍可把“无有效值”计为失败 |
| Import | `import_jobs.import_job_id`、`import_errors.import_error_id` | 使用批准的统计窗口且不晚于 as-of | 错误与 quality issue 必须用去重键避免双扣 |
| 持续质量问题 | `data_quality_issues.quality_issue_id` | 截点下状态/发生时间口径必须逐规则冻结 | 当前评分 Service 的 `open_issue_count=0` 是占位行为（`:177-195`） |

Prediction Service 已实现“可见 VOID 不回退”模式（`backend/services/prediction_service.py:274-311`），可复用其语义但不得复制数据库访问进 evaluator。`source_watermark` 至少记录各来源最大可见主键/时间和非双时态限制；Design V2 `:346-351` 明确只承诺已保存结果/证据可追溯，不承诺任意历史完全重放。

## 3. 缺失与不一致处理

- 必需事实缺失：Evaluator 返回 APPLIED/FAIL（或 0 分），不是 N/A。
- 业务域真正不适用：仅在规则配置明确的适用条件不成立时 N/A，并给非空 reason。
- 修订链损坏、重复权威记录、来源版本晚于 as-of：Evidence Repository 返回稳定契约错误，整次评分回滚；不得任选一条继续。
- 非法配置、未知 evaluator、规则集缺维度：计算前失败，不持久化。
- 批量结果必须带稳定排序，hash 不受数据库返回顺序影响。

### 3.1 修订选择最终候选

- `changed_at` 表示修订对系统可见的业务变更时间；as-of 边界为包含关系 `changed_at <= analysis_as_of`。
- 同一 snapshot 的候选修订先按 `changed_at`、再按自增 `snapshot_revision_id` 排序。ID 仅作为相同时间戳的确定性技术 tie-breaker，不替代 `version_no` 链合法性校验。
- 同时间戳出现多个修订不是自动错误；选择最大 ID，同时 K2 必须验证 version/previous 链。链冲突则 Evidence error，不能任选结果继续评分。
- 重复 snapshot 由业务键 `(drama_platform_id,snapshot_time)` 去重并应受现有唯一约束；检测到重复物理 slot 时整次失败。
- 截点前没有修订：该 expected slot 缺失；截点下最新为 VOID：slot 明确失效且不得回退；revision 行不存在/被删除：`EVIDENCE_REVISION_MISSING`。
- 不连续窗口：对 C4/T1 按各自规则计缺失/桶分；对要求连续链的 evaluator 返回明确失败，禁止插值或补零。

### 3.2 可支持的历史能力

严格支持：保留的 snapshot/revision 在给定 as-of 下的可见选择、VOID、链和指标值。有限支持：import 事实及其当时状态，取决于相应行是否不可变保留。不能严格保证：drama、platform、drama_platform 等非完整双时态主数据在过去截点的状态。

历史新计算必须在 `source_watermark` 标记 `LIMITED_CURRENT_MASTER`，不能宣称完全重放；已有持久化评分按其保存的 as-of、rule set/hash 和 Evidence 摘要查询。相同历史 identity 已存在时优先幂等返回，不使用今天的主数据静默覆盖。

## 4. 初始化与版本管理候选（DQ-04）

Design V2 `:317-324` 要求 V1 规则由受审查的数据 Migration 发布，不开放在线写接口；现仓库没有 migration history 表，也不应修改 V009。推荐批准后采用**独立、仓库版本化、显式执行的 Seed 命令**，而非 FastAPI 启动写入：

1. 规则清单以不可变配置文件随代码审查；稳定业务键为 `(rule_code, rule_version)`，数字 PK 只作内部引用。
2. 命令提供 `--check`（默认只读）与显式 `--apply`；限定目标 DB 名并输出脱敏差异。
3. 一次事务校验完整四维集合：不存在则插入；字段完全一致则 no-op；同键不同内容则中止，禁止 `ON DUPLICATE KEY UPDATE` 静默改历史。
4. 新语义创建新 `rule_version`；规则集成员/权重改变发布新 `rule_set_version`；旧 ACTIVE 在同一事务转 INACTIVE，历史行保留。
5. 生产、开发、验收分别显式执行，不跨库复制；执行者、配置 SHA-256、目标环境和结果写入现有 operation log（能满足契约时）。
6. 失败回滚；若 DDL/新表成为必要项，另提新 Migration，不修改 V001–V013。

与“数据 Migration”文字的差异需用户裁决：本建议用 Seed 命令获得幂等检查、dry-run 和环境保护；若用户要求纯 SQL，则新增独立、不可变的后续 data migration，并配套外部执行记录。两者当前均未实施。

## 5. 未解决问题

- 16 个候选规则的精确证据字段/窗口/分母尚未批准，Repository DTO 不能最终冻结。
- 主数据缺少双时态能力；推荐在 V1 文档/响应 watermark 中披露限制，不为 DQ 单独重构主数据。
- 是否扩展 rule result 保存结构化来源 ID；现有表只有 `evidence_summary`，若要求逐来源持久化可能需要新表，属于 **BREAKING CHANGE — APPROVAL REQUIRED**。

最后审查结论：**职责边界可冻结；具体 DTO 字段须在 DQ-01/DQ-03 批准后定稿。**
