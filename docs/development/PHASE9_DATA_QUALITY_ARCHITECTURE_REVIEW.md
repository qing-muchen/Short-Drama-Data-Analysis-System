# Phase 9 Data Quality & Governance Center Architecture Review

## 1. Review Scope

本次审查对象为 `PHASE9_DATA_QUALITY_DESIGN_PROPOSAL.md`，目标是判断 Phase 9 是否具备进入 Implementation Planning 的条件。审查范围包括：

- 与 Phase 2 Data Quality 的职责边界；
- Read Model 分层与依赖方向；
- Service、Repository、Provider 和 Rule 职责；
- Contracts、Evidence 与版本协议；
- 数据库影响；
- 四条只读 API 与 Frontend 边界；
- 测试策略；
- `[TBD-P9-01]` 至 `[TBD-P9-07]` 的最终处置。

本次 Review 不授权代码、Migration、ORM、Backend 或 Frontend 实现。

## 2. Module Position

### 2.1 审查结论

Phase 9 的定位合理，但必须严格限定为 Data Governance / Quality Monitoring Layer。V1 在请求期间对已有数据执行确定性检查，返回当前 Freshness、Completeness、Consistency 和 Availability，不持久化结果、不修改源数据、不触发其他分析模块。

Phase 9 不创建业务事实，不是第二套 Data Quality Score，也不是自动修复系统。

### 2.2 Phase 2 与 Phase 9 的冻结边界

| 边界 | Phase 2 Data Quality | Phase 9 Data Governance |
| --- | --- | --- |
| 目标 | 规则执行、质量分数和历史事实 | 当前数据治理健康与排障视图 |
| 结果 | 持久化 score/rule result | Request-time DTO，不保存 |
| 写入 | 管理员计算、事务、OperationLog | 只读，无事务提交 |
| 数值评分 | Completeness/Accuracy/Consistency/Timeliness/Total | 不产生任何新分数或 Grade |
| 历史 | 查询已持久化历史 | V1 不提供治理历史趋势 |
| 自动行为 | 无 | 无 |

冻结禁止项：

- Phase 9 不调用 `DataQualityService.calculate_quality_score()`；
- 不写入 `data_quality_scores`、`data_quality_rule_results` 或 `data_quality_issues`；
- 不复制 Phase 2 评分公式；
- 不把 Phase 2 score 重新包装成 Phase 9 的新质量事实；
- 不修改 Score、Prediction、Anomaly、Action、Explanation 或 Drama Profile。

需要展示 Phase 2 已有结果时，只能将其作为只读来源引用，并明确携带既有 `rule_set_version` / `analysis_as_of`。

### 2.3 非功能边界

V1 继续冻结：No AI、No LLM、No Agent、No Machine Learning、No Automation、No Data Mutation、No Recommendation、No Business Recalculation、No New Business Facts。

## 3. Architecture Decision

### 3.1 冻结架构

```text
Data Governance Dashboard
        ↓
Read-only Data Governance API
        ↓
DataGovernanceService
        ├── Providers ──→ DataGovernanceRepository ──→ Existing Data
        └── Deterministic Quality Rules
        ↓
Contracts Response DTO
```

Proposal 中线性表达的 “Service → Rules → Repository” 不作为实现依赖图。Rule 不得访问 Repository；正确结构是 Service 分别编排 Provider 与 Rule，Provider 通过 Repository 准备 Rule Input。

### 3.2 分层职责

`DataGovernanceService`：

- 参数校验；
- 每次请求冻结一次 UTC `analysis_as_of`；
- Provider / Rule 编排；
- Quality Status 与 Availability 聚合；
- Response DTO 组装；
- 单检查异常隔离。

Provider：

- 调用只读 Repository；
- 批量读取所需投影；
- 映射为 Contracts Rule Input；
- 不执行 PASS/WARNING/FAILED 判断。

`DataGovernanceRepository`：

- 只执行 SELECT；
- 支持 `analysis_as_of`、Revision 和窗口过滤；
- 返回不可变投影；
- 不执行质量规则；
- 不 commit、rollback、flush 或创建 Session。

Rule：

- 接收纯 DTO；
- 执行确定性质量判断；
- 输出纯 DTO；
- 不访问数据库、网络、系统当前时间或业务 Service。

### 3.3 异常隔离

一个 Provider/Rule 失败时，对应模块返回 `NOT_AVAILABLE`，其他模块继续返回。技术异常必须记录日志，不能转换为 HEALTHY、零值或空证据。Clock 或规则版本无法确定时，整体请求失败，不生成不可追溯结果。

## 4. Service Naming Decision

`[TBD-P9-01]` 决议：V1 最终名称冻结为 `DataGovernanceService`。

配套名称冻结为：

- `DataGovernanceRepository`；
- `FreshnessProvider`；
- `CompletenessProvider`；
- `ConsistencyProvider`；
- `FreshnessRule`；
- `CompletenessRule`；
- `ConsistencyRule`。

现有 `services/data_quality_service.py::DataQualityService` 保持不变。不得创建第二个同名 Service，也不得通过 import alias 隐藏二者差异。

建议 Phase 9 代码目录仍使用 `backend/services/data_quality/` 存放纯 Contracts、Rules 和 Providers，但 `service.py` 中的类名必须为 `DataGovernanceService`。Router 文件建议使用 `data_governance.py`，Repository 文件建议使用 `data_governance_repository.py`。

## 5. Database Impact Decision

### 5.1 V1 决议

Phase 9 V1 不创建 V014 Migration，不修改 V001–V013，不修改 ORM 或现有表。

明确禁止新增：

- quality result 表；
- quality snapshot 表；
- quality cache 表；
- freshness/completeness/consistency 结果表；
- 自动修复记录表。

V1 采用 Request-time Read Model。所有结果只存在于当前响应中。

### 5.2 历史语义

可版本化数据必须遵守 `changed_at <= analysis_as_of`，并选择截点前最新 Revision。截点前最新 Revision 为 `VOID` 时排除该 observation slot，不回退到更旧有效 Revision。

非版本化主数据无法可靠还原过去状态时，只能：

- 限定为当前状态检查；或
- 返回 `NOT_AVAILABLE` / 明确原因。

禁止读取当前行并声称其为历史事实。

### 5.3 未来持久化

历史治理趋势、固定审计报告、周报/月报或缓存需求必须重新进入 Migration Review，明确身份、版本、保留周期、数据量和删除策略后才能设计后续 Migration。

## 6. Rule Boundary Decision

### 6.1 FreshnessRule

检查单元冻结为每个 ACTIVE Platform 下 ONLINE 的 `drama_platform` metric feed。最新时间取 `analysis_as_of` 前最新可见、非 VOID Snapshot Revision 对应的 `snapshot_time`。

V1 阈值冻结：

| delay | QualityStatus | 含义 |
| --- | --- | --- |
| `0 <= delay <= 24h` | `HEALTHY` | 满足现有系统 24 小时新鲜度基线 |
| `24h < delay <= 72h` | `WARNING` | 至少错过一个日更新周期 |
| `delay > 72h` | `FAILED` | 连续三个日更新周期未获得可见数据 |
| 无可见数据 | `NOT_AVAILABLE` | 不能以零延迟替代缺失数据 |
| `latest_data_at > analysis_as_of` | `FAILED` | 存在未来时间一致性问题 |

`[TBD-P9-02]` 已冻结。24 小时沿用现有 `FRESHNESS_LIMIT`；72 小时为 V1 明确升级阈值。阈值属于 `Freshness Rules V1.0`，变化必须提升规则版本。

Rule 不刷新数据、不触发导入、不读取当前时间。

### 6.2 CompletenessRule

V1 评估对象冻结为在当前可证明状态下：

- Drama status 为 `SERIALIZING` 或 `COMPLETED`；
- 至少一个关联 `drama_platform` 为 ONLINE，且 Platform 为 ACTIVE。

检查范围冻结：

1. Drama 必填字段：`drama_id`、`drama_code`、`drama_name`、`status`；
2. 关联覆盖：目标 Drama 至少存在一个符合条件的平台关系；
3. Metric 覆盖：每个目标 drama-platform 在 `analysis_as_of` 前 7 个完整业务日中，每日存在至少一个可见、非 VOID Snapshot Revision；
4. 必要 Metric：`play_count` 必须存在且非负；
5. 时间连续性：7 个业务日不得缺日。

互动字段在 V1 不作为必填 Metric，因为现有模型没有平台能力元数据来证明所有来源都应提供 like/comment/favorite/share。它们可以作为 Evidence 展示，但不得据此判定 FAILED。

状态冻结：

- 所有必填项和 7 日覆盖满足：HEALTHY；
- Drama 基础字段存在，但部分平台关系或日期缺失：WARNING；
- 必填身份字段非法、目标关系完全不存在或 play_count 不可用：FAILED；
- 无目标 Drama 或不足以建立检查范围：NOT_AVAILABLE，并由 Availability 表达原因。

`[TBD-P9-03]` 已冻结。Rule 不填充字段、不插值、不补零。

### 6.3 ConsistencyRule

V1 仅检查现有结构能够明确解析的以下项目：

1. Snapshot Revision：`current_revision_id` 属于同一 snapshot；版本链连续；截点前最多选择一个最新 Revision；
2. Operation Action Source：ANOMALY → `data_anomaly_records`、QUALITY → `data_quality_scores`、SCORE → `drama_scores`、MANUAL → reference 必须为空；
3. Operation Action Status：主表 status 与截至截点最新状态事件一致；
4. Explanation Lineage：target 为 EXPLANATION 时目标记录存在，且 lineage `analysis_as_of` 与 Explanation 截点一致；
5. 可解析 Lineage Source：SNAPSHOT → `drama_metric_snapshots`、RULE → `data_quality_rules`、ANOMALY_EVIDENCE → `data_anomaly_records`；
6. 时间一致性：被引用来源的可见时间不得晚于目标 `analysis_as_of`。

V1 排除：

- `METRIC` 和 `PREDICTION_INPUT` source ID 的存在性检查，因为当前缺少统一、冻结的 canonical identity；
- 任意文本推断；
- 无边界全库深层递归血缘检查；
- 自动修复、级联删除或补建 Foreign Key。

`[TBD-P9-04]` 已冻结。无法明确解析的弱引用返回 NOT_AVAILABLE Evidence，不猜测目标表。

## 7. Contracts Freeze

### 7.1 QualityStatus

V1 冻结为：

- `HEALTHY`；
- `WARNING`；
- `FAILED`；
- `NOT_AVAILABLE`。

不采用 Proposal 中的 PASS/FAIL/NOT_EVALUATED，避免与 Phase 2 rule result `PASS/FAIL/NOT_APPLICABLE` 混淆。

### 7.2 Availability

V1 冻结为：

- `AVAILABLE`：输入足以完成全部计划检查；
- `PARTIAL`：部分检查完成，部分输入缺失；
- `INSUFFICIENT`：历史长度或样本不足；
- `NOT_AVAILABLE`：无数据、范围不支持或组件失败。

QualityStatus 与 Availability 正交：数据可以被完整评估且结果为 FAILED，此时必须返回 `quality_status=FAILED`、`availability=AVAILABLE`。禁止用 Availability 代替质量结论。

Availability 原因冻结至少包含：

- `NO_DATA`；
- `INSUFFICIENT_HISTORY`；
- `MISSING_REQUIRED_FIELD`；
- `INCOMPLETE_TIME_SERIES`；
- `UNRESOLVED_RELATION`；
- `REVISION_NOT_VISIBLE`；
- `UNSUPPORTED_SCOPE`；
- `NOT_AVAILABLE`。

### 7.3 Issue 类型

`QualityIssueType` 冻结为：

- `FRESHNESS`；
- `COMPLETENESS`；
- `CONSISTENCY`。

### 7.4 Evidence

每个非 HEALTHY 检查必须返回至少一项 `QualityEvidence`。Evidence 冻结字段：

- `issue_type`；
- `check_code`；
- `entity_type`；
- `entity_id`（可空，仅 SYSTEM 汇总证据允许为空）；
- `observed_value`；
- `expected_condition`；
- `source_type`；
- `source_reference_ids`；
- `message`。

Evidence 只包含定位和解释所需最小值，不复制完整业务对象、完整 Snapshot、完整 Revision 或其他模块结果。列表 API 必须分页；Overview 只返回各类型有限数量的代表性 Evidence，V1 上限冻结为每类 5 项。

### 7.5 Rule 版本

版本冻结为：

- `Freshness Rules V1.0`；
- `Completeness Rules V1.0`；
- `Consistency Rules V1.0`；
- `Governance Rule Set V1.0`。

所有结果和 Overview 必须返回具体 `rule_version` 或 `rule_set_version`。V1 不写数据库，但同一版本下不得静默改变阈值、字段集合或检查范围。

### 7.6 Overview 聚合

`[TBD-P9-05]` 已冻结：

- Availability 最差优先级：`NOT_AVAILABLE > INSUFFICIENT > PARTIAL > AVAILABLE`；
- QualityStatus 最差优先级：`FAILED > WARNING > HEALTHY > NOT_AVAILABLE`；
- 若至少一个模块可评估，Overview QualityStatus 只在可评估模块中取最差状态；
- 若所有模块均不可评估，Overview 为 `quality_status=NOT_AVAILABLE`、`availability=NOT_AVAILABLE`；
- 模块失败不得被另一个 HEALTHY 模块覆盖。

## 8. API Boundary

### 8.1 Scope 决议

`[TBD-P9-06]` 已冻结：Phase 9 V1 仅支持 `SYSTEM` scope。

理由：V1 需要先验证跨模块批量查询成本与状态语义；在没有分页/责任边界证据前，不开放 DRAMA/PLATFORM 多态 scope。明细响应仍可包含 entity identity，客户端不能提交任意 scope_type/scope_id。

### 8.2 接口

以下接口冻结为 GET-only：

| Method | Path | 参数 |
| --- | --- | --- |
| GET | `/api/v1/data-quality/overview` | `analysis_as_of?` |
| GET | `/api/v1/data-quality/freshness` | `analysis_as_of?`, `page=1`, `page_size=20` |
| GET | `/api/v1/data-quality/completeness` | `analysis_as_of?`, `page=1`, `page_size=20` |
| GET | `/api/v1/data-quality/consistency` | `analysis_as_of?`, `page=1`, `page_size=20` |

`page_size` 最大 100。`analysis_as_of` 必须是带时区 ISO 8601 时间并由 Service 规范化为 UTC。未提供时由注入 Clock 在 Service 入口读取一次。

接口继续使用现有 `ResponseModel[T]` 与 `ErrorResponse`。JWT Bearer 权限：USER 和 ADMINISTRATOR 可查询；匿名返回 401。V1 不新增 POST、PUT、PATCH 或 DELETE。

### 8.3 与现有 API 共存

新静态路径与现有 `/calculate`、`/score`、`/history`、`/rules` 不冲突。未来实现使用独立 `data_governance.py` Router 和 `DataGovernanceServiceDependency`，不得修改现有 Router 的计算语义。

## 9. Frontend Boundary

`[TBD-P9-07]` 已冻结：页面路径为 `/data-governance`。

页面仅展示：

- Data Health Overview；
- Freshness；
- Completeness；
- Consistency；
- Evidence 明细。

每个模块独立处理 loading、empty、error、success。Frontend 不计算 delay、覆盖率、QualityStatus、Availability 或聚合状态，不提供编辑、补数、刷新数据、修复关联或创建 Action 的入口。

由于 V1 不保存治理结果，Frontend 不展示伪历史趋势。状态卡和 Evidence 表格直接使用 API 数据。

## 10. Testing Strategy

### 10.1 Contracts

- QualityStatus、Availability、IssueType 闭合值；
- DTO 不变性和非法组合；
- FAILED + AVAILABLE 正交语义；
- Evidence 最小字段和每类 Overview 上限；
- 无 ORM、Repository、Session、FastAPI 或数据库依赖。

### 10.2 Rules

- Freshness 24h、72h 精确边界、无数据和未来时间；
- Completeness 必填字段、平台关系、7 日完整/缺口和真实零值；
- Consistency 六类 V1 检查和明确排除项；
- QualityStatus 与 Availability；
- 相同输入相同输出；
- 无当前时间、数据库、网络或 Service 依赖。

### 10.3 Repository

- `analysis_as_of` 过滤；
- 截点前最新有效 Revision 与 VOID；
- Action/Explanation 弱引用投影；
- 状态历史选择；
- 分页、批量查询和空数据；
- 不执行规则或写事务。

### 10.4 Providers

- Repository 投影到 Rule Input DTO；
- 7 日窗口和 freshness feed 映射；
- 缺失、不可解析和非版本化数据；
- 不返回 ORM、不执行 SQL、不调用 Service。

### 10.5 Service

- 同一请求只冻结一次 UTC as-of；
- 三类完整编排；
- Overview 双协议聚合；
- Provider/Rule 单模块异常隔离；
- 分页和参数校验；
- 不访问 ORM/Session/SQL、不调用现有业务 Service。

### 10.6 API

- 四条 GET-only 路径；
- JWT、匿名 401、USER/ADMIN 查询；
- ISO 时间与分页；
- ResponseModel/ErrorResponse/OpenAPI；
- Dependency Override；
- Router 无 Repository/ORM/Rule 访问。

### 10.7 Frontend

- API 参数与 TypeScript Schema；
- HEALTHY/WARNING/FAILED/NOT_AVAILABLE；
- AVAILABLE/PARTIAL/INSUFFICIENT/NOT_AVAILABLE；
- loading/empty/error/success 和模块隔离；
- `vue-tsc --noEmit`；
- `npm run build`；
- 无新增依赖和 lockfile 修改。

## 11. TBD Resolution

| TBD | 决议 | 分类 |
| --- | --- | --- |
| P9-01 Service 名称 | 冻结 `DataGovernanceService` | V1 冻结 |
| P9-02 Freshness 阈值 | `<=24h HEALTHY`、`24–72h WARNING`、`>72h FAILED` | V1 冻结 |
| P9-03 Completeness 范围 | 当前业务 Drama、必要字段/平台关系、7 日 play_count 连续覆盖 | V1 冻结 |
| P9-04 Consistency 清单 | Revision、Action Source/Status、Explanation target/可解析 source、as-of 六类检查 | V1 冻结 |
| P9-05 Overview 聚合 | Availability 与 QualityStatus 分别按最差优先级聚合 | V1 冻结 |
| P9-06 API Scope | 仅 SYSTEM | V1 冻结；DRAMA/PLATFORM 后续扩展 |
| P9-07 Frontend 路径 | `/data-governance` | V1 冻结 |

Implementation Planning 不得重新打开以上决议。若发现现有 Schema 无法提供冻结输入，必须返回 Architecture Review，不得在实现阶段自行改变规则。

后续扩展项：DRAMA/PLATFORM scope、不可解析 METRIC/PREDICTION_INPUT lineage、历史治理趋势、持久化报告、缓存和数据源自定义更新契约。

## 12. Implementation Readiness

### 12.1 通过项

- Phase 2 与 Phase 9 边界已明确；
- Service、Provider、Repository、Rule 单向职责已冻结；
- `DataGovernanceService` 命名已冻结；
- V1 无 Migration、无 ORM 修改、无持久化已冻结；
- 三类 Rule 的 V1 输入、阈值和检查范围已冻结；
- QualityStatus、Availability、Evidence 和版本协议已冻结；
- SYSTEM-only API 和 `/data-governance` Frontend 边界已冻结；
- 测试覆盖和禁止依赖已明确；
- 所有 Proposal TBD 已关闭或明确移出 V1。

### 12.2 最终判断

**Option A：允许进入 Phase 9 Implementation Planning。**

该判断只授权编写实现规划文档，不授权代码、Migration、ORM、Backend 或 Frontend 实现。Implementation Plan 必须将本 Review 作为冻结契约，并继续维持：

- Read-only request-time evaluation；
- No V014 Migration；
- No Phase 2 recalculation；
- No AI / automation / mutation；
- No unresolved TBD entering implementation。
