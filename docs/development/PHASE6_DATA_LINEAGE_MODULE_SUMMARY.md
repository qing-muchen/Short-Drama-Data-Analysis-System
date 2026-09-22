# Phase 6 Data Lineage & Explanation Module Summary

## 1. Module Positioning

Phase 6 是“分析结果解释层”和“数据血缘追踪层”。它面向已经产生的 Score、Quality、Prediction、Anomaly 及后续行动结果，提供可追溯、可阅读的解释信息。

Phase 6 不是新的分析模型、评分系统或预测系统。Explanation 只解释已有结果，不产生新的分析事实，也不重新计算业务指标。

## 2. Architecture Overview

系统链路如下：

```text
Score / Quality / Prediction / Anomaly
                ↓
       Explanation Layer
                ↓
             Storage
                ↓
              Query
                ↓
          Frontend Viewer
```

解释模块遵循单向依赖：业务分析结果由 Explanation 层读取并解释，Explanation 层不反向调用 ScoreService、PredictionService、AnomalyService 或其他业务 Service。

## 3. Database Design

V013 新增三张表：

- `analysis_explanations`：保存面向用户的解释快照；
- `analysis_lineage_records`：保存解释结果与来源之间的关系；
- `metric_dependencies`：保存静态指标依赖图。

三表使用实体类型和业务记录 ID 的弱关联方式，不建立 Explanation 到 Score、Quality、Prediction、Anomaly 或 Operation Action 的跨模块业务外键，避免循环依赖和迁移耦合。

解释记录保留 `algorithm_version`、`rule_set_version` 与 `analysis_as_of`，用于历史版本追踪和结果复现。解释内容是结构化 detail JSON，而不是完整业务结果快照。

## 4. Explanation Generation Architecture

生成链路为：

```text
ExplanationContext
        ↓
ExplanationHandlerRegistry
        ↓
ExplanationGenerator
        ↓
GeneratedExplanation
        ↓
ExplanationValidator
        ↓
Repository
```

Contracts 定义纯 Python 数据契约，Registry 负责显式映射解释类型与 Generator，Validator 负责 detail 结构、禁止字段和实体映射校验，Service 负责编排、幂等判断及持久化。

## 5. Handlers

### MetricExplanationGenerator

用于 Score 结果解释。根据调用方提供的维度贡献和版本信息生成确定性摘要、原因、规则、版本和证据结构，不执行评分公式，也不重新判断等级。

### TrendExplanationGenerator

用于 Prediction 结果解释。说明历史窗口和趋势模型的使用方式，不重新执行移动平均，也不保存完整预测业务对象。

### AnomalyExplanationGenerator

用于异常结果解释。根据调用方提供的异常类型、阈值摘要和证据生成固定模板，不重新计算 Z-score，也不修改异常等级。

三个 Handler 均不访问数据库、不访问 ORM、不调用业务 Service、不接入 LLM；相同输入始终产生相同输出。

## 6. Persistence Layer

Write Repository 负责创建 Explanation 和 Lineage 记录；Query Repository 负责按实体、版本、时间和目标查询历史解释及血缘关系。

Repository 只进行 ORM 查询和 `flush`，不创建 Session、不提交或回滚事务。Explanation 与对应 Lineage 必须在同一 Service 事务中写入，避免出现只有解释没有来源的部分结果。

## 7. API

Phase 6 提供只读查询接口：

```text
GET /api/v1/explanations/{entity_type}/{entity_id}
GET /api/v1/lineage/{target_type}/{target_id}
```

接口支持模块、时间、算法版本、规则集版本及来源条件过滤，并返回统一分页响应。登录用户可以查询，匿名请求由 JWT 鉴权拒绝；查询 API 不修改解释数据。

## 8. Frontend

前端新增 `ExplanationDrawer`，接入：

- `ScoreAnalysis`；
- `PredictionAnalysis`；
- `AnomalyAnalysis`。

查看器展示摘要、原因、规则、证据、版本和数据血缘，并处理 loading、empty、error、success 状态。前端只展示 API 返回结果，不重新计算解释、评分、预测或异常。

## 9. Testing

Backend 测试覆盖：

- V013 ORM 与结构；
- Contracts 和 Registry；
- Metric、Trend、Anomaly Handler；
- Validator；
- Write/Query Repository；
- Generation Service；
- Query API、权限和分页。

Frontend 验证结果：

- `vue-tsc --noEmit` 通过；
- `npm run build` 通过；
- 构建中存在既有的大 chunk size 非阻塞警告。

## 10. Git History

Phase 6 相关提交包括：

| Commit | 内容 |
| --- | --- |
| `01391d1` | add explanation database schema |
| `1b2c471` | add explanation contracts and registry |
| `cee230d` | add explanation handlers |
| `0ae2c4e` | add explanation repositories |
| `21b8cc7` | add explanation service |
| `50f1c9a` | add explanation validator |
| `51189fc` | add explanation query repositories |
| `d211cde` | add explanation query API |
| `325db21` | add explanation viewer frontend |

## 11. Current Limitations

- 当前不自动生成解释，须由明确的调用流程触发；
- 不接入 LLM 或其他生成式模型；
- 尚未自动挂接所有分析模块的解释生成流程；
- Quality Explanation 和 Operation Action Explanation Handler 尚未实现；
- 当前血缘采用弱关联，不提供跨模块数据库外键完整性。

## 12. Future Extensions

后续可扩展：

- Quality Explanation；
- Operation Action Explanation；
- Model Registry 与统一版本治理；
- 自动化 Explanation Pipeline；
- 更完整的指标依赖可视化和历史血缘分析。
