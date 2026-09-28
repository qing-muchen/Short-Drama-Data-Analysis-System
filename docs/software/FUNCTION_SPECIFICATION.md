# 短剧数据管理与分析系统功能说明书

## 1. 文档目的

本文档说明短剧数据管理与分析系统 V1.0 的实际功能范围、使用对象、输入输出和权限边界，用于软件验收、产品说明和软件著作权材料准备。本文档不将规划能力描述为已实现能力。

# 第一章 系统登录与权限管理

## 1.1 用户登录

用户在登录页输入用户名和密码。后端校验 ACTIVE 用户状态及 bcrypt 密码哈希，校验成功后签发带有效期的 JWT Access Token。前端在后续 API 请求中通过 Bearer Token 携带身份。

系统不提供公开注册。初始账户及后续账户由受控的管理员流程维护。

## 1.2 当前用户识别

登录后，前端通过当前用户接口确认登录状态、显示名称和角色。路由守卫在访问受保护页面时检查认证状态；后端对每个受保护接口再次执行身份和角色校验。

## 1.3 权限模型

V1.0 采用两级角色：

| 角色 | 主要权限 |
| --- | --- |
| `ADMINISTRATOR` | 基础数据维护、导入与确认、分析计算、异常状态管理、运营行动管理及所有查询 |
| `USER` | Dashboard、数据查询、分析结果查看、治理查看和报告导出 |

权限以具体后端接口为准。普通用户不能通过隐藏按钮或直接构造请求绕过管理员校验。

# 第二章 数据管理与分析中心

## 2.1 基础数据管理

系统提供短剧、演员、平台和标签的列表、条件查询与详情查看。管理员可在已开放的管理页面和接口中执行新增、修改及停用/删除操作；普通用户以查询为主。

短剧数据支持名称、状态和标签等条件筛选，并关联平台、人物和标签等信息。系统使用关系表维护多对多关系，不以逗号字符串代替核心业务关系。

## 2.2 数据导入与校验

管理员可上传符合模板要求的 CSV 或 XLSX 文件。导入流程包括：

```text
选择导入类型与文件
        ↓
创建导入任务
        ↓
字段、格式和业务约束校验
        ↓
查看任务状态与错误记录
        ↓
确认导入
```

系统保留导入任务和错误信息。校验失败的数据不会被前端自动修正，管理员应根据错误记录修正源文件后重新提交。

## 2.3 Dashboard 数据驾驶舱

Dashboard 展示：

- 短剧、演员、导演、公司、平台等核心数量；
- 总播放量、平均互动率和质量问题数；
- Heat、Growth、Potential 排行；
- 近 30 日运营趋势；
- 数据质量摘要；
- 热门标签分布；
- 各业务中心的导航入口。

Dashboard 对不同数据区域采用独立加载状态；部分接口失败时可保留其他已成功加载的区域。

## 2.4 分析中心

基础分析中心基于历史运营快照提供指标摘要和结果展示，包括播放、互动、增长、热度、潜力及规则化 Insight。分析使用既有历史数据与固定口径，不包含 AI 生成内容。

## 2.5 综合评分

系统支持 Composite Score V1.0：

- 管理员按指定日期触发评分计算；
- 用户查看评分排行、等级分布和单剧评分详情；
- 展示 Heat、Growth、Engagement、Lifecycle 和 Total Score；
- 展示算法版本和分析时间。

前端只展示后端结果，不重新计算评分或等级。

## 2.6 Phase 2 数据质量

Phase 2 Data Quality 是持久化的业务分析质量模块，提供：

- 管理员触发质量评分；
- 当前质量评分；
- 历史质量结果；
- 规则列表和规则执行结果；
- Completeness、Accuracy、Consistency、Timeliness 等评分维度。

该模块与第五章的 Phase 9 Data Governance 不同：前者保存质量评分结果，后者执行请求时治理检查。

## 2.7 趋势预测

Prediction Module 使用固定的 Moving Average V1.0 规则生成下一日累计播放量预测。功能包括：

- 管理员为指定短剧触发预测；
- 用户查看最新预测；
- 用户查看历史预测结果；
- 展示目标日期、预测值、算法版本和 `analysis_as_of`。

历史数据不足时系统返回明确错误或 Availability 状态，不使用零值代替缺失预测。

## 2.8 异常检测

Anomaly Detection Module 提供：

- 管理员触发异常检测；
- 异常统计；
- 按指标、类型、严重程度和状态筛选；
- 单剧异常查看；
- 管理员更新异常状态；
- 展示基线、实际值、偏差和证据摘要。

异常检测基于已冻结规则和算法版本，不调用外部模型。

## 2.9 运营行动管理

Operation Action Module 支持：

- 创建运营行动；
- 查看行动列表、详情和统计；
- 分派负责人；
- 更新 OPEN、IN_PROGRESS、COMPLETED、CANCELLED 等状态；
- 添加处理评论；
- 保留来源与历史记录。

行动记录表达人员执行与跟踪事实，不表示某项行动必然导致指标变化。

## 2.10 解释与数据血缘

Explanation & Data Lineage Module 提供已存分析结果的解释摘要、算法版本、规则版本、分析时间和来源追溯入口。模块不生成新的评分、预测或异常，只解释并定位已有结果。

# 第三章 Drama 360° 全景画像中心

## 3.1 功能定位

Drama Profile 是以短剧为中心的只读聚合视图。系统通过单一页面汇总不同模块的最新可用结果，不创建新的分析事实。

## 3.2 页面内容

页面包含：

1. Drama Header：短剧名称和基础信息；
2. Performance：综合评分、维度摘要、算法版本和分析时间；
3. Quality：质量等级、状态和风险信息；
4. Trend：趋势方向、预测状态和算法版本；
5. Risk：异常数量、最高严重等级和最近异常；
6. Operations：行动状态数量和最近行动；
7. Explanations：最新解释摘要和血缘入口。

## 3.3 Availability

模块使用 `NOT_CALCULATED`、`INSUFFICIENT_HISTORY`、`NO_ANOMALY`、`NOT_DETECTED` 和 `NOT_AVAILABLE` 等原因表达状态。单个 Provider 失败不会使整个 Profile 页面失败。

## 3.4 权限与边界

USER 和 ADMINISTRATOR 均可查看。Profile 不调用评分、预测、异常或行动计算 Service，不自动触发分析任务，前端不通过空值推断业务状态。

# 第四章 运营分析中心

## 4.1 Action Effect

Action Effect 以行动首次完成时间为 T0，比较 T0 前后各 7 个完整业务日的既有指标。结果可以描述“行动后指标较行动前发生变化”，但不声明“行动导致指标变化”。

输出包括行动、时间窗口、指标变化、方向、规则版本和 Availability，不包含成功/失败、因果结果或推荐。

## 4.2 Lifecycle

Lifecycle 使用固定、可解释、版本化规则，将短剧描述为：

- LAUNCH；
- GROWTH；
- STABLE；
- DECLINE；
- ARCHIVED。

规则使用双 7 日窗口和 ±10% 阈值，不使用机器学习分类或概率输出。

## 4.3 Benchmark

Benchmark 对同一平台内显式选择的 2–20 部短剧执行滚动 30 个完整自然日统计比较。系统展示播放变化、互动率、异常频率及组中位数等事实，不生成排名、最佳短剧或推荐结论。

## 4.4 页面状态

Operation Analytics 页面将 Action Effect、Lifecycle 和 Benchmark 分区展示。各模块独立处理 loading、empty、error 和 success 状态。历史不足、范围不可比较或来源不可用时显示明确 Availability。

# 第五章 数据治理中心

## 5.1 模块边界

Data Governance 是 SYSTEM scope 的请求时只读治理检查，不保存治理快照、不修改业务数据，也不替代 Phase 2 Data Quality。

## 5.2 Freshness

比较最新可见数据时间、统一分析截点和冻结阈值，输出 HEALTHY、WARNING 或 NOT_AVAILABLE 等状态、延迟秒数和 Evidence。系统不自动刷新数据。

## 5.3 Completeness

检查必要字段、Metric 覆盖、时间连续性和关键关联覆盖，输出覆盖率、缺失项及 Evidence。系统不自动补字段或填充缺失数据。

## 5.4 Consistency

检查关系、弱引用、Revision 链和 `analysis_as_of` 一致性，输出问题数量和 Evidence。系统不自动修复关系或 Revision。

## 5.5 Evidence

Evidence 仅保存定位质量状态所需的最小类型、消息、来源和 metadata，不复制完整 Drama、Metric、Action 或 ORM 对象。前端原样展示，不进行二次解释。

# 第六章 分析报告中心

## 6.1 Report Catalog

系统显式注册六类报告：Drama Catalog、Score Results、Data Quality Results、Prediction Results、Anomaly Records 和 Operation Actions。Catalog 返回报告名称、说明、Schema Version、Column、Filter、支持格式和 Snapshot Semantics。

## 6.2 Filter

Filter 定义来自 Schema Registry。系统仅接受报告声明允许的字段，并校验字符串、整数、时间和枚举类型。时间统一为 timezone-aware UTC，不进行文本推断。

## 6.3 Preview

用户可预览最多 100 行报告数据。Preview 返回 Metadata、Snapshot、固定顺序 Columns、Rows 和 Availability。前端严格保持服务端 Column 顺序。

## 6.4 Export

系统支持 CSV 和 XLSX：

- CSV：UTF-8 BOM、CRLF、Formula Injection 防护；
- XLSX：write-only 生成、流式临时资源；
- 无有效 Filter 或超过 1,000 行时要求确认；
- CSV 最多 10,000 行；
- XLSX 最多 5,000 行；
- 文件最大 25 MiB。

报告在请求期间根据已有事实生成并通过 StreamingResponse 下载，不保存报告文件、Snapshot、Cache 或下载审计记录。

## 6.5 Availability

报告使用 `AVAILABLE`、`PARTIAL`、`EMPTY`、`INSUFFICIENT` 和 `NOT_AVAILABLE`。非 AVAILABLE 状态包含明确原因，不使用空值代替业务状态。

# 第七章 非功能特性

## 7.1 可追溯性

分析结果通过 `analysis_as_of`、algorithm version、rule version、revision、schema version 和 source version 描述时间截点与来源。

## 7.2 安全性

系统使用 JWT、角色校验、密码哈希、请求参数验证、统一错误响应、文件格式校验、导入限制和导出安全策略。接口不返回密码哈希或内部异常堆栈。

## 7.3 可维护性

前端、API、Service、Provider/Rule、Repository、ORM/Database 分层清晰。Read Model 模块优先读取已有结果，避免跨模块 Service 耦合。

## 7.4 数据一致性

数据库使用主键、唯一约束、检查约束、外键、Revision、UTC 时间和有序 Migration 维护数据一致性。业务写入由 Service 管理事务，Repository 集中处理数据访问。

## 7.5 明确排除范围

系统不具备 AI、自动决策、自动推荐、自动数据修复、因果分析或大规模异步报告能力。V1.0 未实现的内容不得作为验收功能。
