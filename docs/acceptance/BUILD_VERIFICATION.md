# Phase S3 最终构建验证记录

## 1. 验证范围

本记录覆盖 Phase S3 的只读构建与测试检查：

- Backend Python 源码编译；
- Backend 全量测试；
- Frontend TypeScript 类型检查；
- Frontend production build；
- 运行环境版本采集；
- 验收流程和文档材料存在性检查。

验证期间未修改业务代码、数据库、Migration 或 ORM。Python 编译缓存写入系统临时目录；Frontend `dist/`、`node_modules/` 和 Backend `.venv/` 均由现有 `.gitignore` 排除。

## 2. 验证上下文

| 项目 | 值 |
| --- | --- |
| 执行日期 | `2026-09-28` |
| 执行时区 | `UTC+08:00` |
| 记录时间 | 约 `18:23–18:26` |
| 分支 | `main` |
| 验证开始时 HEAD | `7181e2d9a00b706fee4f9c86c08a1928ab6d600f` |
| 工作区 | 非干净，验证包含本地未提交内容 |

因此，本记录证明的是当前工作目录的构建状态，不代表仅检出上述 HEAD 即可复现相同结果。

## 3. 环境信息

| 组件 | 实测版本 |
| --- | --- |
| Python | `3.12.14` |
| FastAPI | `0.141.1` |
| pytest | `9.1.1` |
| Node.js | `v24.11.1` |
| npm | `11.6.2` |
| Vite | `7.3.6`（构建输出） |
| MySQL Client | `8.0.45` |
| Migration | `V001–V013` |

环境限制：全局 PATH 不包含 `python`，实际使用 `backend/.venv/Scripts/python.exe`。

## 4. Backend 编译验证

### 4.1 执行命令

等价标准命令：

```powershell
python -m compileall backend
```

本机实际命令使用项目虚拟环境，并将缓存放到临时目录、排除 `.venv`：

```powershell
backend\.venv\Scripts\python.exe `
  -X pycache_prefix=C:\Users\Muyu\AppData\Local\Temp\phase_s3_project_pycache `
  -m compileall -q -x "\\.venv" backend
```

### 4.2 执行结果

| 项目 | 结果 |
| --- | --- |
| 退出码 | `0` |
| Python 语法编译 | 通过 |
| 业务代码修改 | 无 |
| 仓库新增缓存 | 无；缓存定向至临时目录 |
| 异常信息 | 无 |

首次环境探测使用了 Codex 隔离 Python。该运行时为 Python 3.12.14，但不包含项目 FastAPI/pytest 依赖；随后改用项目 `.venv` 完成正式验证。这是环境选择差异，不是源码编译失败。

## 5. Backend 测试验证

### 5.1 执行命令

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -q `
  --tb=short `
  --basetemp=C:\Users\Muyu\AppData\Local\Temp\phase_s3_pytest_20260928
```

### 5.2 测试结果

| 项目 | 数量 |
| --- | ---: |
| 收集 | 706 |
| 通过 | 702 |
| 失败 | 4 |
| Error | 0（显式临时目录重跑） |
| Warning 类型 | 2 |

整体结论：**测试未全绿，不应将当前状态标记为最终验收通过**。

### 5.3 失败项

| 测试 | 现象 | 分类 |
| --- | --- | --- |
| `test_drama_profile_api.py::test_profile_route_is_registered_and_read_only` | 遍历 `app.routes` 时 `_IncludedRouter` 没有 `path` 属性 | 既有测试/路由兼容问题 |
| `test_drama_profile_api.py::test_schema_boundary_does_not_add_write_routes` | 同上 | 既有测试/路由兼容问题 |
| `test_drama_profile_contracts.py::test_contract_module_has_no_persistence_dependencies` | 禁止词 `query` 命中 Contracts 模块 docstring | 既有边界测试过度字符串匹配问题 |
| `test_routers.py::test_openapi_registers_only_authorized_basic_api_paths` | 首个 Drama 子路径为只读 Profile 路径，断言期望 CRUD 方法 | 既有路由测试选择逻辑问题 |

Phase S3 按要求未修改测试或业务代码。失败项需要在独立 Bug 修复阶段评审，修复后重新执行完整验证。

### 5.4 环境重试记录

首轮测试使用 pytest 默认临时目录时，有 10 项 setup error：

```text
PermissionError: C:\Users\Muyu\AppData\Local\Temp\pytest-of-Muyu
```

使用显式 `--basetemp` 重跑后 10 个 error 全部消失，故将其记录为执行环境权限问题。最终有效测试结论为 702 passed、4 failed。

### 5.5 非阻塞警告

- Starlette/FastAPI TestClient 提示 `httpx` 适配方式将弃用；
- `anyio.abc.BlockingPortal` 别名提示弃用。

警告未阻止测试执行，但应在未来依赖升级评审中处理，不应在源码冻结阶段直接升级依赖。

## 6. Frontend 类型检查

### 6.1 执行命令

在 `frontend/` 目录执行：

```powershell
npm exec vue-tsc -- --noEmit
```

### 6.2 执行结果

| 项目 | 结果 |
| --- | --- |
| 退出码 | `0` |
| TypeScript/Vue 类型检查 | 通过 |
| 错误输出 | 无 |

## 7. Frontend Production Build

### 7.1 执行命令

在 `frontend/` 目录执行：

```powershell
npm run build
```

脚本实际执行：

```text
vue-tsc --noEmit && vite build
```

### 7.2 执行结果

| 项目 | 结果 |
| --- | --- |
| 退出码 | `0` |
| 转换模块 | 2362 |
| Vite 构建时间 | 13.38s |
| Reports 页面产物 | 已生成 |
| Data Governance 页面产物 | 已生成 |
| Operation Analytics 页面产物 | 已生成 |
| 构建结论 | 通过 |

首次在受限沙箱中执行时，esbuild 因父目录读取权限无法解析 `frontend/vite.config.ts`。在允许目录访问的同一主机上重新执行原命令后成功，故不归类为产品构建失败。

### 7.3 非阻塞提示

Vite 报告部分 JavaScript chunk 在压缩前超过 500 kB：

- `index-BSEOSYa7.js`：约 1,090.65 kB；
- `index-DIQPS0R6.js`：约 1,126.64 kB。

该提示不影响构建成功和验收页面运行。代码分包属于后续性能优化项，不应在冻结阶段重构。

## 8. 验收流程覆盖检查

| 验收范围 | 当前证据 | 结论 |
| --- | --- | --- |
| 登录和权限 | S2 流程/清单 | 已规划，需运行环境实操 |
| Dashboard | 前端构建产物、S2 流程 | 构建覆盖 |
| Drama Profile | 前端构建产物、API 测试存在 | 构建覆盖；相关测试有 3 项失败 |
| Operation Analytics | 前端构建产物、既有测试 | 构建覆盖 |
| Data Governance | 前端构建产物、既有测试 | 构建覆盖 |
| Reporting Preview/Export | Reports 构建产物、既有测试 | 构建覆盖；仍需 CSV/XLSX 实操 |
| 软件文档 | `docs/software/` 五份文档 | 存在 |
| 验收文档 | S2 三份文档 | 存在 |

本阶段未启动 Backend、Frontend 或 MySQL 服务，也未执行浏览器端端到端验收，因此登录、权限和真实下载应按 `ACCEPTANCE_FLOW.md` 另行留证。

## 9. 最终验证结论

- Backend 编译：通过；
- Backend 测试：未全绿，4 个既有失败；
- Frontend 类型检查：通过；
- Frontend build：通过，存在非阻塞 chunk size 警告；
- 数据库：未连接，仅核验客户端版本和 Migration 文件范围；
- Git 基线：工作区非干净，尚不具备可复现冻结条件。

建议在 Phase S4 前先完成仓库内容归属确认；如 Phase S4 仅整理材料，可继续，但所有材料必须注明当前冻结状态为“有条件”。正式系统验收签署前应完成干净检出复验。
