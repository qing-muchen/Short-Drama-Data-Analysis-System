# Quality Score V1 / V2 兼容性最终候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.2 |
| Git 基线 | `15b161c09f78b804c42802bc76108613e77d9508` |
| 状态 | **PROPOSED — APPROVAL REQUIRED** |

## 1. Evidence Verified

- V1 Calculator 使用 `Σ(PASS weight)/Σ(all weight)×100`，输入无 rule_score（`analytics/data_quality.py:40-46,159-216`）。
- Design V2 `:363-394` 定义 APPLIED rule_score 0–100 及 `Σ(weight×rule_score)/Σ(weight)`；N/A 排除。
- 实算向量：V1 Completeness 40.00、Total 82.00、A；V2 94.00、98.20、S。
- V009 唯一键包含 `score_date, algorithm_version, rule_set_version, rule_set_hash, scope`，所以表结构可并存 V1/V2（ORM `models/data_quality.py:123-132`）。
- 但当前 `replace_scope_scores()` 删除条件缺少 algorithm_version/hash，仅按 date/rule-set/scope 删除，会在计算 V2 时删除同规则集的 V1（repository `:168-202`）。这是 B2 代码缺陷，不要求 DQ Schema Migration。
- 当前 Pydantic/TypeScript 把版本写死为 V1；Router/Service 当前查询固定 V1。

## 2. V2 计算契约候选

| 项目 | 候选规则 | 状态/影响 |
|---|---|---|
| rule_score | finite Decimal `[0,100]`；PASS_RATE 或 BUCKET_AVERAGE | VERIFIED |
| rule weight | `(0,1]`；同维度相对权重，无需预先和为1，公式按分母归一化 | VERIFIED from schema/formula |
| APPLIED | applicable_count>0、passed+failed=applicable、score非空 | VERIFIED |
| N/A | 仅业务域真正不适用；0/0/0、score NULL、reason非空；权重排除 | VERIFIED |
| 必需 Evidence 缺失 | APPLIED FAIL/0；Evidence 查询本身不一致则整次失败 | VERIFIED + PROPOSED error boundary |
| severity | 不乘分；INFO/WARNING/ERROR 仅治理优先级 | VERIFIED |
| ERROR/WARNING | 均按 rule_score 影响分数；不形成独立阻断 | PROPOSED；会影响失败语义 |
| 维度分 | `Σ(w×score)/Σ(w)`，仅 APPLIED | VERIFIED |
| 无有效规则 | 任一维度无 APPLIED → `INSUFFICIENT_QUALITY_DATA`，不持久化 | VERIFIED |
| 跨维度 | C/A/K/T = 0.30/0.30/0.25/0.15 | VERIFIED |
| 等级 | S≥90；A≥75；B≥60；C<60 | VERIFIED |
| 精度 | Decimal 高精度；维度、总分 HALF_UP 到2位；等级按已舍入总分 | VERIFIED |
| 版本 | V1 永久指二元；V2 永久指 rule_score | PROPOSED，避免同名改义 |
| 持久化 | 同一算法+规则集+hash+scope+date一条；不覆盖另一算法版本 | Schema支持；Repository需修复 |

## 3. API 与查询选择

推荐兼容规则：

1. V2 发布前默认保持 V1；V2 与 Rules 1.0 正式发布后，未指定版本的 current/dashboard/profile/report 默认使用“配置的当前发布组合”=`Quality Score V2.0 + DQ Rules 1.0`，不得仅按字符串或 created_at 猜版本。
2. current/history API 增加可选 `algorithm_version` 和 `rule_set_version`；不传使用当前发布组合；传入则精确筛选。响应继续返回版本字段。
3. 普通 history 默认只返回一个版本组合，禁止将 V1/V2 点混在一条趋势线；跨版本比较必须显式请求并分组显示“不可直接同比”。
4. Reporting、Drama Profile、Data Governance provider 必须显式传版本组合；导出包含版本列。
5. 已有 V1 结果原样保留，不重算、不回填、不改名。开发库当前无 DQ 结果，但契约不能依赖空库。
6. Schema Literal 扩展为 V1|V2 或受控 string；前端展示版本，不把版本隐藏。

## 4. Migration 结论

DQ 表无需 Migration：唯一键已区分 algorithm version。B2 必须把 replace 改为精确 identity 的 insert-or-idempotent-return，或至少删除条件包含 algorithm/hash；推荐不再删除历史结果。若未来需要“当前发布版本”数据库配置表，应另行审批，本阶段推荐应用配置常量，避免新增表。

## 5. 风险与审批文本

- 计算结果改变：是，仅新 V2。
- API 破坏：新增可选过滤参数及响应接受 V2 为向后兼容；把默认值从 V1 切到 V2 是行为变更，需批准并在发布说明中声明。
- 历史风险：当前 replace 若不先修复会删除 V1；这是 B2-C 的硬停止条件。

**DQ-02 候选批准文本：**保留 V1 二元语义；新增 V2 rule_score 语义；V2 发布后成为默认发布组合；V1 可精确查询且不参与默认混合趋势；不回填旧结果；按上述 Decimal、N/A、severity、等级规则实现。

最后结论：**PROPOSED；现有 Schema 支持并存，无 DQ Migration，但 Repository/API/前端版本选择必须修改。**
