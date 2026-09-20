# Phase 4 Anomaly Detection Service

## 1. 服务定位

`AnomalyService`负责一次异常检测批次的业务编排，位于：

```text
历史指标 Provider
        ↓
AnomalyService
   ↙          ↘
Anomaly Calculator   AnomalyRepository
                         ↓
                    OperationLogRepository
```

Service不实现Z-score、异常等级或异常规则，不直接访问ORM和SQL，也不创建Session。Calculator保持纯函数边界，Repository保持数据访问边界。

## 2. 依赖与输入

构造函数注入：

- `AnomalyHistoryProvider`：提供带`changed_at`、revision、平台和质量计数的历史观测；
- `AnomalyRepository`：保存、查询和更新异常记录；
- `OperationLogRepository`：记录检测和状态变更操作；
- 可选`AnomalyDetector`：测试或未来模型替换时使用，默认适配现有四类Calculator函数。

历史 Provider 可以由后续 Analytics 适配层实现。现有 `AnalyticsService` 不需要重构，也不会被本阶段直接修改。

## 3. `detect_anomalies`流程

输入为`analysis_as_of`和操作用户ID。未传入截止时间时使用当前UTC时间并归一化为项目的MySQL UTC约定。

批次流程：

1. 调用历史 Provider；
2. 丢弃`changed_at > analysis_as_of`的未来revision；
3. 对同一短剧、平台、业务日期选择截止点之前最新的revision；
4. 排除VOID或非活跃平台记录；
5. 按短剧和日期聚合有效平台指标；
6. 构造连续9个累计播放量日点；
7. 生成7个历史日增量和1个当前日增量，交给增长/下降检测；
8. 使用同一窗口生成互动率和单日突变检测输入；
9. 汇总`AnomalyFinding`，调用`save_anomalies`一次批量保存；
10. 写入一次`ANOMALY_DETECT`操作日志并提交事务。

9个累计日点的原因是：7个历史日增量加上1个当前检测日增量，需要9个累计点。无法构造连续窗口时不生成伪造的0异常，返回`INSUFFICIENT_HISTORY`或`INSUFFICIENT_METRICS`。

## 4. Data Quality协同

Service只消费 Provider 携带的质量状态，不修改`DataQualityService`：

- 任一参与窗口的ERROR计数大于0：阻断该短剧检测，计入`DATA_QUALITY_BLOCKED`；
- WARNING不阻断，继续交给Calculator；
- 累计播放量倒退视为数据可信问题，阻断该短剧检测；下降异常检测的是“日增量显著低于历史基准”，不是累计事实倒退；
- 数据为空：计入`NO_HISTORY`；
- 互动率播放量低于Calculator门槛：计入`NOT_APPLICABLE`。

质量判断仍属于数据质量模块；AnomalyService只负责将质量结果作为检测资格输入。

## 5. 返回结构

Service结果`AnomalyDetectionResult`（实现类型为`AnomalyDetectionServiceResult`）包含：

- `analysis_as_of`
- `algorithm_version`（固定`Rule-based Detection V1.0`）
- `detected_count`
- `skipped_count`
- `skip_reasons`

检测异常结果按短剧合并为一次批量保存；Service不重新排序、不重新计算等级。

## 6. 查询与状态更新

以下方法只委托Repository：

- `get_anomalies`
- `get_drama_anomalies`
- `get_latest_anomalies`
- `get_statistics`

`update_status`支持`OPEN`、`ACKNOWLEDGED`、`RESOLVED`、`IGNORED`。状态更新和`ANOMALY_STATUS_UPDATE`日志在同一事务中完成；记录不存在抛出`NotFoundException`，非法状态抛出`ValidationException`。

## 7. 事务设计

检测批次事务范围：

```text
BEGIN
  历史读取与输入准备
  Calculator调用
  AnomalyRepository.save_anomalies()
  OperationLogRepository.create(ANOMALY_DETECT)
COMMIT
```

Calculator、Repository或OperationLog任一步失败都会触发`BaseService.transaction()`回滚，禁止留下部分异常记录。成功路径只提交一次。状态更新采用相同原则。

## 8. 测试结果

新增`backend/tests/test_anomaly_service.py`，覆盖：

- 正常检测、无异常和多短剧批量保存；
- 9日窗口、7日历史增量和as-of revision过滤；
- ERROR阻断、WARNING继续、无历史和数据不足；
- Calculator、Repository、OperationLog失败回滚；
- 查询方法委托；
- 状态更新、权限状态校验、操作日志和单次提交。

本阶段测试结果：

```text
Anomaly Service + Service基线测试：28 passed
完整后端回归测试：334 passed
```

## 9. 后续边界

本阶段不实现Router、API、Frontend或Dashboard。后续API只能调用Service，不能绕过Service访问Repository、Calculator或ORM；历史 Provider 的真实数据库适配也应独立于本Service，继续遵守`changed_at <= analysis_as_of`规则。
