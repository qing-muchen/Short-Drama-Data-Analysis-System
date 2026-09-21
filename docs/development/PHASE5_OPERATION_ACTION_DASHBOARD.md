# Phase 5 Operation Action Dashboard

## 页面目标

`/operation-actions` 将后端运营行动呈现为可追踪的处置工作台，展示行动状态、优先级、负责人、来源证据和处理历史。页面不复制任何状态机、来源去重或操作日志逻辑。

## API调用

- `GET /api/v1/operation-actions/statistics`：状态统计卡片与环形图。
- `GET /api/v1/operation-actions`：服务端筛选、分页的行动列表。
- `GET /api/v1/operation-actions/{action_id}`：详情、来源和历史。
- `POST /api/v1/operation-actions`：管理员创建行动。
- `PATCH /api/v1/operation-actions/{action_id}/status`：管理员请求状态变更。
- `PATCH /api/v1/operation-actions/{action_id}/assign`：管理员分派负责人。
- `POST /api/v1/operation-actions/{action_id}/comments`：登录用户添加处理记录。

统一复用现有 Axios 客户端和 JWT 拦截器，页面不拼接 Token，也不直接发起裸请求。

## 页面结构与权限

页面包含行动总数、OPEN、IN_PROGRESS、COMPLETED、CANCELLED 统计卡片；服务端过滤的列表；行动详情抽屉；来源证据；History 时间线；评论输入；管理员创建、状态更新和分派操作。普通用户仅显示查看和评论能力，后端仍负责最终授权。

## 可视化与状态处理

环形图只展示 `/statistics` 返回的状态数量，不在前端推导优先级或状态转换。页面覆盖 loading、空数据、错误和成功状态，并在卸载时移除 resize 监听、销毁 ECharts 实例。

## 验证结果

- `npm exec vue-tsc -- --noEmit`：通过。
- `npm run build`：通过。
- 构建输出包含既有 chunk size warning，为非阻塞提示，未修改构建配置。
