# Phase S5.2-B1.1 Final Design Proposal Review

| 项目 | 值 |
|---|---|
| 文档版本 | 0.1 |
| Git 设计基线 | `15b161c09f78b804c42802bc76108613e77d9508` |
| 正式冻结基线 | `v1.0.0` → `0e350381d1fd7a16eaa9da5cf9bb92c24285c7de` |
| 状态 | **PROPOSED — APPROVAL REQUIRED** |

## 1. 设计证据矩阵

| 主题 | 正式/历史设计证据 | 当前实现/Schema | 测试证明范围 | 收敛结论 |
|---|---|---|---|---|
| DQ 16方向 | Phase2 Design V2 `:396-480` | V009仅提供规则容器 | Mock只证编排 | 16条均已规格化；4条首批 PROPOSED，12条延后 |
| DQ V2公式 | Design V2 `:363-394` | Service保存score但V1 Calculator丢弃 | 向量可区分 | V1 legacy + V2 rule_score |
| DQ版本并存 | Design要求版本/hash | unique含algorithm/rules/hash | Repository测试只证现有replace | Schema足够；replace删除范围不兼容，B2修复 |
| as-of/VOID | Phase2/8/9 revision设计 | Prediction/Anomaly按 `(changed_at,id)` 且VOID不回退 | 现有专项覆盖 | Evidence契约沿用；非双时态主数据只有限重放 |
| Explanation事务 | Phase6结果时生成、GET只读 | 四个Service各自commit，Repo只flush | 仅组件级原子性 | 独立Workflow唯一commit |
| 结果身份 | Phase6历史永久保留 | Score/Prediction delete+insert | Repo测试明确replace | immutable + result revision |
| Lineage source | Phase6弱引用需Service校验 | Governance把 SNAPSHOT id解释为snapshot_id；Handlers自指/空 | 测试只证当前行为 | snapshot_id + 新source_revision_id，完整来源集合 |

## 2. Data Quality 最终候选

候选全集 16 条均保留；首批推荐：

1. `DQ_C_PLAY_COUNT_COVERAGE`：七日 feed/day 播放量覆盖。
2. `DQ_A_CUMULATIVE_NONNEGATIVE`：存在的累计值非负。
3. `DQ_K_REVISION_CHAIN_VALID`：修订链连续且归属正确。
4. `DQ_T_SNAPSHOT_FRESHNESS`：Design V2 既有 bucket，24h expected interval 候选。

理由：每维一条是 Design V2 持久化总分的最低条件；四条均可落到真实 snapshot/revision Evidence。7日、severity、weight=1、非阻断、24h 和 T1 pass threshold=80 仍是 PROPOSED，必须逐项批准。其余12条缺阈值/分母/历史语义或与其他规则重叠，保持 UNRESOLVED/延后。

## 3. Quality Score 与 Evidence

- V1 保持二元语义和历史查询；V2 使用 APPLIED rule_score 加权。
- 维度权重、等级和 HALF_UP 两位沿用已证实设计。
- V2 发布后默认发布组合为 V2 + Rules 1.0；默认历史不混版本，跨版本显式分组且不可直接同比。
- DQ unique 已可区分 V1/V2；无需 DQ Migration。必须先修复 replace 删除条件，否则 V2 会删除同 rule-set 的 V1。
- 修订边界包含 `changed_at == as_of`；同时间以 revision ID 技术定序并验证 version chain；VOID不回退。
- snapshot/revision 可严格按保留记录重放；主数据非双时态，只能记录 LIMITED_CURRENT_MASTER，不得承诺严格历史复现。

## 4. Explanation、结果身份和 Migration

- Workflow 单 Session、单 commit；core/result/log/explanation/lineage全有或全无。
- 业务不足不生成解释；新成功结果不得以 NOT_AVAILABLE 代替完整解释。
- Score/Prediction 增加 result_revision、supersedes、input/result fingerprint；旧行 revision=1、fingerprint NULL。
- 普通重复相同内容幂等，不同内容409；只有管理员显式纠错可插入 revision+1。
- 候选 V014 改结果唯一键/索引，V015 增加 Lineage `source_revision_id` 并为 Score lifecycle 增加 `DRAMA/DRAMA_PLATFORM` 来源类型。这是 **BREAKING CHANGE — HIGH-RISK DDL**，需备份恢复验证和维护窗口。

## 5. 架构兼容性矩阵

| 模块 | 算法 | Service/Repo/ORM/DB | API/前端/历史 | 数据迁移/性能 |
|---|---|---|---|---|
| Composite Score | 不改 | Service拆无commit operation；Repo append；ORM/V014 | current兼容，history加revision语义；Profile选latest | 旧行标rev1；来源采集增加内存/写入 |
| Data Quality | 新增V2，不改V1 | Evidence/Evaluator、精确identity；DB现表足够 | 默认切V2是行为变化；UI显版本 | 无Schema迁移/不回填 |
| Prediction | Moving Average不改 | prepare返回source set；Repo append；ORM/V014 | current兼容；history避免同target混淆 | 旧行rev1；8日source写入增加 |
| Anomaly | 四类规则不改 | internal evidence map；Workflow | API值不变；Explanation完整 | 无结果表Migration；9日多平台source量 |
| Explanation/Lineage | 不计算业务结果 | Handler/Validator/Workflow；V015 | query可增加revision字段；legacy NA | 不回填；lineage行数增长 |
| Drama 360 | 不改 | Provider显式current版本 | 防过期/错版本显示 | 无回填；查询需latest索引 |
| Operation Analytics | 不改 | 指定不可变PK/as-of，不自动latest | 历史来源保持 | 无重算；可能增加join |
| Data Governance | 不改治理规则 | source validator支持revision归属/可见性 | read-only语义不变 | V015后增加校验成本 |
| Reporting/Export | 不改指标 | current subquery/版本过滤 | 导出含algorithm/as-of/revision；禁止重复 | 无重算；需query plan测试 |

## 6. 最终审批决策矩阵

| ID | 背景/确认事实与冲突 | 候选/推荐及理由 | 影响/结果/API/Migration | 风险/工作量 | 可直接批准文本 |
|---|---|---|---|---|---|
| DQ-01 | 16方向、无正式参数；四维无APPLIED不得评分 | 推荐首批C4/A1/K2/T1，12条延后；可验证且覆盖四维 | 产生首批真实分；Seed数据写，无Schema | 参数误批风险；中 | 批准四规则及7日、weight1、severity、非阻断、24h、threshold80 |
| DQ-02 | V1与V2结果显著不同；Schema可并存，replace会误删 | V1 legacy、V2 rule_score；默认发布组合显式配置 | 新结果改变；API默认行为变化；无Migration | 混版风险；中 | 批准V2公式/等级/N/A/Decimal和V1保留、不回填 |
| DQ-03 | revision可as-of，主数据非双时态 | `(changed_at,id)`、inclusive cutoff、VOID不回退、missing FAIL、true N/A；历史limited watermark | 不改API，可增加watermark；无Migration | 历史不可完全重放；中 | 批准Evidence/VOID/缺失与LIMITED_CURRENT_MASTER契约 |
| DQ-04 | 当前规则0，无初始化器 | 显式check/apply Seed；exact no-op、冲突中止、版本不可变 | 数据写；无Schema；无启动写入 | 环境误写；小-中 | 批准受审配置和显式Seed/版本管理 |
| EX-01 | Service分别commit会部分成功 | 独立薄Workflow唯一commit；失败全回滚 | 算法不变；计算失败语义更严格；无Migration | 请求时长/锁；中-大 | 批准core+log+explanation+lineage原子成功 |
| EX-02 | replace使PK和弱引用失效 | immutable as-of+result_revision+fingerprints | Repo/ORM/API history变化；需V014 | 历史/查询风险；大 | 批准不可变结果、latest规则、旧PK永久保留 |
| EX-03 | 同as-of合法纠错未定义 | 普通不同内容409；管理员显式revision+1/supersedes | 新审计语义；V014 | 并发revision；中 | 批准显式纠错，不允许静默覆盖 |
| EX-04 | B1 revision直塞source_id与Governance冲突；Handler来源不完整 | snapshot_id + source_revision_id；三类完整实际集合 | Handler/Governance/API可选字段；V015 | lineage量/来源采集；大 | 批准完整集合，拒绝自指/空/部分Evidence |
| EX-05 | DDL隐式提交且需切唯一键 | V014/V015分离；备份恢复演练、维护窗口、逐项验证 | 高风险DDL；无历史删除 | 数据/停机风险；大 | 批准迁移结构与安全闸门，另行授权执行 |

所有状态均为 **PROPOSED / APPROVAL REQUIRED**；本报告没有把任何项标为 APPROVED 或 FROZEN。

## 7. B2 前置条件与停止规则

- DQ-A～D 需 DQ-01～04 明确批准；EX-E～H 需 EX-01～05 明确批准。
- V014/V015 必须独立提交、备份恢复验证和隔离演练；未满足不得写开发库。
- 找不到完整 revision source、需改变算法/阈值、需删除历史、出现部分commit或默认查询重复统计时立即停止。
- 本阶段未修改生产代码、测试、V001–V013、数据库或验收库，未执行 Seed/Migration/回填。

## 8. 本阶段验证

- 只读数据库：`short_drama_analysis`，131 dramas、64,255 snapshots、64,255 revisions；DQ rules/results/scores 和 explanations/lineage 均为0，前后未变化。
- `information_schema` 已核对 DQ/Score/Prediction/Lineage 四个实际唯一约束，结论与本提案一致。
- 离线向量复算：V1=`40.00/82.00/A`；V2=`94.00/98.20/S`。
- Data Quality + Explanation 现有专项测试：129/129 passed。它只证明当前基线未被文档工作破坏，不证明候选设计已经实现。
- 本阶段未重复运行全量706项，因为无生产代码或测试修改；历史全量结果不冒充本阶段新验证。

## 9. 交付文档

- `DQ_RULES_1_0_FINAL_PROPOSAL.md`
- `DQ_V1_V2_COMPATIBILITY_DECISION.md`
- 更新 `DQ_EVIDENCE_CONTRACT.md`
- `EXPLANATION_TRANSACTION_FINAL_DECISION.md`
- `RESULT_IDENTITY_AND_HISTORY_DECISION.md`
- `RESULT_VERSION_MIGRATION_PROPOSAL.md`
- 更新 `LINEAGE_SOURCE_MAPPING.md`
- 更新 `S5_2_B2_IMPLEMENTATION_PLAN.md`
- 本报告

最终状态：**FINAL DESIGN PROPOSAL READY — PENDING USER APPROVAL**
