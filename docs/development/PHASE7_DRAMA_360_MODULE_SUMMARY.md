# Phase 7 Drama 360° 全景画像中心模块总结

## 1. 模块定位

Drama 360° 全景画像中心是面向短剧实体的 Read Model / Aggregation Layer。它以已有分析结果为数据来源，提供统一的短剧状态视图和模块导航。

本模块不是新分析模型、新评分体系、新预测模型、新异常检测模型或新运营规则系统。Drama Profile 不产生新的业务事实，不复制已有结果，也不触发分析任务。

## 2. 整体架构

```text
Drama Profile Frontend
          ↓
Drama Profile API
          ↓
DramaProfileService
          ↓
Profile Providers
          ↓
Repositories
          ↓
Existing Modules
```

完整实现链路为：

```text
Contracts → Profile Providers → DramaProfileService → Drama Profile API → DramaProfile.vue
```

- Contracts：冻结 DTO、Availability 和响应结构；
- Providers：从现有 Repository 只读获取结果并转换为 DTO；
- Service：聚合模块摘要并隔离单个 Provider 故障；
- API：提供 JWT 保护的统一只读接口；
- Frontend：展示画像并提供模块导航。

## 3. Contracts 设计

核心文件：`backend/services/drama_profile/contracts.py`。

Contracts 定义 Drama 基础信息、Score、Quality、Prediction、Anomaly、Action、Explanation 摘要 DTO，以及最终 `DramaProfileResponse`。本层不包含查询、计算或持久化逻辑，不依赖 ORM、Repository、Session 或数据库。

`AvailabilityReason` 固定为：

- `NOT_CALCULATED`：模块尚未计算；
- `INSUFFICIENT_HISTORY`：历史数据不足，无法生成结果；
- `NO_ANOMALY`：已检测且当前没有异常；
- `NOT_DETECTED`：尚未进行异常检测；
- `NOT_AVAILABLE`：结果或模块暂不可用。

`ModuleAvailability` 使用 `available` 与可选 `reason` 明确表达模块状态，避免调用方通过 null 推断业务语义。

## 4. Profile Providers 设计

Phase 7 实现六类 Provider：

- `ScoreProfileProvider`；
- `QualityProfileProvider`；
- `PredictionProfileProvider`；
- `AnomalyProfileProvider`；
- `ActionProfileProvider`；
- `ExplanationProfileProvider`。

映射关系：

```text
Score       → performance
Quality     → quality
Prediction  → trend
Anomaly     → risk
Action      → operations
Explanation → explanations
```

Provider 统一遵循只读原则：只返回 Contracts DTO，不返回 ORM 对象，不调用业务 Service，不重新计算业务结果，不写入数据库，也不管理事务。

## 5. DramaProfileService 设计

核心文件：`backend/services/drama_profile/service.py`。

`DramaProfileService.get_profile(drama_id)` 负责：

1. 校验 Drama ID；
2. 调用六个 Provider；
3. 保留各模块 Availability；
4. 构造统一 `DramaProfileResponse`。

依赖方向固定为：

```text
DramaProfileService → Profile Providers
```

Service 禁止依赖 ScoreService、PredictionService、AnomalyService、OperationActionService 或 Explanation Service，不执行 commit、rollback、flush、分析计算或行动创建。

## 6. Provider 异常隔离

Profile 是聚合视图，不要求所有模块同时可用。单个 Provider 失败时，Service 将对应模块标记为：

```text
available=false
reason=NOT_AVAILABLE
```

其他 Provider 的结果继续正常返回。例如 Prediction Provider 失败不会阻断 Score、Quality、Anomaly、Action 和 Explanation 的展示。

Provider 正常返回的 `INSUFFICIENT_HISTORY`、`NO_ANOMALY` 等状态由 Service 原样保留，不重新解释或替换。

## 7. API 设计

接口：

```text
GET /api/v1/dramas/{drama_id}/profile
```

接口特点：

- 只读；
- JWT Bearer 保护；
- USER 和 ADMINISTRATOR 均可访问；
- 使用统一 `ResponseModel`；
- 不提供 POST、PUT 或 PATCH。

Router 只负责路径参数、用户认证、Service 调用和 API Schema 转换。Router 不访问 ORM、Repository、Provider 或业务计算逻辑。

## 8. Frontend 设计

核心页面：`frontend/src/views/dramaProfile/DramaProfile.vue`。

路由：

```text
/dramas/:id/profile
```

页面结构：

1. Drama Header；
2. Performance Card；
3. Quality Card；
4. Trend Card；
5. Risk Card；
6. Operations Card；
7. Explanation Card。

前端复用统一 Axios 和 Token 机制，只展示 Profile API 结果并提供 Score、Prediction、Anomaly 和 Operation Action 导航。前端不重新计算、不判断业务等级、不生成解释。

## 9. Availability 展示协议

所有模块统一使用 `available` 与 `reason`：

| Reason | 展示含义 |
| --- | --- |
| `NOT_CALCULATED` | 尚未计算 |
| `INSUFFICIENT_HISTORY` | 历史数据不足 |
| `NO_ANOMALY` | 当前无异常 |
| `NOT_DETECTED` | 尚未检测 |
| `NOT_AVAILABLE` | 暂不可用 |

页面不会通过数据对象是否为 null 推断业务状态。单个模块缺失不会导致整个 Profile 页面失败。

## 10. 测试与验证记录

### Backend

已新增测试覆盖：

- Contracts：DTO 构造、默认值、Availability 枚举和依赖边界；
- Providers：六类 DTO 映射、无数据状态和无业务 Service 依赖；
- Service：完整聚合、部分缺失、Provider 异常隔离；
- API：路由注册、只读方法、Schema 转换和依赖覆盖。

当前执行环境未提供 Python/pytest 可执行文件，因此 Phase 7 后端测试文件未在该环境实际运行；各阶段均已通过 `git diff --cached --check` 静态提交检查。

### Frontend

- `npm exec vue-tsc -- --noEmit`：通过；
- `npm run build`：通过；
- Vite 生产构建成功；
- chunk size warning 为既有非阻塞构建提示；
- 未新增依赖，未修改 lock 文件。

## 11. Phase 7 Git 提交历史

| Commit | Message | 内容 |
| --- | --- | --- |
| `65d7434` | `feat(phase7): add drama profile contracts` | DTO 与 Availability 协议 |
| `579b49a` | `feat(phase7): add drama profile providers` | 六类只读 Provider |
| `12a858d` | `feat(phase7): add drama profile service` | 聚合 Service 与异常隔离 |
| `6951b6f` | `feat(phase7): add drama profile api` | Schema、依赖组装与只读 API |
| `e2d6c82` | `feat(phase7): add drama profile frontend` | API Client、类型、页面、路由与入口 |

## 12. 当前限制

- 无 Profile 缓存；
- 无预计算画像表；
- 无实时推送或自动刷新机制；
- Provider 数量固定；
- 无自动画像标签生成；
- 各模块采用自身 latest available 结果，不提供全局一致时间快照。

这些限制保持了 V1 的只读、可解释和低耦合边界，可在后续独立阶段中评估扩展。

## 13. 未来扩展方向

可考虑：

1. 基于性能数据引入 Profile 缓存层；
2. 增加用户画像、投放效果、市场趋势等业务 Provider；
3. 建立版本化画像标签体系；
4. 增加经过审核的自动化运营建议；
5. 引入 Global Snapshot 后提供跨模块统一时间视图。

未来扩展不得在 Profile 层引入新的业务事实、评分模型或预测模型；新增分析能力仍应由独立业务模块负责。

## 14. 归档结论

Phase 7 已完成 Contracts、Providers、Service、API 和 Frontend 的完整只读聚合链路。Drama 360° 全景画像中心正式形成以 Drama 为核心的统一分析视图，同时保持与 Phase 1–6 业务模块的单向、低耦合依赖。

Phase 7 至此归档。下一阶段可进入 Phase 8 Design Proposal。
