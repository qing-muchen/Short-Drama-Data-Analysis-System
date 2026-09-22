# Phase 7 Drama Profile Frontend

## 1. 页面定位

Drama Profile 前端提供以单部短剧为中心的 360° 只读分析视图，不产生新的分析结果。

## 2. API Client

`frontend/src/api/dramaProfile.ts` 复用现有 Axios Client，调用：

```text
GET /api/v1/dramas/{drama_id}/profile
```

不新增认证逻辑，不直接拼接 Token，不计算业务指标。

## 3. TypeScript 类型

`frontend/src/types/dramaProfile.ts` 与后端 Response Schema 对齐，包含 Drama 基础信息、六个模块摘要、Availability 协议和固定缺失原因。

## 4. 页面结构

页面路径：`/dramas/:id/profile`。

页面包含：

- Drama Header；
- Performance Card；
- Quality Card；
- Trend Card；
- Risk Card；
- Operations Card；
- Explanation Card。

各卡片只读取 Profile API 返回结果，并提供到已有详情页面的导航入口。

## 5. Availability 处理

页面通过 `available` 和后端返回的 `reason` 展示状态，不通过 null 推断业务含义。支持：

- `NOT_CALCULATED`；
- `INSUFFICIENT_HISTORY`；
- `NO_ANOMALY`；
- `NOT_DETECTED`；
- `NOT_AVAILABLE`。

单个模块缺失不会导致整个 Profile 页面失败。

## 6. 路由与 Dashboard 入口

新增受保护路由 `/dramas/:id/profile`，并在 Dashboard 顶部增加 Drama 360° 入口。入口仅负责导航，不自动触发额外分析请求。

## 7. 验证结果

计划执行：

- `npm exec vue-tsc -- --noEmit`；
- `npm run build`；
- `git diff --cached --check`。

本阶段不修改 Backend、Database、Migration、ORM 或 API Contract。
