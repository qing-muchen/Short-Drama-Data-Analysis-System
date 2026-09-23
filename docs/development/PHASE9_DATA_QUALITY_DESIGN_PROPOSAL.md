# Phase 9 Data Quality & Governance Center Design Proposal

## 1. 模块定位

Phase 9 建设 Data Quality & Governance Center，定位为现有分析系统之上的 Data Governance Layer / Quality Monitoring Layer。它在请求期间读取既有数据，使用确定性规则回答以下问题：

- 数据是否按预期时间到达；
- 必要数据是否完整且具有足够覆盖；
- 跨表关联、分析时间和 Revision 是否一致；
- 当前分析结果在数据层面是否具备可评估条件。

Phase 9 V1 是只读、实时计算的治理 Read Model。结果只存在于一次请求的响应中，不持久化、不修改源数据，也不产生新的业务分析事实。

### 1.1 与既有 Phase 2 Data Quality 的边界

现有 Phase 2 已实现 `DataQualityService`、`data_quality_rules`、`data_quality_scores`、`data_quality_rule_results` 及 `/api/v1/data-quality/calculate|score|history|rules`，负责版本化规则执行、质量评分、结果持久化和审计。

Phase 9 不替代或复制上述能力：

| 维度 | Phase 2 Data Quality | Phase 9 Governance Center |
| --- | --- | --- |
| 核心对象 | 版本化规则结果与质量分数 | 当前数据健康与治理可用性视图 |
| 写入 | 计算后持久化并记录 OperationLog | 无写入 |
| 历史 | 查询持久化质量历史 | V1 不保存历史 |
| 输出 | Completeness/Accuracy/Consistency/Timeliness Score | Freshness/Completeness/Consistency 监控结果与证据 |
| 用途 | 质量评分事实 | 数据可信状态检查与排障入口 |

未来实现不得调用 Phase 2 `DataQualityService.calculate_quality_score()`，不得重新生成或覆盖 `data_quality_scores`。如需消费 Phase 2 结果，只允许通过只读 Repository 读取其已存在事实并标注来源版本。

### 1.2 非目标

Phase 9 V1 不包含：

- AI、LLM、Agent 或机器学习；
- 自动修复、自动补数或自动修改业务数据；
- 推荐、自动决策或自动运营建议；
- Score、Prediction、Anomaly、Action、Explanation 或 Phase 2 Quality 的重新计算；
- 数据质量总分的新算法；
- 历史趋势持久化、快照或缓存；
- 写接口或治理工单自动创建。

## 2. 系统价值

现有模块能够产生评分、预测、异常、运营行动和解释结果，但调用者仍需判断这些结果背后的输入数据是否及时、完整和一致。Phase 9 提供统一、可解释的治理状态协议，使用户能够：

- 区分“业务指标为零”和“数据尚未到达”；
- 在使用分析结果前识别历史覆盖不足；
- 定位缺失字段、时间序列断点和失效关联；
- 检查历史 as-of 查询是否混入未来 Revision；
- 查看确定性规则版本及最小证据，而不修改原始数据。

该价值属于可信度监控，不是新的业务表现判断。

## 3. 架构设计

### 3.1 推荐调用链

纯 Rule 不应位于 Repository 的上游或直接读取数据库。推荐结构为：

```text
Data Quality Dashboard
        ↓
Read-only Data Quality API
        ↓
DataGovernanceService
        ├── Quality Providers ──→ DataGovernanceRepository ──→ Existing Data Sources
        └── Quality Rules (pure deterministic evaluation)
        ↓
Governance Response DTO
```

Provider 负责准备 Rule Input；Rule 只负责判断；Service 负责冻结分析截点、编排与聚合。所有依赖均为单向。

### 3.2 命名隔离

项目已经存在 `services/data_quality_service.py::DataQualityService`。为避免名称冲突和误用，Phase 9 推荐实现名称为：

- `DataGovernanceService`；
- `DataGovernanceRepository`；
- `backend/services/data_quality/` 作为纯 Contracts、Rules 和 Providers 包；
- `backend/routers/data_governance.py` 作为独立 Router 文件，并使用既有 `/data-quality` URL 前缀下的不冲突只读路径。

是否采用 `DataGovernanceService` 作为最终类名标记为 `[TBD-P9-01]`，由 Architecture Review 冻结。无论最终名称如何，都不得修改现有 Phase 2 Service 的职责。

### 3.3 依赖边界

Phase 9 禁止调用：

- `ScoreService`；
- 现有 `DataQualityService` 的计算入口；
- `PredictionService`；
- `AnomalyService`；
- `OperationActionService`；
- `AnalysisExplanationService`；
- `DramaProfileService`；
- `OperationAnalyticsService`。

需要使用已有结果时，通过对应只读 Repository 或专用投影查询获取，不反向依赖业务编排层。

## 4. Database 影响分析

Phase 9 V1 不创建 Migration，不修改 V001–V013，不新增业务表。

明确不新增：

- `data_quality_results`；
- `quality_snapshots`；
- `quality_cache`；
- `freshness_results`；
- `completeness_results`；
- `consistency_results`。

V1 使用现有数据源，包括但不限于：

- `dramas` 及其关联表；
- `drama_metric_snapshots` 与 Revision；
- 现有 Phase 2 quality rules/scores/results；
- `prediction_results`；
- `data_anomaly_records`；
- `operation_actions` 及 history/source；
- `analysis_explanations` 与 lineage。

不建立跨模块新 Foreign Key。若未来需要长期质量趋势、审计报告、周报/月报或固定证据快照，必须单独进入 Migration Review，明确保留周期、唯一身份和来源版本后才能考虑 V014 或后续 Migration。

## 5. Contracts 设计

建议位置：`backend/services/data_quality/contracts.py`。Contracts 为纯 Python frozen DTO，不导入 ORM、Repository、Session、FastAPI 或数据库。

### 5.1 Enum

`QualityAvailabilityStatus`：

- `AVAILABLE`；
- `PARTIAL`；
- `INSUFFICIENT`；
- `NOT_AVAILABLE`。

建议使用 `QualityAvailabilityStatus` 而不是通用 `AvailabilityStatus`，避免与 Phase 7/8 不同语义的 Enum 被错误混用。

`QualityStatus`：

- `PASS`：规则范围内未发现问题；
- `WARNING`：存在可继续使用但需要关注的问题；
- `FAIL`：存在违反冻结规则的问题；
- `NOT_EVALUATED`：Availability 不允许形成结论。

`QualityIssueType`：

- `FRESHNESS`；
- `COMPLETENESS`；
- `CONSISTENCY`。

`AvailabilityReason` 至少包含：

- `NO_DATA`；
- `INSUFFICIENT_HISTORY`；
- `MISSING_REQUIRED_FIELD`；
- `INCOMPLETE_TIME_SERIES`；
- `UNRESOLVED_RELATION`；
- `REVISION_NOT_VISIBLE`；
- `UNSUPPORTED_SCOPE`；
- `NOT_AVAILABLE`。

### 5.2 通用 DTO

`QualityAvailability`：

- `status`；
- `reasons`（闭合 Enum 集合）；
- `evaluated_as_of`。

`QualityEvidence`：

- `check_code`；
- `observed_value`；
- `expected_condition`；
- `source_type`；
- `source_reference_ids`；
- `message`。

Evidence 只保存最小解释信息，不复制完整 ORM 或业务结果。

`QualityRuleVersion`：

- `rule_code`；
- `rule_version`；
- `parameters`（冻结、类型化参数，不接受任意 JSON）。

### 5.3 结果 DTO

`FreshnessResult`：

- scope identity；
- `latest_data_at`；
- `delay_seconds`；
- `quality_status`；
- `availability`；
- `rule_version`；
- `evidence`。

`CompletenessResult`：

- scope identity；
- `required_item_count`；
- `observed_item_count`；
- `missing_items`；
- `coverage_window`；
- `quality_status`；
- `availability`；
- `rule_version`；
- `evidence`。

`ConsistencyResult`：

- scope identity；
- `checked_relation_count`；
- `issue_count`；
- `quality_status`；
- `availability`；
- `rule_version`；
- `evidence`。

`DataQualityGovernanceResponse`：

- `analysis_as_of`；
- `scope`；
- `freshness`；
- `completeness`；
- `consistency`；
- `availability`；
- `rule_set_version`。

V1 不增加新的质量分数或 Grade。Overview 只聚合三类状态，不生成与 Phase 2 `total_score` 竞争的数值。

## 6. Quality Rule 设计

Rule Component 必须确定性、版本化、无数据库、无网络、无外部服务。输入和输出均使用 Contracts DTO，相同输入必须产生相同结果。

### 6.1 FreshnessRule

输入：

- `analysis_as_of`；
- 数据集期望更新周期；
- 最新可见数据时间；
- 最近更新时间间隔序列（如范围支持）。

输出：`FreshnessResult`。

计算：

```text
delay_seconds = analysis_as_of - latest_data_at
```

规则不得读取当前时间，必须使用 Service 冻结的 `analysis_as_of`。建议状态为 PASS、WARNING、FAIL、NOT_EVALUATED；具体延迟阈值需要按数据源更新约定冻结，当前标记为 `[TBD-P9-02]`。在阈值未冻结前不得编码。

### 6.2 CompletenessRule

输入：

- 必填字段存在性投影；
- 期望 Metric 类型集合；
- 期望日期窗口；
- 每个日期/平台的可见 Observation 状态。

检查：

- Drama 必要展示字段是否存在；
- 支持指标是否有可用值；
- 指定时间窗口是否连续；
- 必要关联是否有最小覆盖。

Rule 不填充字段、不插值、不以 0 代替缺失。必要字段集合、Metric 覆盖范围和时间窗口为 `[TBD-P9-03]`，需在 Review 中依据现有 Schema 冻结。

### 6.3 ConsistencyRule

输入：

- 关联身份投影；
- Source/Target identity；
- `analysis_as_of` 与 source timestamps；
- Snapshot/Revision identity；
- 当前状态与历史事件投影。

检查：

- 非空 Drama 关联是否指向有效实体；
- Action Source 的弱关联是否可解析；
- Explanation Lineage 的弱关联是否可解析；
- 分析结果是否引用晚于自身 `analysis_as_of` 的输入；
- Snapshot 在截点前是否能选出唯一最新有效 Revision；
- 状态与历史事件是否存在明显矛盾。

Rule 只报告不一致证据，不修正关联或状态。V1 支持的跨模块检查清单标记为 `[TBD-P9-04]`，必须避免一次性扫描所有模块造成无边界范围。

### 6.4 版本策略

建议版本：

- `Freshness Rules V1.0`；
- `Completeness Rules V1.0`；
- `Consistency Rules V1.0`；
- `Governance Rule Set V1.0`。

版本随响应返回，V1 不持久化。规则参数变化必须提升版本，禁止在同一版本下静默改变阈值。

## 7. Repository 设计

建议新增只读 `DataGovernanceRepository`，避免与现有负责 Phase 2 评分持久化的 `DataQualityRuleRepository`、`DataQualityScoreRepository` 和 `DataQualityRuleResultRepository` 混淆。

Repository 只执行查询并返回不可变投影，建议能力：

- `get_latest_dataset_timestamp(scope, analysis_as_of)`；
- `get_update_intervals(scope, start_at, analysis_as_of)`；
- `get_drama_required_field_projection(drama_ids, analysis_as_of)`；
- `get_metric_coverage(drama_ids, window, analysis_as_of)`；
- `get_relation_projection(scope, analysis_as_of)`；
- `get_revision_visibility(snapshot_ids, analysis_as_of)`；
- `get_weak_reference_projection(source_types, analysis_as_of)`。

所有可版本化查询必须满足 `changed_at <= analysis_as_of`，并选择截点前最新有效 Revision；历史最新状态为 `VOID` 时不得回退到更旧有效值伪造当前可见事实。

Repository 禁止：

- 计算 PASS/WARNING/FAIL；
- 计算覆盖率或数据新鲜等级；
- 调用 Rule/Provider/Service；
- 创建 Session；
- 执行写入、commit、rollback 或 flush。

非版本化表无法精确重建旧状态时，V1 必须返回 `NOT_AVAILABLE` 或限定为当前截点，不能声称完成历史还原。

## 8. Provider 设计

### 8.1 FreshnessProvider

批量读取最新数据时间和更新间隔，构造 `FreshnessRuleInput`。Provider 不判断 DELAYED/FAIL，也不读取系统当前时间。

### 8.2 CompletenessProvider

读取必要字段投影、Metric 覆盖和日期连续性输入，构造 `CompletenessRuleInput`。Provider 不补数、不计算质量分数。

### 8.3 ConsistencyProvider

读取关系、弱引用、analysis timestamp 与 Revision 投影，构造 `ConsistencyRuleInput`。Provider 不决定问题严重程度，也不自动修复。

所有 Provider：

- 只依赖只读 Repository Protocol 和 Contracts；
- 不返回 ORM Model；
- 不执行 SQL；
- 不写数据库；
- 不调用任何业务 Service；
- 使用批量查询避免 N+1。

## 9. Service 设计

逻辑职责名为 Data Quality Governance Service；为避免与现有类冲突，推荐实现 `DataGovernanceService`。

公开方法建议：

- `get_overview(scope, analysis_as_of)`；
- `get_freshness(scope, analysis_as_of, page, page_size)`；
- `get_completeness(scope, analysis_as_of, page, page_size)`；
- `get_consistency(scope, analysis_as_of, page, page_size)`。

Service 负责：

1. 校验 scope、分页和时间参数；
2. 每次请求冻结一次带时区 UTC `analysis_as_of`；
3. 调用对应 Provider；
4. 调用对应纯 Rule；
5. 聚合 Availability 与响应 DTO；
6. 隔离单个检查失败，保留其他检查结果。

Service 不负责 SQL、ORM、数据修改、自动修复、Phase 2 质量评分或其他业务模块重算。V1 为只读，不建立事务提交边界。

Overview 的聚合优先级建议为 `NOT_AVAILABLE > INSUFFICIENT > PARTIAL > AVAILABLE`，但状态合并细节需在 Review 中冻结为 `[TBD-P9-05]`。

## 10. API 设计

Phase 9 V1 仅规划 JWT Bearer 保护的 GET 接口：

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/data-quality/overview` | 获取治理总览 |
| GET | `/api/v1/data-quality/freshness` | 查询数据新鲜度 |
| GET | `/api/v1/data-quality/completeness` | 查询数据完整性 |
| GET | `/api/v1/data-quality/consistency` | 查询数据一致性 |

上述路径与现有 `/calculate`、`/score`、`/history`、`/rules` 不冲突。实现时推荐独立 Router 文件并保持静态路径在动态路径之前注册。

共同参数建议：

- `analysis_as_of`：可选、带时区 ISO 8601 时间，Service 规范化为 UTC；
- `scope_type`：治理范围；
- `scope_id`：范围身份，按 scope 类型决定是否必填；
- `page`：默认 1；
- `page_size`：默认 20，最大 100。

V1 scope 是否仅支持 SYSTEM，或同时支持 DRAMA/PLATFORM，标记为 `[TBD-P9-06]`。在 scope 冻结前不得自行扩展参数语义。

成功响应继续使用 `ResponseModel[T]`；错误继续使用现有 `ErrorResponse`。权限：

- `USER`：允许查看；
- `ADMINISTRATOR`：允许查看；
- 匿名：401。

V1 不提供 POST、PUT、PATCH 或 DELETE。

## 11. Frontend 规划

建议页面：`/data-governance`，避免与现有 Phase 2 `/data-quality` 页面职责混淆。最终路径标记为 `[TBD-P9-07]`。

页面结构：

1. Data Health Overview：展示三类状态和统一 Availability；
2. Freshness：展示最新数据时间、延迟及规则证据；
3. Completeness：展示必要字段、Metric 覆盖和时间序列缺口；
4. Consistency：展示关系、as-of 和 Revision 问题；
5. Evidence Drawer：展示规则版本、期望条件和来源引用。

每个模块独立处理 loading、empty、error、success。单模块失败不阻断其他模块。Frontend 只展示 API 数据，不计算阈值、覆盖率、质量状态或严重程度，不提供修复按钮和自动操作入口。

V1 优先使用状态卡、趋势无关的证据表格和问题明细。由于不保存历史结果，不设计伪历史趋势图。

## 12. 测试规划

### 12.1 Contracts

- Enum 闭合值；
- DTO 正常与非法构造；
- Availability 状态/原因组合；
- 真实零值与缺失值语义；
- 无 ORM、Repository、Session 或数据库依赖。

### 12.2 Rules

- Freshness 阈值两侧及精确边界；
- Completeness 必填项、窗口缺口和真实零值；
- Consistency 有效/失效关系、未来输入和 Revision 冲突；
- 相同输入输出一致；
- 不读取当前时间、不访问数据库或网络。

### 12.3 Repository

- `analysis_as_of` 过滤；
- 截点前最新有效 Revision；
- `VOID` 处理；
- 批量查询和空数据；
- 无 commit、rollback、flush 或业务判断。

### 12.4 Providers

- Repository 投影到 Rule Input DTO；
- 批量读取与缺失数据；
- 不返回 ORM；
- 不调用 Service；
- 不执行质量判断。

### 12.5 Service

- 单次请求统一 `analysis_as_of`；
- 三类完整流程；
- Availability 聚合；
- 单规则/Provider 异常隔离；
- 参数和分页校验；
- 不访问 ORM/Session/SQL，不调用现有业务 Service。

### 12.6 API

- 四条 GET 路径和无写方法；
- JWT Bearer、匿名 401、USER/ADMIN 查询；
- 参数与分页；
- Schema/ResponseModel/ErrorResponse；
- Dependency Override；
- Router 分层边界和 OpenAPI。

### 12.7 Frontend

- API Client 参数映射；
- 四种 Availability；
- loading/empty/error/success；
- 单模块失败隔离；
- `vue-tsc --noEmit`；
- `npm run build`；
- 无新增依赖和 lockfile 修改。

## 13. 风险分析

### 13.1 与 Phase 2 重复

风险：Phase 9 再次生成质量分数或使用同名 Service，形成两套“Data Quality”事实。

控制：Phase 9 不输出数值总分、不持久化、使用独立 Governance Service/Repository 名称，并禁止调用 Phase 2 计算入口。

### 13.2 实时查询成本

风险：完整性和一致性扫描可能跨越大量 Snapshot、Revision 和弱关联数据。

控制：V1 冻结 scope、时间窗口、分页和批量投影；禁止无边界全库明细扫描。暂不引入缓存，先通过查询计划与真实指标验证性能。

### 13.3 阈值误导

风险：统一延迟阈值无法适用于不同来源更新频率。

控制：阈值必须按数据源契约冻结并版本化；未知契约返回 `NOT_EVALUATED/NOT_AVAILABLE`，不猜测阈值。

### 13.4 历史可追溯限制

风险：部分主数据表缺少 Revision，无法可靠还原历史状态。

控制：Repository 明示可证明范围；无法历史还原时返回 Availability 原因，不读取当前行伪装历史事实。

### 13.5 弱关联解析

风险：Action Source 与 Lineage 使用逻辑引用，不存在数据库 FK，来源记录可能已不存在。

控制：Consistency 只报告不可解析引用，不级联删除、不自动修复，也不为弱关联补建 FK。

### 13.6 无持久化的功能限制

风险：V1 不能提供治理状态历史趋势和审计快照。

控制：Dashboard 不伪造趋势；历史保存需求进入独立 Migration Review。

## 14. 未来扩展方向

后续独立 Phase 可评估：

- 按数据源配置版本化更新契约；
- 更多跨模块一致性检查；
- 经审查的治理报告与历史快照；
- 数据责任人、人工确认和受控处置流程；
- 质量规则配置治理与变更审计；
- 在性能证据支持下引入只读缓存。

未来扩展仍须遵守 No AI、No Automation、No Data Mutation、No Business Recalculation 和 No New Business Facts。自动修复、自动决策和推荐能力不属于本模块方向。

## 15. 建议实施路线

本提案通过 Architecture Review 后，建议依次进行：

1. Design V2：冻结 scope、阈值、规则输入、Availability 和命名；
2. Implementation Review：冻结目录、Repository 查询能力和 API Schema；
3. Contracts；
4. Deterministic Rules；
5. Read Repository + Providers；
6. Governance Service；
7. Read-only API；
8. Frontend Dashboard；
9. Module Summary。

在 Architecture Review 明确 `[TBD-P9-01]` 至 `[TBD-P9-07]` 前，不进入代码、Migration、ORM 或 Frontend 实现。
