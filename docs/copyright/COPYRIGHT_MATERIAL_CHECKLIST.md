# 短剧数据管理与分析系统软著材料检查表

## 1. 使用说明

本检查表用于短剧数据管理与分析系统 V1.0 的软件著作权材料准备。执行人应在“结果”栏填写 `Pass`、`Fail`、`N/A` 或 `Pending`，并在“证据/备注”栏记录文件名、截图编号、Commit 或待确认责任人。

当前源码为 Conditional Freeze。凡依赖最终干净代码基线的项目，在基线完成前应标记为 `Pending`，不得提前勾选通过。

## 2. 申请基本信息

| 编号 | 检查项 | 期望内容 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- |
| INFO-01 | 软件中文全称 | 短剧数据管理与分析系统 |  |  |
| INFO-02 | 软件英文名称 | Short Drama Data Management and Analysis System |  |  |
| INFO-03 | 版本 | V1.0 |  |  |
| INFO-04 | 著作权人 | 与证件和申请表一致 |  |  |
| INFO-05 | 开发完成日期 | 已由申请人确认 |  |  |
| INFO-06 | 首次发表信息 | 状态、日期和地点已确认 |  |  |
| INFO-07 | 开发方式 | 独立/合作/委托等已确认 |  |  |
| INFO-08 | 权利范围 | 与申请人实际权利一致 |  |  |
| INFO-09 | 冻结基线 | 最终 Commit/Tag 可复现 |  |  |
| INFO-10 | 当前状态披露 | Conditional Freeze 未被误写为最终冻结 |  |  |

## 3. 软件环境信息

| 编号 | 检查项 | 期望内容 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- |
| ENV-01 | Python | 3.12+，验证版本 3.12.14 |  |  |
| ENV-02 | Backend Framework | FastAPI，版本记录一致 |  |  |
| ENV-03 | Frontend | Vue 3 + TypeScript + Vite |  |  |
| ENV-04 | Node/npm | 验证版本已记录 |  |  |
| ENV-05 | Database | MySQL 8.x |  |  |
| ENV-06 | Migration | V001–V013 |  |  |
| ENV-07 | 时间语义 | UTC |  |  |

## 4. 功能说明材料

| 编号 | 检查项 | 期望内容 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- |
| FUN-01 | 登录与权限 | JWT、USER、ADMINISTRATOR |  |  |
| FUN-02 | 数据管理 | 基础数据、关联和导入 |  |  |
| FUN-03 | 数据分析 | Score、Quality、Prediction、Anomaly |  |  |
| FUN-04 | 运营行动 | Action、状态、历史和解释 |  |  |
| FUN-05 | Drama Profile | 单剧综合画像 |  |  |
| FUN-06 | Operation Analytics | Action Effect、Lifecycle、Benchmark |  |  |
| FUN-07 | Data Governance | Freshness、Completeness、Consistency、Evidence |  |  |
| FUN-08 | Reporting | Catalog、Preview、CSV、XLSX |  |  |
| FUN-09 | 非因果表述 | 行动变化未描述为导致关系 |  |  |
| FUN-10 | 产品边界 | 无 AI、推荐、自动决策或因果推断 |  |  |

## 5. 操作说明材料

| 编号 | 检查项 | 期望内容 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- |
| OPS-01 | 登录流程 | 与实际登录页面一致 |  |  |
| OPS-02 | Dashboard | 入口和概览一致 |  |  |
| OPS-03 | 数据管理 | 查询、维护和导入步骤真实 |  |  |
| OPS-04 | 数据分析 | 页面路径和操作真实 |  |  |
| OPS-05 | Drama Profile | 选择短剧并查看画像 |  |  |
| OPS-06 | Operation Analytics | 三类分析流程完整 |  |  |
| OPS-07 | Data Governance | Overview、三类检查和 Evidence |  |  |
| OPS-08 | Reporting | 选择、Filter、Preview、Export |  |  |
| OPS-09 | 安全退出 | 不保留敏感凭据 |  |  |

## 6. 页面截图计划

| 编号 | 截图内容 | 建议画面 | 对应材料 | 结果 |
| --- | --- | --- | --- | --- |
| PIC-01 | 登录界面 | 软件名称、账号输入、登录按钮；不显示密码 | 登录与权限 |  |
| PIC-02 | Dashboard 首页 | 核心概览和模块入口 | 产品总览 |  |
| PIC-03 | 数据分析页面 | 指标/Score/Prediction/Anomaly 中具有代表性的页面 | 数据分析中心 |  |
| PIC-04 | Drama Profile | 基础信息和多个画像区域 | Drama Profile |  |
| PIC-05 | Operation Analytics | Action Effect、Lifecycle 或 Benchmark | 运营分析 |  |
| PIC-06 | Data Governance | Overview 和质量状态 | 数据治理 |  |
| PIC-07 | Evidence Drawer | Evidence type、message、source、metadata | 数据治理依据 |  |
| PIC-08 | Reports Catalog | 报告目录、Schema Version、格式 | 报告中心 |  |
| PIC-09 | Reports Preview | Filter、Snapshot、Columns、Rows、Availability | 报告预览 |  |
| PIC-10 | CSV 导出结果 | 文件名、扩展名和可打开内容 | 报告导出 |  |
| PIC-11 | XLSX 导出结果 | 工作簿内容和列顺序 | 报告导出 |  |
| PIC-12 | 权限对照 | USER/ADMINISTRATOR 的真实入口差异 | 权限控制 |  |

截图要求：

- 使用同一 V1.0 Demo 环境和统一 `T_demo`；
- 保持页面语言、主题、窗口尺寸和浏览器缩放一致；
- 截图内容与功能说明、操作步骤一一对应；
- 遮盖密码、Token、连接串、真实姓名和真实商业数据；
- 不通过后期合成添加系统中不存在的按钮、状态或数据；
- 原始截图和脱敏成品分别受控保存；
- 在截图清单中记录文件名、采集日期和对应版本。

## 7. 技术材料

| 编号 | 检查项 | 期望内容 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- |
| TEC-01 | 系统架构说明 | Frontend→API→Service→Provider/Rule→Repository→Database |  |  |
| TEC-02 | 数据库说明 | MySQL 8、V001–V013、主要关系 |  |  |
| TEC-03 | 源程序说明 | Backend、Frontend、Database 结构 |  |  |
| TEC-04 | Read Model 边界 | Phase 7–10 只读聚合边界准确 |  |  |
| TEC-05 | 源程序清单 | 仅包含自产源码 |  |  |
| TEC-06 | 第三方依赖排除 | `.venv`、`node_modules` 未混入 |  |  |
| TEC-07 | 构建产物排除 | `dist`、cache 未混入 |  |  |
| TEC-08 | 敏感信息扫描 | 无密码、Secret、Token、真实连接串 |  |  |
| TEC-09 | 页码与页眉 | 名称、版本、页码连续一致 |  |  |
| TEC-10 | 源程序来源 | 最终 Commit/Tag 和生成 Hash 已记录 |  |  |

## 8. 软件说明书

| 编号 | 检查项 | 期望内容 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- |
| DOC-01 | 软件概述 | `docs/software/SOFTWARE_OVERVIEW.md` |  |  |
| DOC-02 | 功能说明 | `docs/software/FUNCTION_SPECIFICATION.md` |  |  |
| DOC-03 | 用户手册 | `docs/software/USER_MANUAL.md` |  |  |
| DOC-04 | 系统架构 | `docs/software/SYSTEM_ARCHITECTURE.md` |  |  |
| DOC-05 | 部署说明 | `docs/software/DEPLOYMENT_GUIDE.md` |  |  |
| DOC-06 | 软著基本信息 | `COPYRIGHT_SOFTWARE_INFO.md` |  |  |
| DOC-07 | 软著功能说明 | `COPYRIGHT_FUNCTION_DESCRIPTION.md` |  |  |
| DOC-08 | 软著操作说明 | `COPYRIGHT_OPERATION_MANUAL.md` |  |  |
| DOC-09 | 源程序说明 | `COPYRIGHT_SOURCE_CODE_DESCRIPTION.md` |  |  |

## 9. 验收材料

| 编号 | 检查项 | 期望内容 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- |
| ACC-01 | Demo 数据方案 | 已核对且不含真实敏感数据 |  |  |
| ACC-02 | 验收流程 | 用户操作路径完整 |  |  |
| ACC-03 | 验收检查表 | 已执行并签署 |  |  |
| ACC-04 | 冻结记录 | 最终状态和 Commit 明确 |  |  |
| ACC-05 | 构建记录 | Backend/Frontend 结果完整 |  |  |
| ACC-06 | 仓库清理报告 | 未提交内容已完成处置 |  |  |
| ACC-07 | 验收截图 | 图片齐全且可追溯 |  |  |
| ACC-08 | CSV/XLSX 样例 | 使用 Demo 数据且无敏感信息 |  |  |

## 10. 一致性检查

| 编号 | 检查项 | 期望内容 | 结果 | 证据/备注 |
| --- | --- | --- | --- | --- |
| CON-01 | 软件名称 | 全部为“短剧数据管理与分析系统” |  |  |
| CON-02 | 软件版本 | 全部为 V1.0 |  |  |
| CON-03 | 模块名称 | 与实际页面和 API 一致 |  |  |
| CON-04 | 功能边界 | 未描述不存在的功能 |  |  |
| CON-05 | 技术版本 | 与冻结记录一致 |  |  |
| CON-06 | 截图功能 | 与说明文字对应 |  |  |
| CON-07 | 源码版本 | 与最终 Commit/Tag 对应 |  |  |
| CON-08 | Conditional Freeze | 阻塞项处置前保持披露 |  |  |

## 11. 当前待办与阻塞项

| 编号 | 项目 | 类型 | 处置要求 |
| --- | --- | --- | --- |
| BLOCK-01 | 31 个已跟踪未提交源码文件 | 冻结阻塞 | 确认归属并分批审查 |
| BLOCK-02 | 238 个未跟踪文件 | 冻结阻塞 | 分类提交、外移或忽略 |
| BLOCK-03 | Backend 4 个测试失败 | 验收阻塞/风险接受 | 修复回归或正式接受风险 |
| BLOCK-04 | 最终 Commit/Tag 未确定 | 材料阻塞 | 干净复验后记录 |
| BLOCK-05 | 申请主体信息未提供 | 申请阻塞 | 由申请人确认 |
| BLOCK-06 | 最终截图尚未采集 | 材料阻塞 | 按计划采集和脱敏 |
| BLOCK-07 | 源程序页数/交存方式未确认 | 材料阻塞 | 生成后按受理规则确认 |

## 12. 材料包目录建议

```text
copyright-package/
├── 01_application/          # 申请表及主体证明
├── 02_software-info/        # 软件基本信息与功能说明
├── 03_operation-manual/     # 操作说明和截图
├── 04_source-code/          # 最终源程序交存文件
├── 05_acceptance/           # 验收流程、记录和构建证据
├── 06_export-samples/       # 脱敏 CSV/XLSX 示例
└── 07_hash-manifest/        # 文件清单、Hash 和版本记录
```

该目录为材料归档建议，不代表需要在源码仓库中创建全部内容。包含主体证件、签章文件或真实联系方式的申请材料应放在受控存储中，不应提交到 Git。

## 13. 最终签署

| 角色 | 姓名 | 日期 | 结论/签名 |
| --- | --- | --- | --- |
| 材料整理人 |  |  |  |
| 技术复核人 |  |  |  |
| 产品复核人 |  |  |  |
| 申请主体授权人 |  |  |  |

只有在阻塞项关闭、材料一致性检查通过并完成最终干净基线复验后，才能将材料状态标记为“可提交”。
