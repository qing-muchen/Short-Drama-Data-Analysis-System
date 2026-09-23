# Phase 10 Analysis Reporting & Export Center Architecture Review

> Review对象：`PHASE10_ANALYSIS_REPORTING_DESIGN_PROPOSAL.md`
> Review范围：架构、数据边界、安全导出、API、Frontend、测试与实施准入。本文档不授权编码。

## 1. Module Position Review

### 1.1 结论：保留

Analysis Reporting & Export Center 定位为 Reporting / Read Model Layer 合理。它解决的是已有查询和分析事实的结构化交付，不是新的分析模型、运营模块或治理事实层。

冻结职责：

- 读取已有持久化事实；
- 应用与来源查询一致的筛选、权限和截点；
- 使用版本化 Report Schema 生成 Preview、CSV 和 XLSX；
- 传播已有版本、NULL、质量提示和 Snapshot Semantics；
- 在单次请求内生成文件，不保存报告结果。

禁止职责：

- 生成新指标、评分、预测、异常、生命周期或推荐；
- 重新执行 Phase 2–9 的分析规则；
- 修改来源记录或形成报告业务实体；
- 使用 LLM、AI Agent、推荐模型、机器学习或自动决策。

### 1.2 与已有模块边界

| 模块 | 既有职责 | Phase 10边界 |
| --- | --- | --- |
| Phase 2 Data Quality | 形成并持久化质量评分与规则结果 | 只导出已保存结果，不重新评分 |
| Phase 6 Explanation | 保存解释快照和血缘 | V1 不导出 Explanation，避免未冻结 JSON/Lineage 列契约 |
| Phase 7 Drama Profile | 请求时聚合多个模块摘要 | 不调用 DramaProfileService，不复制 Profile 聚合逻辑 |
| Phase 8 Operation Analytics | 请求时计算行动效果、生命周期和 Benchmark | V1 不导出临时计算结果，不复制规则 |
| Phase 9 Data Governance | 请求时评估可信状态 | V1 不调用 DataGovernanceService，不导出临时治理结果 |

Reporting 只能消费已有表中的事实。对于仅存在于请求内的 Phase 7–9 结果，没有持久化事实就没有 Phase 10 V1 导出来源。

## 2. Architecture Review

### 2.1 主链路：通过

```text
Reporting Frontend
        ↓
Read-only Reporting API
        ↓
ReportingService
        ↓
Report Providers
        ↓
ReportingRepository
        ↓
Existing Tables
```

各层职责清晰且依赖方向单向：

- Frontend：选择后端声明的 Report Type / Filter，展示 Preview 和触发下载；
- API：JWT、参数验证、Service 调用、JSON/文件响应；
- Service：截点冻结、权限上下文、Provider 选择、限制策略和序列化编排；
- Provider：projection 到 immutable Report Row DTO；
- Repository：Count、筛选、稳定排序、as-of / Revision 和 projection；
- Existing Tables：唯一业务事实来源。

禁止 ReportingService 调用 ScoreService、DataQualityService、PredictionService、AnomalyService、OperationActionService、ExplanationService、DramaProfileService、OperationAnalyticsService 或 DataGovernanceService。

### 2.2 Report Schema Registry位置：通过并冻结

Schema Registry 位于 Service/serialization 边界内的纯配置层，不属于 Repository 或 Frontend。

职责：

- Report Type 与列集合映射；
- 列 key、标题、顺序、类型、nullable 和格式；
- Filter Schema；
- `report_schema_version`；
- 允许的 Export Format。

禁止：查询数据、计算业务指标、判断 QualityStatus、扩展权限或根据行内容动态改变列。

Registry 必须显式注册，不进行动态 import、目录扫描或插件发现。

### 2.3 Serializer位置：通过并冻结

CSV/XLSX Serializer 是纯传输转换组件，输入为 Report Schema、Metadata 和 Report Row DTO。它不访问 Repository、Provider、Service、ORM 或 Session。

Serializer 只能执行列顺序、类型、NULL、字符安全和文件编码转换，不得计算指标、补齐缺失数据或改变业务值。

## 3. Database Impact Review

### 3.1 V1 No Migration：通过并冻结

Preview、Count、CSV 和 XLSX 可通过现有表、只读 projection、受限行数和请求期临时文件完成。V1 不需要持久化结果。

禁止新增：

- Report Job；
- Report Result；
- Report Snapshot；
- Report File / File Metadata；
- Export History；
- Report Cache。

不修改 V001–V013、ORM 或 Existing Tables。

### 3.2 请求期临时文件

允许使用受限的 `SpooledTemporaryFile` 或同等请求期资源作为 Serializer 输出缓冲。该资源不是业务持久化：

- 不进入数据库；
- 不使用固定业务目录；
- 响应完成或失败后必须关闭；
- 不提供再次下载；
- 不记录可查询文件身份。

### 3.3 未来必须重新Review的需求

以下任一需求出现时，必须重新进行 Architecture Review；涉及表结构时还必须进行 Migration Review：

- 异步 Report Job；
- 历史报告保存或再次下载；
- 下载记录、审批或发布；
- 文件归档或外部对象存储；
- 定期报表、邮件发送或分享链接；
- Report Cache / Materialized View。

## 4. Report Schema Registry Review

### 4.1 schema_version：必须保留

每个 Report Type 独立维护 `report_schema_version`，建议初始形式为 `<REPORT_TYPE> Schema V1.0`。Version 必须进入 Catalog、Preview Metadata、文件 Metadata Sheet（XLSX）或 CSV companion headers/metadata约定，并纳入测试。

以下变化必须提升版本：

- 列 key、顺序、类型或 nullable 改变；
- NULL 表示改变；
- Filter 语义或 Snapshot Semantics 改变；
- 字段业务含义或来源改变。

仅修改不影响机器消费的展示标题可以保持版本，但必须通过 Review 并记录变更；实现阶段不得自行判断。

### 4.2 V1 Report Catalog冻结

首版只允许六种持久化事实报告：

1. `DRAMA_CATALOG`；
2. `SCORE_RESULTS`；
3. `DATA_QUALITY_RESULTS`；
4. `PREDICTION_RESULTS`；
5. `ANOMALY_RECORDS`；
6. `OPERATION_ACTIONS`。

`ANALYSIS_EXPLANATIONS` 进入 V1 排除项。原因：Explanation `detail` JSON、Lineage 弱引用、Evidence 展开层级和敏感信息列尚无冻结导出 Schema。Phase 6 页面查询能力不等于可以安全批量导出。

Phase 8 Operation Analytics 与 Phase 9 Data Governance 继续排除，因为它们没有持久化结果，Reporting 不得调用其 Service 或复制规则。

## 5. Serializer Review

### 5.1 CSV规则冻结

- Encoding：UTF-8 with BOM（`utf-8-sig`）；
- 行结束：CRLF；
- 转义：使用标准 CSV writer 处理逗号、引号和换行，不手工拼接；
- NULL：空单元格；业务字符串在进入 Report Row 前必须保持非空/空语义，不得把 NULL 转为 `0`、`false` 或字符串 `NULL`；
- Formula Injection：字符串移除判断不允许。若忽略前导空白后首字符为 `=`, `+`, `-`, `@`，输出值必须以前置单引号转为文本；原始值不得执行；
- 数字、布尔和日期按 Schema 类型序列化，不对字符串尝试类型推断；
- 自由文本中的控制字符处理规则必须写入 Serializer 测试矩阵。

CSV 空单元格无法区分 NULL 与空字符串，因此 V1 Report Schema 不允许有意义的空字符串作为独立业务值；Provider 对业务字符串只能保留非空字符串或 NULL。该约束进入 Contracts 测试。

### 5.2 XLSX规则冻结

- MIME：`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`；
- 扩展名：`.xlsx`；
- 使用现有 `openpyxl`；
- 使用 write-only Workbook 写入请求期临时文件；
- 不写公式、宏、外链或隐藏 Sheet；
- 文本型危险前缀使用与 CSV 相同的文本防护；
- 日期时间输出 UTC ISO 8601 文本，避免客户端时区自动转换；
- 第一 Sheet 为数据，允许第二个固定 Metadata Sheet；Sheet 名由 Registry 常量提供，不使用用户自由文本；
- NULL 写为空单元格，不转为 0。

### 5.3 Streaming决议

V1 采用“先完成有界文件生成，再开始 HTTP StreamingResponse”：

1. Count、权限、Filter、Limit 和 Schema 校验；
2. 在 `SpooledTemporaryFile` 中完整生成；
3. 生成成功后设置 Header 并开始响应；
4. 响应结束关闭资源。

因此生成错误可以在 Header 发送前转换为统一 ErrorResponse。响应开始后的客户端断开或网络错误属于传输失败，不再尝试发送 JSON 错误，也不保存半成品供重试。

## 6. API Contract Review

### 6.1 接口：通过并冻结

```http
GET /api/v1/reports/catalog
GET /api/v1/reports/preview
GET /api/v1/reports/export
```

三个接口均为只读 GET。V1 不注册 POST、PUT、PATCH、DELETE。

### 6.2 Catalog

返回当前用户可用的 Report Type、Format、Filter Schema、列 Schema、`report_schema_version` 和 Snapshot Semantics。Catalog 不返回数据库表名或 ORM 字段名。

### 6.3 Preview

冻结公共 Query：

- `report_type`：闭合 Enum；
- `analysis_as_of?`：timezone-aware ISO 8601；
- `preview_limit`：默认 20，范围 1–100；
- 各 Report Type 的显式 Filter 参数。

返回 `ResponseModel[ReportPreviewSchema]`：Metadata、Column Schema、Preview Rows、预计总行数、Availability、来源版本和 Snapshot Semantics。

### 6.4 Export

公共 Query：

- 与 Preview 相同的 `report_type`、`analysis_as_of` 和 Filter；
- `format=CSV|XLSX`；
- `confirmed_row_count?`。

行数规则：

- Preview 不受导出确认影响；
- `total_rows <= 1000` 且存在至少一个有效 Filter 时可直接导出；
- 无 Filter 或 `total_rows > 1000` 时，首次请求返回 409 `EXPORT_CONFIRMATION_REQUIRED`，details 包含当前 `total_rows`；
- 客户端使用完全相同 Query 并传 `confirmed_row_count=<total_rows>` 重试；
- 重计数与确认数不同仍返回 409，不生成文件；
- CSV 硬上限 10,000 行；XLSX 硬上限 5,000 行；超过上限返回 422 `EXPORT_LIMIT_EXCEEDED`，不得通过确认绕过。

成功响应：

- CSV：`text/csv; charset=utf-8`；
- XLSX：固定 MIME；
- `Content-Disposition` 使用 RFC 5987 安全文件名；
- 可增加只含受控 ASCII 的 `X-Report-Schema-Version`、`X-Analysis-As-Of`、`X-Snapshot-Semantics`；
- 禁止把用户自由文本直接写入 Header。

### 6.5 错误语义

- 参数校验：422；
- 匿名：401；
- 越权：403；
- 需要重新确认：409；
- 无匹配行：Preview 200 + `EMPTY`；Export 返回 409 `EMPTY_REPORT`，不下载空文件；
- 生成开始前失败：现有 ErrorResponse；
- 响应开始后网络失败：传输终止，不生成第二响应。

## 7. Filter Policy Review

### 7.1 决议

Filter 只能来自已存在、已冻结且可以通过强类型参数表达的字段。禁止自由 SQL、自由列名、自由排序表达式、全文语义推断或从用户文本猜测 Filter。

Implementation Planning 必须为六种 Report Type 建立 Filter Allowlist。最低公共 Filter 可包含：

- `drama_id`；
- `platform_id`（仅来源真实支持时）；
- `start_time` / `end_time`（仅对应来源时间字段）；
- 状态 Enum；
- 明确的版本字段。

并非所有 Report Type 都支持全部公共 Filter。Catalog 必须按 Report Type 返回允许项；不支持参数返回 422 `UNSUPPORTED_REPORT_FILTER`，不能静默忽略。

Filter 只缩小读取范围，不修改业务事实、不重新计算、不补齐数据。默认稳定排序由 Registry/Provider 冻结，客户端 V1 不提交任意 sort key。

### 7.2 标签和分类

Tag Filter 只有在对应 Repository 能复用当前系统 Tag OR 语义时才允许；category 当前没有标准化字段，不进入 V1。禁止用 Drama 标题、标签文本或备注推断分类。

## 8. Snapshot / as-of Review

### 8.1 analysis_as_of：必须保留

Service 在每次 Preview/Export 入口冻结一次 UTC `analysis_as_of`。显式参数必须 timezone-aware；未提供时注入 Clock 只读取一次。Count、Row Query、Metadata 和文件名使用同一截点。

### 8.2 来源能力矩阵

| Report Type | Snapshot Semantics | V1规则 |
| --- | --- | --- |
| `DRAMA_CATALOG` | `CURRENT_STATE_AT_REQUEST` | 当前主数据无完整 temporal history；`analysis_as_of` 仅记录请求截点，不声称历史重建 |
| `SCORE_RESULTS` | `AS_OF_RECONSTRUCTED` | 只读取自身 `analysis_as_of <= cutoff` 的已保存结果，保留算法/规则版本 |
| `DATA_QUALITY_RESULTS` | `AS_OF_RECONSTRUCTED` | 按 score date/创建时间与规则集版本读取已保存结果；具体同日选择规则在 Planning 冻结 |
| `PREDICTION_RESULTS` | `AS_OF_RECONSTRUCTED` | 只读取预测自身分析截点不晚于 cutoff 的已保存结果 |
| `ANOMALY_RECORDS` | `CURRENT_STATE_AT_REQUEST` | 异常事实可按检测时间过滤，但当前 status 可能后续变化，不能重建历史状态 |
| `OPERATION_ACTIONS` | `CURRENT_STATE_AT_REQUEST` | History 可展示事件时间，但 Action 当前字段不能被描述为历史截点状态 |

`AS_OF_RECONSTRUCTED` 只表示报告行来自 cutoff 前已保存的分析结果，不表示重算当时数据。Repository 必须排除未来记录并使用稳定版本选择。

### 8.3 Preview / Export一致性

Preview 返回的 `analysis_as_of` 必须由 Frontend 原样带入 Export。`confirmed_row_count` 只能防止范围变化，不能作为 Snapshot token。对于 `CURRENT_STATE_AT_REQUEST` 来源，Preview 与 Export 之间仍可能变化；Response 必须保留该语义，不承诺字节级一致。

## 9. Permission Review

### 9.1 V1权限冻结

- 匿名：不可访问；
- `USER`：可使用六种 V1 Report Type，范围不得超过其现有查询权限；
- `ADMINISTRATOR`：使用同一 Catalog，不自动获得绕过行数上限、Filter 或确认的能力；
- 当前系统没有细粒度行级 RBAC，因此 V1 不虚构团队、组织或 Drama ownership 范围。

Catalog、Preview、Export 必须使用同一权限策略。Frontend 隐藏不是权限控制；Service 必须从认证上下文建立范围，不能信任客户端角色或 scope 参数。

### 9.2 Import Errors决议

`IMPORT_ERRORS` V1 排除。原因：导入任务与错误的普通用户读取边界尚未冻结，且错误内容可能包含原始导入数据。未来加入前必须单独完成权限与敏感字段 Review。

### 9.3 导出审计决议

V1 保持严格只读，不写 OperationLog，也不建立 Export History。此选择存在下载审计缺口，但符合当前 Read Model 边界。

若后续要求审计下载，必须独立评审：

- 审计是否属于基础设施访问日志而非业务 OperationLog；
- 写入失败是否阻止下载；
- 记录范围、文件摘要、用户、Filter 和保留周期；
- 事务与隐私边界。

实现阶段不得自行增加日志写入。

## 10. TBD Review

| TBD | Review结果 | 决议 |
| --- | --- | --- |
| `TBD-P10-01` Report Catalog | Implementation前解决 | 冻结六种类型；Explanation、Phase 8/9 临时结果排除 |
| `TBD-P10-02` 行数与确认 | Implementation前解决 | Preview 1–100；直接导出阈值 1000；CSV 10000；XLSX 5000；使用 `confirmed_row_count` |
| `TBD-P10-03` 历史截点 | Implementation前解决 | 冻结六类型 Snapshot Semantics 能力矩阵 |
| `TBD-P10-04` 导出审计 | V1排除 | V1 不写日志；未来独立 Review |
| `TBD-P10-05` CSV规则 | Implementation前解决 | UTF-8 BOM、CRLF、标准 writer、空单元格 NULL、公式前缀防护 |
| `TBD-P10-06` Streaming错误 | Implementation前解决 | 有界临时文件完整生成后再发送 Header；传输中失败只终止连接 |
| `TBD-P10-07` 权限 | V1冻结 / 部分排除 | USER/ADMIN 同 Catalog；Import Errors 排除；无虚构行级权限 |

Design Proposal 的七项 TBD 已全部关闭或明确列入 V1 排除，不允许原样带入编码阶段。

## 11. Testing Review

测试计划覆盖充分，但 Implementation Planning 必须补充以下冻结用例：

### 11.1 Contracts / Registry

- 六种且仅六种 Report Type；
- Schema Version 变更规则；
- 列 key 唯一、顺序稳定、类型闭合；
- Registry 无动态扫描；
- Row 禁止 ORM、dict 嵌套业务对象和自由公式。

### 11.2 Serializer安全

- CSV `=`, `+`, `-`, `@` 及前导空白公式注入；
- 逗号、双引号、CR/LF、中文和 BOM；
- NULL 与空字符串约束；
- XLSX 无 formula、macro、external link、hidden sheet；
- MIME、扩展名、Content-Disposition、Header 注入；
- 请求期临时资源成功/失败均关闭。

### 11.3 Repository / Provider

- 每类型 Filter Allowlist；
- Count 与 Rows 同条件；
- 截点和 Snapshot Semantics 能力矩阵；
- Revision / VOID；
- 稳定排序和批量读取；
- 不返回 ORM、不执行写事务。

### 11.4 Service / API

- Clock 一次；
- Preview 与 Export Schema 一致；
- 1000、5000、10000 边界及确认重计数；
- Empty / Partial / Not Available；
- USER / ADMIN / anonymous；
- 不调用其他业务 Service；
- 只注册三条 GET；
- 文件生成失败发生在 Response Header 之前。

### 11.5 Frontend

- Catalog 驱动 Filter；
- Preview / Export 使用同一 `analysis_as_of`；
- 确认对话框显示当前行数、格式和截点；
- filename 清理；
- loading、empty、partial、error、success；
- TypeScript 和生产构建。

## 12. Implementation Boundary Review

### 12.1 冻结设计项

1. Reporting / Read Model 定位；
2. 六种 V1 Report Type；
3. No Migration、No Result Persistence、No Audit Write；
4. 单向依赖和禁止跨业务 Service；
5. 显式 Schema Registry 与 `report_schema_version`；
6. CSV/XLSX 安全序列化规则；
7. `analysis_as_of` 与 Snapshot Semantics 能力矩阵；
8. Preview / Export 行数上限和 `confirmed_row_count`；
9. 三条 GET API；
10. `/reports` Frontend 只展示和下载；
11. No AI、No Recommendation、No Business Recalculation。

### 12.2 Proposal必须修改并由Planning吸收的事项

无需单独生成 Design V2，但 Implementation Plan 必须将以下 Review 决议写成文件级契约：

- Candidate Catalog 收缩为六种；
- `ANALYSIS_EXPLANATIONS`、Import Errors、Phase 8/9 临时结果排除；
- 固定行数、确认和硬上限；
- Snapshot Semantics 矩阵；
- CSV/XLSX 安全细节；
- Spooled Temporary File 的生成后响应策略；
- V1 不写 OperationLog。

Implementation Planning 不得重新打开上述决议；若必须改变，返回 Architecture Review。

### 12.3 Review结论

**Option A：允许进入 Implementation Planning。**

理由：模块定位、单向依赖、No Migration、只读边界和安全导出架构成立；Proposal 的七项 TBD 已在本 Review 中关闭或明确排除。当前批准只允许编写 Implementation Plan，不允许创建 Contracts、Serializer、Repository、Provider、Service、API 或 Frontend 代码。

## Final Decision Summary

- Architecture Review：Option A；
- Database：V1 No Migration，Request-time bounded export；
- API：Catalog / Preview / Export 三条 GET；
- Frontend：`/reports`，Catalog 驱动，不计算业务结果；
- Permission：USER / ADMINISTRATOR 可导出相同六类授权数据，匿名 401；
- Audit：V1 排除写日志；
- 下一阶段：仅允许 Phase 10 Implementation Planning。
