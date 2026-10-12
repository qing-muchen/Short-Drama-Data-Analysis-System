# Phase S5.2-B Data Quality 设计—实现对照

结论：**DESIGN APPROVAL REQUIRED**。当前不是简单“缺配置”，而是生产规则发布、证据层和聚合口径尚未形成一致的冻结契约。

## 1. 对照表

| 设计来源 | 实际实现 | 已有能力 | 缺失/冲突 | 是否改变规则 | 处理 |
|---|---|---|---|---|---|
| `PHASE2_DATA_QUALITY_DESIGN_V2.md` 2–3 | V009、`models/data_quality.py` | 三表、版本、有效期、约束、规则集 hash | 无初始规则数据 Migration | 是：需选择规则内容 | 等批准 |
| Design V2 5、Review 4.4 | `repositories/data_quality_repository.py` | 规则、结果、评分 Repository | 无 `QualityEvidenceRepository` | 否，但其查询口径依赖规则 | 等规则冻结后实现 |
| Service 文档 3.1 | `services/data_quality_service.py` | evaluator registry Protocol、原子持久化、回滚 | 生产依赖工厂传入 `{}`，无生产 evaluator | 是：evaluator 即规则语义 | 等批准 |
| Calculator 文档 | `analytics/data_quality.py` | 二元 PASS/FAIL 加权、四维固定权重、等级、Decimal | 与 Design V2 的 0–100 rule score 聚合冲突 | 是：改变结果 | 必须裁决 |
| Design V2 4.1–4.2 | Service `_prepare_rule_result` | 计算并持久化 PASS_RATE/BUCKET_AVERAGE `rule_score` | Calculator 输入不包含 `rule_score`，维度分只看 PASS/FAIL | 是：改变结果 | 必须裁决 |
| Design V2 3.4、5 | 当前 Service | as-of、rule set hash、重算 replace | `open_issue_count` 固定 0，`source_watermark` 未由证据层提供 | 否/取决于证据范围 | 证据层实现项 |
| API / Dashboard 设计 | Router、Schema、Vue 页面 | 权限、空状态、历史/规则查询、业务提示 | 无成功态真实数据 | 否 | 实现后验证 |

## 2. 为什么测试规则不能发布

`test_data_quality_service.py` 中的 `DQ_COMPLETENESS`、`DQ_ACCURACY`、`DQ_CONSISTENCY`、`DQ_TIMELINESS` 及四个 `MagicMock` evaluator 是 Service 编排夹具。`database/tests/constraint_test.sql` 中的 `DQ_TEST_*` 仅用于约束测试。它们没有冻结分母、证据来源、去重键、配置 Schema 和真实查询语义，不能当作生产规则。

Design V2 给出了四个维度的候选检查方向和 Timeliness 分段建议，但同时要求每条规则明确评估对象、时间窗、适用分母、主证据来源和去重业务键；仓库没有完成该发布清单。

验收库仅有一条 `SNAPSHOT_DAILY_COVERAGE` 演示规则，无法覆盖四维，版本又与当前 `Quality Score V1.0 / DQ Rules 1.0` API 契约不一致，不能复制使用。

## 3. 当前运行证据

- 开发库：规则 0、规则结果 0、评分 0。
- 生产依赖：`get_data_quality_service(..., {})`。
- `POST /api/v1/data-quality/calculate`：HTTP 400，`NO_ACTIVE_RULE_SET`。
- 失败调用前后评分、规则结果、操作日志计数不变。
- 查询：current 404；history/rules 200 空集合；匿名 401。

## 4. 需要用户批准的最小决议

1. 逐条批准 `DQ Rules 1.0` 规则发布表，而不是只批准四个维度名称。
2. 明确维度计算采用：
   - A：已交付 Calculator 的规则级二元 PASS/FAIL 权重；或
   - B：Design V2 的 `Σ(weight × rule_score) / Σ(weight)`。
3. 明确 as-of 下主数据非双时态时的可追溯承诺和 source watermark。
4. 明确 VOID revision、缺失必需数据与真正 NOT_APPLICABLE 的逐规则语义。
5. 批准独立、可审计的数据 Migration/初始化编号；不得修改 V009。

在上述决议前，本阶段没有实现 evaluator、没有插入规则，也没有声称 Data Quality 闭环完成。

