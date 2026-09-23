# Phase 8 Operation Analytics Dashboard

## 1. 页面定位

Operation Analytics Dashboard 是 Phase 8 只读展示层，路径为 `/operation-analytics`。页面展示后端已经生成的行动前后指标变化、生命周期判断和 Benchmark 统计比较，不重新执行分析规则，不生成因果结论、排名或运营建议。

## 2. API Client

`frontend/src/api/operationAnalytics.ts` 复用现有 Axios Client、Base URL、Token 拦截器和统一错误处理，封装：

- `getOperationEffectiveness()` → `GET /api/v1/operations/effectiveness`；
- `getDramaLifecycle()` → `GET /api/v1/dramas/{drama_id}/lifecycle`；
- `getDramaBenchmark()` → `GET /api/v1/dramas/benchmark`。

Benchmark 的 `drama_ids` 使用重复查询参数传递，不创建新的认证逻辑或 Axios 实例。

## 3. TypeScript 类型

`frontend/src/types/operationAnalytics.ts` 与 Phase 8.5 HTTP Schema 对齐，包含：

- `AnalysisAvailability`、`AvailabilityStatus`、`AvailabilityReason`；
- `AnalysisWindow`、`MetricChange`；
- `OperationEffectivenessResult` 和分页结构；
- `LifecycleResult`、`LifecycleEvidence`、`LifecycleStage`；
- `BenchmarkResult`、比较范围、成员和指标结构；
- 三类 API 查询参数。

类型中不存在 `success`、`causal_result`、`rank`、`winner` 或 `recommendation`。

## 4. 页面结构

页面由三个相互隔离的区域组成：

1. Operation Effectiveness：支持 Action ID、Drama ID 查询和分页，展示 Before/After 窗口、后端指标变化、变化方向与非因果免责声明；
2. Lifecycle：按 Drama ID 查询，展示生命周期阶段、规则版本、评估时间和后端证据；
3. Benchmark：输入 Platform ID 和 2-20 个 Drama ID，展示 30 日窗口、成员指标、组中位数、规则版本和分析时间。

Dashboard 增加导航入口，路由使用现有 `requiresAuth` 守卫，USER 与 ADMINISTRATOR 均可访问。

## 5. Availability 处理

页面严格展示后端状态：

- `AVAILABLE`：数据可用；
- `PARTIAL`：部分数据缺失；
- `INSUFFICIENT`：历史数据不足；
- `NOT_AVAILABLE`：暂不可用。

`reasons` 仅映射为用户可读文案。页面不使用 `null` 推断 Availability，也不把数据不足显示为零。

三个区域分别维护 loading、empty、error 和 success 状态。一个接口失败不会清空或阻断其他模块。

## 6. 可视化设计

V1 使用状态标签、摘要卡、可展开指标表格和比较表格展示 API 原始结果。没有引入新的 ECharts 实例，避免为了图形展示而在前端聚合、排序或推导指标。

行动效果表直接显示后端给出的 `before_value`、`after_value`、`absolute_change` 和 `direction`；Benchmark 直接显示各成员返回的统计值与组中位数。页面不生成 Top 列表或最佳 Drama 结论。

## 7. 验证结果

执行：

```text
npm exec vue-tsc -- --noEmit
npm run build
```

结果：

- TypeScript 检查通过；
- Vite 生产构建通过；
- Operation Analytics 页面独立生成异步 chunk；
- 未新增依赖，未修改 lockfile；
- 构建存在既有大 chunk warning，为非阻塞提示，未修改 Vite 配置。
