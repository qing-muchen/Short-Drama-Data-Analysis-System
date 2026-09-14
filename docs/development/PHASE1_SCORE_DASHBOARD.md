# Phase 1 Score Dashboard

## 页面目标

短剧综合评分分析页用于展示后端Composite Score V1.0计算结果，帮助运营人员查看综合排行、等级结构和单剧四维表现。页面不是CRUD列表，不在浏览器中重新计算评分或判断等级。

## 数据来源

| 展示模块 | API |
|---|---|
| 综合评分Top 10 | `GET /api/v1/scores/ranking` |
| 等级分布 | `GET /api/v1/scores/level-distribution` |
| 单剧详情与雷达图 | `GET /api/v1/scores/{drama_id}` |
| 管理员重新计算 | `POST /api/v1/scores/calculate` |

页面查询固定使用第一页、每页10条，并显式传递评分日期。算法版本、作用域、各项分数和等级全部来自API。

## 组件设计

- 页面工具栏：选择评分日期、刷新数据；管理员额外显示重新计算按钮。
- 等级分布：使用S/A/B/C四张统计卡展示API返回数量。
- 排行表：展示排名、短剧名称、综合评分、等级、Heat、Growth和Engagement。
- 详情区：点击排行作品后加载其最近评分，展示综合评分、算法版本、分析时间和作用域。
- 状态反馈：排行为空使用空状态；列表、分布或详情请求失败时显示可重试错误提示。

## 图表设计

详情使用ECharts Radar展示Heat、Growth、Engagement和Lifecycle四个API评分维度，统一最大值为100。图表监听详情变化和窗口缩放，并在无详情或组件卸载时释放实例。

Lifecycle在页面中明确表述为规则化生命周期阶段评分，不描述为预测模型。

## 测试结果

2026-09-14完成验证：

- 从Git暂存区导出的隔离副本执行`npm run build`通过，`vue-tsc --noEmit`未发现类型错误，Vite成功转换2315个模块。
- ScoreAnalysis独立生成懒加载产物：JavaScript 9.83 kB（gzip 4.21 kB），CSS 3.27 kB（gzip 0.91 kB）。
- 构建产物确认包含排行、等级分布、详情和计算四个Score API调用。
- 页面加载时并行请求排行与等级分布，并自动加载首部短剧详情。
- 空排行显示`el-empty`；列表、分布和详情失败均具有错误提示或重试路径。
- Radar配置及Heat、Growth、Engagement、Lifecycle四个API数值已进入生产构建产物。
- 重新计算按钮使用`v-if="isAdmin"`，普通用户不渲染该按钮。

项目当前未配置前端组件测试框架，本阶段未增加测试依赖；上述交互分支通过严格类型检查、生产构建及构建产物检查验证。构建存在既有公共chunk超过500 kB的Vite警告，不影响本次构建成功。
