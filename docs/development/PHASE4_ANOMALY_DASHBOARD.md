# Phase 4 Anomaly Detection Dashboard

## 1. 页面目标

异常检测分析页面用于展示后端生成的结构化异常记录，帮助运营人员观察异常规模、严重等级、处理状态、历史变化和解释性证据。页面只负责展示与交互，不在前端计算异常、严重等级或业务状态。

页面路由为 `/anomalies`，驾驶舱提供“异常检测分析”入口。

## 2. API 调用

页面复用项目现有 Axios 实例及 JWT Bearer 认证机制：

- `GET /api/v1/anomalies`：按严重等级、状态、指标类型查询分页异常列表。
- `GET /api/v1/anomalies/statistics`：获取总异常数、A/B/C 分布和 OPEN 数量。
- `GET /api/v1/anomalies/{drama_id}`：API Client 提供单剧异常查询能力，供后续详情场景复用。
- `POST /api/v1/anomalies/detect`：API Client 提供管理员检测能力；当前页面不自动触发检测。
- `PATCH /api/v1/anomalies/{record_id}/status`：管理员更新异常状态。

后端当前没有独立趋势接口。页面不新增后端协议，而是读取异常列表，将 `analysis_as_of` 按日期分组形成展示用计数序列；这只是可视化转换，不参与异常判定。

## 3. 页面结构

页面包含：

1. 统计概览：总异常数、A/B/C 数量和 OPEN 数量，全部直接使用 statistics 响应。
2. 异常列表：展示短剧、指标、异常类型、等级、状态、分析时间和证据，筛选参数传给后端。
3. 异常趋势：ECharts 折线图展示列表数据覆盖范围内的每日异常数量。
4. 异常详情：抽屉展示证据、算法版本和分析时间，不自行解释证据。
5. 分页：支持 20、50、100 条每页，最大值符合 API 限制。

页面覆盖 loading、empty、error 和 success 状态；请求失败时保留可用模块并显示可理解错误。

## 4. 权限逻辑

- `USER` 与 `ADMINISTRATOR` 均可查看统计、列表、趋势和详情。
- 仅 `ADMINISTRATOR` 显示状态修改入口。
- 所有权限最终仍由后端校验，前端隐藏按钮只改善交互体验。

## 5. 可视化设计

趋势图由 ECharts 绘制。组件挂载时注册窗口 resize 监听，卸载时移除监听并 dispose 图表实例，避免重复初始化和页面卸载后的实例残留。

## 6. 验证结果

- `vue-tsc --noEmit`：通过。
- `npm run build`：通过，Vite 完成生产构建。
- 构建输出存在既有的 chunk size warning（部分公共 chunk 大于 500 kB），不阻塞构建，未为此修改配置。
- 未增加依赖，未修改 lock 文件或构建配置。
