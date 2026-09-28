# Phase S3 仓库检查与清理报告

## 1. 检查目的

本报告记录源码冻结前的 Git 状态、文件分类和清理决策。Phase S3 不删除、不移动、不重写任何已有文件，仅提供可审计的处置建议。

## 2. Git 状态检查

### 2.1 执行命令

```powershell
git branch --show-current
git rev-parse HEAD
git status --branch --short
git diff --stat
git ls-files --others --exclude-standard
git status --ignored --short
```

### 2.2 基线结果

| 项目 | 结果 |
| --- | --- |
| 分支 | `main` |
| 验证开始时 HEAD | `7181e2d9a00b706fee4f9c86c08a1928ab6d600f` |
| 与远端关系 | `main...origin/main [ahead 94]` |
| 已跟踪修改 | 31 个文件 |
| 已跟踪 Diff | 1,516 insertions、163 deletions |
| 未跟踪文件 | 238 个实际文件 |
| 暂存区 | Phase S3 文档暂存前为空 |

结论：当前仓库不是干净工作区，不能在不处理既有修改的情况下形成可由单一 Commit 复现的最终验收版本。

## 3. 已提交验收材料

Phase S2 已提交：

- `docs/acceptance/DEMO_DATA_PLAN.md`；
- `docs/acceptance/ACCEPTANCE_FLOW.md`；
- `docs/acceptance/ACCEPTANCE_CHECKLIST.md`。

提交：`7181e2d9a00b706fee4f9c86c08a1928ab6d600f`。

Phase S3 仅计划新增：

- `docs/acceptance/SOURCE_FREEZE_RECORD.md`；
- `docs/acceptance/BUILD_VERIFICATION.md`；
- `docs/acceptance/REPOSITORY_CLEANUP_REPORT.md`。

## 4. 已跟踪修改分类

### 4.1 Backend：20 个文件

涉及：

- Dashboard schemas/service/repository/router；
- Imports template/validator/repository；
- Drama、Tag repository/router/schema/service；
- Analytics service；
- Import Job model；
- Dashboard 与 Router 测试。

Diff 规模显示这些不是格式性小改动，而是成组功能变化。Phase S3 无权判断其业务正确性，也不能将其与验收文档一同提交。

清理决策：**保留原状，待所有者确认后按功能拆分审查和提交**。在确认前不得丢弃。

### 4.2 Frontend：11 个文件

涉及：

- Axios 与 API 导出；
- Dashboard API、类型和页面；
- Router；
- Drama、Master Data 类型；
- DramaList、ImportUpload；
- Vite 配置。

清理决策：**保留原状，待与 Backend 对应变更一起评审**。Router、Dashboard 和 Vite 配置属于高影响共享文件，必须精确检查后提交。

## 5. 未跟踪文件分类

实际未跟踪文件共 238 个，按顶层目录统计：

| 顶层范围 | 文件数 | 分类 | 当前决策 |
| --- | ---: | --- | --- |
| `.reasonix/` | 39 | 工具/分析产物 | 不纳入验收源码；确认工具需求后移出或加入忽略规则 |
| `backend/` | 7 | Backend 源码与测试 | 可能属于批量导入/Tag 功能；必须独立代码审查 |
| `frontend/` | 6 | Frontend 源码 | 可能属于批量导入、Tag、Drama Detail；必须独立代码审查 |
| `docs/` | 113 | 设计、测试、图片和结果材料 | 逐类判断是否属于软著/验收材料，再按文档主题提交 |
| `scripts/` | 11 | 报告处理辅助脚本 | 不进入产品运行路径；确认可复现用途和敏感信息后决定归档 |
| `simulation/` | 60 | 模拟/验证材料 | 不纳入正式源码基线，建议移至验收附件仓或独立归档 |
| `backup_before_v007.sql` | 1 | 数据库备份 | 可能包含敏感数据；禁止直接提交，优先移至受控备份位置 |
| `reasonix.toml` | 1 | 工具配置 | 确认团队是否采用该工具后再决定提交或忽略 |

### 5.1 未跟踪 Backend/Frontend 源码

主要包括：

- `backend/imports/batch.py`；
- `backend/models/import_batch.py`；
- `backend/routers/import_batches.py`；
- `backend/schemas/import_batch.py`；
- `backend/services/batch_import_service.py`；
- `backend/tests/test_batch_import.py`；
- `backend/tests/test_tags_feature.py`；
- `frontend/src/api/batch-import.ts`；
- `frontend/src/api/tag.ts`；
- `frontend/src/types/batch-import.ts`；
- `frontend/src/views/drama/DramaDetail.vue`；
- `frontend/src/views/import/BatchImport.vue`；
- `frontend/src/views/master/TagList.vue`。

这些文件参与当前构建或测试，但不属于当前 HEAD。清理决策：不得删除，也不得混入 Phase S3 提交；应作为独立功能批次明确来源、设计依据、Migration 影响和测试结论。

### 5.2 未跟踪文档

包含 Phase 2、3、5、6、7、8 的设计/审查文档，以及 `docs/pic/`、`docs/result/` 和测试报告。

清理决策：

- 架构与设计文档可在核对版本后按 Phase 分组提交；
- 图片和结果材料应检查是否含账号、Token、连接串或真实数据；
- JSON/Markdown 测试报告需核对生成时间和对应 Commit；
- 不应把全部文档无差别加入一次提交。

### 5.3 备份、脚本和模拟材料

清理决策：

- `backup_before_v007.sql`：不提交；先检查是否包含数据和凭据，移动到受控备份存储；
- `scripts/`：保留待审，区分可复现构建工具与一次性报告处理脚本；
- `simulation/`：保留待审，若属于课程或验收模拟材料，应与生产源码分离；
- `.reasonix/`、`reasonix.toml`：确认工具采用策略后再决定是否忽略或提交。

本阶段未执行任何删除或移动。

## 6. 忽略文件与构建产物

已确认以下目录由 `.gitignore` 排除：

- `backend/.venv/`；
- Python `__pycache__/`；
- `frontend/node_modules/`；
- `frontend/dist/`。

另外存在根目录和 Backend 的 `.pytest_cache/`。它们属于测试缓存，不应提交。Phase S3 没有删除这些目录，因为用户仅授权检查和记录。

Frontend build 生成的 `frontend/dist/` 保持忽略状态，没有进入 Git 变更列表。

## 7. 数据库与 Migration 检查

仓库中的正式 Migration 范围为 `V001–V013`。当前 Git 状态未显示已跟踪 Migration 被修改，也没有新的正式 Migration 文件。

但存在：

- 未跟踪 `backend/models/import_batch.py`；
- 未跟踪 `backup_before_v007.sql`。

前者是 ORM Model，后者是数据库备份。二者均不得在缺少独立数据库/Migration Review 的情况下进入冻结基线。

## 8. 清理决策汇总

| 对象 | 决策 | 理由 |
| --- | --- | --- |
| Phase S3 三份文档 | 精确提交 | 本阶段明确授权 |
| 31 个已跟踪源码修改 | 保留、不提交 | 既有用户工作，需功能审查 |
| 13 个未跟踪 Backend/Frontend 源码文件 | 保留、不提交 | 当前可能参与构建，归属未确认 |
| 113 个未跟踪 docs 文件 | 分批审查 | 版本和敏感信息需确认 |
| `backup_before_v007.sql` | 不提交，建议受控归档 | 备份可能含敏感数据 |
| `scripts/` | 保留待分类 | 可能是一次性辅助工具 |
| `simulation/` | 保留待分类 | 非正式产品源码候选 |
| `.reasonix/` 与配置 | 保留待确认 | 工具配置/产物策略未冻结 |
| `.venv`、`node_modules`、`dist`、cache | 继续忽略 | 环境依赖或生成产物 |

## 9. 源码冻结风险

### 阻塞项

1. 工作区非干净；
2. 现有 HEAD 无法代表当前实际构建内容；
3. Backend 有 4 个测试失败；
4. 未跟踪 ORM Model 可能涉及未审查的数据结构边界；
5. 本地分支超前远端 94 个提交，发布/备份策略未确认。

### 非阻塞项

1. Frontend chunk size warning；
2. FastAPI/Starlette 测试依赖弃用警告；
3. 全局 PATH 缺少 `python`，项目虚拟环境可正常使用；
4. 首轮测试和构建的沙箱权限限制，已通过明确环境重试定位。

## 10. 推荐清理顺序

1. 创建仓库外备份或使用受控分支保存当前工作区；
2. 识别批量导入、Tag、Dashboard、Drama Detail 等修改的业务归属；
3. 对可能涉及 ORM 的 `import_batch.py` 单独进行 Migration Review；
4. 将源码按功能拆分提交并运行对应测试；
5. 将设计文档、图片、结果和脚本按用途分批归档；
6. 将数据库备份移出源码仓库；
7. 对工具目录、模拟材料和缓存制定 `.gitignore`/外部归档策略；
8. 修复或正式接受 4 个 Backend 测试失败；
9. 在新的干净检出目录执行完整构建和验收流程；
10. 创建最终验收 Tag，并更新 `SOURCE_FREEZE_RECORD.md`。

## 11. 本阶段操作确认

Phase S3：

- 未删除文件；
- 未移动已有文件；
- 未修改 Backend、Frontend、Database、Migration 或 ORM；
- 未执行数据库写入；
- 仅新增三份 `docs/acceptance/` 文档；
- Git 提交将精确限定为这三份文档。
