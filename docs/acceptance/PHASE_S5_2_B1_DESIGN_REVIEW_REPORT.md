# Phase S5.2-B1 Design Review Report

| 项目 | 值 |
|---|---|
| 文档版本 | 0.1 |
| 适用软件版本 | V1.0 maintenance baseline |
| Git 分支 / 基线 | `main` / `0bd34f44d2f0e8065c22cdc423cf50d1373b8e9a` |
| 正式发布基线 | `v1.0.0` → `0e350381d1fd7a16eaa9da5cf9bb92c24285c7de`（未修改） |
| 设计状态 | **STATUS: PROPOSED — USER APPROVAL REQUIRED** |

## 1. 执行范围与证据基线

本阶段只新增候选设计文档。未修改生产代码、测试、V001–V013、Calculator、规则数据、分析结果或数据库结构；未初始化规则、未回填 Explanation、未进入 S5.2-B2。

开始状态：工作区干净；`main` 比 `origin/main` ahead 109。只读数据库复核为 MySQL 8.0.45 / `short_drama_analysis`：31 表、131 dramas、64,255 snapshots、64,255 revisions、82 scores、1 prediction、2 anomalies；DQ rules/active/results/scores 均 0；explanations/lineage/metric_dependencies 均 0。

主要证据链：

| 设计要求 | 文档 | 实现/Schema | 测试 | 缺口/状态 |
|---|---|---|---|---|
| DQ 规则版本化、四维、rule_score | Phase 2 Design V2 `:99-163,294-480` | V009、DQ ORM/Service | DQ model/service/calculator tests | 无生产规则；PROPOSED |
| DQ 聚合 | Design V2 `:363-394` vs Calculator doc `:62-78` | Service `:399-425`、Calculator `:40-46,159-216` | calculator/service tests | 两口径冲突；APPROVAL REQUIRED |
| Evidence 分层 | Design V2 `:506-583` | 无 QualityEvidenceRepository；生产 registry 为空（dependencies `:445-453`） | mock evaluator tests | 生产闭环缺失 |
| 结果时 Explanation | Phase 6 Design V2 `:24-34,270-285` | Handler/Registry/Service 存在 | 129 项专项基线通过 | 无生产调用方/事务编排 |
| 弱引用来源校验 | Design V2 `:116-136,208` | V013 + validator 只校验字段 | Handler/Service tests | 无实际来源 Provider |
| 历史永久保留 | Design V2 `:163,190-194` | Score/Prediction replace delete+insert | repository tests 明确 delete | 历史目标悬空 |

## 2. 关键结论

### Data Quality

原设计列出 16 个检查方向，但没有任何一条同时具备生产 Rule ID、完整判断、阈值、证据、severity、权重、缺失语义和去重键。T-01 只有分段分值较完整。因此 `DQ Rules 1.0` 仍不能直接 Seed。

评分推荐采用双版本兼容：保留现有二元 `Quality Score V1.0` 的历史含义；新计算以 `Quality Score V2.0` 实现 Design V2 rule_score 聚合。代表向量产生 V1=82.00/A、V2=98.20/S，证明必须显式版本化。

Evidence 推荐由 Repository 批量读取真实事实，Service 编排事务，Evaluator 纯计算；历史 as-of 选择最新可见 revision，最新为 VOID 时禁止回退。规则初始化推荐显式、受审、可 dry-run 的版本化 Seed 命令，不在应用启动时写入。

### Explanation / Lineage

推荐上层 Workflow 成为唯一 commit 所有者，使核心结果、Explanation、Lineage 和日志原子提交。当前各 Service 的独立 commit 不能组合成同一事务；后置可靠重试又缺 outbox/job 基础。

推荐 Score/Prediction 改为不可变 as-of 版本，不再 delete+insert；这需要新 Migration 调整唯一键，属于 **BREAKING CHANGE — APPROVAL REQUIRED**。三类来源都应落到真实 snapshot revision：Score 使用 `SNAPSHOT`，Prediction 使用逻辑 `PREDICTION_INPUT`，Anomaly 使用逻辑 `ANOMALY_EVIDENCE`；后两者的 source_id 均明确映射到 `snapshot_revision_id`。

## 3. 决策矩阵

| ID | 主题 / 现有行为 | 候选与推荐 | 兼容性/数据风险 | Migration / 结果变化 | 状态 |
|---|---|---|---|---|---|
| DQ-01 | 无 ACTIVE 生产规则 | 批准逐条完整规则表；在字段补齐前不发布 | 错规则会产生错误业务结果 | 数据 Seed；会产生新结果 | APPROVAL REQUIRED |
| DQ-02 | V1 二元，Service 又保存 rule_score | 推荐 V1 legacy + V2 rule_score | API Literal/默认版本需扩展 | 无 DB Migration；结果改变 | APPROVAL REQUIRED |
| DQ-03 | 无 Evidence Repository | 推荐真实表/PK/revision/as-of DTO；VOID 不回退 | 主数据非双时态，历史重放有限 | 结构化逐来源若入库可能需新表 | APPROVAL REQUIRED |
| DQ-04 | 无初始化机制 | 推荐显式、幂等、可审计 Seed，不随启动写 | 环境误写/同键冲突必须 fail closed | 默认无 schema Migration | APPROVAL REQUIRED |
| EX-01 | 核心与 Explanation 分别 commit | 推荐同 Session 的 Workflow 单次 commit | 解释失败将回滚主结果 | Pipeline 无新表 | APPROVAL REQUIRED |
| EX-02 | Score/Prediction delete+insert | 推荐不可变 as-of 版本 | 若错误实施可丢历史/错 latest | **需要新 Migration** | APPROVAL REQUIRED |
| EX-03 | Handler 自指或空 evidence | 推荐真实 snapshot revision 映射 | 来源量增加；需准确保留计算输入 | V013 不变 | APPROVAL REQUIRED |
| EX-04 | 只校验字段，不校验来源 | 推荐存在/归属/版本/as-of/窗口完整校验；不允许部分解释 | 更严格写路径，可能暴露旧数据缺口 | 无必需 Migration | APPROVAL REQUIRED |

## 4. 可直接批准/修改/驳回的决策文本

1. **DQ-01**：批准以 `DQ_RULES_1_0_SPEC.md` 的 16 个来源设计方向作为候选全集，但只有在逐条补齐并批准 production rule_code/name、weight、severity、分母、窗口、阈值、Evidence、去重键、evaluator/config 后才可激活；未补齐项不得实现。
2. **DQ-02**：批准保留二元算法为 `Quality Score V1.0` legacy，新生产评分发布 `Quality Score V2.0`，按 APPLIED rule_score 加权；N/A 排除、缺任一维度不持久化，severity 不二次乘权且不自动阻断。
3. **DQ-03**：批准 Evidence Repository 只读真实业务表，按 as-of 选择最新可见 revision；最新为 VOID 时不回退，必需事实缺失计 FAIL/0，真正不适用才 N/A；披露主数据非双时态限制。
4. **DQ-04**：批准仓库版本化配置 + 显式 `check/apply` Seed；完全一致重复执行 no-op，同键异内容中止，禁止启动自动插入和原地修改已使用规则。
5. **EX-01**：批准上层 Workflow/Unit of Work 为唯一事务提交者；核心结果、日志、Explanation、Lineage 全有或全无；不产生核心结果的业务场景不生成解释。
6. **EX-02**：批准 Score/Prediction 使用不可变 as-of 版本，并以新 Migration 扩展唯一身份；完全相同 identity 幂等，不同内容冲突，current 取最新 as-of，旧 PK/解释永久保留。
7. **EX-03**：批准 Score lineage 指向实际 `snapshot_revision_id`（source type SNAPSHOT）；Prediction/Anomaly 的逻辑来源类型分别映射到实际参与计算的 revision IDs；禁止把结果 PK 当输入来源。
8. **EX-04**：批准 Explanation 至少包含一个经验证来源及类型专属证据；空/自指 evidence 不完整，来源缺失、VOID、越过 as-of 或窗口/版本不一致时拒绝并按 EX-01 回滚。

## 5. 未解决问题与阻塞

- DQ-01 的逐条业务字段仍需产品/业务所有者给出；这是 WP1/2 的硬阻塞。
- 同一 `analysis_as_of` 的纠错重算是否新增 `result_revision` 无现有依据；当前推荐冲突停止。
- 若不接受 Explanation 失败回滚核心结果，则必须另行设计 outbox/job，现有仓库无法提供可靠后置恢复。
- Score 计算当前未保留所有输入 revision IDs；B2 必须从真实计算上下文传递，不能事后猜测。

## 6. 文档与审查结论

新增：

- `docs/development/DQ_RULES_1_0_SPEC.md`
- `docs/development/DQ_SCORING_DECISION.md`
- `docs/development/DQ_EVIDENCE_CONTRACT.md`
- `docs/development/EXPLANATION_PIPELINE_DECISION.md`
- `docs/development/LINEAGE_SOURCE_MAPPING.md`
- `docs/development/S5_2_B2_IMPLEMENTATION_PLAN.md`
- 本报告

本阶段没有以自动化测试“证明新设计正确”，因为没有实现；只执行了 Git/代码/文档/Schema/测试证据审计及数据库只读复核。历史 706/706、129/129 是进入本阶段的既有基线，不冒充本设计的实现验收。

最终状态：**DESIGN REVIEW COMPLETED — PENDING USER APPROVAL**
