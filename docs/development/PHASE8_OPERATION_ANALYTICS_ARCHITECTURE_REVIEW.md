# Phase 8 Short Drama Operation Analytics Center Architecture Review

> 审查对象：`PHASE8_OPERATION_ANALYTICS_DESIGN_V2.md`
>
> 审查范围：架构、数据来源、确定性规则、Availability、只读 API 与数据库影响。
>
> 本文不授权创建 Migration、数据库表或业务代码。

## 1. Review 结论

Phase 8 Design V2 已将 Design Proposal 和前次 Review 中的核心约束转化为可实现契约：固定窗口、明确公式、版本常量、Availability、revision/as-of 规则、分层边界和只读 API 均已定义。

审查选择：**Option A——允许进入 Implementation Planning，不要求 Design V3。**

该结论不等于允许立即编码。Implementation Planning 必须先把本文“实现前冻结条件”落实到 Contracts、Rule Component、Provider 和 API Schema 的文件级计划中。两个 TBD 已被限定为 V1 排除项，不阻塞已冻结范围；任何实现不得绕过排除项自行推断。

## 2. 模块定位审查

Phase 8 定位保持为运营分析与复盘层，属于 Read Model / Analytics Layer。它在请求期间消费已有事实和版本化结果，返回临时分析 DTO，不产生新的业务事实。

V1 实际使用的数据域包括：

- Operation Action 与 Action History；
- Anomaly records；
- revision-aware Historical Metrics；
- Drama 与 DramaPlatform 的结构化基础信息。

Prediction、Score 和 Drama Profile 属于可复用的现有能力，但 Design V2 的三套 V1 公式并不依赖它们。实现不得为了“覆盖模块列表”而额外调用 PredictionService、ScoreService 或 DramaProfileService。未来如将其纳入计算，必须升级相应规则版本并重新评审口径。

Phase 8 不替代 Phase 3 Prediction、Phase 4 Anomaly、Phase 5 Operation Action 或 Phase 7 Drama Profile。此项通过。

## 3. AI 边界审查

Design V2 明确排除 LLM、AI Agent、自动运营助手、自动策略生成、推荐算法、机器学习模型和自动分类模型。

Action Effect 使用固定统计公式，Lifecycle 使用确定性阈值规则，Benchmark 使用明确组内统计。所有结论均可由输入 DTO、公式和版本复现。生命周期“分类”是规则分类，不得在 API、文档或页面中表述为 AI 识别。

此项通过。

## 4. 架构依赖审查

冻结依赖方向：

```text
Operation Analytics API
          ↓
OperationAnalyticsService
          ↓
Pure Rule Components ← Analysis Providers
                              ↓
                    Existing Repositories
```

禁止 `OperationAnalyticsService` 调用 ScoreService、PredictionService、AnomalyService、OperationActionService、DramaProfileService 或 ExplanationService。

Service 负责冻结 `analysis_as_of`、编排、规则调用、口径校验和响应组装；Provider 读取数据；Rule Component 纯计算；Repository 执行只读查询。该方向不会形成业务 Service 之间的循环依赖。

此项通过。

## 5. Provider 与 Rule Component 审查

### 5.1 OperationEffectivenessProvider

只负责批量读取 Action 与历史事件、完成时间锚点候选、重叠 Action、前后窗口累计指标、窗口内 Anomaly records、输入 revision 与来源版本。

它不计算差值、不判断方向、不判断行动成功、不执行因果分析、不推荐后续动作。

### 5.2 LifecycleInputProvider

Design V2 中的名称和边界应保留为 `LifecycleInputProvider`，不应改成负责分类的 `LifecycleProvider`。它只读取 Drama 状态、release time 和连续累计日点。

生命周期阶段必须由纯 `LifecycleClassifier` 输出。把分类规则放入 Provider 会破坏“读取与计算分离”，因此该替代方案不通过。

### 5.3 BenchmarkProvider

只负责批量读取显式比较组的统一平台、统一日期窗口数据、异常记录和来源版本。它不计算中位数、不排序价值、不产生名次或推荐。

### 5.4 统一边界

所有 Provider 必须：

- 只读；
- 返回 Contracts DTO；
- 不向上返回 ORM；
- 不写数据库；
- 不 commit/rollback；
- 不调用业务 Service；
- 不承载统计公式或状态分类。

此项通过，但 Contracts 和源码边界测试必须锁定上述职责。

## 6. Operation Effectiveness Analysis 审查

### 6.1 数据来源

V1 输入冻结为：

- `operation_actions`；
- `operation_action_history`；
- `drama_metric_snapshots` 及其 revision；
- `data_anomaly_records`。

Prediction 结果不参与 V1 Action Effect 公式。不得把预测值与实际值混合为行动效果，也不得调用 PredictionService。

### 6.2 Action 资格与锚点

一次 Action 由唯一 `action_id` 标识。V1 只分析 `drama_id` 非空、截止 `analysis_as_of` 已存在第一次进入 `COMPLETED` 的历史事件、且可以构建固定窗口的 Action。

时间锚点冻结为：

```text
T0 = 第一次进入 COMPLETED 的历史事件 created_at
```

若 `CLOSE` 和 `STATUS_CHANGE -> COMPLETED` 同时存在，按 `created_at ASC, history_id ASC` 选择第一条。

由于当前没有实际活动开始时间，结果语义必须写作“完成时间前后指标变化”或 “post-completion metric movement”，不能写作完整活动周期的 before/after effect。`operation_actions.created_at` 到 T0 仅是记录生命周期，不能当作活动 duration。

### 6.3 固定窗口

按 Asia/Shanghai 业务日冻结：

```text
Before = T0 所在业务日前第 7 日至前第 1 日
After  = T0 所在业务日后第 1 日至后第 7 日
```

Anchor Day 不进入任一窗口。V1 不接受客户端覆盖窗口长度，不插值、不补 0。`analysis_as_of` 早于 After 最后一个完整日结束时间时，返回 `INSUFFICIENT / INCOMPLETE_AFTER_WINDOW`。

### 6.4 指标口径

以下指标冻结：

1. `views_change`：两个 7 日窗口播放增量总和之差和相对变化；
2. `engagement_change`：两个窗口“互动增量总和 / 播放增量总和”之差；
3. `growth_rate_change`：两个窗口日均播放增量的相对变化；
4. `anomaly_count_change`：两个窗口 Anomaly record 数量之差。

累计指标必须先按相邻日末值做差，再跨固定平台集合聚合。负增量不截断为 0，而是返回 `INVALID_CUMULATIVE_SEQUENCE`。Before 分母为 0 时相对值为 null，并返回 `ZERO_BASELINE`。

输出方向只允许 `INCREASED`、`UNCHANGED`、`DECREASED`、`UNAVAILABLE`。不允许 `SUCCESSFUL`、`EFFECTIVE`、`IMPROVED` 等价值或因果结论。

允许文案：“观察到行动完成后 7 日播放增量较完成前 7 日变化 12%。”

禁止文案：“该行动导致播放提升 12%。”

### 6.5 重叠行动

同一 Drama 的其他 Action 锚点落入任一窗口时，结果可以返回，但必须标记 `PARTIAL / OVERLAPPING_ACTIONS` 并列出重叠 action IDs。V1 不做影响分摊或归因。

### 6.6 缺失处理

| 情况 | Availability |
|---|---|
| Action 尚未完成或无完成事件 | `INSUFFICIENT / NOT_COMPLETED` |
| 全局 Action 无 `drama_id` | `NOT_AVAILABLE / GLOBAL_ACTION_UNSUPPORTED` |
| Before 日点不足 | `INSUFFICIENT / INCOMPLETE_BEFORE_WINDOW` |
| After 日点不足 | `INSUFFICIENT / INCOMPLETE_AFTER_WINDOW` |
| 必需指标缺失 | 单项 `INSUFFICIENT / MISSING_METRIC` |
| 累计序列回退 | `NOT_AVAILABLE / INVALID_CUMULATIVE_SEQUENCE` |

Action Effect 设计具备实现条件。

## 7. Lifecycle Analysis 审查

### 7.1 阶段与输入

阶段冻结为：

```text
LAUNCH / GROWTH / STABLE / DECLINE / ARCHIVED
```

输入冻结为 Drama status、release time 和连续 15 个累计播放量日点，由此生成连续 14 个日增量，并划分为前后两个 7 日窗口。

### 7.2 分类规则

规则冻结为：

1. `dramas.status = INACTIVE` → `ARCHIVED`；
2. 非 INACTIVE 且距 release time 为 0–14 个完整业务日 → `LAUNCH`；
3. 其他情况缺少连续 15 日点 → 不分类，返回 `INSUFFICIENT_HISTORY`；
4. 前窗均值为 0、后窗均值大于 0 → `GROWTH`；
5. 前后窗均值均为 0 → `STABLE`；
6. 前窗均值大于 0时，变化率 `>= +0.10` → `GROWTH`；
7. 变化率 `<= -0.10` → `DECLINE`；
8. 其余 → `STABLE`。

优先级冻结为：

```text
ARCHIVED > LAUNCH > 输入有效性 > GROWTH/DECLINE/STABLE
```

`release_time` 缺失、晚于 `analysis_as_of` 或无法形成合法业务日时，不得猜测阶段，必须返回 `NOT_AVAILABLE`。这一边界应写入 Contracts 测试。

### 7.3 版本与状态语义

版本冻结为：

```text
lifecycle_rule_version = "Lifecycle Rules V1.0"
```

V1 是指定 `analysis_as_of` 的点时分类，不持久化状态，也不提供历史状态转换事件。页面不得把两次独立查询描述为已审计的状态迁移。

Lifecycle 设计为确定性规则，不含机器学习，具备实现条件。

## 8. Benchmark Analysis 审查

### 8.1 比较组

V1 冻结为调用方显式传入 2–20 个不同 Drama IDs，并要求单一 `platform_id`。不自动选择相似 Drama，不使用全库平均，不按 category 或 tag 自动分组。

至少需要 2 个 Availability 为 AVAILABLE 或 PARTIAL 且指标可比的成员，才能计算组中位数。否则返回 `INCOMPARABLE_SCOPE`。

### 8.2 时间范围

Benchmark 时间口径是**滚动 30 个完整自然业务日**：截止 `analysis_as_of` 前一完整业务日，向前取连续 30 日；需要连续 31 个累计日末点生成 30 个增量。

它不是固定自然月，也不是从每个 Drama 上线日开始的相对 30 日。V1 不允许请求改成 7 日或 90 日。

### 8.3 指标与缺失值

冻结指标：

- `play_increment_total`；
- `mean_daily_play_increment`；
- `engagement_rate`；
- `anomaly_frequency`；
- `lifecycle_state`。

数值指标返回成员原始值和可比成员组中位数。缺失成员保留在响应中并携带 Availability，但不以 0 填充，也不进入该指标的中位数。V1 不返回综合分、名次、赢家、推荐或价值标签。

全局 Data Quality Score 是 `ALL / 0` 口径，不能复制为 Drama 级 Benchmark 指标。此排除合理。

### 8.4 版本

冻结：

```text
benchmark_version = "Benchmark Comparison V1.0"
```

来源异常算法版本混合时必须显式返回版本集合和 PARTIAL 状态，不可静默合并为单一版本。

Benchmark 设计具备实现条件。

## 9. Availability 协议审查

顶层和指标级统一使用：

```json
{
  "status": "AVAILABLE",
  "reasons": []
}
```

状态冻结为 `AVAILABLE`、`PARTIAL`、`INSUFFICIENT`、`NOT_AVAILABLE`。

原因码至少包含 Design V2 已列出的 `NOT_CALCULATED`、`INSUFFICIENT_HISTORY`、前后窗口不足、不可比较、指标缺失、零基线、重叠行动、混合版本、无效累计序列、未完成和全局行动不支持。

合法真实零值与缺失必须区分：真实零值可以在 AVAILABLE 状态下返回 0；数据不足必须返回 null 加原因，不得返回伪造的 0。此项通过。

## 10. Revision 与历史追溯审查

`analysis_as_of` 是硬截止时间；snapshot revision 必须满足 `changed_at <= analysis_as_of`，并按槽位选择截止时点可见的最高版本。VOID 排除，未来修订不可见。

规则版本冻结：

- `Action Effect Analysis V1.0`；
- `Lifecycle Rules V1.0`；
- `Benchmark Comparison V1.0`。

`analysis_revision` 使用稳定 canonical JSON 的 SHA-256，覆盖请求参数、`analysis_as_of`、输入 revision IDs、来源结果 IDs/版本和规则版本。该值只存在于响应，不写数据库。

规则、阈值、窗口或公式变化时必须升级版本，不得静默替换。此项通过。

## 11. 数据库影响审查

Phase 8 V1 继续保持实时 Read Model：

- 不创建 V014 Migration；
- 不新增 `operation_effectiveness_results` 或 `operation_outcomes`；
- 不新增 `lifecycle_snapshots`；
- 不新增 `benchmark_snapshots` 或 `benchmark_results`；
- 不新增 analytics cache 表；
- 不修改 V001–V013 或既有业务表。

Action Effect、Lifecycle 和 Benchmark 结果仅在请求期间存在。未来若需要历史报告、周报/月报、固化分析结果或物化性能优化，必须重新进行 Database Design 与 Migration Review。

数据库审查结论：**V1 无数据库变更。**

## 12. TBD 审查

### 12.1 TBD-P8-01：Drama category

当前没有标准化 category。V1 明确不支持 category 自动分组、同类剧自动 Benchmark 或从名称/标签推断 category。

未来启用前必须先冻结 Category 主数据、Drama 关联关系、分类治理规则和历史变更语义。该 TBD 作为 V1 排除项，不阻塞当前实现规划。

### 12.2 TBD-P8-02：Action 结构不足

当前没有结构化 Action Type、实际开始时间和活动持续时间。V1 明确不支持 promotion/recommendation/campaign/release_event 类型分析、活动周期分析或文本推断。

V1 只使用 action ID、Drama 关联、完成历史事件、priority、source evidence 和结构化状态。该 TBD 作为 V1 排除项，不阻塞当前实现规划。

## 13. API 设计审查

### 13.1 Action Effectiveness

```http
GET /api/v1/operations/effectiveness
```

- 权限：USER、ADMINISTRATOR；匿名 401；
- 参数：`action_id`、`drama_id`、固定值 `status=COMPLETED`、`analysis_as_of`、`page`、`page_size`；
- `page >= 1`，`page_size` 为 1–100；
- 固定 7 日窗口，不暴露 `window_days`；
- 返回 `ResponseModel[PageResponse[ActionEffectResponse]]`。

### 13.2 Lifecycle

```http
GET /api/v1/dramas/{drama_id}/lifecycle
```

- 权限：USER、ADMINISTRATOR；
- 参数：正整数 `drama_id`，可选 `analysis_as_of`；
- Drama 不存在为 404；历史不足为 200 + Availability；
- 返回 `ResponseModel[LifecycleResponse]`。

### 13.3 Benchmark

```http
GET /api/v1/dramas/benchmark
```

- 权限：USER、ADMINISTRATOR；
- 参数：去重后 2–20 个 `drama_ids`、必填 `platform_id`、可选 `analysis_as_of`；
- 显式组有严格上限，V1 不分页；
- 返回 `ResponseModel[BenchmarkResponse]`；
- 静态 `/benchmark` 必须先于动态 `/{drama_id}` 注册。

三个接口全部只读，不提供 POST、PUT、PATCH。Router 不访问 Repository、ORM、Provider 或 Rule Component。API 设计通过。

## 14. Dashboard 设计审查

Operation Analytics Dashboard 冻结为三个展示区：Operation Effectiveness、Lifecycle Overview 和 Benchmark Analysis。

前端只请求和展示 API 结果，不计算指标、生命周期、Benchmark 中位数或 Availability。页面必须展示 `analysis_as_of`、分析窗口、规则版本、Availability，以及行动完成前后变化不构成因果关系的提示。

禁止 AI 建议、自动方案、推荐排名和“最佳短剧”模块。此项通过。

## 15. 风险与实现控制

| 风险 | 控制措施 |
|---|---|
| 因果误判 | 固定非因果字段名、文案、免责声明和测试 |
| 完成时间被误认为开始时间 | 统一称“完成前后窗口”，不描述活动全周期 |
| 指标口径不一致 | 固定业务时区、平台集合、窗口、as-of 与版本 |
| 数据不足被误作 0 | Availability + null，真实零值单独表达 |
| 重叠 Action 干扰 | PARTIAL + overlapping IDs，不作分摊 |
| Provider 承载业务规则 | Provider/Rule 源码边界测试 |
| Benchmark 查询膨胀 | 显式 2–20 IDs、单平台、批量 Repository 查询 |
| 临时结果被当成历史事实 | 不落库，响应携带 revision 与版本 |

## 16. 实现前冻结条件

以下设计项已冻结，Implementation Planning 不得自行修改：

1. Action Effect 以首次完成事件为 T0，前后各 7 个完整业务日；
2. Action Effect 四项指标公式和非因果语义；
3. Lifecycle 五阶段、15 日点/双 7 日窗口、±10% 阈值和优先级；
4. Benchmark 为同一平台、显式 2–20 Drama、滚动 30 个完整自然业务日；
5. Availability 的四个状态、固定原因码和 null/0 区分；
6. Provider 只读、Rule Component 纯计算、Service 只编排；
7. `analysis_as_of`、snapshot revision 选择和三个规则版本；
8. V1 不新增 Migration、不持久化任何分析结果；
9. API 仅 GET、JWT 保护、统一 ResponseModel/ErrorResponse；
10. TBD-P8-01 与 TBD-P8-02 作为 V1 排除项。

Implementation Planning 还必须把以下边界写入测试计划：

- release time 缺失或晚于 `analysis_as_of` 时不分类；
- Lifecycle 分类只在纯 Rule Component；
- Action 文案使用“完成前后变化”；
- Provider 批量读取并避免 N+1；
- 前端不得执行任何分析公式。

## 17. 最终准入判断

Design V2 的模块定位、AI 边界、数据来源、确定性规则、Availability、版本治理、API 和数据库策略满足 Phase 1–7 的架构约束。

最终判断：**允许进入 Phase 8 Implementation Planning；不需要 Design V3。**

在 Contracts、Rule Components、Providers、Service 和 API Schema 的实施计划完成并确认上述冻结条件后，才可按独立阶段进入代码实现。当前仍禁止创建 Migration、数据库表或跨模块 Service 依赖。
