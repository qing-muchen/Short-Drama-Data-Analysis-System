# Phase 9 Data Governance Module Summary

## 1. Module Position

Phase 9 建设 Data Governance / Quality Monitoring Layer。它在请求期间读取已有系统事实，以确定性规则评估数据新鲜度、完整性、一致性和输入可用状态，为现有分析系统提供可信度监控。

Phase 9 是只读治理层，负责：

- 数据更新时间和延迟状态；
- 必要字段、Metric 与时间序列覆盖；
- 关联、弱引用、Revision 与 `analysis_as_of` 一致性；
- QualityStatus、Availability 和最小 Evidence；
- SYSTEM scope 的实时治理查询和展示。

Phase 9 不负责：

- 修改、补齐或自动修复数据；
- 创建新的业务事实或持久化治理结果；
- 修改 Score、Prediction、Anomaly、Action、Explanation 等模块结果；
- 业务决策、推荐、自动化、AI、LLM、Agent 或 Machine Learning。

核心原则为 Read Only、No Data Mutation、No New Business Facts、No AI。

## 2. Architecture Overview

完整读取链路：

```text
Data Governance Dashboard
          ↓
Read-only Data Governance API
          ↓
DataGovernanceService
          ↓
Freshness / Completeness / Consistency Providers
          ↓
DataGovernanceRepository
          ↓
Existing Data Sources
```

规则执行链：

```text
DataGovernanceService
          ↓
Provider-produced Rule Input DTO
          ↓
Deterministic Quality Rules
          ↓
Result DTO
          ↓
Availability aggregation and API response
```

各层职责严格分离：Repository 读取事实，Provider 映射输入，Rule 纯计算，Service 编排，Router 认证与转换，Frontend 展示结果。依赖方向单向，不调用已有业务 Service。

## 3. Phase 2 Boundary

Phase 2 Data Quality 与 Phase 9 Data Governance 的职责不同，禁止混合：

| 模块 | 定位 | 结果形态 | 主要职责 |
| --- | --- | --- | --- |
| Phase 2 Data Quality | 业务分析质量模块 | 持久化质量评分和规则结果 | 形成业务分析层的质量结果，支持评分、历史和计算流程 |
| Phase 9 Data Governance | 治理监控层 | Request-time Read Model | 检查现有数据的可信状态、关联一致性和可用性，不保存检查结果 |

Phase 9 不替代 Phase 2，不调用或修改 Phase 2 的计算流程。现有 `/api/v1/data-quality/calculate`、`/score`、`/history`、`/rules` 保持原语义；Phase 9 只增加独立的只读治理路径。

## 4. Contracts

实现文件：`backend/services/data_governance/contracts.py`。

Contracts 使用纯 Python `@dataclass(frozen=True, slots=True)` 和不可变 tuple，不依赖 Pydantic、ORM、Repository、Session、FastAPI 或数据库。

### 4.1 Enums

- `QualityStatus`：`HEALTHY`、`WARNING`、`FAILED`、`NOT_AVAILABLE`；
- `AvailabilityStatus`：`AVAILABLE`、`PARTIAL`、`INSUFFICIENT`、`NOT_AVAILABLE`；
- `AvailabilityReason`：闭合的缺失、历史不足、关联、Revision 和评估失败原因；
- `QualityIssueType`：`FRESHNESS`、`COMPLETENESS`、`CONSISTENCY`；
- `GovernanceScope`：V1 仅允许 `SYSTEM`。

### 4.2 DTOs

- `DataQualityAvailability`；
- `EvidenceItem`；
- `FreshnessRuleInput`；
- `CompletenessRuleInput`；
- `ConsistencyCheckInput`；
- `ConsistencyRuleInput`；
- `FreshnessResult`；
- `CompletenessResult`；
- `ConsistencyResult`；
- `DataGovernanceResponse`。

Evidence 只包含定位和解释所需的 JSON-safe 最小值，不复制 Drama、Metric、Action、Snapshot、Revision 或 ORM 对象。

## 5. Quality Rules

三个 Rule 均为确定性纯计算组件，不访问数据库、Repository、Provider、Service、网络或当前时间，不修改任何数据。

### 5.1 FreshnessRule

- 职责：比较最新可见数据时间、统一分析截点和冻结阈值，判断延迟状态；
- 输出：状态、Availability、延迟秒数和 Evidence；
- 版本：`Freshness Rules V1.0`。

Rule 只报告延迟或未来时间问题，不触发数据刷新。

### 5.2 CompletenessRule

- 职责：检查必要字段、Metric 覆盖、时间序列连续性和关键关联覆盖；
- 输出：状态、覆盖率、缺失项和 Evidence；
- 版本：`Completeness Rules V1.0`。

Rule 不填充字段、不补齐 Metric、不生成缺失日期。

### 5.3 ConsistencyRule

- 职责：检查关系和弱引用、Revision 链、来源可见性及 `analysis_as_of` 一致性；
- 输出：状态、问题数量和 Evidence；
- 版本：`Consistency Rules V1.0`。

Rule 不修复关系、不删除记录、不修改 Revision。

三个规则由 `Governance Rule Set V1.0` 统一标识。V1 只记录版本，不提供版本注册、启停或回放平台。

## 6. Repository and Providers

### 6.1 DataGovernanceRepository

实现文件：`backend/repositories/data_governance_repository.py`。

Repository 只执行 SELECT，支持：

- Freshness 最新可见记录读取；
- Completeness 字段与 Metric 覆盖投影；
- Action source、Action status、Lineage 和 Revision 一致性事实读取；
- `analysis_as_of` 截点过滤；
- 截点前最大有效 Revision 选择；
- VOID Revision 过滤；
- frozen projection 返回。

Repository 不返回 ORM Model，不计算 QualityStatus、Availability、覆盖率或 Evidence，不调用 Rule，也不执行 commit、rollback 或 flush。

### 6.2 Providers

实现：

- `FreshnessProvider`：Repository projection → `FreshnessRuleInput`；
- `CompletenessProvider`：字段、Metric 和七日覆盖事实 → `CompletenessRuleInput`；
- `ConsistencyProvider`：关联、Lineage、Revision 和截点事实 → `ConsistencyRuleInput`。

Provider 只准备输入 DTO，不返回 ORM、不执行 SQL、不调用 Rule 或 Service、不生成质量结论。

## 7. DataGovernanceService

实现文件：`backend/services/data_governance/service.py`。

`DataGovernanceService` 负责：

- 冻结统一 `analysis_as_of`；
- 调用三个 Provider；
- 调用三个 Quality Rule；
- 聚合 QualityStatus 和 Availability；
- 组装 `DataGovernanceResponse`；
- 对单模块 Provider/Rule 异常进行隔离并记录日志。

时间策略：

- 未提供 `analysis_as_of`：注入 Clock 只调用一次，生成统一 UTC 截点；
- 显式提供：不读取 Clock，校验 timezone-aware 后规范化为 UTC；
- 一次 Overview 请求中的 Provider、Rule 和 Response 使用同一截点。

异常策略：一个模块失败时返回显式 `NOT_AVAILABLE + EVALUATION_FAILED`，其他模块继续执行；不使用 `None` 隐藏失败。Service 不访问 ORM、SQL、Session 或其他业务 Service，也不写数据库。

## 8. API Design

Phase 9 API 只提供 JWT 保护的 GET 接口：

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/data-quality/overview` | SYSTEM scope 完整治理概览 |
| GET | `/api/v1/data-quality/freshness` | Freshness 结果与分页 Evidence |
| GET | `/api/v1/data-quality/completeness` | Completeness 结果与分页 Evidence |
| GET | `/api/v1/data-quality/consistency` | Consistency 结果与分页 Evidence |

共同规则：

- `USER` 与 `ADMINISTRATOR` 均可查询；
- 匿名返回 401；
- 支持可选 timezone-aware `analysis_as_of`；
- 明细 Evidence 支持 `page/page_size`，`page_size <= 100`；
- 成功使用 `ResponseModel[T]`，错误使用现有 `ErrorResponse`；
- 不提供 POST、PUT、PATCH 或 DELETE。

API Schema 与内部 Contracts 分离，并显式转换 Availability、QualityStatus 和 Evidence。Router 不访问 ORM、Repository、Provider、Rule 或 Session。

## 9. Frontend Dashboard

页面路径：`/data-governance`。

页面包含：

1. Data Health Overview；
2. Freshness Card；
3. Completeness Card；
4. Consistency Card；
5. Evidence Drawer。

Frontend 复用现有 Axios Client、Token interceptor 和认证路由守卫。Overview 与三个模块使用独立请求及 loading、empty、error、success 状态；单模块失败不阻断其他模块。

页面只展示 API 返回的状态、延迟、覆盖率、问题数、缺失项、规则版本和 Evidence。它不计算指标、不判断阈值、不解释 Evidence、不提供修复、推荐、自动化或 AI 功能。当前页面无需图表，因此没有引入额外 ECharts 逻辑或新依赖。

## 10. Availability Protocol

AvailabilityStatus 表示形成治理结论所需输入的可用程度：

- `AVAILABLE`：计划输入可用；
- `PARTIAL`：部分输入缺失；
- `INSUFFICIENT`：历史长度或样本不足；
- `NOT_AVAILABLE`：无法获得评估输入或执行失败。

QualityStatus 表示质量判断结果，与 AvailabilityStatus 正交。例如输入完整但发现严重问题可以表示为 `FAILED + AVAILABLE`。

协议约束：

- 不使用 `None`、空字符串或数值 0 表达业务状态；
- 非 AVAILABLE 状态必须提供闭合的 AvailabilityReason；
- 原因去重并保持稳定顺序；
- Backend、API 和 Frontend 保持相同状态语义；
- Frontend 不重新映射或推导新状态。

## 11. Database Impact

Phase 9 V1 不创建 Migration，不新增：

- Quality Result 表；
- Quality Snapshot 表；
- Quality Cache 表；
- Quality History 表。

Phase 9 不修改 V001–V013、ORM Model 或 Existing Tables，采用 Request-time Read Model。治理结果只存在于单次请求响应中，不形成新的持久化业务事实。

未来如需治理历史趋势、固定报告、周报/月报、审计快照或缓存，必须重新完成独立的 Architecture Review、Database Design 和 Migration Review，不得在当前结构上隐式增加持久化。

## 12. Testing Record

| 阶段 | 验证范围 | 结果 |
| --- | --- | --- |
| Phase 9.1 Contracts | Enum、不可变 DTO、边界和无数据库依赖 | 13 passed |
| Phase 9.2 Rules | Freshness、Completeness、Consistency 规则与确定性 | 17 passed |
| Phase 9.1–9.2 | Contracts + Rules 回归 | 30 passed |
| Phase 9.3 Repository + Providers | as-of、Revision、VOID、projection、DTO 映射 | 18 passed |
| Phase 9.1–9.3 | Backend 回归 | 48 passed |
| Phase 9.4 Service | Clock、三链路、Availability、异常隔离 | 11 passed |
| Phase 9.1–9.4 | Backend 回归 | 59 passed |
| Phase 9.5 API | 路由、GET-only、JWT、Schema、Availability、边界 | 20 passed |
| Phase 9.1–9.5 | Backend 回归 | 79 passed |
| Phase 9.6 Frontend | `npm exec vue-tsc -- --noEmit` | passed |
| Phase 9.6 Frontend | `npm run build` | passed |

Frontend 构建没有新增依赖或 lockfile 修改。Vite 仅报告现有 chunk size 非阻塞警告，未修改构建配置。

## 13. Git History

| Commit | Message | 内容 |
| --- | --- | --- |
| `abe9f28` | `docs(phase9): add data quality design proposal` | Phase 9 初始设计提案 |
| `0f655f1` | `docs(phase9): add data quality architecture review` | 架构审查与 V1 边界冻结 |
| `fa223f3` | `docs(phase9): add data quality implementation plan` | 文件级实施与测试规划 |
| `74c122d` | `feat(phase9): add data governance contracts` | Contracts 与协议测试 |
| `9a358e8` | `feat(phase9): add data governance quality rules` | 三个确定性 Quality Rule |
| `e5ab784` | `feat(phase9): add data governance repositories and providers` | 只读 Repository 与输入 Providers |
| `6bdedac` | `feat(phase9): add data governance service` | Service 编排与异常隔离 |
| `a3c1cde` | `feat(phase9): add data governance api` | 只读 API、Schema、Dependency 与测试 |
| `e2df149` | `feat(phase9): add data governance frontend dashboard` | Frontend Dashboard 与构建验证 |
| 本归档提交 | `docs(phase9): add data governance module summary` | Phase 9 完整模块归档 |

## 14. Current Limitations

1. V1 仅支持 `SYSTEM` scope，不支持 DRAMA、PLATFORM、USER、TEAM 或自定义 scope。
2. 治理结果不持久化，因此不提供质量历史趋势、快照回放或跨请求报告。
3. 不支持自动修复、自动补数、关系修复或 Revision 修改。
4. 不提供用户级责任归属、治理工单或审批工作流。
5. Rule 版本仅用于追踪，不提供规则注册、启停、灰度、版本管理或历史执行平台。
6. Weak Reference 只按已冻结映射验证；无法证明的 identity 返回显式不可用 Evidence，不猜测目标表。
7. Evidence 保持最小化；Overview 每类仅返回有限代表性 Evidence，明细通过分页查询。

## 15. Future Extensions

未来可独立评估：

- Quality Trend Read Model；
- DRAMA / PLATFORM 等更多治理 Scope；
- 更细粒度、可分页和可筛选的 Evidence 查询；
- 数据治理审计报告、周报或月报；
- 规则注册与版本治理；
- 人工触发的数据修复工作流及完整审计。

上述扩展必须经过独立 Architecture Review。涉及长期保存、Snapshot、Cache、History 或报告固化时，还必须进行 Database Design 与 Migration Review；不得改变 Phase 9 V1 的只读、无自动修复、无 AI 和不产生新业务事实原则。
