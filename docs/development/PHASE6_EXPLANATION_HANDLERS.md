# Phase 6.1 Explanation Handlers

## 1. 目标

本阶段实现三个确定性的规则驱动 Explanation Handler：Metric、Trend 和 Anomaly。Handler 只接收调用方已经确定的业务输入，生成用户可读摘要、受控 detail 和 Lineage 来源描述。

本阶段不接入 LLM，不访问数据库，也不修改既有分析模块。

## 2. Handler列表

### `MetricExplanationGenerator`

解释 SCORE 类型结果，使用调用方提供的正向贡献维度和较弱维度生成固定模板：

> 综合评分主要由{positive_dimension}贡献，{weak_dimension}相对较弱。

Handler 不执行评分公式，不重新判断 S/A/B/C，也不保存 `score_value`。

### `TrendExplanationGenerator`

解释 PREDICTION 类型结果，记录趋势方向、窗口长度和模型描述。它不执行 Moving Average，不保存 `prediction_value`，并通过 `PREDICTION_INPUT / USES_WINDOW` 描述输入来源。

### `AnomalyExplanationGenerator`

解释已有异常记录，根据四类异常类型使用固定模板，保留阈值摘要和证据说明。它不计算 Z-score，不修改 severity，也不保存完整异常对象。

## 3. 共同边界

所有 Handler：

- 实现 `ExplanationGenerator` Protocol；
- 只访问 `ExplanationContext.payload`；
- 不导入 SQLAlchemy、Session、Repository 或已有业务 Service；
- 不使用当前时间、随机内容、网络请求或模型调用；
- 对相同输入产生相同输出。

Registry 由后续 Service 显式注册 Handler，当前不使用自动扫描。

## 4. 输出结构

输出统一包含：

- `summary`
- `detail.reason`
- `detail.inputs`
- `detail.rules`
- `detail.versions`
- `detail.evidence`
- `lineage_sources`

`detail` 不复制 Score、Prediction 或 Anomaly 的完整业务结果。

## 5. 测试结果

覆盖：

- 三类 Handler 正常生成；
- detail 结构与禁止字段；
- Lineage 来源类型和关系；
- 相同输入输出一致；
- Handler 不依赖数据库对象。
