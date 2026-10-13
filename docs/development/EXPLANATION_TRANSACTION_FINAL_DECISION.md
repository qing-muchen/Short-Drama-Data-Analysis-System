# Explanation 单事务最终候选决策

| 项目 | 值 |
|---|---|
| 文档版本 | 0.2 |
| Git 基线 | `15b161c09f78b804c42802bc76108613e77d9508` |
| 状态 | **PROPOSED — APPROVAL REQUIRED** |

## 1. 兼容性核验

- ScoreService `calculate_scores()`、PredictionService `calculate_prediction()`、AnomalyService `detect_anomalies()` 与 AnalysisExplanationService 都使用 `with self.transaction()`；`BaseService.transaction()` 成功 commit、异常 rollback（`services/base.py:35-47`）。
- Repository 只 add/execute/flush，不 commit；适合由外层统一事务所有者复用。
- 当前 FastAPI Session 生命周期可为一个请求提供同一 Session，但调用两个提交型 Service 仍会产生两个事务；共享 Session 不等于共享 commit。
- Handler 是纯生成；Explanation Service 在事务前生成并校验，在事务内写 explanation+lineage，当前不校验真实来源。

因此可以在不改变分析算法的前提下引入统一事务，但必须改变既有 Service 的提交职责。推荐独立 Application Workflow，而不是让核心 Service 反向依赖 Explanation Service。

## 2. 推荐事务模型 EX-01

每个生成命令由 Workflow 独占一个 Session/事务：读取并计算 → flush 核心结果取得 PK → 校验完整来源 → 生成并 flush Explanation → 写 Lineage → 写 Operation Log → commit 一次。核心 Service 拆出不提交的内部 operation；原公开读接口不变，原计算 Router 改为调用 Workflow。

API 兼容：成功响应 DTO 保持；业务不足仍按现有 400/业务 reason；identity 内容冲突建议 409；持久化/commit 失败继续由统一异常处理返回脱敏 500。Explanation 成为成功写入的必要组成，因此 Explanation 失败会使整个计算请求失败——这是业务成功语义变化，必须批准。

## 3. 失败路径状态表

| 路径 | Core | Explanation | Lineage | Commit/Rollback | API 候选 |
|---|---|---|---|---|---|
| 计算失败/历史不足 | 无 | 无 | 无 | 无写；事务回滚/结束 | 现有业务 400 reason；不足场景不伪造解释 |
| 核心结果 flush 失败 | 无已提交 | 无 | 无 | rollback | 脱敏 500 |
| Explanation 生成/完整性失败 | 已 flush 未提交 | 无 | 无 | 全 rollback | 422/400 稳定业务码 `EXPLANATION_EVIDENCE_INCOMPLETE` |
| 来源存在性/as-of 校验失败 | 已 flush 未提交 | 无 | 无 | 全 rollback | 409 或稳定 400；推荐 409 |
| Explanation flush 失败 | 已 flush 未提交 | 无已提交 | 无 | 全 rollback | 脱敏 500 |
| Lineage flush 失败 | 已 flush 未提交 | 已 flush未提交 | 无已提交 | 全 rollback | 脱敏 500 |
| Operation log 失败 | 均已 flush未提交 | 已 flush | 已 flush | 全 rollback | 脱敏 500 |
| 最终 commit 失败 | 未确认 | 未确认 | 未确认 | SQLAlchemy rollback；不得报告成功 | 脱敏 500；客户端可用幂等键重试 |
| 完全相同重复请求 | 查到相同 fingerprint/identity | 复用相同 | 集合一致 | 不写或安全提交 | 200，返回既有结果 |
| 同 identity 不同内容 | 保留原记录 | 保留原记录 | 保留原记录 | rollback | 409 Conflict |
| 并发相同请求 | 一方成功；另一方捕获唯一冲突后重读 | 同 | 同 | loser rollback/reload | 内容相同 200；不同 409 |
| 请求取消/超时 | 未 commit 的全部 | 同 | 同 | cancellation 必须向上传播并 rollback；禁止后台继续 commit | 客户端超时；服务端日志记录 request_id |

## 4. 幂等、锁与性能

- 幂等键由完整业务 identity + input/result fingerprint 构成；唯一约束是最终并发防线，不能只做“先查后写”。
- 不对全表加锁；按目标 identity 查询/插入。批量 Score 仍是一条命令，任一 explanation 失败推荐整批回滚。
- 事务会增加来源校验和 lineage insert 时长。Evidence 应在事务前批量读取并在事务中验证 watermark/IDs 未变化；禁止 N+1。若无法确保一致，可在事务内批量锁定所需 revision 行，但需单独压测。
- 不需要任务队列或新通用架构层；一个面向三个命令的薄 Workflow/Unit of Work 是满足“一个提交所有者”的最小入口。

## 5. 旧结果

已持久化旧结果不自动回填 Explanation。它们继续可查询并标记 explanation `NOT_AVAILABLE`；只有显式、受审的历史生成/回填任务获批后才能补建。开发库当前 explanation/lineage 为0，不代表其他环境可忽略该规则。

**EX-01 候选批准文本：**批准单 Session、单 Workflow、单 commit；Explanation/Lineage/日志是计算成功的原子组成；失败全回滚；业务不足不生成；相同请求幂等、不同内容冲突；旧结果不自动回填。

最后结论：**PROPOSED；技术上兼容现有 Repository 和算法，但会改变写 Service 的提交职责与成功语义。**
