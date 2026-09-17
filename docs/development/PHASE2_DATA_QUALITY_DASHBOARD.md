# Phase 2 Data Quality Dashboard

## 1. 页面目标

Data Quality Dashboard将Phase 2后端生成的全局数据质量评价结果转换为可视化治理视图，帮助运营人员查看当前质量水平、四维得分、历史变化和当前已发布规则。

页面路径：

```text
/data-quality
```

页面只展示Data Quality API返回的持久化结果，不在浏览器中重新计算维度分、综合分或S/A/B/C等级。

## 2. 数据来源

| 页面模块 | API | 用途 |
|---|---|---|
| 当前质量评分 | `GET /api/v1/data-quality/score` | 综合分、等级、规则集版本和分析时间 |
| 四维雷达图 | `GET /api/v1/data-quality/score` | Completeness、Accuracy、Consistency、Timeliness |
| 历史趋势 | `GET /api/v1/data-quality/history` | 按评分日期展示综合质量分变化 |
| 当前规则列表 | `GET /api/v1/data-quality/rules` | 规则编码、维度、权重和状态 |
| 重新计算 | `POST /api/v1/data-quality/calculate` | 管理员触发指定日期质量评分 |

所有请求复用现有Axios实例，由请求拦截器自动携带JWT Bearer Token。API Client统一解包`ResponseModel<T>`的`data`字段。

## 3. TypeScript设计

`frontend/src/types/dataQuality.ts`与后端Schema一一对应，包含：

- `DataQualityScore`
- `DataQualityHistory`与`DataQualityHistoryItem`
- `DataQualityRuleList`与`DataQualityRule`
- `DataQualityCalculationResult`
- 质量等级、维度、规则状态、规则评分方式等联合类型

Phase 2 V1通过字面量类型固定：

```text
score_scope_type = ALL
score_scope_id = 0
algorithm_version = Quality Score V1.0
rule_set_version = DQ Rules 1.0
```

## 4. 页面组件设计

页面由四个分析区域组成：

1. 当前质量评分卡：展示综合质量分、等级、规则集版本、评分日期、分析时间及算法版本。
2. 四维质量雷达图：展示完整性、准确性、一致性和及时性评分。
3. 历史趋势图：展示最近最多90个评分日的综合质量分折线。
4. 当前规则列表：展示规则编码、质量维度、权重和状态。

顶部工具栏提供刷新操作；管理员额外显示评分日期选择器和“重新计算质量评分”按钮，普通用户不显示计算按钮。

Dashboard首页新增“数据质量治理”入口，所有已登录用户均可进入分析页面。

## 5. 图表生命周期

雷达图和趋势图均使用ECharts：

- 数据变化后通过`nextTick`创建或更新图表。
- 空数据时主动`dispose`旧实例，避免展示过期结果。
- 监听窗口`resize`并调用两个实例的`resize()`。
- 页面卸载时移除事件监听并`dispose`全部实例。

图表输入直接使用API评分字段，不进行前端标准化、加权或等级判断。

## 6. 稳定性处理

- 当前评分404按“暂无评分”空状态处理。
- 历史和规则为空时分别显示独立空状态。
- 三类读取请求使用`Promise.allSettled`并行执行；部分失败时保留其他成功模块。
- 读取和计算分别维护`loading`状态，避免重复请求。
- 请求失败通过项目统一`getApiErrorMessage()`生成用户提示，并提供重新加载入口。
- 重新计算成功后重新读取全部分析数据，保证页面展示服务端最终结果。

## 7. 权限设计

- 页面路由使用现有`requiresAuth`守卫。
- USER和ADMINISTRATOR都能查看评分、趋势和规则。
- 仅当当前用户角色为`ADMINISTRATOR`时渲染重新计算按钮。
- 后端仍执行最终权限校验，前端按钮隐藏不替代API鉴权。

## 8. 验证结果

- 路由：`/data-quality`已注册并受现有JWT路由守卫保护。
- TypeScript：`npm exec vue-tsc -- --noEmit`通过。
- 生产构建：`npm run build`通过，Vite完成2330个模块转换并生成`DataQualityAnalysis`异步资源。
- 非阻塞提示：Vite报告部分公共chunk压缩后超过500 kB；本阶段没有修改既有打包策略或依赖拆分配置。

## 9. 设计取舍

- 未修改后端、数据库或API协议。
- 未把Data Quality接口混入原有Dashboard API，保持领域API边界清晰。
- 当前评分、规则和趋势允许独立失败，避免单个接口异常导致整个治理页面不可用。
- `/rules`展示后端返回的当前已发布规则集，不提供规则在线编辑能力。
