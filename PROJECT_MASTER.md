# 短剧数据管理与分析系统

> 本文档是项目唯一设计真源（Single Source of Truth）。任何 Agent 在开始 Task 前必须完整阅读本文档；除非 Task 获得项目负责人明确授权，不得更改已冻结内容。

## 0. 文档信息

| 项目 | 内容 |
| --- | --- |
| 中文名称 | 短剧数据管理与分析系统 |
| 英文名称 | Short Drama Data Management and Analysis System |
| 软件版本 | V1.0 |
| 文档版本 | V0.1 |
| 当前 Phase | Phase 0 - Completed |
| 当前 Task | TASK-P0-03 |
| 文档状态 | Requirements Baseline Established |
| 下一阶段状态 | Waiting for Phase 1 Task |
| 最近更新日期 | 2026-09-07 |

状态标签：

- 【已冻结】：项目负责人已经确认，未经明确授权不得修改。
- 【待后续设计】：需求方向明确，但具体技术设计尚未确定。
- 【未来扩展】：不属于 V1.0 开发范围。

本文档记录真实的软件工程设计与开发状态，不是课程设计报告正文，也不代表数据库概念设计、逻辑设计或 Schema 已获批准。

## 1. 项目定义

### 1.1 基本属性【已冻结】

- 项目性质：数据库系统课程设计项目，同时作为可持续完善的软件工程项目。
- 开发形式：个人开发。
- 开发模式：项目负责人负责需求和架构决策；Codex、DeepSeek V4 Pro 等 Agent 按 Task 辅助实现。
- 长期方向：课程设计结束后继续完善，形成相对完整的软件产品，并作为软件著作权相关材料的基础。

### 1.2 系统定位【已冻结】

本系统是面向短剧数据管理、短剧运营分析和短剧行业数据研究的数据管理与分析平台，主要服务于短剧运营人员、短剧数据管理人员、数据分析人员、行业研究人员和普通数据查询人员。

本系统不是短剧播放平台。项目核心主线必须保持为：

```text
数据管理 → 数据处理 → 数据分析 → 数据可视化 → 形成有价值的数据结果
```

系统不得退化为只有增、删、改、查的简单管理系统。

## 2. 已冻结需求

### 2.1 短剧与平台范围【已冻结】

- V1.0 不按抖音、快手、红果、小程序或长视频平台等来源拆分短剧体系，统一作为 `Drama` 管理。
- `Platform` 是独立业务实体，用于表达某部 `Drama` 在某个平台上线。
- `Drama` 与 `Platform` 业务上为 M:N；同一短剧可以在多个平台上线。
- 同一短剧在不同平台上的运营数据必须独立记录。
- 平台上线关系未来可能包含平台作品编号、平台上线时间、平台页面 URL、上线状态等关系属性，具体属性【待后续设计】。
- 运营数据必须基于 `Drama + Platform` 确定的平台上线关系，不得在快照中冗余保存可关联查询得到的 `drama_name`、`platform_name` 等描述字段。

### 2.2 人物、公司与标签关系【已冻结】

- `Actor` 必须作为独立业务实体，支持基础资料、参演作品、角色名称、角色类型、主演/配角等参与信息、作品数量分析和相关作品表现分析。
- `Drama` 与 `Actor` 业务上允许 M:N。禁止用逗号字符串保存演员名单；演员自身属性不得重复存入短剧演员关系。
- `Director` 必须作为独立业务实体并进入统计分析体系，支持基本信息、参与作品、作品数量、作品平均表现和作品热度分析。
- 一部短剧允许存在多个导演，不得永久冻结为一剧一导演的 `Drama.director_id` 结构。
- `Company` 必须作为独立实体并进入统计分析体系；同一短剧可关联多个公司，关系可表达出品、制作、发行、联合制作及其他合理类型。
- `DramaCompany` 需要能够表达 `relation_type`；采用枚举/约束还是独立关系类型实体【待后续设计】。
- 短剧采用多标签体系，`Drama` 与 `Tag` 业务上为 M:N。禁止以逗号字符串或 JSON 字符串规避正规关系设计，除非未来存在明确的非关系型附加需求。
- `Actor` 字段、`Drama-Director` 具体关系模式及其他最终实体字段【待后续设计】。

### 2.3 历史运营数据【已冻结】

- 系统必须保存历史运营快照，不能只保存最新值。
- 核心原始指标至少包括：`play_count`、`like_count`、`comment_count`、`favorite_count`、`share_count`、`ranking`、`snapshot_time`。
- 后续分析须支持相邻快照变化、24 小时变化、7 日趋势、30 日趋势、热度排名、潜力排名和异常增长检测。
- 候选结构 `DramaMetricSnapshot` 优先通过 `DramaPlatform` 关联具体作品与平台。
- 同一 `DramaPlatform` 在完全相同的 `snapshot_time` 原则上不应存在两条业务快照；正式 UNIQUE 候选键【待数据库逻辑设计阶段确认】。

### 2.4 V1.0 边界【已冻结】

V1.0 暂不实现完播率、付费转化率、广告消耗、收益、ROI、用户留存、用户付费行为和精细化投流数据。这些指标属于【未来扩展】，不得为其提前构建大量无实际用途的数据结构。

V1.0 自动分析结论不使用大语言模型；V2.0 可将 AI 自动分析报告作为【未来扩展】。自动 Word、PDF 数据分析报告和 PPT 报告不属于 V1.0 要求。

## 3. 系统用户与权限

### 3.1 用户体系【已冻结】

V1.0 采用管理员与普通用户两级用户体系，不开放公开注册，普通账号由管理员创建。

管理员主要权限：用户管理、基础数据管理、数据导入、数据修改、数据删除、数据处理、数据分析、数据导出和日志查看。

普通用户主要权限：查询、数据筛选、Dashboard、数据分析、图表和数据导出。

V1.0 暂不实现复杂的按钮级 RBAC，但架构不得阻碍未来扩展更多角色。`Role` 是否作为独立表【待数据库概念设计阶段审查】。

### 3.2 操作日志【已冻结】

- 记录新增、修改、删除、数据导入、重要数据修正及其他高价值管理操作。
- 不要求记录每次普通 GET 查询。
- `OperationLog` 具体结构【待后续设计】。
- 即使业务实体发生逻辑删除或物理删除，历史操作记录仍应保有审计意义。

## 4. 功能范围

### 4.1 V1.0 功能方向【已冻结】

- 短剧、平台、演员、导演、制作公司、标签等基础数据管理；
- 历史运营快照管理；
- CSV / Excel 数据导入、清洗、质量检查与错误记录；
- 原始数据统计、派生指标计算、趋势和排名分析；
- 业务规则异常与统计异常检测；
- Dashboard 与数据可视化；
- 基于统计结果、规则和模板的自动基础结论；
- CSV / Excel 数据导出；
- 用户权限与重要操作日志。

以上为 V1.0 规划范围，不代表相关功能已经实现。

### 4.2 Dashboard【已冻结业务范围】

Web 首页为 Dashboard 数据驾驶舱，计划展示短剧、平台、演员、导演、制作公司和历史运营记录数量，今日新增数据和当前异常数据数量，以及：

- 综合热度 TOP10；
- 潜力短剧 TOP10；
- 近 30 日总体播放趋势；
- 题材分布及各题材平均表现；
- 不同平台表现；
- 互动指标构成；
- 数据异常趋势。

页面布局、图表类型、接口结构和刷新策略【待后续前端 / Dashboard 专项 Task】。

### 4.3 备份与恢复【未来扩展】

V1.0 课程项目阶段不要求完整自动备份恢复系统。手动备份、自动备份、恢复和数据版本管理留待后续版本，当前不得提前开发。

## 5. 数据范围

### 5.1 V1.0 数据内容【已冻结】

V1.0 覆盖播放量、点赞量、评论量、收藏量、分享量、热度、排名、上线时间、集数、单集时长、题材 / 标签、平台、演员、导演和制作公司。

必须严格区分原始数据和派生分析数据：播放量、点赞量等属于原始指标，热度属于派生指标。

### 5.2 当前数据来源【已冻结】

- V1.0 课程项目阶段不连接真实企业生产数据，首先使用模拟数据。
- 模拟数据用于验证数据库结构、数据导入、数据清洗、统计分析、异常检测、Dashboard 和系统整体流程。

### 5.3 模拟数据规模【已冻结】

- 短剧数量：约 100 部。
- 历史跨度：90 天。
- 默认模拟频率：每天 4 个快照，默认时间为 08:00、12:00、18:00、22:00。
- 每天 4 次只是模拟数据生成策略，数据库模型不得限制每日只能生成 4 个快照。
- 真实系统应允许同一短剧在同一平台于任意合理时间生成运营数据快照。
- V1.0 预计历史运营数据约 7 万～10 万条，具体取决于短剧的平台覆盖数量。

## 6. 候选业务实体

### 6.1 候选清单【待后续设计】

候选业务对象：`User`、`Role`、`Drama`、`Platform`、`Actor`、`Director`、`Company`、`Tag`。

候选关系或业务过程对象：`DramaActor`、`DramaDirector`、`DramaCompany`、`DramaTag`、`DramaPlatform`、`DramaMetricSnapshot`、`ImportJob`、`ImportError`、`DataQualityIssue`、`OperationLog`。

这些名称仅是候选实体，不是已冻结数据库表。概念结构设计必须重新审查其独立性、合并或拆分需要、业务表达、冗余和至少 3NF 的符合性。禁止为了达到固定表数量而机械建表。

## 7. 数据分析指标体系

### 7.1 原始指标与派生指标【已冻结】

基础业务数据库主要保存 `play_count`、`like_count`、`comment_count`、`favorite_count`、`share_count`、`ranking` 等原始数据。

派生指标包括 `LikeRate`、`CommentRate`、`FavoriteRate`、`ShareRate`、`EngagementRate`、`GrowthRate`、`HeatScore` 和 `PotentialScore`。

`like_rate`、`comment_rate`、`favorite_rate`、`share_rate`、`engagement_rate`、`growth_rate`、`heat_score`、`potential_score` 原则上不得直接冗余存入基础运营快照表，应优先通过 SQL、View、Service、Pandas 或 NumPy 动态计算。

若未来因真实性能问题需要缓存，必须建立独立分析结果 / 汇总层，并至少记录数据范围、计算时间和模型版本。不得为方便前端展示而破坏关系数据库规范化。

### 7.2 互动指标【已冻结】

```text
LikeRate = like_count / play_count
CommentRate = comment_count / play_count
FavoriteRate = favorite_count / play_count
ShareRate = share_count / play_count

EngagementRate =
  (like_count + comment_count + favorite_count + share_count)
  / play_count
```

当 `play_count = 0` 时，上述比率必须返回 `NULL`，不得返回 `0`。“没有有效播放数据”和“有播放但没有互动”是不同的数据含义。

### 7.3 增长指标【已冻结基础公式】

```text
Growth = (CurrentValue - PreviousValue) / PreviousValue
```

系统后续至少支持相邻快照、24 小时、7 日和 30 日增长率；Dashboard 优先展示 7 日增长表现。`PreviousValue = 0` 等边界问题【待分析算法实现阶段统一处理】。

### 7.4 Heat Model V1【已冻结】

```text
N(x) = (x - xmin) / (xmax - xmin)

Heat = 100 × (
  0.40 × N(play_count)
  + 0.20 × N(like_count)
  + 0.15 × N(comment_count)
  + 0.15 × N(favorite_count)
  + 0.10 × N(share_count)
)
```

采用 Min-Max 标准化，输出范围目标为 0～100。权重已冻结，不得修改。

`xmin / xmax` 的计算范围、时间窗口、平台内或跨平台比较、极端值影响、`NULL`、`xmax = xmin` 及无有效数据等规则【待分析算法专项 Task 冻结】。

### 7.5 Potential Model V1【已冻结】

模型用于发现总体规模未必最大，但近期增长较快且互动质量较好的短剧。

```text
QualityEngagement = (like_count + comment_count) / play_count

Potential = 100 × (
  0.45 × N(7日播放增长率)
  + 0.25 × N(QualityEngagement)
  + 0.20 × N(FavoriteRate)
  + 0.10 × N(ShareRate)
)
```

权重已冻结，不得修改。模型重点衡量增长速度和互动质量，而不是当前播放总量。边界条件【待分析算法专项 Task 冻结】。

### 7.6 自动分析结论【已冻结】

V1.0 使用统计结果、规则和模板生成基础数据结论，不使用 LLM。结论可描述题材互动表现、热度排名、7 日增长和潜力排名等客观结果。AI 自动分析报告属于 V2.0【未来扩展】。

## 8. 数据质量与异常检测

### 8.1 两层异常检测【已冻结方向】

第一层为业务规则异常，包括各累计指标小于 0、非法时间、未知平台、必填字段缺失和明显不合理的累计值下降。

第二层为统计异常，优先采用 `Median + MAD + Robust Z-score` 检测异常增长和异常下降；V1.0 不采用机器学习异常检测模型。

滚动窗口大小、`MAD = 0`、Z-score 阈值、最低样本数和多平台异常比较范围【待异常检测算法专项 Task 冻结】。

### 8.2 数据清洗【已冻结】

V1.0 支持缺失值、重复数据、数据类型、非法负数、日期 / 时间格式、未知平台和极端异常值检查，并支持安全自动修正与错误数据记录。

允许去除字符串首尾空格、处理数字千位符、转换明确可识别的数字与时间格式、将空字符串转为 `NULL`，以及执行明确无歧义的数据名称映射和格式转换。

禁止将负播放量直接改为 0、用平均值填补缺失播放量、随机匹配未知演员或平台、制造不存在的运营数据，或用虚构值掩盖数据质量问题。重要数据处理必须可追溯。

## 9. 数据导入导出

### 9.1 数据导入【已冻结】

V1.0 支持 CSV 和 Excel，至少覆盖基础业务数据与运营快照数据。目标流程为：

```text
读取文件 → 字段验证 → 数据类型转换 → 重复/缺失/异常检测
→ 安全修正 → 错误记录 → 数据库写入 → 导入报告
```

批量正式数据写入必须使用 Transaction 保证一致性。TASK-P0-02 不实现导入功能。

### 9.2 数据导出【已冻结】

V1.0 支持 CSV 和 Excel，计划支持短剧列表、查询结果、排行结果、分析结果和异常结果导出。自动 Word、PDF 分析报告和 PPT 报告不属于 V1.0。

## 10. 模拟数据规范

### 10.1 生成原则【已冻结】

模拟运营指标不得彼此完全独立随机，应体现合理业务关联，例如点赞、评论、收藏和分享数量由播放量与相应比率共同影响。

必须主动设计爆款短剧、普通短剧、潜力短剧、衰退短剧和异常短剧五类数据行为，用于验证分析算法能否识别不同数据模式，而不是只生成数量足够但没有业务意义的数据。

## 11. 数据库设计原则

### 11.1 范式总要求【最高优先级已冻结】

整个关系数据库逻辑结构必须至少满足第三范式（3NF），这是硬性验收条件，不是建议。

### 11.2 第一范式（1NF）【已冻结】

每个字段必须原子化。禁止在单字段内保存演员、标签、平台或导演列表，多值关系必须通过实体与关联关系表达。

### 11.3 第二范式（2NF）【已冻结】

对于具有联合候选键的关联关系，所有非主属性必须完全依赖完整候选键。例如关系中的角色名称、角色类型和排序可描述某演员在某短剧中的参与关系；演员性别只依赖演员，短剧名称只依赖短剧，均不得复制到该关系中。

### 11.4 第三范式（3NF）【已冻结】

- 禁止非主属性通过其他非主属性产生不必要的传递依赖。
- 公司名称和地址等公司属性应属于公司实体，不得重复放入短剧实体。
- 平台名称应来自平台实体，不得重复放入运营快照。
- 禁止为了减少 JOIN 将大量其他实体信息复制到事实数据中。

### 11.5 3NF Review【后续数据库阶段必须执行】

在 Schema 正式冻结前，每张核心业务表必须逐表回答并通过以下审查：主键与候选键；属性原子性与多值属性；部分函数依赖；传递函数依赖；其他实体数据重复；可动态计算的不必要冗余字段；外键合理性；INSERT、UPDATE、DELETE 异常风险。

只有完成 E-R Conceptual Design、Logical Schema 和逐表 3NF Review，且所有核心表 Review PASS 后，才能标记 `DB Schema Freeze V1`。当前不得标记数据库设计、概念设计或 Schema 已批准。

### 11.6 完整性与外键【已冻结要求】

- 后续数据库必须体现实体完整性、参照完整性和用户定义完整性。
- 合理使用 PRIMARY KEY、FOREIGN KEY、UNIQUE、NOT NULL、CHECK 和 INDEX。
- 核心业务关系必须在 MySQL 中建立真实 FOREIGN KEY，不得只在 SQLAlchemy ORM 中声明 `relationship`。
- 最终外键及 ON DELETE 策略【待后续设计】。

### 11.7 主键原则【当前设计原则】

- 核心业务实体内部主键默认优先考虑 `BIGINT UNSIGNED AUTO_INCREMENT`。
- `drama_code` 等业务编号应作为独立字段并设置 UNIQUE。
- 无充分设计理由不得用复杂、可变业务编码作为数据库主键。
- 最终字段与 MySQL 数据类型【待数据库逻辑设计阶段冻结】。

### 11.8 时间原则【已冻结方向】

- 后端业务时间统一使用 UTC。
- 前端默认按 Asia/Shanghai（UTC+8）展示。
- MySQL 使用 DATETIME 还是 TIMESTAMP，以及 ORM 时区处理策略【待数据库和后端专项 Task 冻结】。

### 11.9 原始与派生指标分离【已冻结】

基础关系模型主要保存原始指标，派生分析指标按第 7 节原则动态计算或进入独立分析结果 / 汇总层，不得直接污染基础运营快照结构。

### 11.10 数据库高级功能【已冻结方向】

后续数据库应合理体现 E-R 模型、关系模式、主键、外键、完整性约束、索引、View、Transaction、SQL 初始化 / Migration 和数据字典。Trigger 与 Stored Procedure 为可选项，只有具备真实业务价值时才使用，不得为展示技术数量而强行引入。

最终 E-R 模型、实体字段、关系模式、候选键、MySQL 数据类型、删除策略、外键 ON DELETE 策略、索引、View、Migration 和数据字典均【待后续设计】。本文档不包含具体 Schema 或建表 SQL。

## 12. 系统架构

### 12.1 总体架构【已冻结】

```text
Vue 3 Frontend → RESTful API → FastAPI → Service / Analytics
→ SQLAlchemy → MySQL
```

系统采用前后端分离架构。严格禁止 Vue 直接连接 MySQL。后端业务逻辑不得全部堆入 Router，后续分层方向为 Router → Service → Repository / ORM → Database。

```text
MySQL Raw Data → SQL / Pandas / NumPy → Derived Metrics
→ FastAPI → Vue / ECharts
```

具体前后端内部目录结构【待各自初始化 Task】。

## 13. 技术栈

### 13.1 Web 技术栈【已冻结】

- 前端：Vue 3、Vite、Element Plus、Vue Router、Pinia、Axios、ECharts。
- 后端与分析：Python 3.12、FastAPI、SQLAlchemy 2.x、Pydantic、Alembic、Pandas、NumPy、openpyxl。
- 数据库：MySQL 8.x。
- 版本管理：Git、GitHub。

这里只冻结主要技术栈。第三方包精确版本以后以 requirements、pyproject、package-lock 等工程锁定文件为准，不在当前文档中虚构小版本号。

## 14. 前端约束

### 14.1 UI 方向【已冻结方向】

- Web 端支持 Light / Dark Theme。
- 整体风格为现代化数据管理后台。
- 数据分析模块可以具有较强的数据可视化表现。
- V1.0 不单独开发另一套完全独立的“科技大屏系统”。
- 具体视觉规范和前端布局【待 UI 专项设计 Task】。
- 业务规则不得只写在 Vue 页面中。

## 15. 后端约束

### 15.1 API 与分层【已冻结】

- 使用 FastAPI 提供 RESTful API。
- 业务逻辑不得全部堆入 Router。
- 数据访问通过 SQLAlchemy 与 MySQL 完成。
- 数据分析由 SQL、Pandas、NumPy 等在后端分析链路中完成，再由 API 提供给前端。
- 重要批量数据写入需要 Transaction。
- API 具体路径、请求响应模型、模块边界和异常处理规范【待后端专项 Task】。

## 16. 企业数据接入扩展

### 16.1 接入原则【已冻结】

未来企业数据不得被要求完全符合当前数据库输入格式，也不得直接破坏系统内部标准关系模型。统一接入链路为：

```text
企业数据源 → Adapter / ETL / Import → Validation / Mapping
→ 系统内部统一数据模型 → MySQL → Analytics
```

未来可接入 REST API、CSV、Excel、外部数据库及其他结构化业务数据。具体 Adapter、Mapping 与接入协议【未来扩展】。

## 17. 桌面端规划

### 17.1 桌面端【未来扩展】

- V1.0 只开发 Web，不开发桌面端。
- 桌面端技术方案尚未确定，候选包括 Tauri、Electron、PySide。
- 当前系统必须保持后端 API 化，使未来桌面客户端尽量复用现有 API 和业务逻辑。

## 18. 测试与验收原则

### 18.1 通用原则【已冻结】

- 每个 Task 只验证本 Task 授权范围，不伪造未执行的测试。
- 数据库阶段必须完成概念结构设计、逻辑结构设计和逐表 3NF Review 后，方可冻结 Schema。
- 模拟数据应能够验证导入、清洗、统计分析、异常检测、Dashboard 和系统整体流程。
- 功能完成情况必须以实际代码、测试和 Git 记录为依据，不得提前宣称实现。
- V1.0 最终验收在 Phase 17 进行。

## 19. Agent 开发规范

### 19.1 Task 驱动流程【已冻结】

任何 Agent 开始 Task 前必须完整阅读本文件。标准流程：

```text
Read PROJECT_MASTER → Inspect Repository → Confirm Task Scope
→ Implement → Test → Self Review → Update PROJECT_MASTER
→ Git Commit → Stop
```

一个 Task 只解决一个明确阶段的问题，完成后立即停止。禁止直接开发整个项目。

### 19.2 修改权限【已冻结】

- 后续 Task 必须明确允许修改与禁止修改范围。
- 未获授权不得大范围重构其他模块。
- 发现冻结设计存在潜在问题时，可以提出建议并记录原因，但不得自行改变架构，必须等待项目负责人批准。

### 19.3 禁止事项【已冻结】

未经明确 Task 授权，禁止更换 Vue、FastAPI 或 MySQL；删除数据库外键以规避报错；用冗余字段破坏 3NF；修改 Heat Model V1 或 Potential Model V1 权重；引入 Redis、微服务、Kafka、Elasticsearch、机器学习、大语言模型或与课程规模不匹配的复杂分布式基础设施；大规模修改无关代码或删除用户已有代码；Force Push 或改写 Git 历史。

## 20. Git 规范

### 20.1 版本管理【已冻结】

- 版本管理使用 Git，远程平台为 GitHub，默认分支为 `main`。
- `main` 原则上保持可运行、可恢复。
- Commit 推荐使用 `feat:`、`fix:`、`docs:`、`test:`、`refactor:`、`chore:` 前缀。
- 已有 TASK-P0-01 提交：`8e6b762 chore: initialize project structure`。
- 禁止 `git push --force`，未经许可不得通过 rebase / reset 改写已有公共历史。
- 当前 GitHub remote 尚未配置，不得猜测远程地址，不执行 push。

## 21. 开发路线

以下仅为阶段路线，不代表已经实现：

| Phase | 内容 | 状态 |
| --- | --- | --- |
| Phase 0 | 项目初始化和设计基线 | Completed |
| Phase 1 | 需求与功能模块正式冻结 | Waiting |
| Phase 2 | 数据分析规则细化 | Waiting |
| Phase 3 | 数据库概念结构设计 | Waiting |
| Phase 4 | 数据库逻辑结构与 3NF Review | Waiting |
| Phase 5 | MySQL Schema 实现 | Waiting |
| Phase 6 | 模拟数据系统 | Waiting |
| Phase 7 | FastAPI 基础架构 | Waiting |
| Phase 8 | 核心业务 API | Waiting |
| Phase 9 | 数据导入与清洗 | Waiting |
| Phase 10 | 数据分析服务 | Waiting |
| Phase 11 | Vue 基础架构 | Waiting |
| Phase 12 | 后台数据管理页面 | Waiting |
| Phase 13 | Dashboard 与数据可视化 | Waiting |
| Phase 14 | 用户权限与操作日志 | Waiting |
| Phase 15 | 数据导出 | Waiting |
| Phase 16 | 系统测试与修复 | Waiting |
| Phase 17 | V1.0 最终验收 | Waiting |
| Phase 18 | 课程设计报告统一生成 | Waiting |
| Phase 19 | 后续软件完善 / 软著准备 | Future |

## 22. 当前 Task 状态

| Task | 内容 | 状态 |
| --- | --- | --- |
| TASK-P0-01 | 项目工程初始化 | Completed |
| TASK-P0-02 | 建立并冻结 PROJECT_MASTER.md 项目设计真源 V0.1 | Completed |
| TASK-P0-03 | 同步项目说明并完成 Phase 0 收尾 | Completed |

- 当前 Phase：Phase 0 Completed。
- 文档版本：V0.1。
- 文档状态：Requirements Baseline Established。
- 项目状态：Waiting for Phase 1 Task。
- 最终 E-R 模型尚未设计、绘制或冻结；数据库概念结构设计、逻辑结构设计和 DB Schema 均未批准或冻结。

## 23. 设计决策记录

### ADR-001：唯一设计真源【已冻结】

`PROJECT_MASTER.md` 是项目唯一设计真源，后续 Agent 必须先完整阅读再执行 Task。

### ADR-002：关系数据库规范化【已冻结】

主业务数据库采用 MySQL 8.x，关系模型必须至少满足 3NF，核心业务关系必须建立真实 FOREIGN KEY，原始数据与派生分析数据分离。

### ADR-003：分析模型基线【已冻结】

Heat Model V1 和 Potential Model V1 的公式与权重按第 7 节执行；尚未确认的标准化范围和边界条件不得自行冻结。

### ADR-004：Web 优先与 API 化【已冻结】

V1.0 采用 Vue 3 + FastAPI + MySQL 的前后端分离 Web 架构，桌面端作为未来扩展并复用 API 与业务逻辑。

### ADR-005：报告生成时机【已冻结】

当前不生成正式课程设计报告或软著材料。系统、数据库、分析、页面和测试完成后，在专项阶段基于真实素材统一整理，不得为报告格式改变实际软件架构。

## 24. Bug 与技术债务

- 当前无已确认的软件 Bug。
- TASK-P0-01 时 `PROJECT_MASTER.md` 信息不足的问题已由 TASK-P0-02 建立 V0.1 设计基线解决。
- README 技术栈说明过时的一致性问题已由 TASK-P0-03 修复。
- 所有标记为【待后续设计】的事项属于计划内设计工作，不得误报为已实现功能或当前 Bug。

## 25. 最终报告 / 软著素材索引

当前仅维护真实素材状态，不撰写课程设计报告正文或正式软著材料。

| 素材 | 状态 |
| --- | --- |
| 项目需求 | 已建立 V0.1 基线 |
| 架构设计决策 | 已建立初始记录 |
| E-R 图 | 待完成 |
| 最终数据库 Schema | 待完成 |
| 数据字典 | 待完成 |
| 3NF Review | 待完成 |
| 主键 / 外键 / 完整性设计 | 待完成 |
| 索引 | 待完成 |
| View | 待完成 |
| Transaction 设计与验证 | 待完成 |
| SQL / Migration | 待完成 |
| Git Commit | 持续保留 |
| 测试记录 | 待后续 Task 产生 |
| Bug 修复记录 | 待后续 Task 产生 |
| 核心代码位置 | 待后续 Task 产生 |
| 系统运行截图 | 待完成 |
| Dashboard 截图 | 待完成 |
| 数据分析结果 | 待完成 |
| 模拟数据说明 | 待完成 |
| 实际软件版本 | 持续维护 |
| 最终运行环境 | 待最终确认 |

项目长期持续保留清晰的软件名称、软件版本、Git 历史、开发与功能变更记录、系统截图、数据库设计、功能说明、稳定工程目录和可运行代码。正式课程设计报告安排在 Phase 18，后续软件完善与软著准备安排在 Phase 19。

## 26. 开发记录

### TASK-P0-01

- 日期：2026-09-07。
- 任务：项目工程初始化。
- 完成内容：建立基础目录、README、`.gitignore`、`.env.example` 并初始化 Git `main` 分支。
- 未开发内容：未创建数据库表、Vue 页面、FastAPI 业务接口或业务代码。
- 当前状态：Completed。
- Commit：`8e6b762 chore: initialize project structure`。

### TASK-P0-02

- 日期：2026-09-07。
- 任务：建立并冻结 `PROJECT_MASTER.md` 项目设计真源 V0.1。
- 完成内容：整理项目定义、冻结需求、数据范围、分析模型、数据质量、技术架构、数据库规范、Agent 与 Git 规则、路线和素材索引。
- 未开发内容：未创建数据库表或 SQL，未初始化 FastAPI 或 Vue，未开发 API、页面、Dashboard、分析程序、模拟数据、导入导出等业务功能，未生成课程设计报告。
- 当前状态：Completed；Waiting for Next Task。
- Commit：`docs: establish project requirements baseline`（本 Task 提交，以 Git 历史记录的 Hash 为准）。

### TASK-P0-03

- 日期：2026-09-07。
- 任务：同步项目说明并完成 Phase 0 收尾。
- 完成内容：README 与 `PROJECT_MASTER.md` V0.1 基线同步；清除 README 过时说明；Phase 0 标记为 Completed；检查 GitHub remote 状态。
- 未开发内容：未进行数据库设计，未初始化或开发 Vue、FastAPI，未开发任何业务功能，未生成课程设计报告。
- GitHub remote：Not Configured。
- 当前状态：Completed；Waiting for Phase 1 Task。
- Commit：`docs: sync project documentation baseline`（本 Task 提交，Commit Hash 以 Git 历史记录为准）。
