# Data Quality 评分口径决策候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.1 |
| 适用软件版本 | V1.0 maintenance baseline |
| Git 基线 | `0bd34f44d2f0e8065c22cdc423cf50d1373b8e9a` |
| 设计状态 | **STATUS: PROPOSED — USER APPROVAL REQUIRED** |

## 1. 已核实冲突

- 方案 A（当前实现）：`QualityRuleResult` 只有 dimension/status/weight，维度分为 `Σ(PASS weight)/Σ(all weight)×100`（`backend/analytics/data_quality.py:40-46,159-216`；Calculator 文档 `:62-78`）。
- 方案 B（Design V2）：每条 APPLIED 规则输出 0–100 `rule_score`，维度分为 `Σ(weight×rule_score)/Σ(APPLIED weight)`，N/A 排除，缺任一维度则不持久化（Design V2 `:363-394`）。
- Service 已计算并持久化 PASS_RATE/BUCKET_AVERAGE 的 `rule_score`，但在构造 Calculator 输入时只传 status/weight（`backend/services/data_quality_service.py:399-425`）。因此当前数据库事实与聚合输入语义不一致。

## 2. 同一输入的可复核向量

假设 Completeness 有两条 APPLIED 规则：R1 权重 0.60，9/10 通过、执行状态 FAIL、`rule_score=90`；R2 权重 0.40，10/10 通过、状态 PASS、`rule_score=100`。其余三个维度均为 100。

| 口径 | Completeness | Total | Grade |
|---|---:|---:|---|
| A 二元 | `(0×0.60 + 1×0.40)/(1.00)×100 = 40.00` | `0.30×40 + 0.30×100 + 0.25×100 + 0.15×100 = 82.00` | A |
| B rule_score | `(0.60×90 + 0.40×100)/1.00 = 94.00` | `0.30×94 + 0.30×100 + 0.25×100 + 0.15×100 = 98.20` | S |

两者不是实现细节差异，而是会改变等级的业务口径。若一条规则 N/A，B 从分子与分母同时排除；A 的 Service 当前也通过不传 Calculator 达到排除效果。所有运算使用 Decimal，最终 `ROUND_HALF_UP` 两位（实现 `:91-97`；Design V2 `:393-456`）。

## 3. 方案比较

| 维度 | A：二元 PASS/FAIL | B：0–100 rule_score | C：双版本兼容（推荐） |
|---|---|---|---|
| 原始依据 | Calculator 文档及已交付代码 | Phase 2 Design V2、V009 `rule_score` | 以 B 为新语义，A 只作为历史实现版本 |
| Schema | 可用，但 `rule_score` 成为未使用事实 | 原生匹配 `rule_score DECIMAL(5,2)` | 无表结构变更；版本字段区分 |
| Service | 当前兼容 | 需把 rule_score 传入新 Calculator | 保留旧函数，新增明确版本的新函数/分派 |
| API | 当前 Literal `Quality Score V1.0` | 若仍叫 V1.0 会混淆 | 扩展响应版本契约；查询可按版本，默认当前批准版 |
| 测试 | 当前用例稳定 | 需增加区分向量 | 旧断言保留，新版本新增断言，不改写历史语义 |
| 历史结果 | 同名可混淆 | 同名重定义会混淆 | 不重写、不回填；按 algorithm_version 并存 |
| 可解释性 | 规则 90 分可能因 FAIL 被聚合为 0 | 聚合与持久化规则分一致 | 新结果清晰；旧结果标明 legacy |
| 风险 | 丢失部分通过信息，BUCKET_AVERAGE 几乎失真 | 改变当前结果 | API/前端需接受多个版本，实施量略增 |

## 4. 推荐决策 DQ-02

推荐 C：**后续新计算采用 Design V2 的方案 B，并发布新的 `algorithm_version = Quality Score V2.0`；`Quality Score V1.0` 永久表示现有二元实现，不以同名重定义。**

理由：Design V2 和 V009 已把 0–100 规则分定义为权威事实，尤其 Timeliness 的 BUCKET_AVERAGE 无法用二元聚合忠实表达；同时，Design V2 `:467` 明确标准化方法变化必须发布新 algorithm version。开发库当前无 DQ 历史结果，但兼容策略不能依赖“当前恰好为空”，更不能混淆验收或其他环境中的旧结果。

实施影响（仅供 B2，当前不实施）：

- 修改 `backend/analytics/data_quality.py`，新增接收 `rule_score` 的 V2 输入与聚合；不改变 V1 函数语义。
- 修改 Service 版本选择及 Calculator 输入；结果仍写现有三表。
- 扩展 `backend/schemas/data_quality.py:40-104` 和 `frontend/src/types/dataQuality.ts:22-86` 的版本契约，查询默认值需明确为 V2。
- 更新 Data Governance/Reporting 的版本过滤或展示；不回填、不重算旧分数。
- 无数据库 Migration 必需；若决定只允许 V2 且删除 V1 API，则属于 **BREAKING CHANGE — APPROVAL REQUIRED**，本方案不推荐删除。

## 5. 未解决问题与待批准细节

- ERROR/WARNING：Design V2 只证明 severity 不乘入分数，未证明 ERROR 阻断；推荐 V1 规则集中 severity 仅用于治理排序，评分失败只由 evaluator/证据契约错误触发，不由 FAIL+ERROR 自动阻断。需用户批准。
- 没有有效规则：沿用 `NO_ACTIVE_RULE_SET`；有规则但某维度无 APPLIED：`INSUFFICIENT_QUALITY_DATA` 且不持久化。
- `rule_score` 必须有限且在 `[0,100]`；N/A 必须为 NULL；每层以高精度 Decimal 计算并在维度及总分边界 HALF_UP 两位。

最后审查结论：**推荐双版本兼容并以 V2 承载 rule_score 口径；尚未批准、未修改 Calculator。**
