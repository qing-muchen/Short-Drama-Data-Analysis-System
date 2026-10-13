# Phase S5.2-B2 最小实现与测试规格候选

| 项目 | 值 |
|---|---|
| 文档版本 | 0.1 |
| 适用软件版本 | V1.0 maintenance baseline |
| Git 基线 | `0bd34f44d2f0e8065c22cdc423cf50d1373b8e9a` |
| 设计状态 | **STATUS: PROPOSED — USER APPROVAL REQUIRED** |

本计划不授权实现。DQ-01～04、EX-01～04 未获明确批准前，所有工作包停止。

## 1. 依赖顺序与工作包

| WP | 前置批准 | 预期修改范围/内容 | DB 影响 | 验证/完成标准 | 停止条件 |
|---|---|---|---|---|---|
| 1 规则契约与初始化 | DQ-01、DQ-04 | 受审配置、validator、dry-run/apply Seed、生产 registry 组成 | 无新表；插入规则属于受控数据写 | 全规则字段获批；check/apply 幂等；冲突中止；审计可追踪 | 任一规则字段 UNRESOLVED；目标库不明确 |
| 2 Evidence Repository + Evaluator | DQ-01、DQ-03 | 新 DQ evidence repository/DTO；按批准规则实现白名单 evaluator；依赖注入 registry | 只读业务表 | as-of/VOID/缺失/批量查询测试通过；evaluator 无 DB 副作用 | 来源/分母/窗口未批准；检测到不一致证据 |
| 3 Calculator 版本兼容 | DQ-02 | 保留 V1；新增 V2 rule_score Calculator；Service 分派、Schema/type 版本兼容 | 无 Migration | 区分向量得到 V1=82.00/A、V2=98.20/S；旧测试不被削弱 | 用户拒绝新版本标识或历史策略 |
| 4 DQ 闭环 | WP1-3 | Service、API、持久化、错误响应、前端状态/版本展示 | 写 DQ 三表 | 真实规则成功评分；无规则/不足/失败清晰；原子回滚 | 需要改阈值/算法才能通过 |
| 5 Pipeline + 结果身份 | EX-01、EX-02 | 新 application Workflow；拆出无 commit operation；Score/Prediction immutable write/current/history query | **新 Migration** 调整唯一键；备份/演练 | 单一 commit owner；重复同 identity 幂等；旧 PK 保留 | 无迁移批准/备份；同 as-of 重算语义未定 |
| 6 来源 Provider + 完整性 | EX-03、EX-04 | 三类 source provider、Handler payload/evidence、validator | 无表变更 | 每条 lineage 来源存在且窗口/版本/as-of 一致；空 evidence 被拒绝 | 找不到真实 revision IDs；需伪造来源 |
| 7 三条生成路径接入 | WP5-6 | Score/Prediction/Anomaly Workflow/Router composition；不反向注入 Service | 写结果+解释+血缘 | 成功全写、任一步失败全回滚；不足历史不写解释 | 部分提交、静默吞错、循环依赖 |
| 8 集成/浏览器/报告 | WP1-7 | 自动化、真实 API、两分辨率浏览器、报告 | 测试库优先 | 全量回归、真实证据、用户清单；不宣布人工验收 | P0/P1 未闭环或证据不足 |

## 2. 兼容性矩阵

| 模块 | API/Schema | 数据/历史 | 前端/测试 | 风险 |
|---|---|---|---|---|
| Composite Score | 当前计算公式不变；生成入口可能由 Workflow 包装 | 推荐新增不可变 as-of 版本；旧行保留 | latest 响应可兼容；history 需明确版本 | **BREAKING CHANGE — APPROVAL REQUIRED**（唯一键/历史） |
| Data Quality | 版本 Literal 扩展到 V1/V2；错误码保持 | 现有三表可用；规则显式 Seed | 页面需显示算法/规则集版本 | 计算结果会改变，需 DQ-02 |
| Prediction | Moving Average V1.0 不变；生成入口包装 | 推荐不可变版本；旧行保留 | latest 可兼容，history 可能出现同 target 多版本 | **BREAKING CHANGE — APPROVAL REQUIRED** |
| Anomaly | 算法/枚举不变 | 结果 identity 幂等策略需补强 | detail 增加真实 evidence | 重复请求冲突策略需批准 |
| Explanation/Lineage | 查询 API 原则不变；生成仅内部 | 新记录，旧空库不回填；弱引用校验 | Drawer 可渐进展示 detail | 不允许部分 evidence |
| Drama 360 | 仍取 latest | 多版本查询必须稳定选最新 as-of | 现有类型多为 string，兼容 | 错选旧版本 |
| Operation Analytics | 不改算法 | 若引用结果 PK，必须指向不可变版本 | 回归来源展示 | 历史引用迁移不得静默发生 |
| Data Governance | Evidence 与 DQ 严格分层 | lineage consistency 可检查缺失目标/源 | 版本文字兼容 | 不应把 governance 规则当 DQ 生产规则 |
| Reporting/Export | 增加/保留 algorithm/as-of 过滤 | 多版本导出需防重复语义 | schema/行数回归 | 默认 current 与 history 需明确 |

## 3. Data Quality 测试规格

| ID | 输入 | 预期 | 失败判定 |
|---|---|---|---|
| DQT-01 | 完整批准配置，空规则库 | Seed 一次插入全规则；二次 exact no-op；hash 一致 | 重复行或静默更新 |
| DQT-02 | 同 rule_code/version 但字段不同 | apply 中止、0 变更、明确 conflict | 覆盖历史 |
| DQT-03 | 每类真实 Evidence + 固定 as-of | DTO 含表/PK/revision/time；稳定排序 | evaluator 查询 DB 或丢来源 |
| DQT-04 | 截点前 correction，截点后 correction | 只选截点前最新 | 使用未来修订 |
| DQT-05 | 截点下最新为 VOID | 不回退；按规则计 FAIL/0 | 使用旧有效 revision |
| DQT-06 | 必需字段缺失 | APPLIED FAIL/0，不是 N/A | N/A 绕过扣分 |
| DQT-07 | 业务域确实不适用 | 0/0/0、score NULL、非空 reason，权重排除 | 进入分母 |
| DQT-08 | 未注册 evaluator/非法配置 | 稳定业务错误；0 持久化 | HTTP 500 泄漏或部分写 |
| DQT-09 | 区分向量 | V1=82.00/A；V2=98.20/S | 两口径给同结果或浮点偏差 |
| DQT-10 | 某维度全部 N/A | `INSUFFICIENT_QUALITY_DATA`；不持久化 | 生成误导总分 |
| DQT-11 | ERROR/WARNING FAIL | 严格按批准的 severity 契约 | severity 偷乘权重/未批准阻断 |
| DQT-12 | 规则/结果/日志中途失败 | 单事务全部 rollback | 任一残留 |
| DQT-13 | 相同计算并发/重复 | 一个 identity，内容一致幂等或受控冲突 | 重复评分/死锁未映射 |
| DQT-14 | admin/user/anonymous | 遵循现有 200/401/403 契约 | 仅前端隐藏权限 |
| DQT-15 | V1/V2 历史并存 | 可按版本查询；默认返回批准的 current | 同名混淆/旧结果不可查 |

## 4. Explanation / Lineage 测试规格

| ID | 输入 | 预期 | 失败判定 |
|---|---|---|---|
| EXT-01 | 三类完整 payload + 实际 revisions | 三 Handler 确定性、非空 evidence、来源集合精确 | 自指/空 evidence |
| EXT-02 | 不存在/错 drama/未来/VOID 来源 | `LINEAGE_SOURCE_*`；整次 rollback | 写入弱引用 |
| EXT-03 | source 与 target algorithm/as-of 不匹配 | 拒绝 | 仅校验正整数 |
| EXT-04 | 核心和解释均成功 | 同一 Session 一次 commit，全记录存在 | 多次 commit |
| EXT-05 | Handler/validator/lineage/log 任一步失败 | 核心结果也不存在 | 部分成功 |
| EXT-06 | Prediction 历史不足 | 原业务响应；无结果/解释/lineage | 伪造空解释 |
| EXT-07 | 完全相同重复命令 | 返回同 result/explanation identity | 新增重复行 |
| EXT-08 | 同 identity 不同内容 | Conflict，原记录不变 | 覆盖历史 |
| EXT-09 | 不同 as-of 重算 | 新不可变结果+新解释；旧链仍可查 | delete 旧目标 |
| EXT-10 | 同 as-of 纠错重算 | 按获批策略冲突或新 revision | 隐式覆盖 |
| EXT-11 | 并发相同 identity | 唯一约束转换为幂等/稳定冲突 | 原始 DB 异常外泄 |
| EXT-12 | latest/history/空结果 | 排序、过滤、分页准确；空列表不 500 | 历史丢失/错 latest |
| EXT-13 | admin/user/anonymous | 遵循既有读写权限 | 未授权生成 |
| EXT-14 | Migration 前后已有结果 | PK/数量保留、current 结果一致 | 数据丢失或重排 |

## 5. 验收闸门

- 每项测试必须记录数据库前后计数、请求/响应和失败分类；不得只以单元测试替代真实集成验证。
- 新 Migration 必须完整备份、隔离演练、结构/数据比对后才可进入开发库。
- Backend 全量 pytest、compileall、vue-tsc、production build 和真实浏览器均通过，才能报告“自动化/Agent 浏览器预验收通过”；用户人工验收仍独立。
- 任一未批准语义、破坏性 DDL、来源不可验证、历史结果会被删除或需伪造数据时立即停止。

最后审查结论：**计划可执行，但所有 WP 仍受审批闸门约束；本阶段未开始 B2。**
