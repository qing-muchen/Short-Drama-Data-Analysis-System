# Phase 6 Data Lineage & Analysis Explanation Center Architecture Review

## 1. Review结论

Phase 6 设计总体方向正确，可以进入 Design V2，但不建议直接进入 V013 Migration。当前设计已经明确 Explanation Center 是解释层和追溯层，而不是新的业务事实存储层；仍需在 Design V2 中冻结解释生成策略、记录粒度、查询分页和历史保留规则。

结论：**有条件允许进入 Design V2；V013 暂不准入。**

## 2. 通过项

### 2.1 模块定位清晰

Phase 6 不重新计算 Score、Quality、Prediction 或 Anomaly，也不修改 Operation Action。它保存解释文本、输入关系和指标依赖，能够补足现有系统“结果可用但依据分散”的缺口。

不应在 Phase 6 表中复制：

- `drama_scores` 的完整评分结果；
- `prediction_results` 的完整预测结果；
- `data_anomaly_records` 的完整异常结果；
- `data_quality_scores` 或规则结果的完整副本；
- `operation_actions` 的状态和历史。

这些实体仍由原模块作为事实来源，Explanation Center 只保存解释所需的摘要、版本、时间截点和逻辑引用。

### 2.2 三表职责基本合理

- `analysis_explanations` 面向用户，回答“为什么”。
- `analysis_lineage_records` 面向追溯，回答“依赖了什么”。
- `metric_dependencies` 面向指标图，回答“指标如何组成”。

三者没有明显职责重叠，可以保持第三范式。

### 2.3 依赖方向正确

```text
Score / Quality / Prediction / Anomaly / Operation Action
                         ↓ 只读消费
                Explanation Center
```

Explanation Center 不调用已有业务 Service 执行计算，已有模块也不反向依赖 Explanation Service，符合分层和单向依赖原则。

### 2.4 版本字段方向正确

`algorithm_version` 用于评分、预测和异常算法；`rule_set_version` 用于数据质量规则集。两者语义不同，不应合并成单一版本字段。`analysis_as_of` 是历史解释可复现的必要字段。

V1 暂不引入 `model_registry` 是合理的：当前版本只需保存版本快照，不需要提前引入模型发布、参数、训练集和生命周期管理。

## 3. 风险项

### 3.1 解释生成时机尚未冻结

如果每次查询都动态生成解释，结果可能随源数据修订、规则版本或代码变化而改变；如果只在结果生成时保存，又需要保证结果生成流程同步写入解释和血缘。

建议 Design V2 冻结为：V1 在分析结果生成或显式解释刷新时保存解释快照，查询只读已保存内容；禁止普通 GET 请求隐式重新计算。

### 3.2 `detail` 结构过于宽泛

仅使用长文本会降低前端展示和审计能力；直接保存完整业务对象又会造成重复存储。建议 V2 将 `detail` 定义为受控 JSON 结构，限制为解释项、贡献值、阈值、窗口摘要等小型证据，不保存完整 snapshot 或完整结果对象。

### 3.3 弱关联的一致性风险

`target_type/target_id` 和 `source_type/source_id` 能避免多态外键，但数据库无法保证来源记录一定存在。该风险可接受，但必须由 Service 在写入时校验允许的类型、ID和版本，并通过唯一约束防止重复血缘。

### 3.4 血缘数量可能快速增长

一次 Score 解释可能依赖多个指标和多个 snapshot；Prediction 和 Anomaly 也可能产生窗口级血缘。若每个原始点都落一条长期记录，数据规模会明显超过业务结果表。

### 3.5 指标依赖图可能与运行血缘混淆

`metric_dependencies` 应是版本化静态配置，不能每次运行动态生成；运行时具体输入仍由 `analysis_lineage_records` 保存。两者必须在命名和 API 中明确区分。

## 4. 必须修改项（Design V2冻结）

### 4.1 冻结解释快照策略

V1 推荐：

- 解释在分析结果写入后由显式编排流程生成；
- 保存 `summary`、受控 JSON `detail`、版本和 `analysis_as_of`；
- 查询接口只读，不重新执行算法；
- 同一实体、同一模块、同一分析截点和版本只能有一个当前解释快照；新版本生成新记录，不覆盖历史记录。

### 4.2 冻结三表字段和唯一性

`analysis_explanations` 至少需要：

`explanation_id`、`entity_type`、`entity_id`、`module_type`、`summary`、`detail`、`algorithm_version`、`rule_set_version`、`analysis_as_of`、`created_at`、`updated_at`。

建议唯一性：

```text
(entity_type, entity_id, module_type, analysis_as_of,
 algorithm_version, rule_set_version)
```

`analysis_lineage_records` 建议唯一性：

```text
(target_type, target_id, source_type, source_id,
 relationship_type, analysis_as_of, algorithm_version,
 rule_set_version)
```

允许 `algorithm_version` 或 `rule_set_version` 为空时，必须以一致的空值策略处理，避免 MySQL UNIQUE 对 NULL 的行为造成重复记录。

### 4.3 冻结弱关联边界

V1 推荐弱关联方案 A，而不是跨模块多态外键方案 B，也不引入事件驱动方案 C：

- 方案 A：兼容已有五个分析模块，Migration简单，耦合低；由 Service 校验来源类型和记录存在性。
- 方案 B：无法在 MySQL 中优雅表达多种目标表，容易造成多组 nullable 外键和循环依赖。
- 方案 C：适合高吞吐实时解释，但会增加消息一致性、重试和部署复杂度，不适合当前 V1。

### 4.4 冻结指标依赖图为静态版本化配置

`metric_dependencies` V1 需要独立表，因为依赖关系要被 API、文档和解释生成器复用，并且需要版本和启停状态。它不应在每次分析运行时动态写入。V1 禁止在线编辑和循环依赖；写入或发布配置时进行 DAG 校验。

### 4.5 增加历史查询约束

API 必须支持：

- `page/page_size` 分页；
- `analysis_as_of` 时间过滤；
- `module_type`、`source_type` 过滤；
- 明确按 `analysis_as_of DESC, id DESC` 稳定排序。

默认只返回最新解释或最新血缘，历史查询必须显式传递时间或版本过滤，避免一次返回全部窗口记录。

## 5. API审查

原规划的三个 GET 接口方向足够，但需要补充查询约束：

- `GET /explanations/{entity_type}/{id}`：默认最新解释；支持 `module_type`、`analysis_as_of`、`algorithm_version` 和分页历史。
- `GET /lineage/{entity_type}/{id}`：支持 `source_type`、`relationship_type`、`analysis_as_of` 和分页。
- `GET /metrics/{metric_name}/dependencies`：支持 `algorithm_version`、`enabled` 和递归深度上限。

V1 不开放客户端写入任意 explanation 或 lineage；生成和刷新接口如有需要，应由管理员或内部 Service 使用，不应让前端提交来源关系。

## 6. Dashboard审查

不建议 V1 建设独立解释中心页面。解释应嵌入已有详情：

- Score 详情展示四维贡献和算法版本；
- Quality 详情展示失败规则和规则集版本；
- Prediction 详情展示输入窗口和 analysis_as_of；
- Anomaly 详情展示基线、阈值、偏差和版本；
- Operation Action 详情展示来源证据快照。

独立页面会重复已有导航和业务上下文；嵌入式入口更符合“解释当前结果”的使用场景。未来当跨模块血缘图和全局审计需求成熟，再评估独立页面。

## 7. 数据规模治理建议

V1 必须冻结以下策略：

- 解释快照保留完整历史，但只保存小型摘要和受控 detail；
- 血缘记录按结果批次和版本保存，禁止重复写入；
- `metric_dependencies` 只保存少量配置，不按运行批次复制；
- 暂不自动 TTL 删除分析证据，先建立按月归档和容量监控；
- 后续可增加归档表、内容哈希和版本合并，但不得静默删除可追溯历史。

## 8. V013准入判断

当前不允许直接进入 V013 Migration。完成上述 Design V2 冻结后，满足以下条件才可准入：

1. 三表字段、NULL策略、唯一约束和索引已确定。
2. 解释生成时机和 `detail` JSON结构已确定。
3. 弱关联来源校验责任归属 Service，并有失败回滚方案。
4. lineage 与静态 metric dependency 的边界已写入实现规范。
5. API分页、时间过滤、默认最新策略已确定。
6. 历史保留、归档和容量监控方案已记录。

因此，Phase 6 当前结论为：**允许进入 Design V2，不允许直接创建 V013。**

## 9. 当前Git状态

本阶段只新增本审查文档，不执行 `git add` 或 `git commit`。工作区其他已有修改保持原状。
