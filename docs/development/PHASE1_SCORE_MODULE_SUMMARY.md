# Phase 1 综合评分模块总结

## 1. 模块目标

Phase 1新增短剧综合评分模块，用于把分散的运营指标加工为统一、可比较、可追溯的综合评价结果，为运营人员提供排行观察、作品诊断和决策参考。

本系统的定位不是短剧信息CRUD，而是面向短剧运营场景的数据治理与智能分析平台。综合评分模块补齐了以下核心价值链路：

```text
运营数据
  ↓
指标计算
  ↓
综合评价
  ↓
决策支持
```

评分结果用于表达作品在指定评分日期的相对运营表现，不代替人工业务判断，也不对未来表现作预测承诺。

## 2. 完整数据流程

```text
drama_metric_snapshots
  ↓
AnalyticsService
  ↓
Composite Score V1.0
  ↓
drama_scores
  ↓
Score API
  ↓
Score Dashboard
```

1. `drama_metric_snapshots`及其revision保存各平台运营指标的历史状态。
2. `AnalyticsService`按评分上下文提取并汇总有效指标，评分模块不重复查询快照或复制既有Analytics逻辑。
3. `Composite Score V1.0`纯计算模块完成标准化、分项评分、加权汇总和等级输出，不产生数据库副作用。
4. `ScoreService`执行资格检查、调用计算核心、构造评分结果，并在同一事务中批量替换`drama_scores`和写入一次操作日志。
5. `Score API`向认证用户提供排行、等级分布和单剧详情，管理员可以触发指定日期的批量计算。
6. `Score Dashboard`展示Top 10、S/A/B/C分布和四维雷达图，不在前端重新计算评分或判断等级。

Phase 1评分上下文固定为算法版本`Composite Score V1.0`、作用域`ALL / 0`。`analysis_as_of`记录实际分析截止时间，使历史日期评分具备明确的数据时间边界。

## 3. 架构设计

### 3.1 数据库层

评分结果独立保存在`drama_scores`，不写回`dramas`或运营快照表，原因如下：

- 保留按评分日期形成的历史评价结果，避免覆盖运营原始事实。
- 通过`algorithm_version`支持未来算法升级、结果复核和版本对比。
- 通过评分作用域字段为后续平台、标签等范围评价预留扩展边界；Phase 1数据库约束固定为`ALL / 0`。
- 将高成本计算与高频查询解耦，排行和Dashboard直接读取已持久化结果。
- 使用业务唯一约束避免同一短剧、日期、算法版本和作用域出现重复评分。

### 3.2 计算层

Composite Score V1.0采用可解释的规则模型。各分项均有明确业务来源、标准化方式和权重，便于课程验收、运营解释、边界测试和后续版本迭代。计算核心保持纯函数特征，不访问数据库、不提交事务。

### 3.3 Service层

`ScoreService`负责业务编排，而不是承担指标算法：

- 创建评分日期、分析截止时间、算法版本和作用域上下文。
- 调用`AnalyticsService`取得运营指标并执行评分资格检查。
- 调用Composite Score纯计算模块并构造`DramaScore`对象。
- 调用`ScoreRepository`批量替换同一评分集合。
- 在Service事务内写入一次`SCORE_CALCULATE`操作日志；任一步骤失败时整体回滚。

这种职责划分保证Analytics、Calculator、Repository和审计日志各自边界清晰。

### 3.4 API层与展示层

FastAPI后端负责参数校验、JWT鉴权、管理员权限、业务调用和统一响应；Vue前端负责交互与可视化。评分算法、等级规则、作用域和算法版本均由后端控制，客户端不能传入或改写这些业务规则。

前后端分离使评分计算与展示独立演进，并确保Web页面、未来报表或其他客户端读取同一份权威评分结果。

## 4. 核心算法

Composite Score V1.0的综合评分公式为：

```text
Total Score = 0.4 × Heat
            + 0.3 × Growth
            + 0.2 × Engagement
            + 0.1 × Lifecycle
```

- Heat：由播放、点赞、评论、收藏、分享等运营量级指标标准化得到。
- Growth：根据当前与历史指标的增长表现计算；缺少必要历史时不生成评分。
- Engagement：根据互动行为与播放量关系计算；播放量为零时不生成评分。
- Lifecycle：固定运营阶段评分，依据发布日期与评分分析时间之间的天数赋值，不代表预测模型。

Lifecycle Stage Score规则：

| 上线天数 | 分数 |
|---|---:|
| 0—7天 | 100 |
| 8—30天 | 80 |
| 31—90天 | 60 |
| 91—180天 | 40 |
| 大于180天 | 20 |

综合评分范围为0—100，并使用`ROUND_HALF_UP`保留两位小数。等级由后端计算结果直接确定：

| 等级 | 分数范围 |
|---|---|
| S | `>= 90` |
| A | `>= 75`且`< 90` |
| B | `>= 60`且`< 75` |
| C | `< 60` |

## 5. 测试结果

2026-09-15完成Phase 1归档复核：

- Backend：完整测试套件`157 passed`，耗时6.48秒。
- Frontend：`npm run build`通过。
- TypeScript：构建前置的`vue-tsc --noEmit`类型检查通过。
- Vite：成功转换2326个模块并生成生产构建产物。
- 构建存在既有公共chunk超过500 kB的非阻塞警告，不影响构建成功。

评分专项测试已经覆盖纯计算公式与边界、生命周期阶段、异常数据、Repository替换与排行、Service事务与回滚、API鉴权与统一响应，以及Dashboard空数据、失败状态和雷达图生产构建验证。

## 6. Git版本记录

| Commit | Message | 归档内容 |
|---|---|---|
| `80b389b` | `feat(phase1): complete composite score engine workflow` | Migration、ORM、计算核心、Repository、Service及后端测试 |
| `e511be2` | `feat(phase1): add score api layer` | Schema、Router、鉴权依赖、API测试及API文档 |
| `be4f1c1` | `feat(phase1): add score dashboard visualization` | 前端类型、API封装、路由、综合评分页面及Dashboard文档 |

以上三个功能提交共同构成Phase 1综合评分模块的数据库、计算、业务编排、接口和展示闭环。
