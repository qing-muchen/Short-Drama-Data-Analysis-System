# 短剧数据管理与分析系统

**Short Drama Data Management and Analysis System**

## 项目简介

本项目是一个面向短剧数据管理、运营数据处理、统计分析和可视化的数据管理与分析系统。当前 V1.0 主要开发 Web 端，以数据管理、数据处理、数据分析和数据可视化为核心；本系统不是短剧播放平台。

## 当前状态

- 当前阶段：Phase 0 Completed。
- 项目基础工程和需求设计基线已经建立。
- 当前尚未开始业务功能开发。
- 下一阶段：等待项目负责人下达 Phase 1 Task。

## 技术栈

- Frontend：Vue 3、Vite、Element Plus、Vue Router、Pinia、Axios、ECharts。
- Backend：Python 3.12、FastAPI、SQLAlchemy 2.x、Pydantic、Alembic、Pandas、NumPy、openpyxl。
- Database：MySQL 8.x。
- Version Control：Git + GitHub。

以上仅列出已冻结的主要技术栈；详细约束以 `PROJECT_MASTER.md` 为准。

## 项目结构

```text
Short Drama Data Analysis System/
├── PROJECT_MASTER.md
├── README.md
├── .gitignore
├── .env.example
├── frontend/
├── backend/
├── database/
├── scripts/
└── assets/
```

## 项目设计真源

`PROJECT_MASTER.md` 是本项目唯一设计真源（Single Source of Truth）。所有 Agent 在执行开发任务前必须首先完整阅读该文件；需求、数据库规范、分析模型、Agent 开发规范和项目状态均以该文件为准。

## 当前开发原则

- 采用 Task 驱动开发，一次只完成一个明确任务。
- 关系数据库必须至少满足第三范式（3NF）。
- 系统采用前后端分离架构。
- 当前不生成正式课程设计报告。
- 项目完成后再统一整理课程设计报告和软件著作权相关材料。
