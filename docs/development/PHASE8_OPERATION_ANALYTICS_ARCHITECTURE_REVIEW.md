# Phase 8 Short Drama Operation Analytics Center Architecture Review

## 1. Review 结论

Phase 8 Design Proposal 的定位、依赖方向和业务价值与 Phase 1–7 兼容，审查结论为：**有条件通过，允许进入 Design V2**。

进入实现前必须在 Design V2 中冻结行动效果口径、生命周期阶段规则、Benchmark 比较范围、Availability 状态和 revision/as-of 选择方式。当前不允许直接进入 Backend、Frontend 或数据库实现。

## 2. 核心架构原则审查

Phase 8 保持 Read Model / Analytics Layer 定位，只消费：

- Prediction；
- Anomaly；
- Operation Action；
- Drama Profile；
- revision-aware 历史运营指标。

它不修改 Score、Prediction、Anomaly、Action、Explanation 或 Profile 结果，也不重新执行评分、预测和异常检测。

该边界符合现有分层设计，能够避免 Phase 8 成为新的业务事实中心或跨模块编排中心。

## 3. AI 边界审查

Phase 8 V1 明确排除：

- LLM；
- AI Agent；
- 自动运营建议；
- 自动决策；
- 推荐系统；
- 机器学习模型。

所有输出必须来自明确指标、固定规则和可解释统计逻辑。生命周期阶段属于规则分类，不得描述为智能识别或预测模型；Benchmark 不得生成推荐结论。

此项通过。

## 4. 子模块审查

### 4.1 Operation Effectiveness Analysis

输入由 Operation Action、Action History、Before Metrics 和 After Metrics 组成，输出只描述行动前后指标变化。

必须冻结：

- 锚点事件：V1 建议使用行动 `COMPLETED`/`CLOSE` 事件时间；
- 默认窗口：行动前后各 7 个完整日点；
- 指标：V1 建议限定为累计播放量对应的日增量、互动率和异常数量；
- 聚合口径：全部有效平台，revision 满足 `changed_at <= analysis_as_of`；
- 缺失状态：`INSUFFICIENT_HISTORY`、`INCOMPLETE_BEFORE_WINDOW`、`INCOMPLETE_AFTER_WINDOW`；
- 非因果措辞：只使用“行动发生前后变化”，禁止“导致”“贡献”“提升来源”。

V1 不需要新增 `operation_outcomes` 表。效果结果可实时计算为只读 DTO；若未来需要发布和锁定复盘报告，应另行设计持久化模型。

### 4.2 Drama Lifecycle Analysis

阶段集合可以保留：

```text
LAUNCH / GROWTH / STABLE / DECLINE / ARCHIVED
```

但 Proposal 尚未冻结每个阶段的严格规则。Design V2 必须明确：

- 发布后天数边界；
- 所需最小历史日点；
- 增长率、连续增长/下降天数和稳定区间阈值；
- `ARCHIVED` 是显式业务状态还是规则推导；
- 多条件冲突时的阶段优先级；
- `lifecycle_rule_version`；
- 零增长、数据缺口、累计值回退和历史不足处理。

禁止机器学习分类。规则计算应放在纯规则模块，不应由 Provider、Repository、Router 或前端实现。

### 4.3 Drama Benchmark Analysis

Benchmark 只提供统计比较，不产生“最佳短剧”、价值判断或推荐排序。

Design V2 必须冻结：

- V1 指标集合：播放规模、日增量、互动率、异常频率、生命周期阶段、数据质量；
- 比较组形成方式：显式 drama IDs，或相同平台/标签的受限筛选组；
- 时间口径：同一 `analysis_as_of` 或明确可比较窗口；
- 版本口径：不得混用不同算法版本后直接比较；
- 缺失数据：保留不可用状态，不以 0 填充；
- 排序：仅按用户选择的客观指标排序，不提供价值排名。

比较指标可统一后进入 V1，但不应直接复用 Profile 页面显示值作为不可追溯的输入。Provider 应从原结果 Repository 读取版本化数据。

## 5. 数据库影响审查

Phase 8 V1 应继续保持无 Migration 方案：

- 不新增 `operation_outcomes`；
- 不新增 `lifecycle_snapshot`；
- 不新增 `benchmark_snapshot`；
- 不修改 V001–V013。

三类分析均可由现有事实表和历史数据实时形成 Read Model。提前持久化会产生重算、版本同步和历史冲突风险。

若未来出现发布复盘报告、长期生命周期快照或大规模 Benchmark 物化需求，必须重新进入 Migration Review，并明确结果身份、版本和失效策略。

数据库审查结论：**V1 不需要 V014 Migration**。

## 6. 架构依赖审查

冻结架构：

```text
Operation Analytics API
          ↓
OperationAnalyticsService
          ↓
Analysis Providers / Pure Rules
          ↓
Existing Repositories
```

禁止 `OperationAnalyticsService` 调用 ScoreService、PredictionService、AnomalyService、OperationActionService 或 DramaProfileService。

Service 负责参数校验、Provider 编排、口径一致性和响应聚合。Repository 负责数据访问；纯生命周期规则负责确定性计算。依赖保持单向，不反向修改 Phase 1–7。

## 7. Provider 设计审查

建议 V1 Provider：

- `OperationEffectivenessProvider`：读取行动事件和前后窗口；
- `LifecycleInputProvider`：读取生命周期规则所需的版本化输入；
- `BenchmarkProvider`：批量读取统一口径的比较数据。

Provider 必须：

- 只读；
- 返回 DTO；
- 不向上返回 ORM 对象；
- 不调用业务 Service；
- 不执行写入或事务提交；
- 不承载复杂业务流程。

生命周期阶段判断不应放入 Provider，应由纯规则组件处理。行动效果的前后差值可以由纯统计组件处理，Provider 只准备窗口数据。

## 8. API 设计审查

### 行动效果

```text
GET /api/v1/operations/effectiveness
```

应支持 `action_id`、`drama_id`、`status`、`analysis_as_of`、受限 `window_days` 和分页。必须返回窗口、数据完整性和非因果声明。

### 生命周期

```text
GET /api/v1/dramas/{drama_id}/lifecycle
```

支持可选 `analysis_as_of`，返回阶段、规则版本、证据、输入窗口和 Availability。

### Benchmark

```text
GET /api/v1/dramas/benchmark
```

必须限制 drama ID 数量或分页筛选组，返回指标口径、版本和 `analysis_as_of`。静态 `/benchmark` 路径必须在动态 `/{drama_id}` 路径之前注册。

三个接口均只允许 USER/ADMINISTRATOR 查询，匿名返回 401。V1 不提供写接口。

## 9. Dashboard 设计审查

Operation Analytics Dashboard 可以包含：

1. Action Effectiveness；
2. Lifecycle Overview；
3. Benchmark Analysis。

前端只展示 API 结果和查询条件，不计算行动效果、生命周期或 Benchmark 指标。必须明确显示非因果说明、分析时间、窗口和版本。禁止 AI 建议卡片、自动方案和推荐排名。

## 10. Availability 与历史追溯

Design V2 应建立 Phase 8 专用 Availability 协议，至少覆盖：

- `NOT_CALCULATED`；
- `INSUFFICIENT_HISTORY`；
- `INCOMPLETE_BEFORE_WINDOW`；
- `INCOMPLETE_AFTER_WINDOW`；
- `INCOMPARABLE_SCOPE`；
- `NOT_AVAILABLE`。

所有历史读取必须满足：

```text
changed_at <= analysis_as_of
```

不得使用当前 revision 覆盖历史复盘。响应需携带来源算法版本、规则版本、窗口和数据截点。

## 11. 主要风险

### 因果误判

风险最高。通过固定非因果术语、API 字段命名和页面免责声明控制。

### 指标口径不一致

通过统一窗口、平台聚合、算法版本和 `analysis_as_of` 校验控制；不满足时返回 `INCOMPARABLE_SCOPE`。

### 历史数据不足

通过 Availability 协议明确表达，禁止用 0 或空数组伪造有效分析。

### 系统复杂度

V1 仅实现三个明确子模块、固定统计逻辑和纯规则，不引入持久化层、缓存、机器学习或自动决策。

### 查询性能

Benchmark 和历史窗口必须使用批量 Repository 查询，避免按 Drama 或 Action 循环产生 N+1。

## 12. Design V2 必须冻结项

进入实现前必须冻结：

1. 三个子模块的最终 V1 范围；
2. Action 效果锚点、窗口、指标和非因果术语；
3. 生命周期五阶段精确规则、优先级和 `lifecycle_rule_version`；
4. Benchmark 指标集合、比较组、时间和版本一致性；
5. Phase 8 Availability 枚举；
6. revision/as-of 读取规则；
7. Provider、纯规则组件与 Service 的职责边界；
8. API 参数上限、分页和静态路径注册顺序；
9. V1 不新增 Migration、不持久化分析结果。

## 13. 最终准入判断

Phase 8 架构方向合理，与 Phase 1–7 互补且未引入 AI 内容或重复业务事实。

最终判断：**允许进入 Phase 8 Design V2，暂不允许进入代码或数据库实现。**

Design V2 完成并通过实现准入审查后，方可依次开发 Contracts、纯规则、Providers、Service、API 和 Dashboard。
