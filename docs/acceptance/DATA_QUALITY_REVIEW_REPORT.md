# Phase S5.2 Data Quality 可用性审查

审查日期：2026-10-12（Asia/Shanghai）  
目标数据库：`short_drama_analysis`（只读审计）  
隔离验证数据库：`short_drama_s5_2_20261012_171116`

## 1. 结论

Data Quality 的表结构、ORM、Repository、评分公式、事务编排、查询 API 与页面均已存在，但“成功计算”所需的业务规则发布和生产 evaluator/evidence 实现并不存在。当前开发库三张表的实况为：

| 表 | 行数 |
|---|---:|
| `data_quality_rules` | 0 |
| `data_quality_rule_results` | 0 |
| `data_quality_scores` | 0 |

因此管理员调用 `POST /api/v1/data-quality/calculate` 返回 HTTP 400、`VALIDATION_ERROR`、`details.reason=NO_ACTIVE_RULE_SET`，与当前 Service 契约一致，不是数据库异常。它同时揭示了一个尚未完成的 V1 能力：仓库没有初始规则数据 Migration、初始化命令、生产 evaluator 或 `QualityEvidenceRepository`。测试中出现的四类 evaluator 都是 `MagicMock`，不能作为生产实现。

本阶段没有擅自创建规则或阈值，也没有用测试 evaluator 生成虚假评分。

## 2. 正确业务执行流程

1. 管理员提交 `score_date`。
2. Service 按 Asia/Shanghai 业务日生成 UTC `analysis_as_of`。
3. Repository 加载在该时点有效且 `status=ACTIVE` 的规则。
4. Service 计算规则集 SHA-256，并按 `evaluator_key` 调用白名单 evaluator。
5. evaluator 从受控证据源产生适用量、通过量、失败量、规则分和证据摘要。
6. 纯计算器要求完整性、准确性、一致性、及时性四个维度均至少有一个 APPLIED 结果，再按冻结权重生成总分和 S/A/B/C 等级。
7. Service 在一个事务中替换同身份 Score、写 Rule Results，并写一条操作日志；任一步失败全部回滚。
8. 查询 API 与前端只读取持久化结果，不重新计算。

## 3. 十项问题逐项回答

1. **正确流程是什么？** 见上一节；Router → Service → Rule Repository/evaluator → 纯计算器 → Score/Result Repository → Operation Log。
2. **是否要先配置或启用规则？** 是。V1 没有独立 `enabled` 字段，只有 `DRAFT/ACTIVE/INACTIVE`；计算只加载有效期内的 ACTIVE 规则。
3. **当前是否有规则记录？** 没有，开发库和隔离副本均为 0。
4. **是否有启用规则？** 没有。
5. **是否有 evaluator 注册机制？** Service 构造器接受 `evaluator_key → RuleEvaluator` 映射，但生产依赖工厂当前显式传入 `{}`。
6. **evaluator 是否已实现但未配置？** 否。仓库只有 Protocol、结果校验和测试替身，没有生产 evaluator/evidence provider。
7. **HTTP 400 是预期还是缺陷？** 在“零活动规则”现状下，400 是明确的业务契约；从完整产品能力看，规则发布和 evaluator 尚未交付，是阻止成功评分的实现/配置缺口，而非 S5.1 数据库恢复失败。
8. **历史评分能否对应现有数据？** 当前没有历史评分或规则结果，不能验证业务对应关系。API 正确返回：current score 404、history 200 空数组、rules 200 空数组。
9. **是否有现成初始化流程？** 没有。V009 只建结构；设计要求初始规则由独立、受审查的数据 Migration 发布，但 V001～V013 中不存在该 Migration。`database/tests/constraint_test.sql` 的 INSERT 仅用于约束测试。
10. **前端是否解释清楚？** 修复前会把预期的 score 404 显示为英文通用错误；修复后空页面不报错，计算失败显示“尚未发布可执行的数据质量规则，当前仅可查看已有评分与历史记录”。

## 4. 场景区分

| 场景 | 判定依据 | 当前行为 |
|---|---|---|
| 规则未配置 | 有效 ACTIVE 规则数为 0 | HTTP 400，`NO_ACTIVE_RULE_SET` |
| 规则未启用 | 有规则但均非 ACTIVE/不在有效期 | 与上项相同；当前库无规则，未单独出现 |
| evaluator 缺失 | ACTIVE 规则的 `evaluator_key` 不在注册表 | 会抛 `DataQualityRuleExecutionError` 并回滚；当前未到达该分支 |
| 历史数据不足 | evaluator 返回 N/A 或计算器缺维度 | 应返回对应领域失败且不持久化；生产 evaluator 未实现，无法真实验证 |
| 评分计算失败 | evaluator/计算器结果非法 | 原子回滚；单元测试覆盖 |
| 数据库异常 | SQLAlchemy/持久化失败 | 脱敏 500 `PERSISTENCE_ERROR`；测试覆盖 |

## 5. 本阶段处理

- 未修改 V009 或任何历史 Migration。
- 未向开发库或隔离库插入 Data Quality 规则/评分。
- 修复页面对 current score 404 的误报。
- 增加 `NO_ACTIVE_RULE_SET` 的中文可操作说明。
- 将 Data Quality 四维展示统一为中文，内部 API 枚举保持不变。

## 6. 待用户确认的设计工作

成功计算需要一个独立后续设计/实现任务，至少冻结：初始规则业务定义、阈值和权重、证据查询口径、四维覆盖、evaluator 配置 Schema、规则集版本发布方式及数据 Migration 编号。未经这些确认，本阶段不应创建规则或实现 evaluator。

浏览器证据：[空状态](evidence/phase_s5_2/data-quality-empty-1920x1080.png)；[无活动规则提示](evidence/phase_s5_2/data-quality-no-rules-1920x1080.png)。
