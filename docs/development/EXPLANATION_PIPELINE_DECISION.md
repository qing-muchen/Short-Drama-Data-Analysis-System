# Explanation Pipeline 事务与结果身份决策候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.1 |
| 适用软件版本 | V1.0 maintenance baseline |
| Git 基线 | `0bd34f44d2f0e8065c22cdc423cf50d1373b8e9a` |
| 设计状态 | **STATUS: PROPOSED — USER APPROVAL REQUIRED** |

## 1. 已核实事实

- 冻结设计选择“分析结果产生时保存 Explanation Snapshot；GET 只读，不隐式重算”（`PHASE6_DATA_LINEAGE_DESIGN_V2.md:24-34`）。
- 同一设计禁止核心业务 Service 与 Explanation Service 互相反向依赖（`:24`）；架构审查建议显式编排（`PHASE6_DATA_LINEAGE_ARCHITECTURE_REVIEW.md:41-55`）。
- `BaseService.transaction()` 在上下文成功时 commit、任意异常 rollback（`backend/services/base.py:20-47`）。Score、Prediction、Anomaly 与 Explanation Service 各自拥有事务；当前 Explanation 只保证 explanation+lineage 原子写入（`backend/services/explanation/service.py:86-128`），没有生产组合入口。
- V013 是弱引用：没有跨模块 FK；Service 当前只校验正整数和枚举，不查来源存在/版本（`database/migrations/V013__create_analysis_explanation_tables.sql:46-81`；validator `:95-107`）。

## 2. 事务方案比较

| 维度 | A 同一事务 + Workflow | B 核心提交后生成 + 可靠恢复 | C GET/按需生成 |
|---|---|---|---|
| 一致性 | 强；结果、操作日志、Explanation、Lineage 全有或全无 | 最终一致；必须显式 pending/failed 状态 | 查询时才有，历史内容受代码/源数据变化影响 |
| 失败传播 | 解释失败使核心写入回滚 | 核心成功，解释失败可重试 | GET 失败影响读取且可能有副作用 |
| 主业务可用性 | Explanation 成为写路径必要条件 | 核心更可用，但短期无解释 | 表面高，违反只读查询 |
| 幂等/并发 | 一个 UoW；数据库唯一约束 + 查询后冲突处理 | 需任务幂等、lease/retry/dead-letter | 并发 GET 争写，复杂且不可预测 |
| 恢复 | 重试整个确定性命令 | 需要可靠 job/outbox 和可观察状态 | 无可靠历史补偿 |
| 性能 | 增加同事务查询/写入时间 | 主事务短；引入队列开销 | 把写开销移到读请求 |
| 现有基础 | 需要拆分 Service 提交所有权，但可复用同一 Session/Repository | 仓库无任务队列、outbox 或 explanation job 表；需新 Migration/worker | 与已冻结 V1 直接冲突 |
| DB 变化 | Pipeline 本身无需新表 | 至少需要可靠任务/outbox 状态表 | 无，但不可接受 |

## 3. 推荐 EX-01

推荐 A：引入**显式 Application Workflow/Unit of Work**，由它成为唯一 commit 所有者；核心 Service 与 Explanation Service 不互相注入。Workflow 使用同一个 SQLAlchemy Session，顺序执行：

```text
validate request / load evidence
BEGIN (Workflow owns transaction)
  persist or resolve immutable core result; flush -> target PK
  validate every source record/version/as-of
  pure Handler generate + validate completeness
  persist Explanation; flush -> explanation PK
  persist Lineage
  persist operation log
COMMIT once
on any error: ROLLBACK once
```

B2 不能在 Workflow 内调用当前 `generate_explanation()` 或核心 `calculate()` 的提交型入口后再继续；必须提取不提交的 transaction-bound operation，或让 Service 支持显式外部 UoW。Repository 仍不得 commit。Handler 可在写事务前纯计算，但其来源验证所依据的读快照必须与写事务一致。

失败语义候选：

- 有核心结果就必须有完整解释和至少一个经验证来源；解释不完整/冲突/来源失效使整个命令失败并回滚。
- 业务上“不产生核心结果”（如 Prediction `INSUFFICIENT_HISTORY`）不生成解释，保留原业务响应，不视为 Pipeline 失败。
- 重复完全相同命令返回同一不可变结果与解释；相同 identity 不同内容返回冲突，不覆盖历史。
- 该选择会提高写路径严格性，但不改变 GET 协议；需用户明确批准。

方案 B 只作为未来候选：若用户要求“核心结果优先成功”，必须先批准 outbox/job 数据模型、状态 API、重试上限、幂等键和运维恢复；不得用捕获异常后静默吞错代替可靠恢复。

## 4. Score / Prediction 重算身份

当前真实行为：

- Score `replace_scope_scores()` 按 drama/date/algorithm/scope delete 后 insert/flush（`backend/repositories/score_repository.py:20-53`）；唯一键不含 `analysis_as_of`（`backend/models/score.py:30-38`）。
- Prediction `replace_prediction()` 按 drama/metric/algorithm/target_date delete 后 insert/flush（`backend/repositories/prediction_repository.py:29-45`）；唯一键也不含 `analysis_as_of`（`backend/models/prediction.py:22-29`）。
- Explanation identity 包含目标物理 PK、as-of 和版本；弱引用不会随上述删除迁移（V013 `:17-20,56-76`）。

| 策略 | 优点 | 不满足项/风险 | 结论 |
|---|---|---|---|
| A 稳定 PK 原地更新 | 无 schema 变化，弱引用不悬空 | 旧解释指向被覆盖的新值，不能证明历史结果；同 PK 多 as-of 语义混乱 | 不推荐作为历史契约 |
| B 不可变版本结果 | 每个解释指向仍存在的确切结果；历史可查询 | 需改变唯一键和写入/查询策略 | **推荐，需批准 Migration** |
| C replace 后迁移/重建引用 | 可沿用结果表唯一键 | 改写旧解释来源，历史含义改变；删除旧解释违反永久保留 | 不推荐 |
| D 保持现状并标记来源失效 | 最小代码改动 | 主动制造不可追溯记录，不满足设计目标 | 不接受 |

## 5. 推荐 EX-02：不可变版本

推荐新 Migration（不得修改 V008/V010）：

1. 将 Score/Prediction 业务唯一键扩展为包含 `analysis_as_of`，保留现有 PK；现有行原位兼容。
2. B2 写路径改为“同一完整 identity 读取并校验内容相同则幂等返回；不同 as-of 插入新版本；同 identity 不同内容冲突”，不再 delete+insert。
3. “当前”查询按 `analysis_as_of DESC, created_at DESC, PK DESC` 选择；历史查询保留所有版本并明确返回 as-of。
4. Explanation 的 `entity_id` 始终引用不可变目标 PK；旧解释继续可查。来源或目标不存在时返回明确 `LINEAGE_SOURCE_MISSING/LINEAGE_TARGET_MISSING`，不伪造、不自动迁移。
5. 对相同历史 `analysis_as_of` 但事实被事后修正的重算，禁止覆盖；若业务需要同 as-of 多次重算，则需新增明确 `result_revision`，这是尚未批准的扩展。

这是 **BREAKING CHANGE — APPROVAL REQUIRED**：需要新 Migration、Repository 查询调整、API 历史语义与测试更新。现有开发数据不回填 Explanation；只对已有结果保留原 PK，迁移前必须备份与演练。

## 6. 未解决问题

- 是否允许同一 `analysis_as_of` 的纠错重算产生新 `result_revision`；现有设计无依据，当前推荐冲突并停止。
- Score 批量中一条解释失败是否回滚整批：为保持一次命令原子性，推荐整批回滚，需批准。
- Anomaly 已以 as-of 进入 identity，仍需定义完全重复请求是幂等返回还是冲突；不得重复插入。

最后审查结论：**推荐单事务 Workflow + 不可变版本结果；两项均等待用户批准。**
