# Phase S5.2-B2 收敛实施与测试计划候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.2 |
| Git 基线 | `15b161c09f78b804c42802bc76108613e77d9508` |
| 状态 | **PROPOSED — APPROVAL REQUIRED** |

本计划不授权实施。任何工作包缺少列明的批准或安全前置条件时必须停止。

## 1. 工作包与依赖顺序

| WP | 前置批准/依赖 | 主要模块与文件候选 | DB写入 / Migration | 风险与测试 | 完成/停止/提交 |
|---|---|---|---|---|---|
| B2-A DQ配置与Seed | DQ-01、DQ-04 | 新受审规则配置、seed CLI；DQ model/repository/service composition | 显式 apply 写规则；无 Schema Migration | dry-run、目标库保护、exact no-op、同键冲突、审计 | 四规则精确落库；字段未批或目标库不明即停；独立 `feat(data-quality)` 提交 |
| B2-B Evidence+Evaluator | B2-A规格、DQ-03 | 新 `data_quality_evidence_repository`/DTO/evaluators；dependencies registry | 只读业务表 | as-of/tie/VOID/7日/批量/非双时态 watermark；纯计算 | 四 evaluator 真实 Evidence；任何分母不明即停；独立提交 |
| B2-C Quality V2兼容 | DQ-02、B2-B | analytics DQ V2、Service calculator input、Repository精确identity、Schemas/TS版本 | 写测试库评分；无 Migration | 82/A vs 98.20/S、V1/V2并存、replace不得删V1 | 版本筛选和默认发布组合准确；旧结果删除即停；独立提交 |
| B2-D DQ闭环 | A-C | router/service/API、Data Quality UI、Profile/Governance/Reporting provider | 测试库写DQ三表 | 权限、错误码、current/history、空态、真实浏览器 | 真实评分可复核；不得以HTTP200代替结果校验；独立提交 |
| B2-E 版本Migration | EX-02/03/05；备份恢复验证 | 新 V014/V015、ORM/Repository查询兼容 | **高风险 DDL；单独维护窗口** | 临时恢复库演练、行数/约束/current查询、rollback恢复 | 两迁移逐项验证；未备份/重复identity即停；Migration单独提交 |
| B2-F 单事务Workflow | EX-01、B2-E | 新薄 workflow/UoW；Score/Prediction/Anomaly/Explanation 无commit operation；Router composition | 业务写入同事务 | 失败矩阵、commit一次、超时/并发/唯一冲突 | 任何部分提交即停；独立 backend 提交 |
| B2-G 真实Lineage | EX-04、B2-E/F | Score candidate、Prediction prepare、Anomaly daily evidence DTO；Handlers/Validator/Governance | 写 explanation/lineage | 8日/9日完整集合、revision归属/as-of/VOID、legacy NA | 不允许自指/空/部分来源；独立提交 |
| B2-H 自动生成接入 | B2-F/G | 三个 Workflow 正式启用；查询/Drawer可选revision字段 | 生产式测试库写入 | 成功全写、业务不足全不写、重复幂等、纠错revision | 三条真实路径通过；算法输出不得改变；独立提交 |
| B2-I 全量验收 | A-H | 全仓库测试、API、浏览器、报告 | 测试库；开发库须另授权 | pytest/compileall/vue-tsc/build、1920/1366、DB计数和性能 | P0/P1=0且证据齐全；独立 test/docs 提交 |

推荐顺序：A→B→C→D；并行完成 E 的演练，获部署批准后 E→F→G→H；最后 I。DQ 与 Explanation 不混入同一巨大提交。

## 2. Data Quality 测试规格

| ID | 输入 | 预期与验收条件 |
|---|---|---|
| DQ-01 | 空库 apply 两次；同键异内容 | 首次4规则、再次0变更；异内容全回滚 |
| DQ-02 | Rules 1.0 四维及版本变更 | 每维恰有首批规则；修改配置必须新 rule version/set |
| DQ-03 | 同 snapshot 多 revisions、相同 changed_at | 选 cutoff内最大 `(changed_at,id)`，并独立校验 version链 |
| DQ-04 | cutoff前后 revision；边界相等 | `<=`可见，`>`不可见，无未来污染 |
| DQ-05 | 最新 revision VOID | 不回退；C4 missing、T1 0、K2仍校验合法链 |
| DQ-06 | 7日期间缺日/无feed/可选字段NULL | 缺日按C4 FAIL；无业务域 N/A；可选字段不伪造 FAIL |
| DQ-07 | V1/V2区分向量 | V1=82.00/A；V2=98.20/S；Decimal HALF_UP |
| DQ-08 | 一维全N/A/无规则/evaluator错误 | 不持久化；稳定业务 reason；无部分结果/日志 |
| DQ-09 | 同日相同Rules的V1和V2 | 两行并存；计算V2不删除V1；按版本精确查询 |
| DQ-10 | 默认/current/history/report/profile | 默认仅当前发布组合；跨版本必须显式并分组，不混趋势 |
| DQ-11 | 并发相同评分 | 相同内容幂等，冲突稳定；无重复和原始DB泄漏 |
| DQ-12 | admin/user/anonymous | 遵循现有计算/读取权限，后端真实拒绝 |

## 3. Explanation / 历史测试规格

| ID | 输入 | 预期与验收条件 |
|---|---|---|
| EX-01 | Score 完整 calculation evidence | 每个实际 revision 有 lineage；四维值/权重一致；算法结果不变 |
| EX-02 | Prediction 8日×共同平台 | 完整 snapshot/revision集合；少一条即不生成并回滚 |
| EX-03 | 四类 Anomaly | 各自9日完整来源、metric/门槛/threshold正确；未来类型不套用固定窗 |
| EX-04 | source不存在/错snapshot/VOID/未来 | 来源校验失败，core/explanation/lineage/log均0提交 |
| EX-05 | core/handler/lineage/log/commit分别失败 | 符合失败状态表；一次rollback，无部分成功 |
| EX-06 | 相同 identity、fingerprint、内容 | 返回同PK/Explanation；不新增历史 |
| EX-07 | 同identity不同内容，普通请求 | 409，旧记录不变 |
| EX-08 | 管理员显式纠错 | revision+1、supersedes正确；旧结果/解释仍可查，new为current |
| EX-09 | 并发纠错 | revision唯一连续或一方受控冲突；无双current语义 |
| EX-10 | Migration前旧结果/lineage | PK/数量保持；legacy fingerprint/revision evidence为空并标NA |
| EX-11 | Reporting/Profile/current/history | 默认不重复统计；Profile最新；指定旧PK仍返回旧解释 |
| EX-12 | timeout/cancel | 未commit事务回滚；不得请求结束后后台commit |
| EX-13 | anonymous/user/admin | 查询/生成权限符合既有契约；无前端-only保护 |

## 4. 量化验收闸门

- 所有重要测试断言业务值、identity、source set、版本和数据库前后计数，不以 HTTP 200 为唯一标准。
- V014/V015 必须有完整备份、独立恢复验证、Schema diff、数据计数、唯一性预检和 explain plan。
- 全量测试不得减少既有用例；新增失败须分为环境/测试/迁移/业务缺陷。
- 前端必须实际验证 current/history/版本标签/NOT_AVAILABLE/失败提示；自动化通过不等于用户验收。
- 任何需要修改算法、阈值、V001–V013、删除历史或伪造来源的情况立即停止。

最后结论：**PROPOSED；工作包已可独立审批和提交，但尚未进入 B2。**
