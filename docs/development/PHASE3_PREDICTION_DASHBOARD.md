# Phase 3 Prediction Dashboard

## 1. 页面目标

`/predictions` 页面用于展示短剧运营趋势预测结果，帮助运营人员查看单剧下一日累计播放量预测和历史预测走势。

页面定位是运营趋势辅助分析，不涉及收益、投资或成功概率判断。

## 2. 页面结构

- 短剧 ID 查询区域：输入短剧 ID 后加载预测数据。
- 当前预测卡片：展示目标日期、预测累计播放量、算法版本、指标和数据截止时间。
- 预测结果说明：说明 `PLAY_COUNT`、`Moving Average V1.0` 及运营分析用途。
- 历史预测趋势图：使用 ECharts 折线图展示 `target_date` 与 `predicted_value`。
- Dashboard 入口：驾驶舱提供“播放趋势预测”入口，但不会自动触发计算。

## 3. API调用关系

| 前端操作 | API |
|---|---|
| 查询最近预测 | `GET /api/v1/predictions/{drama_id}` |
| 查询历史预测 | `GET /api/v1/predictions/{drama_id}/history?limit=100` |
| 管理员重新预测 | `POST /api/v1/predictions/calculate` |

API Client 只转换统一 `ResponseModel` 数据，不在前端复制移动平均公式、计算增量或判断算法版本。

## 4. 数据展示原则

前端只展示 API 返回字段：

- `predicted_value`
- `target_date`
- `algorithm_version`
- `analysis_as_of`
- `metric_type`

不展示或计算 `daily_increment`、`input_window`、`confidence` 和 revision 细节。页面明确标注预测结果仅供运营分析参考。

## 5. 权限控制

- 已登录用户可以查询预测结果。
- 管理员显示“重新预测”按钮并调用计算 API。
- 普通用户隐藏计算按钮。
- 后端 API 仍执行最终管理员权限校验。

## 6. ECharts设计

历史预测折线图：

- X 轴：`target_date`
- Y 轴：`predicted_value`
- 数据：`PredictionHistoryResponse.items`

组件挂载后初始化 ECharts，数据变化后更新配置，窗口变化调用 `resize()`，组件卸载时调用 `dispose()`，避免重复初始化或残留实例。

## 7. 状态处理

- `loading`：查询和刷新期间显示 Element Plus loading。
- `error`：请求失败显示可重试错误提示。
- `empty`：没有短剧 ID、没有预测结果或历史为空时显示明确空状态。
- `success`：展示当前预测卡片和历史趋势图。

## 8. 验证结果

本阶段使用项目现有前端脚本验证：

```bash
vue-tsc --noEmit
npm run build
```

验证结果：

- `vue-tsc --noEmit`：通过。
- `npm run build`：通过，Vite 成功转换 2334 个模块并生成生产构建产物。
- Vite 报告已有的 chunk size warning（部分压缩后 chunk 超过 500 kB），属于非阻塞提示，本阶段未修改构建配置。

验证重点包括 TypeScript 类型、路由懒加载、ECharts 编译和 API Client 类型匹配。
