# 短剧数据管理与分析系统软件概述

## 1. 软件名称

中文名称：**短剧数据管理与分析系统**

英文名称：**Short Drama Data Management and Analysis System**

当前产品版本：**V1.0**

## 2. 软件定位

短剧数据管理与分析系统是一套面向短剧数据管理、运营数据分析和运营复盘场景的 Web 应用。系统以短剧、平台、历史运营指标及相关业务记录为基础，提供数据导入、基础资料管理、指标分析、趋势与异常观察、运营行动跟踪、全景画像、数据治理和分析报告输出能力。

系统主要面向：

- 短剧运营人员；
- 数据管理人员；
- 数据分析人员；
- 业务管理与验收人员；
- 需要查看分析结果的普通用户。

系统的产品主线为：

```text
数据管理 → 数据处理 → 数据分析 → 运营复盘 → 数据治理 → 报告输出
```

本系统不是短剧播放平台，也不是 AI、推荐或自动决策系统。V1.0 的分析结论来自已实现的固定算法、确定性规则和既有业务数据。

## 3. 建设目标

系统建设目标包括：

1. 集中管理短剧、平台、演员、导演、公司、标签及短剧平台关系等基础数据；
2. 保留历史运营快照和版本信息，支持可追溯分析；
3. 提供综合评分、数据质量、预测、异常检测和解释血缘等分析能力；
4. 建立运营行动记录及行动前后指标变化的复盘视图；
5. 以短剧为中心聚合分散的分析结果；
6. 监控数据新鲜度、完整性与一致性；
7. 将已有事实按稳定 Schema 预览并导出为 CSV 或 XLSX。

## 4. 核心特点

### 4.1 多维数据分析能力

系统围绕短剧内容与运营数据提供多维分析，包括：

- Dashboard 核心指标、热度、增长和潜力概览；
- 综合评分及等级分布；
- 数据质量评分和规则结果；
- 播放量趋势预测及历史预测；
- 异常记录、严重程度、状态和证据；
- 运营行动状态、负责人和处理历史；
- 行动前后指标变化、生命周期和同平台 Benchmark；
- 解释摘要与数据血缘入口。

不同模块保持各自的事实所有权。聚合与报告模块只读取已有结果，不重复计算或修改原分析结果。

### 4.2 模块化分层架构

系统采用前后端分离和分层架构，主要业务模块包括：

- **Drama Profile**：以短剧为中心聚合 Performance、Quality、Trend、Risk、Operations 和 Explanation；
- **Operation Analytics**：展示行动前后指标变化、生命周期和同平台统计比较；
- **Data Governance**：请求时检查 Freshness、Completeness 和 Consistency；
- **Reporting Center**：提供 Report Catalog、Preview 及安全导出；
- **基础分析模块**：评分、数据质量、预测、异常、运营行动、解释与血缘。

模块依赖保持单向，Read Model 优先通过 Repository 读取已有事实，不跨模块调用业务 Service。

### 4.3 数据治理能力

Data Governance Center 提供：

- **Freshness**：检查最新数据时间与延迟状态；
- **Completeness**：检查必要字段、指标覆盖和时间序列连续性；
- **Consistency**：检查关联、Revision 和分析截点一致性；
- **Evidence**：展示形成治理状态所使用的最小依据。

治理结果在请求期间计算，不自动修改、补齐或修复业务数据。

### 4.4 报告输出能力

Analysis Reporting & Export Center 提供：

- Report Catalog；
- API Schema 驱动的 Filter；
- Snapshot 与 `analysis_as_of` 展示；
- Preview Table；
- CSV Export；
- XLSX Export；
- 导出确认、行数和文件大小限制；
- CSV Formula Injection 防护和流式下载。

报告基于已有数据事实生成，不创建新的业务指标，也不持久化报告文件。

### 4.5 可追溯与显式状态

系统通过分析时间、算法版本、规则版本、Revision、Schema Version、Snapshot Semantics 和 Availability 协议描述结果来源与可用状态。数据不足、未计算、无异常或不可用等情况均使用显式状态表达，不以空值替代业务语义。

### 4.6 权限与安全边界

系统采用 JWT Bearer 认证，角色包括：

- `ADMINISTRATOR`：可执行授权范围内的数据维护、导入、分析计算和管理操作；
- `USER`：可进行查询、筛选、Dashboard、分析查看和报告导出。

系统不开放公开注册。后端在受保护接口上重新验证身份与角色，前端仅根据用户状态展示入口，不能替代后端授权。

## 5. 主要功能组成

| 功能域 | 主要能力 |
| --- | --- |
| 认证与权限 | 登录、当前用户识别、JWT、管理员/普通用户权限 |
| 数据管理 | 短剧、演员、平台、标签及相关基础资料查询维护 |
| 数据导入 | CSV/XLSX 上传、校验、错误查看和确认 |
| 数据驾驶舱 | 核心数量、排行、趋势、质量和标签分布 |
| 基础分析 | 综合评分、数据质量、预测、异常检测 |
| 运营管理 | 运营行动、负责人、状态、评论和处理历史 |
| 解释与血缘 | 分析解释摘要、版本和来源追溯 |
| Drama Profile | 单剧 360° 聚合视图 |
| Operation Analytics | 行动变化、生命周期、Benchmark |
| Data Governance | Freshness、Completeness、Consistency、Evidence |
| Reporting | Catalog、Filter、Preview、CSV/XLSX Export |

## 6. 技术形态

- 前端：Vue 3、TypeScript、Vite、Element Plus、Vue Router、Pinia、Axios、ECharts；
- 后端：Python 3.12、FastAPI、SQLAlchemy 2、Pydantic 2；
- 数据库：MySQL 8，字符集 `utf8mb4`，统一使用 UTC 时间语义；
- 数据库演进：有序 SQL Migration `V001–V013`；
- 接口：REST 风格 `/api/v1`，统一响应结构和错误结构；
- 文件格式：CSV、XLSX。

## 7. 产品边界

V1.0 明确不包含：

- LLM、AI Agent 或机器学习平台；
- 自动运营建议或自动决策；
- 推荐算法；
- 因果推断；
- 自动修复数据；
- 自动生成 Word、PDF 或 PPT 报告；
- 报告文件长期归档、异步报告任务或下载审计表；
- 完播率、付费转化、广告消耗、ROI、用户留存等尚无数据基础的指标。

未来新增上述能力时，需要重新进行需求、架构、安全及必要的数据库迁移审查。

## 8. 软件验收关注点

验收时建议重点验证：

1. 登录、身份保持和角色权限；
2. Dashboard 与基础数据查询；
3. 分析结果和明确的 Availability 状态；
4. Drama Profile 的多模块聚合；
5. Operation Analytics 的非因果表述和固定规则版本；
6. Data Governance 的三类检查与 Evidence；
7. Reports 的 Catalog、Preview、确认和下载链路；
8. 各层单向依赖、只读边界与数据库 Migration 一致性。
