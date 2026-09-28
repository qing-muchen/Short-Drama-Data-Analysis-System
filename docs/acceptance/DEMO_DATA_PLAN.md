# Phase S2 Demo 数据规划

## 1. 文档目的

本文档定义短剧数据管理与分析系统 V1.0 的演示数据基线，用于页面展示、功能验证和软件验收。本文档仅规划数据，不提供数据写入脚本，不修改数据库、Migration、ORM、业务规则或权限体系。

Demo 数据必须通过现有管理、导入或受控初始化流程准备，并满足现有数据库约束。验收环境不得使用真实个人信息、真实商业数据或生产密码。

## 2. Demo 数据目标

Demo 数据应覆盖以下主要路径：

- 用户登录与两级权限；
- 基础数据管理和 CSV/XLSX 导入；
- Dashboard 数量、排行、趋势、质量和标签分布；
- Score、Quality、Prediction、Anomaly 和 Operation Action；
- Drama 360° Profile 聚合；
- Operation Analytics 的 Action Effect、Lifecycle 和 Benchmark；
- Data Governance 的 Freshness、Completeness、Consistency 与 Evidence；
- Reporting 的 Catalog、Filter、Preview、CSV 和 XLSX Export。

验收基线应同时具备“正常可用”和“显式空/不足状态”的可解释场景，但不得通过破坏外键或绕过数据库约束制造异常。

## 3. 时间与环境基线

### 3.1 统一时间锚点

每次准备演示环境时确定一个 timezone-aware UTC 时间：

```text
T_demo = 本次验收演示的统一 analysis_as_of
```

将实际 UTC 值记录在验收记录中，例如：

```text
T_demo: ______________________________
Prepared at: _________________________
Prepared by: _________________________
Database backup/reference: __________
```

所有 Metric、Score、Prediction、Anomaly、Action、Explanation 和验收请求均以同一个 `T_demo` 为基准。禁止由不同操作者在不同页面临时选择互相矛盾的时间。

### 3.2 相对时间规划

| 数据 | 相对范围 |
| --- | --- |
| 日度 Metric Snapshot | `T_demo - 45天` 至 `T_demo - 1天` |
| Lifecycle 最近窗口 | `T_demo - 14天` 至 `T_demo - 1天` |
| Benchmark 窗口 | 最近 30 个完整自然日 |
| Action completed_at | 建议 `T_demo - 8天` |
| Action Before | completed_at 前 7 个完整业务日 |
| Action After | completed_at 后 7 个完整业务日 |
| 最新 Governance 数据 | 在 Freshness V1 阈值允许范围内 |
| Prediction analysis_as_of | 不晚于 `T_demo` |

相对时间设计使演示数据可重复生成，并保证 Operation Analytics 所需窗口完整。

## 4. 演示账号规划

### 4.1 Administrator

| 项目 | 规划值 |
| --- | --- |
| 用户名 | `admin_demo` |
| 角色 | `ADMINISTRATOR` |
| 状态 | `ACTIVE` |
| 用途 | 展示完整系统入口、基础数据维护、导入、分析计算、异常和行动管理 |
| 可访问范围 | 所有授权查询，以及管理员专属写操作 |

### 4.2 User

| 项目 | 规划值 |
| --- | --- |
| 用户名 | `user_demo` |
| 角色 | `USER` |
| 状态 | `ACTIVE` |
| 用途 | 展示普通业务用户的查询、分析查看、治理查看和报告导出 |
| 可访问范围 | Dashboard、列表、Profile、Operation Analytics、Data Governance、Reports 等只读功能 |

### 4.3 密码管理

- 本文档不记录任何密码；
- 两个账号使用不同的强密码；
- 密码通过安全渠道交付演示人员；
- 数据库只保存 bcrypt 哈希；
- 验收结束后应停用或更换演示凭据；
- 不创建新角色，不扩大现有 USER/ADMINISTRATOR 权限。

## 5. 基础主数据规划

### 5.1 Platform

至少准备两个 ACTIVE 平台：

| Demo Code | 展示名称 | 用途 |
| --- | --- | --- |
| `PLATFORM_DEMO_A` | 星河短剧 | 主 Benchmark 平台，至少关联 4 部 Drama |
| `PLATFORM_DEMO_B` | 云帆剧场 | 展示跨平台关系和 Dashboard 平台统计 |

名称均为虚构演示名称。

### 5.2 Tag 与分类展示

当前 Drama 没有标准化 `category` 字段。Demo 的题材/分类展示必须通过现有 Tag 与 DramaTag 关系表达，不得新增字段或将自由文本伪装为 Category。

建议准备 ACTIVE Tag：

- 都市；
- 悬疑；
- 成长；
- 轻喜剧；
- 情感。

### 5.3 Actor、Director、Company

为主展示 Drama 配置：

- 至少 6 名虚构演员；
- 至少 3 名虚构导演；
- 至少 2 家虚构公司；
- 建立有效 DramaActor、DramaDirector、DramaCompany 关系；
- 主演/配角及公司关系类型使用数据库允许值；
- 不使用真实身份证明、联系方式或商业主体信息。

## 6. Drama 数据规划

建议至少准备 5 部短剧，其中 4 部用于同平台 Benchmark，1 部用于空/不足状态演示。

| Drama Code | 名称 | 状态 | 首播时间规划 | Tag | Platform | 主要用途 |
| --- | --- | --- | --- | --- | --- | --- |
| `DEMO_DRAMA_001` | 星光之下 | `SERIALIZING` | `T_demo - 60天` | 都市、成长 | A、B | 主 Profile、Action Effect、GROWTH、报告 |
| `DEMO_DRAMA_002` | 雾城来信 | `COMPLETED` | `T_demo - 90天` | 悬疑 | A | STABLE、Benchmark、异常记录 |
| `DEMO_DRAMA_003` | 夏日合伙人 | `SERIALIZING` | `T_demo - 45天` | 轻喜剧、都市 | A | DECLINE、Benchmark |
| `DEMO_DRAMA_004` | 归途有风 | `COMPLETED` | `T_demo - 120天` | 情感 | A | Benchmark 对照、无异常状态 |
| `DEMO_DRAMA_005` | 初见新章 | `DRAFT` | 未首播或临近首播 | 成长 | B | 未计算/历史不足/空状态演示 |

每部正式展示 Drama 应配置：

- 唯一 `drama_code`；
- 非空 `drama_name`；
- 适度长度的虚构 synopsis；
- 正数 episode_count；
- 正数 episode_duration_seconds；
- 与状态一致的 premiere_date；
- ACTIVE Platform 和 Tag 关系。

`DEMO_DRAMA_005` 用于显式 Availability 演示时，不应填充伪造的 Score、Prediction 或历史 Metric；页面应展示真实的未计算或历史不足状态。

## 7. Historical Metric 与 Revision 规划

### 7.1 Snapshot 覆盖

为 `DEMO_DRAMA_001–004` 在 `PLATFORM_DEMO_A` 建立最近 45 个完整自然日的日度 `DramaMetricSnapshot`。主剧在 Platform B 可准备至少 30 日数据，用于跨平台展示。

每个有效 Revision 包含：

- `play_count`；
- `like_count`；
- `comment_count`；
- `favorite_count`；
- `share_count`；
- 可选 `ranking`；
- `version_no`、`revision_action`、`changed_at` 和操作者。

累计计数必须非负并保持可解释趋势。不可用数据使用缺失/Availability 表达，不得将 NULL 自动替换为 0。

### 7.2 趋势形态

| Drama | 最近前 7 日与后 7 日规划 | 预期 Lifecycle |
| --- | --- | --- |
| `DEMO_DRAMA_001` | 最近 7 日播放增量比前 7 日高于 +10% | GROWTH |
| `DEMO_DRAMA_002` | 最近 7 日变化落在 ±10% 内 | STABLE |
| `DEMO_DRAMA_003` | 最近 7 日播放增量比前 7 日低于 -10% | DECLINE |
| `DEMO_DRAMA_004` | 保持完整可比数据，作为组统计对照 | 由固定规则得出 |
| `DEMO_DRAMA_005` | 无完整双 7 日窗口 | INSUFFICIENT |

具体数值应由现有校验和规则测试确认，不在 Demo 规划中修改阈值或 Rule Component。

### 7.3 Revision 演示

可为一条非关键历史 Snapshot 准备：

1. `INITIAL` version 1；
2. `CORRECTION` version 2；
3. 非空 change_reason；
4. 正确 previous_revision_id；
5. `changed_at <= T_demo`。

该记录用于展示 as-of/revision 查询。主验收基线不应使用错误链、孤立 previous revision 或违反外键的记录。

## 8. Analysis 数据规划

### 8.1 Score

为 `DEMO_DRAMA_001–004` 准备同一 score_date 和算法版本的 Score 结果，覆盖至少两个等级。主剧 `DEMO_DRAMA_001` 必须存在：

- heat_score；
- growth_score；
- engagement_score；
- lifecycle_score；
- total_score；
- level；
- algorithm_version；
- `analysis_as_of <= T_demo`。

Score 应通过现有管理员计算流程生成或使用已验证结果，不手工制造不符合计算口径的数值。

### 8.2 Phase 2 Data Quality

准备至少一条当前 `DataQualityScore` 及其 Rule Results：

- Completeness、Accuracy、Consistency、Timeliness；
- total_score 和 quality_grade；
- active rule_set_version 与 hash；
- evaluated_entity_count 和 open_issue_count；
- 可展示的 evidence_summary。

质量结果通过现有计算流程产生，不与 Phase 9 请求时 Governance Result 混用。

### 8.3 Prediction

为主剧准备最新 Prediction 和至少 3 条历史 Prediction：

- metric_type = `PLAY_COUNT`；
- algorithm_version = `Moving Average V1.0`；
- timezone-aware `analysis_as_of`；
- target_date；
- 非负 predicted_value。

`DEMO_DRAMA_005` 不准备 Prediction，用于展示 `NOT_CALCULATED` 或 `INSUFFICIENT_HISTORY`。

### 8.4 Anomaly

至少准备两种状态：

| Drama | 示例类型 | Severity | Status | 用途 |
| --- | --- | --- | --- | --- |
| `DEMO_DRAMA_001` | PLAY_COUNT_GROWTH_ANOMALY | B | OPEN | Profile Risk、Action Source、异常列表 |
| `DEMO_DRAMA_002` | ENGAGEMENT_RATE_ANOMALY | C | ACKNOWLEDGED | 筛选、状态和 Evidence |
| `DEMO_DRAMA_004` | 无记录 | — | — | `NO_ANOMALY` 场景 |

每条记录包含 baseline、actual、deviation、algorithm_version、detected_at 和非空 evidence_summary。

### 8.5 Operation Action

至少准备：

1. 一条关联 `DEMO_DRAMA_001` 的 COMPLETED Action；
2. 一条 IN_PROGRESS Action；
3. 一条 OPEN Action；
4. MANUAL 与 ANOMALY 等合法 Source；
5. CREATE、ASSIGN、STATUS_CHANGE、COMMENT/CLOSE 等实际发生的 History。

主 Action 规划：

| 字段 | 规划 |
| --- | --- |
| title | 调整主剧运营节奏（演示） |
| priority | HIGH |
| final status | COMPLETED |
| assignee | `user_demo` |
| completed anchor | 首个进入 COMPLETED 的 History，约 `T_demo - 8天` |
| source | 主剧 Anomaly 或合法 MANUAL Source |

Metric 数据应使该行动前后窗口存在可观察变化，但验收文案必须保持“行动后观察到变化”，不得表述为因果结论。

### 8.6 Explanation 与 Lineage

为主剧的 Score、Prediction 或 Anomaly 准备可查询的解释与血缘数据：

- summary；
- detail；
- module_type、entity_type、entity_id；
- algorithm_version、rule_set_version；
- analysis_as_of；
- 可追溯来源。

用于 Drama Profile Explanation Card 和血缘入口展示，不生成新的分析结果。

## 9. Drama Profile 数据覆盖

主展示对象固定为 `DEMO_DRAMA_001`。验收前确认下列 Provider 均有数据：

| Profile 模块 | 数据来源 | 预期 |
| --- | --- | --- |
| drama | Drama + relations | 名称和基础信息完整 |
| performance | Score | AVAILABLE |
| quality | Phase 2 Quality | AVAILABLE 或明确 PARTIAL |
| trend | Prediction | AVAILABLE |
| risk | Anomaly | 至少 1 条当前异常 |
| operations | Operation Action | OPEN/IN_PROGRESS/COMPLETED 可展示 |
| explanations | Explanation/Lineage | 最新摘要和入口可展示 |

另使用 `DEMO_DRAMA_005` 验证部分模块缺失不会使 Profile 整体失败。

## 10. Operation Analytics 数据覆盖

### 10.1 Action Effect

- 主 Action 有唯一、可追溯的首次 COMPLETED 时间；
- Before/After 各 7 个完整业务日；
- 两个窗口使用可比较的平台集合；
- 无无法解释的重叠 Action，或按既有 Availability 明确显示；
- 输出包含规则版本和非因果声明。

### 10.2 Lifecycle

- `DEMO_DRAMA_001`：GROWTH；
- `DEMO_DRAMA_002`：STABLE；
- `DEMO_DRAMA_003`：DECLINE；
- `DEMO_DRAMA_005`：历史不足；
- 如需展示 LAUNCH/ARCHIVED，应通过现有状态和发布时间规则新增合规 Demo Drama，不修改分类规则。

### 10.3 Benchmark

- Platform：`PLATFORM_DEMO_A`；
- Drama：`DEMO_DRAMA_001–004`；
- 成员数量：4，符合 2–20 限制；
- 窗口：最近 30 个完整自然日；
- 指标：播放增量、日均增量、互动率、异常频率和生命周期；
- 输出只展示统计比较与组中位数，不生成排名或推荐。

## 11. Data Governance 数据覆盖

### 11.1 主验收基线

主验收数据库保持结构一致且数据及时：

- 最新可见数据位于 Freshness 阈值内；
- 关键 Drama 字段和关系完整；
- 主剧有连续的 Metric 覆盖；
- Action Source、History 和用户引用有效；
- Explanation/Lineage 引用有效；
- Revision 链合法，无未来数据污染；
- 所有检查使用统一 `T_demo`。

### 11.2 预期展示

| 模块 | 主基线预期 | Evidence 示例 |
| --- | --- | --- |
| Freshness | HEALTHY / AVAILABLE | 最新时间、延迟秒数、阈值 |
| Completeness | HEALTHY 或按真实覆盖返回明确状态 | 字段覆盖、Metric覆盖、日期范围 |
| Consistency | HEALTHY / AVAILABLE | 关系检查、Revision检查、as-of检查 |

规则即使返回 HEALTHY 也应提供最小 Evidence。若实际数据产生 WARNING/PARTIAL，应保留真实结果并在验收记录中说明，不得修改前端或规则强制显示绿色状态。

### 11.3 可选负向副本

如需要演示 WARNING/INSUFFICIENT，应在独立的可恢复数据库副本中，通过合法缺失场景准备，例如：

- 新建无历史 Metric 的 DRAFT Drama；
- 保留非必要字段为空；
- 使用不足 7/30 日的合法时间序列。

不得破坏外键、构造错误 Revision 链或在主验收库中删除数据。

## 12. Reporting 数据覆盖

### 12.1 Catalog

Catalog 不依赖 Demo 行数，但验收应确认六类显式 Report 全部显示：

- DRAMA_CATALOG；
- SCORE_RESULTS；
- DATA_QUALITY_RESULTS；
- PREDICTION_RESULTS；
- ANOMALY_RECORDS；
- OPERATION_ACTIONS。

### 12.2 Preview

前述 Demo 数据应保证每类 Report 至少存在一条可通过允许 Filter 查询的 Row。建议演示：

- Drama Catalog：按 status 或 platform_id；
- Score Results：按 drama_id；
- Data Quality Results：按 rule_set_version；
- Prediction Results：按 drama_id；
- Anomaly Records：按 severity/status；
- Operation Actions：按 drama_id/status。

### 12.3 Export

至少执行：

1. 带 Filter 的小型 CSV 导出；
2. XLSX 导出；
3. 一次无 Filter 导出的服务器确认流程；
4. 下载文件名、MIME、Header、行列和中文内容检查；
5. CSV 公式安全检查使用专门的非生产演示文本，不导入真实公式。

Demo 行数应低于 CSV 10,000、XLSX 5,000 和 25 MiB 限制，避免将性能压力测试混入功能验收。

## 13. 数据准备顺序

建议顺序：

1. 初始化 V001–V013；
2. 创建 `admin_demo`、`user_demo`；
3. 创建 Platform、Tag、Actor、Director、Company；
4. 创建 Drama 及关系；
5. 创建 DramaPlatform；
6. 通过现有导入/受控流程准备 Snapshot 与 Revision；
7. 运行现有 Score、Data Quality、Prediction、Anomaly 流程；
8. 创建 Operation Action 并形成完整 History；
9. 准备 Explanation 与 Lineage；
10. 记录 `T_demo`；
11. 预检 Profile、Operation Analytics、Data Governance 和 Reports；
12. 生成数据库备份或可恢复验收基线。

## 14. 数据验证清单

- [ ] 两个账号均为 ACTIVE，角色正确；
- [ ] 不存在明文密码或真实个人信息；
- [ ] 5 部 Drama 及其关系符合约束；
- [ ] 4 部同平台 Drama 有完整 30 日数据；
- [ ] 主 Action 前后各 7 日完整；
- [ ] 主剧具备 Score、Quality、Prediction、Anomaly、Action、Explanation；
- [ ] `DEMO_DRAMA_005` 能展示明确不足状态；
- [ ] Revision 链及 `changed_at <= T_demo`；
- [ ] Governance 主基线不含破坏性一致性错误；
- [ ] 六类 Report 至少一类 Filter 可返回数据；
- [ ] CSV/XLSX 数据量低于 V1 硬限制；
- [ ] 所有演示时间均为 UTC 或可明确转换为 UTC。

## 15. 重置与保密

- 验收前从已验证备份恢复数据库，可确保演示重复性；
- 每轮演示不要在主流程中执行不可逆删除；
- 需要展示写操作时使用专门 Demo 记录并记录预期变化；
- 演示结束后停用账号、清理下载文件并妥善处置数据库副本；
- 截图中不得出现密码、Token、数据库连接串或真实敏感信息。
