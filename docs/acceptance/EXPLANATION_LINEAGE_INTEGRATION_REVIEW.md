# Phase S5.2-B Explanation / Lineage 集成审查

结论：组件能力为 **IMPLEMENTED WITH LIMITATIONS**，生产自动生成链路为 **DESIGN APPROVAL REQUIRED**。

## 1. 设计—实现对照表

| 设计来源 | 实际实现 | 已有能力 | 缺失/风险 | 是否需批准 |
|---|---|---|---|---|
| Design V2 2 | `AnalysisExplanationService` | 结果产生时所需的确定性生成 API、幂等 identity | 没有生产调用方/组合入口 | 是，需冻结编排边界 |
| Handler 文档 | Metric/Trend/Anomaly Handler | 固定模板、禁止复制完整结果、无 LLM | Metric evidence 只有维度名；Trend evidence 为空 | 是，真实证据载荷需冻结 |
| Service 文档 2–4 | Explanation + Lineage Repository | 两表同一 Explanation Service 事务、冲突检测 | 与核心结果不是同一事务 | 是 |
| Design V2 3.3、7 | Lineage ORM/Repository | 弱关联、唯一约束、查询索引 | 写入时未验证 source 实际存在和版本一致 | 是，需来源 Provider 映射 |
| Module Summary 7–8 | 查询 API、`ExplanationDrawer` | 认证、分页、空/错/成功状态 | 开发库无真实记录 | 否；实现后验证 |
| Design V2 3.4 | `metric_dependencies` ORM | 表和模型存在 | 无静态依赖配置/发布流程 | 是，如纳入 V1 |

## 2. 空表根因

不是 Handler 未注册失败或数据库异常。仓库中：

- 三个 Handler 和 Registry 可在测试中显式组合；
- `AnalysisExplanationService` 可生成并在同一事务写 Explanation + Lineage；
- 生产依赖工厂只注册 `AnalysisExplanationQueryService`；
- Score、Prediction、Anomaly 计算 Router/Service 均未调用生成流程；
- 因此开发库两张表保持 0 条，查询 API 正常返回空集合。

专项测试覆盖组件级生成、幂等、冲突和 Lineage 失败回滚，但没有覆盖“核心结果 + Explanation”的生产事务。

## 3. 不能直接接线的证据

### 3.1 事务语义未冻结

设计一处要求“分析结果产生时生成”，另一处明确风险处理需“同一事务或补偿重试策略”。现有 Score、Prediction、Anomaly Service 均自行 commit；Explanation Service 也自行 commit。Router 顺序调用会产生“核心结果已提交、解释失败、HTTP 却失败”的部分成功状态。

### 3.2 依赖方向限制

冻结文档写明 Explanation 层只读消费业务结果，已有业务模块不得反向调用 Explanation Service。把 Explanation Service 直接注入三个业务 Service 虽容易实现，却违反该边界。正确做法需要批准一个更高层的显式 Workflow/Unit of Work，或批准可观察的后置补偿流程。

### 3.3 来源 ID 语义不完整

现有 Handler 测试使用：

- `METRIC` → `score_id`；
- `PREDICTION_INPUT` → 可选 `prediction_input_id`，缺省为 `prediction_id`；
- `ANOMALY_EVIDENCE` → `anomaly_id`。

但模型没有说明 `METRIC` 和 `PREDICTION_INPUT` 的权威来源表；Service 也没有查询实际存在性。预测与异常原始输入已带 snapshot revision ID，Score 的 `MetricResult` 却没有保留用于计算的 revision ID 集合。若自行选择，会改变血缘含义。

### 3.4 replace 导致历史悬空

`ScoreRepository.replace_scope_scores()` 和 `PredictionRepository.replace_prediction()` 采用 delete + insert。重复计算会产生新结果主键，而旧 Explanation 的弱关联不会被数据库级联或自动修复。直接自动生成会留下指向已删除 Score/Prediction 的历史记录，与“来源实际存在”和“历史永久可追溯”冲突。

## 4. 已验证能力

- Metric、Trend、Anomaly Handler 确定性输出。
- Registry 显式注册和未注册错误。
- detail 白名单和禁止字段校验。
- Explanation + Lineage 同事务；Lineage 失败回滚。
- 相同 identity/内容幂等返回，不同内容冲突。
- 查询 API：认证用户 200 空集合，匿名 401。
- 前端 Drawer 的 loading、empty、error、detail 和 lineage 展示代码存在；TypeScript/build 通过。

## 5. 需要批准的最小方案

建议批准一个不新增表的 V1 方案，但必须先明确：

1. Workflow 是单事务协调核心结果与 Explanation，还是结果提交后写入并提供明确失败状态/重试。
2. 三类 source type 各自映射到哪张实际表、使用哪个 ID、如何校验 as-of 和版本。
3. Score/Prediction replace 改为保留主键、保留旧业务结果，还是同步管理旧解释；三者会影响历史契约。
4. Score 的计算输入 revision IDs 如何从 Analytics 层传到只读 Explanation Provider，而不污染纯计算模块。
5. Explanation 失败是否允许核心计算成功；若允许，用户/API 如何得知解释待补偿。

未获批准前，不应增加隐式 GET 生成、静默吞错、伪造来源或全量历史回填。

