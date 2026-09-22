# Phase 7 Drama Profile API

## 1. API 定位

Drama Profile API 是只读聚合接口，将 `DramaProfileService` 输出的全景画像暴露给登录用户。它不创建实体、不更新状态、不触发分析任务。

## 2. Endpoint

```text
GET /api/v1/dramas/{drama_id}/profile
```

返回统一 `ResponseModel[DramaProfileResponseSchema]`。接口只接受 `drama_id` 路径参数，不提供 POST、PUT 或 PATCH。

## 3. Schema 结构

API Schema 与 Service DTO 分离，包含：

- Drama 基础信息；
- availability；
- performance；
- quality；
- trend；
- risk；
- operations；
- explanations。

`ModuleAvailabilitySchema` 使用固定 `AvailabilityReasonSchema`，禁止任意状态字符串。Schema 不绑定 ORM Model。

## 4. Dependency 组装

`get_drama_profile_service` 在同一个请求 Session 中组装六个 Profile Provider 和一个 Drama 基础信息适配器。Router 只依赖 `DramaProfileServiceDependency`，不访问 Repository、ORM 或 Provider。

Drama 基础信息适配器通过现有 `DramaRepository` 读取短剧是否存在；不存在时由统一异常体系返回 404。

## 5. 权限设计

沿用 JWT `AuthenticatedUserDependency`：USER 和 ADMINISTRATOR 均可查看，匿名请求返回 401。不需要管理员权限，因为该接口仅展示已有分析结果。

## 6. 错误处理

- `drama_id` 非法：FastAPI 参数校验返回 422；
- Drama 不存在：统一 404；
- Provider 异常：由 `DramaProfileService` 隔离为对应模块 `NOT_AVAILABLE`；
- 成功响应：统一 `{ "data": ..., "message": "success" }`。

## 7. 测试结果

测试覆盖：

- 路径注册；
- 仅注册 GET 方法；
- Service DTO 到 Response Schema 转换；
- Availability 原因保留；
- Dependency Override；
- 不新增写接口。

本阶段不修改数据库、Migration、ORM、Score、Prediction、Anomaly、Action 或 Explanation 模块。
