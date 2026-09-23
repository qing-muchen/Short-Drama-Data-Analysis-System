# Phase 9 Data Quality & Governance Center Implementation Plan

## 1. Implementation Scope

### 1.1 目标

Phase 9 V1 实现 Data Governance / Quality Monitoring Layer，在请求期间读取现有数据并执行确定性治理检查，提供：

- Data Freshness；
- Data Completeness；
- Data Consistency；
- Data Health Overview；
- 最小、可定位的 Quality Evidence。

本计划将 Architecture Review 的冻结结论转换为文件级实施边界、组件接口、测试范围和提交顺序。进入各实现阶段后不得自行改变规则阈值、检查范围、API 路径或状态协议。

### 1.2 V1 非目标

V1 不包含：

- AI、LLM、Agent、Machine Learning 或推荐系统；
- 自动补数、自动刷新、自动修复或业务数据修改；
- 新质量评分、Grade 或持久化业务事实；
- 治理历史趋势、周报、月报或缓存；
- DRAMA / PLATFORM scope API；
- 对 Phase 2 Data Quality 的重新计算或替代。

### 1.3 Phase 2 边界

Phase 2 `DataQualityService` 继续负责质量规则执行、质量分数、规则结果和历史事实持久化。Phase 9 `DataGovernanceService` 只负责当前治理健康检查，返回 request-time DTO，不写入 `data_quality_scores`、`data_quality_rule_results` 或其他表。

禁止 Phase 9：

- 调用 Phase 2 的计算方法；
- 复制 Phase 2 的评分公式；
- 把 Phase 2 score 重新包装为 Phase 9 新事实；
- 修改 Score、Prediction、Anomaly、Action、Explanation 或 Drama Profile。

### 1.4 数据库边界

Phase 9 V1 不创建 V014 Migration，不修改 V001–V013、ORM Model 或现有表，不新增 quality result、snapshot、cache、history 或 repair 表。结果只存在于单次请求响应中。

未来若需要持久化趋势、固定报告或缓存，必须重新进行 Migration Review，不得在 Phase 9.1–9.7 中扩展数据库范围。

## 2. Architecture Overview

### 2.1 最终调用结构

```text
Data Governance Dashboard
            ↓
Read-only Data Governance API
            ↓
DataGovernanceService
       ┌────┴────┐
       ↓         ↓
   Providers    Quality Rules
       ↓
DataGovernanceRepository
       ↓
Existing Data Sources
```

Service 同时编排 Provider 和 Rule。Provider 通过 Repository 准备纯 DTO 输入；Rule 只接收 DTO 并执行确定性判断。Rule 不位于 Repository 调用链中，也不得访问数据库。

### 2.2 依赖方向

允许：

```text
Router → DataGovernanceService
DataGovernanceService → Providers + Rules
Providers → DataGovernanceRepository
Schemas → Contracts（仅转换语义）
```

禁止：

```text
Rule → Repository / Session / ORM
Provider → Rule / Service
Repository → Rule / Service
DataGovernanceService → Existing Business Services
Router → Repository / Provider / Rule / ORM
Frontend → Business Calculation
```

Phase 9 不调用 `DataQualityService`、`ScoreService`、`PredictionService`、`AnomalyService`、`OperationActionService`、`AnalysisExplanationService` 或 `DramaProfileService`。

### 2.3 请求时序

1. Router 校验认证和 HTTP 参数；
2. Service 读取注入 Clock 一次，冻结 UTC `analysis_as_of`；
3. Service 将相同截点传给三个 Provider；
4. Provider 调用 Repository 并映射 Rule Input DTO；
5. Service 调用对应 Rule；
6. Service 聚合 QualityStatus、Availability 和 Evidence；
7. Router 将 Contracts DTO 转换为 API Schema；
8. 响应结束后不保存任何治理结果。

## 3. Directory Structure

### 3.1 Backend

```text
backend/
├── repositories/
│   └── data_governance_repository.py
├── routers/
│   ├── data_governance.py
│   └── dependencies.py                  # 仅 Phase 9.5 追加依赖组装
├── schemas/
│   └── data_governance.py
└── services/
    └── data_governance/
        ├── __init__.py
        ├── contracts.py
        ├── providers.py
        ├── service.py
        └── rules/
            ├── __init__.py
            ├── freshness.py
            ├── completeness.py
            └── consistency.py
```

必要导出仅在对应阶段精确更新 `backend/repositories/__init__.py`、`backend/routers/__init__.py` 和 `backend/schemas/__init__.py`。不得进行批量导入整理。

### 3.2 Backend tests

```text
backend/tests/
├── test_data_governance_contracts.py
├── test_data_governance_rules.py
├── test_data_governance_repository.py
├── test_data_governance_providers.py
├── test_data_governance_service.py
└── test_data_governance_api.py
```

如项目已有 import/route 汇总测试，仅在对应实施阶段做最小更新，并纳入该阶段精确提交范围。

### 3.3 Frontend

```text
frontend/src/
├── api/dataGovernance.ts
├── types/dataGovernance.ts
├── views/dataGovernance/DataGovernance.vue
└── components/dataGovernance/
    ├── DataHealthOverview.vue
    ├── FreshnessCard.vue
    ├── CompletenessCard.vue
    ├── ConsistencyCard.vue
    └── EvidenceDrawer.vue
```

Phase 9.6 可根据现有页面风格将小组件保留在页面内部；若拆分组件，只能使用上述目录，不新增状态计算层。路由和 Dashboard 仅增加 `/data-governance` 导航入口。

### 3.4 Documentation

```text
docs/development/
├── PHASE9_DATA_GOVERNANCE_CONTRACTS.md
├── PHASE9_DATA_GOVERNANCE_RULES.md
├── PHASE9_DATA_GOVERNANCE_REPOSITORY_PROVIDERS.md
├── PHASE9_DATA_GOVERNANCE_SERVICE.md
├── PHASE9_DATA_GOVERNANCE_API.md
├── PHASE9_DATA_GOVERNANCE_DASHBOARD.md
└── PHASE9_DATA_GOVERNANCE_MODULE_SUMMARY.md
```

## 4. Contracts Plan

### 4.1 文件与约束

文件：`backend/services/data_governance/contracts.py`。

Contracts 使用纯 Python `Enum` 与不可变 dataclass/value object。禁止导入 SQLAlchemy、ORM Model、Repository、Session、FastAPI 或数据库组件。

### 4.2 Enums

`QualityStatus`：

- `HEALTHY`；
- `WARNING`；
- `FAILED`；
- `NOT_AVAILABLE`。

`AvailabilityStatus`：

- `AVAILABLE`；
- `PARTIAL`；
- `INSUFFICIENT`；
- `NOT_AVAILABLE`。

`AvailabilityReason` 至少包含：

- `NO_DATA`；
- `INSUFFICIENT_HISTORY`；
- `MISSING_REQUIRED_FIELD`；
- `INCOMPLETE_TIME_SERIES`；
- `UNRESOLVED_RELATION`；
- `REVISION_NOT_VISIBLE`；
- `UNSUPPORTED_SCOPE`；
- `NOT_AVAILABLE`。

`QualityIssueType`：

- `FRESHNESS`；
- `COMPLETENESS`；
- `CONSISTENCY`。

### 4.3 通用 Value Objects

`DataQualityAvailability`：

- `status: AvailabilityStatus`；
- `reasons: tuple[AvailabilityReason, ...]`；
- `message: str | None`。

`EvidenceItem`：

- `issue_type`；
- `check_code`；
- `entity_type`；
- `entity_id`（仅 SYSTEM 汇总证据允许为空）；
- `observed_value`；
- `expected_condition`；
- `source_type`；
- `source_reference_ids`；
- `message`。

Evidence 中的动态值使用 JSON-safe scalar/list/map，不携带 ORM 或完整业务对象。

### 4.4 Rule Input DTO

为避免 Rule 接收 Repository 投影，Contracts 同时定义：

- `FreshnessCheckInput`：entity identity、latest_data_at、analysis_as_of；
- `CompletenessCheckInput`：Drama 必填字段状态、平台关系状态、7 日 daily coverage、play_count 可用性；
- `ConsistencyCheckInput`：检查类型、source/target identity、revision/status/as-of 比较所需最小值。

Input DTO 不包含查询行为或状态判断。

### 4.5 Result DTO

`FreshnessResult`、`CompletenessResult`、`ConsistencyResult` 统一包含：

- `quality_status`；
- `availability`；
- `analysis_as_of`；
- `rule_version`；
- `summary`；
- `evidence`。

`DataGovernanceResponse` 包含：

- `scope`，V1 固定 `SYSTEM`；
- `analysis_as_of`；
- `quality_status`；
- `availability`；
- `rule_set_version`；
- `freshness`；
- `completeness`；
- `consistency`；
- 每类最多 5 条代表性 Evidence。

QualityStatus 与 Availability 必须正交。例如数据完整可评估且发现严重问题时为 `FAILED + AVAILABLE`，不得用 `NOT_AVAILABLE` 代替失败结论。

### 4.6 Contract tests

- Enum 闭合值和非法值；
- DTO 正常构造、不可变性和时间类型；
- Availability reasons 去重与稳定顺序；
- `FAILED + AVAILABLE` 合法；
- Evidence 最小字段、JSON-safe 内容和 SYSTEM nullable 边界；
- Overview 每类代表性 Evidence 上限；
- 源码边界不包含 ORM、Repository、Session 或数据库依赖。

## 5. Rules Plan

### 5.1 公共边界

Rule 是无状态纯计算组件：相同输入产生相同输出，不读取系统当前时间、不访问数据库/网络、不调用 Service、不修改输入。阈值和版本作为显式常量或构造参数冻结，并写入结果。

### 5.2 FreshnessRule

文件：`rules/freshness.py`。

输入：一组 `FreshnessCheckInput` 和固定 `analysis_as_of`。

规则：

- `0 <= delay <= 24h`：HEALTHY；
- `24h < delay <= 72h`：WARNING；
- `delay > 72h`：FAILED；
- 无可见数据：quality status NOT_AVAILABLE，availability NOT_AVAILABLE/NO_DATA；
- `latest_data_at > analysis_as_of`：FAILED，并产生未来时间 Evidence。

版本：`Freshness Rules V1.0`。

Rule 不触发刷新或导入。

### 5.3 CompletenessRule

文件：`rules/completeness.py`。

输入：一组 `CompletenessCheckInput`，覆盖当前可证明的 SERIALIZING/COMPLETED Drama、ONLINE drama-platform、ACTIVE Platform 和截点前 7 个完整业务日。

检查：

- `drama_id`、`drama_code`、`drama_name`、`status`；
- 至少一个符合条件的平台关系；
- 每个目标 drama-platform 的 7 日可见、非 VOID 覆盖；
- `play_count` 存在且非负；
- 7 日时间序列无缺日。

状态：

- 全部满足：HEALTHY；
- 部分平台关系或日期缺失：WARNING；
- 身份字段非法、目标关系完全不存在或 play_count 不可用：FAILED；
- 无法建立检查范围：NOT_AVAILABLE，并由 Availability 提供原因。

互动指标不作为 V1 必填项。Rule 不补零、不插值、不填充字段。版本：`Completeness Rules V1.0`。

### 5.4 ConsistencyRule

文件：`rules/consistency.py`。

仅处理 Provider 已准备的六类输入：

1. Snapshot revision identity/chain；
2. Operation Action Source 逻辑引用；
3. Operation Action 主状态与最新状态事件；
4. Explanation Lineage target 与 as-of；
5. 可解析 lineage source：SNAPSHOT、RULE、ANOMALY_EVIDENCE；
6. 来源可见时间不晚于目标 `analysis_as_of`。

无法解析的 METRIC / PREDICTION_INPUT identity 不做存在性猜测，输出 NOT_AVAILABLE Evidence。Rule 不修复关联、删除数据或创建 FK。版本：`Consistency Rules V1.0`。

### 5.5 Rule tests

- Freshness 24h、72h 精确边界、无数据、未来时间和时区；
- Completeness 必填字段、关系覆盖、完整 7 日、缺日、真实零值与负值；
- Consistency 六类检查、弱引用未解析和 as-of 边界；
- HEALTHY/WARNING/FAILED/NOT_AVAILABLE 与 Availability 正交组合；
- Evidence code、内容和稳定顺序；
- 相同输入结果一致；
- 无数据库、网络、Clock、Repository 或 Service 依赖。

## 6. Repository Plan

### 6.1 文件与定位

文件：`backend/repositories/data_governance_repository.py`。

`DataGovernanceRepository` 使用外部注入的现有 Session，只执行 SELECT，返回轻量只读投影或现有统一分页对象。禁止 commit、rollback、flush、Session 创建、质量判断和 Rule 调用。

### 6.2 查询能力

Freshness：

- 批量列出 ACTIVE Platform 下 ONLINE drama-platform feed；
- 查询各 feed 在 `analysis_as_of` 前最新可见、非 VOID Snapshot Revision 的 `snapshot_time`。

Completeness：

- 批量读取目标 Drama 必填字段投影；
- 批量读取符合条件的平台关系；
- 查询截点前 7 个完整业务日的 observation slots；
- 每个 slot 选择截点前最新 Revision；最新 Revision 为 VOID 时排除该 slot，不回退旧 Revision；
- 返回 play_count 存在性、值和日期覆盖，不计算质量状态。

Consistency：

- Snapshot/revision identity 与 version chain 投影；
- Action source reference 与目标存在性投影；
- Action current status 与状态历史投影；
- Explanation/lineage target、source 与 as-of 投影；
- 分页返回检查候选，避免无边界全库加载。

### 6.3 as-of 与历史限制

所有版本化查询必须使用 `changed_at <= analysis_as_of` 或对应冻结时间字段。非版本化主数据只标记为 current-state source；不得把当前状态声明为历史状态。无法保证历史语义时返回足够信息供 Provider 产生 NOT_AVAILABLE Input。

### 6.4 性能要求

- 避免按 Drama/feed 循环查询；
- 使用批量 projection、分组和稳定排序；
- 明细列表分页，`page_size <= 100`；
- 查询仅选择规则所需字段；
- 不加载完整 ORM graph。

### 6.5 Repository tests

- as-of 之前/之后数据隔离；
- 最新 revision、VOID 和不回退行为；
- 7 日窗口与跨日期边界；
- Action/Explanation 弱引用投影；
- 状态历史选择；
- 分页、稳定排序、空结果；
- 查询次数边界；
- 源码中无 commit、rollback、flush、sessionmaker 或规则逻辑。

## 7. Provider Plan

### 7.1 文件与公共约束

文件：`backend/services/data_governance/providers.py`。

实现 `FreshnessProvider`、`CompletenessProvider`、`ConsistencyProvider`。Provider 依赖 Repository 接口，接收显式 `analysis_as_of`，返回 Contracts Input DTO 集合和输入级 Availability 信息。

Provider 不返回 ORM，不执行 SQL，不调用 Rule/Service，不生成最终 QualityStatus，不修改数据。

### 7.2 FreshnessProvider

- 调用 Repository 读取目标 feed 与最新可见时间；
- 映射为 `FreshnessCheckInput`；
- 无 feed 或无 visible revision 时保留 NO_DATA / REVISION_NOT_VISIBLE 语义；
- 不计算 delay 或阈值状态。

### 7.3 CompletenessProvider

- 根据冻结 scope 准备目标 Drama/platform；
- 构造截点前 7 个完整业务日集合；
- 将字段、关系、daily coverage 与 play_count 投影映射为 `CompletenessCheckInput`；
- 不补日期、不把缺失值变成 0、不判定 WARNING/FAILED。

“完整业务日”的日期切分使用项目冻结业务时区；V1 规划采用系统业务时区 `Asia/Shanghai`，转换后将截点所在未完成日排除。若实现前项目配置与该时区不一致，必须在 Contracts 实现审查中统一，不得由 Provider自行选择。

### 7.4 ConsistencyProvider

- 按六类冻结检查分批读取最小投影；
- 映射 source/target identity、状态、revision 与 as-of 比较值；
- 对不支持的 weak reference 类型标记 UNSUPPORTED_SCOPE；
- 不解析文本、不猜测表、不修复关系。

### 7.5 Provider tests

- Repository projection 到 Input DTO 的完整映射；
- 同一 `analysis_as_of` 原样传递；
- 7 个完整业务日和时区边界；
- no data、insufficient 和 unresolved relation；
- 批量读取，不产生 N+1；
- 不调用 Service/Rule，不依赖 Session 或 ORM，不执行写操作。

## 8. Service Plan

### 8.1 文件与依赖注入

文件：`backend/services/data_governance/service.py`。

`DataGovernanceService` 构造器注入：

- `FreshnessProvider`；
- `CompletenessProvider`；
- `ConsistencyProvider`；
- `FreshnessRule`；
- `CompletenessRule`；
- `ConsistencyRule`；
- Clock。

Service 内部不得实例化具体 Repository、Provider 或 Rule，不访问 ORM、Session 或 SQL。

### 8.2 方法

- `get_overview(analysis_as_of=None)`；
- `get_freshness(analysis_as_of=None, page=1, page_size=20)`；
- `get_completeness(analysis_as_of=None, page=1, page_size=20)`；
- `get_consistency(analysis_as_of=None, page=1, page_size=20)`。

V1 scope 固定 SYSTEM，不暴露任意 scope 参数。

### 8.3 编排与截点

Service 在入口校验分页和时间。未传 `analysis_as_of` 时仅调用 Clock 一次；传入时间必须带时区并转换为 UTC。同一 overview 请求的三个 Provider 和 Rule 共享相同截点。

单项方法只调用对应 Provider/Rule。Overview 调用三组组件并聚合结果，不通过再次调用公开 Service 方法制造多个 Clock 截点。

### 8.4 聚合与异常隔离

Availability 最差优先级：

```text
NOT_AVAILABLE > INSUFFICIENT > PARTIAL > AVAILABLE
```

QualityStatus 最差优先级：

```text
FAILED > WARNING > HEALTHY > NOT_AVAILABLE
```

若至少一个模块可评估，只在可评估模块中选最差 QualityStatus；所有模块不可评估时返回 `NOT_AVAILABLE + NOT_AVAILABLE`。Overview 每类最多包含 5 项 Evidence。

单个 Provider/Rule 异常转换为对应模块 NOT_AVAILABLE，并记录技术日志，其他模块继续。Clock 或规则版本不可确定时整体失败，不伪造响应。

### 8.5 Service tests

- 四个方法完整流程；
- Clock 只读一次和统一 UTC as-of；
- Provider/Rule 参数与调用顺序；
- Overview 双协议聚合优先级；
- 每类 Evidence 上限；
- Provider 和 Rule 单模块异常隔离；
- Clock/版本失败为整体错误；
- 分页校验；
- 不访问 ORM/Session/SQL、不调用已有业务 Service、不写事务。

## 9. API Plan

### 9.1 Schema

文件：`backend/schemas/data_governance.py`。

API Schema 与内部 Contracts 分离，定义：

- `AvailabilityResponse`；
- `EvidenceResponse`；
- `FreshnessResponse`；
- `CompletenessResponse`；
- `ConsistencyResponse`；
- `DataGovernanceOverviewResponse`。

所有时间使用带时区 ISO 8601；Enum 值与 Contracts 一致；响应使用现有 `ResponseModel[T]`，错误使用 `ErrorResponse`。

### 9.2 Router

文件：`backend/routers/data_governance.py`。

接口冻结：

| Method | Path | Query |
| --- | --- | --- |
| GET | `/api/v1/data-quality/overview` | `analysis_as_of?` |
| GET | `/api/v1/data-quality/freshness` | `analysis_as_of?`, `page=1`, `page_size=20` |
| GET | `/api/v1/data-quality/completeness` | `analysis_as_of?`, `page=1`, `page_size=20` |
| GET | `/api/v1/data-quality/consistency` | `analysis_as_of?`, `page=1`, `page_size=20` |

`page_size` 最大 100。四条接口仅允许 USER / ADMINISTRATOR，匿名返回 401。不得新增 POST、PUT、PATCH、DELETE。

新静态路径必须在任何可匹配动态路径之前注册，并与现有 `/calculate`、`/score`、`/history`、`/rules` 保持并存，不改变旧接口语义。

### 9.3 Dependency assembly

`backend/routers/dependencies.py` 新增 `get_data_governance_service()`，在同一请求 Session 中组装 Repository、三个 Provider、三个 Rule 和 Clock。因为全部只读，不调用 commit/rollback/flush。

Router 只能依赖 `DataGovernanceService`，不得导入 Repository、Provider、Rule、ORM 或 Session。

### 9.4 API tests

- 四条 GET 路径与 OpenAPI；
- POST/PUT/PATCH/DELETE 不存在；
- JWT Bearer、匿名 401、USER/ADMIN 成功；
- `analysis_as_of`、page、page_size 参数传递和 422；
- Availability/QualityStatus/Evidence Schema 转换；
- `ResponseModel` / `ErrorResponse`；
- Dependency Override 使用 Fake Service，不连接真实数据库；
- Router 源码边界无 Repository/ORM/Provider/Rule。

## 10. Frontend Plan

### 10.1 API client 与类型

`frontend/src/api/dataGovernance.ts` 复用现有 Axios client 和 Token interceptor，封装四个 GET 请求，不创建新 Axios 实例。

`frontend/src/types/dataGovernance.ts` 与 API Schema 一致，定义 QualityStatus、AvailabilityStatus、AvailabilityReason、QualityIssueType、Evidence 和四类响应。不得使用自由字符串替代冻结 Enum。

### 10.2 页面与组件

页面：`frontend/src/views/dataGovernance/DataGovernance.vue`。

路由：`/data-governance`，USER 和 ADMINISTRATOR 可访问。

页面结构：

1. `DataHealthOverview`：整体 QualityStatus、Availability、规则集版本和截点；
2. `FreshnessCard`：最新数据时间、延迟状态和 Evidence；
3. `CompletenessCard`：字段/关系/7 日覆盖状态；
4. `ConsistencyCard`：关联、Revision 和 as-of 状态；
5. `EvidenceDrawer`：分页展示最小 Evidence。

每个模块独立支持 loading、empty、error、success。单模块失败不遮蔽其他模块。Frontend 不计算延迟、覆盖率、状态、聚合结果，不补零、不自动修复、不创建 Action。

V1 不展示历史趋势或伪造时间序列。无需图表时不引入 ECharts；如后续实现使用现有 ECharts，只能直接可视化 API 数据，并遵守初始化、resize、dispose 生命周期。

### 10.3 Frontend validation

- TypeScript API/Schema 对齐；
- 所有 QualityStatus 与 Availability 状态展示；
- loading/empty/error/success 和模块隔离；
- Evidence 分页；
- `npm exec vue-tsc -- --noEmit`；
- `npm run build`；
- 无新增依赖、无 lockfile 修改。

## 11. Testing Plan

### 11.1 Test pyramid

| Layer | 核心验证 | 数据库 |
| --- | --- | --- |
| Contracts | Enum、DTO、正交状态、边界 | 无 |
| Rules | 阈值、窗口、Evidence、确定性 | 无 |
| Repository | as-of、revision、VOID、批量查询 | 测试 Session |
| Providers | 投影到 Input DTO、缺失语义 | Fake Repository |
| Service | 编排、Clock、聚合、异常隔离 | Fake Provider/Rule |
| API | 权限、参数、Schema、OpenAPI | Dependency Override |
| Frontend | 类型、状态展示、构建 | Mock API / Build |

### 11.2 Required boundary checks

使用源码或 AST 测试固定边界：

- Contracts 无 SQLAlchemy/Repository/Service/Session；
- Rules 无 Repository/Session/ORM/Network/Clock；
- Repository 无质量判断、commit/rollback/flush/sessionmaker；
- Providers 无 Service/Rule/SQL/ORM write；
- Service 无 ORM/Session/SQL/业务 Service；
- Router 无 Repository/Provider/Rule/ORM/Session；
- Frontend 无质量计算和数据修改调用。

### 11.3 Regression

每个阶段先执行新增专项测试，再执行现有 Backend 全量 `pytest`。Phase 9.6 执行 TypeScript 检查和生产构建。若全量环境依赖不可用，必须记录准确命令、失败原因和未验证范围，不得宣称通过。

## 12. Implementation Order

### Phase 9.1 — Contracts

交付：Contracts、单元测试、Contracts 文档。

冻结检查：Enum、DTO、Evidence、QualityStatus/Availability 正交语义。

建议提交：`feat(phase9): add data governance contracts`。

### Phase 9.2 — Quality Rules

交付：三个 Rule、Rule 测试、Rules 文档。

前置：Phase 9.1 已提交。不得修改 Contracts 语义；如发现缺陷先进行契约审查。

建议提交：`feat(phase9): add data governance rules`。

### Phase 9.3 — Repository + Providers

交付：只读 Repository、三个 Provider、测试与文档。

前置：规则输入契约冻结。验证 as-of、Revision、VOID、批量查询和 DTO 映射。

建议提交：`feat(phase9): add data governance repository and providers`。

### Phase 9.4 — DataGovernanceService

交付：Service、编排测试、Service 文档。

前置：Providers 和 Rules 已提交。验证 Clock、聚合和异常隔离。

建议提交：`feat(phase9): add data governance service`。

### Phase 9.5 — API

交付：Schemas、Router、Dependency、API 测试与文档。

前置：Service 接口冻结。只实现四条 GET 接口。

建议提交：`feat(phase9): add data governance api`。

### Phase 9.6 — Frontend Dashboard

交付：API client、TypeScript types、页面/组件、路由、Dashboard 入口和文档。

前置：API Contract 冻结。验证 TypeScript 与生产构建。

建议提交：`feat(phase9): add data governance dashboard`。

### Phase 9.7 — Module Summary

交付：Phase 9 模块归档文档，汇总架构、规则、API、测试和提交记录。

建议提交：`docs(phase9): add data governance module summary`。

每阶段必须精确暂存，不使用 `git add .`，不得携带其他工作区修改。一个阶段完成后等待下一阶段授权，不提前实现后续层。

## 13. Risk Analysis

### 13.1 与 Phase 2 Data Quality 冲突

风险：形成第二套评分或同名 Service，导致规则和用户语义混乱。

控制：独立 `data_governance` 命名空间，类名固定 `DataGovernanceService`；Phase 9 不产生分数、不调用 Phase 2 计算、不写 Phase 2 表。

### 13.2 结果持久化诱导

风险：为了趋势或性能临时新增 snapshot/cache 表，绕过数据库审查。

控制：V1 只允许 request-time DTO；任何持久化、缓存、历史报告需求必须重新 Migration Review。

### 13.3 规则过度业务化

风险：Rule 开始计算评分、触发 Action 或给出运营建议。

控制：Rule 输入输出均为治理 Contracts，只判断可验证的数据健康条件；源码边界测试禁止业务 Service、写入和推荐字段。

### 13.4 Evidence 数据膨胀

风险：返回完整业务对象或无边界全库异常，导致响应和内存增长。

控制：Evidence 最小字段；Overview 每类最多 5 项；明细分页且 `page_size <= 100`；Repository 使用 projection 和批量查询。

### 13.5 Availability 状态不统一

风险：把 FAILED 当作不可用，或用 null/0 表达数据不足。

控制：QualityStatus 与 Availability 正交；统一 Enum 和聚合优先级；Contracts、Service、API、Frontend 全层测试相同状态矩阵。

### 13.6 Request-time 查询成本

风险：SYSTEM scope 跨多表检查造成慢查询或 N+1。

控制：批量投影、分页、稳定窗口和查询次数测试；V1 不以未审查缓存规避问题。达到性能瓶颈后先测量，再单独评审缓存或持久化方案。

### 13.7 历史语义误导

风险：非版本化主数据被当作历史状态，或 Revision 选择越过 as-of。

控制：版本化查询严格过滤截点并遵守 VOID；非版本化来源明确标记 current-state，无法还原时返回 NOT_AVAILABLE，不伪造历史事实。

### 13.8 Weak Reference 误解析

风险：对多态弱引用猜测目标表，产生错误一致性结论。

控制：只解析 Review 冻结映射；METRIC / PREDICTION_INPUT 等未冻结 identity 返回 UNSUPPORTED_SCOPE / NOT_AVAILABLE Evidence。

## Planning Decision

本计划完成 Phase 9 的文件结构、Contracts、Rules、Repository、Providers、Service、API、Frontend、测试和实施顺序规划，并保持 No Migration、No Mutation、No AI、No New Business Facts。

下一阶段仅允许在获得明确授权后进入 Phase 9.1 Contracts Implementation；本计划本身不授权代码实现。
