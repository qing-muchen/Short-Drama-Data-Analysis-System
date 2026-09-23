# Phase 9 Data Governance API

## 1. API 定位

Phase 9.5 将 `DataGovernanceService` 暴露为 JWT 保护的只读 HTTP 查询接口。API 层仅负责认证、参数校验、Service 调用和显式 Schema 转换。

该层不访问 ORM、Repository、Provider、Rule 或 Session，不执行 SQL、质量判断、自动修复、数据写入或 AI 推断。现有 Phase 2 `/data-quality/calculate`、`/score`、`/history`、`/rules` 行为保持不变。

## 2. 接口列表

| Method | Path | Query | Response data |
| --- | --- | --- | --- |
| GET | `/api/v1/data-quality/overview` | `analysis_as_of?` | `DataGovernanceResponseSchema` |
| GET | `/api/v1/data-quality/freshness` | `analysis_as_of?`, `page`, `page_size` | `FreshnessSchema` |
| GET | `/api/v1/data-quality/completeness` | `analysis_as_of?`, `page`, `page_size` | `CompletenessSchema` |
| GET | `/api/v1/data-quality/consistency` | `analysis_as_of?`, `page`, `page_size` | `ConsistencySchema` |

所有接口仅注册 GET。Phase 9 不提供 POST、PUT、PATCH 或 DELETE。

`analysis_as_of` 是可选的带时区 ISO 8601 时间。API 不生成时间；未提供时由 Service 的 Clock 冻结截点。明细 Evidence 默认 `page=1`、`page_size=20`，`page_size` 范围为 1–100。Overview 返回 Service 已限制的每类最多五项代表性 Evidence。

## 3. Schema 设计

文件：`backend/schemas/data_governance.py`。

API Schema 与内部 frozen dataclass 分离，并定义独立的闭合 Enum：

- `QualityStatusSchema`；
- `AvailabilityStatusSchema`；
- `AvailabilityReasonSchema`；
- `GovernanceScopeSchema`；
- `QualityIssueTypeSchema`。

响应 Schema：

- `DataQualityAvailabilitySchema`：`status`、`reasons`、`message`；
- `EvidenceItemSchema`：`evidence_type`、`message`、`source`、`metadata`；
- `FreshnessSchema`：质量状态、Availability、延迟、Evidence、规则版本与截点；
- `CompletenessSchema`：质量状态、覆盖率、缺失项、Evidence、规则版本与截点；
- `ConsistencySchema`：质量状态、问题数、Evidence、规则版本与截点；
- `DataGovernanceResponseSchema`：SYSTEM scope、统一截点、整体 Availability、三个模块结果与规则集版本。

三个明细 Schema 同时返回 Evidence 的 `page`、`page_size` 和 `total`。API 不改变 Service 的质量状态或 Availability，只进行传输格式转换。

Evidence 使用显式映射：

- `evidence_type` 来自 `QualityIssueType`；
- `source` 来自最小来源类型；
- `metadata` 仅包含 check code、entity identity、观察值、预期条件和来源引用 ID；
- 不暴露内部 dataclass、ORM 对象或完整业务对象。

成功响应继续使用 `ResponseModel[T]`，错误响应使用项目现有 `ErrorResponse`。

## 4. Availability 协议

API 原样保留以下状态：

- `AVAILABLE`；
- `PARTIAL`；
- `INSUFFICIENT`；
- `NOT_AVAILABLE`。

所有 `AvailabilityReason` 与 Contracts 保持一致，支持多个稳定排序的原因。API 不重新解释状态，也不通过 `null`、空列表或数值零替代业务状态。

## 5. 权限模型

四个接口统一使用现有 `AuthenticatedUserDependency`：

- `USER`：允许查询；
- `ADMINISTRATOR`：允许查询；
- 匿名：返回 `401 AUTHENTICATION_FAILED`。

不存在管理员专属写权限，因为本模块没有写接口。

## 6. Dependency 组装

`get_data_governance_service()` 位于 `backend/routers/dependencies.py`，使用同一请求级 Session 组装：

```text
DataGovernanceRepository
  -> FreshnessProvider / CompletenessProvider / ConsistencyProvider
  -> FreshnessRule / CompletenessRule / ConsistencyRule
  -> DataGovernanceService + SystemClock
```

Router 仅依赖 `DataGovernanceServiceDependency`，不感知上述 Repository、Provider、Rule 或 Clock。

## 7. Router 边界

`backend/routers/data_governance.py` 只包含：

- 静态路径定义；
- JWT 用户依赖；
- `analysis_as_of` 与 Evidence 分页参数校验；
- Service 方法调用；
- DTO 到 API Schema 的转换。

Router 不导入 SQLAlchemy、ORM Model、Repository、Provider 或 Rule，不调用 commit、rollback、flush，也不包含质量业务判断。

## 8. 测试记录

专项测试覆盖：

- 四条 GET 路径和 OpenAPI 注册；
- 不存在 POST、PUT、PATCH、DELETE；
- 匿名 401，USER 与 ADMINISTRATOR 均可查询；
- Service DTO 到 API Schema 的显式转换；
- AVAILABLE、PARTIAL、INSUFFICIENT、NOT_AVAILABLE 原样保留；
- Evidence 最小结构转换；
- timezone-aware `analysis_as_of` 传递及 naive 时间 422；
- page/page_size 校验和 Evidence 分页；
- Dependency Override 不连接数据库；
- Router 无 Repository、ORM、Provider、Rule 或写操作依赖。

验证命令：

```text
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_data_governance_api.py -q
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_data_governance_contracts.py backend/tests/test_data_governance_rules.py backend/tests/test_data_governance_repository.py backend/tests/test_data_governance_providers.py backend/tests/test_data_governance_service.py backend/tests/test_data_governance_api.py -q
backend/.venv/Scripts/python.exe -m compileall backend/schemas/data_governance.py backend/routers/data_governance.py backend/routers/dependencies.py backend/tests/test_data_governance_api.py
```

验证结果：API 专项测试及 Phase 9.1–9.5 回归测试全部通过；编译检查通过。
