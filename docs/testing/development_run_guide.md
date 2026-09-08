# Development Run Guide（系统联调启动流程 V0.1）

- 任务：TASK-PHASE6-01
- 日期：2026-09-08
- 用途：Phase 6 联调环境准备说明，仅记录启动流程与验证命令，不包含任何真实密码。

## 1. 环境检查记录（本机实测）

| 项目 | 检查项 | 结果 | 说明 |
| --- | --- | --- | --- |
| Backend | Python 版本 | PASS | 项目 venv `backend/.venv` 为 Python 3.12.14（满足 3.12+ 基线）；全局 Python 3.13.9 缺少 alembic，不作为项目解释器 |
| Backend | 依赖安装 | PASS | venv 内 fastapi/sqlalchemy/alembic/pymysql/uvicorn/pydantic/pydantic-settings/bcrypt/PyJWT/openpyxl/python-multipart/tzdata/pytest/httpx 全部可 import |
| Backend | FastAPI 启动方式 | PASS（流程确认） | `uvicorn main:app --reload`（见 backend/README.md）；健康检查 `GET /health` 不连库 |
| Backend | 启动前置配置 | FAIL | `backend/.env` 当前不存在；`import main` 因 `secret_key` 缺失抛 ValidationError，需先按示例创建本地 `.env` |
| Frontend | Node 版本 | PASS | Node v24.11.1 |
| Frontend | npm 依赖 | PASS | `frontend/node_modules` 存在；`npm run build` 已在 TASK-P5-07 PASS（2311 modules） |
| Frontend | Vite 启动方式 | PASS | `npm run dev`，默认端口 5173 |
| Frontend | 启动前置配置 | FAIL | `frontend/.env` 当前不存在；axios `baseURL` 回退为同源 `/api/v1`，而 vite.config 未配置 proxy，本地直连后端需显式 `VITE_API_BASE_URL=http://localhost:8000/api/v1` |
| Database | MySQL 版本 | PASS | MySQL Community Server 8.0.45（`mysql.exe Ver 8.0.45`） |
| Database | 服务状态 | PASS | `mysqld.exe` 进程存在，Windows 服务 `mysql` 已启动 |
| Database | 数据库连接配置 | FAIL（按设计不提交真实凭据） | 仓库仅有 `.env.example`，`DATABASE_USER`/`DATABASE_PASSWORD` 为空占位；`root` 无密码 TCP ping 返回 Access denied，说明服务在线但缺少可用凭据，应用级连接需操作者本地配置 |
| Docker | 备用方案 | FAIL（当前不可用） | Docker 29.6.2 已安装，但 Docker Desktop daemon 未启动，暂不能作为 MySQL 替代 |

结论：MySQL 服务与前后端工具链就绪；阻断联调的只有两处本地配置——`backend/.env` 与 `frontend/.env`，以及数据库凭据。这些均属操作者本地机密文件，本 Task 按安全边界不代为创建、不写入真实密码。

## 2. 启动流程（按顺序执行）

### 2.1 启动 MySQL

Windows 本机已安装 MySQL 8.0.45，确认服务已启动：

```powershell
net start mysql        # 若未启动
mysqladmin --host=127.0.0.1 --port=3306 --user=root --password ping
```

### 2.2 初始化数据库（仅首次）

选择一个基线路径执行（二选一，勿重复执行）：

```powershell
# 路径 A：DDL 基线（7 个文件，含建库）
mysql --host=127.0.0.1 --port=3306 --user=<DB_USER> --password < database/ddl/001_create_database.sql
mysql --host=127.0.0.1 --port=3306 --user=<DB_USER> --password short_drama_analysis < database/ddl/002_create_core_tables.sql
mysql --host=127.0.0.1 --port=3306 --user=<DB_USER> --password short_drama_analysis < database/ddl/003_create_relation_tables.sql
mysql --host=127.0.0.1 --port=3306 --user=<DB_USER> --password short_drama_analysis < database/ddl/004_create_snapshot_tables.sql
mysql --host=127.0.0.1 --port=3306 --user=<DB_USER> --password short_drama_analysis < database/ddl/005_create_import_quality_tables.sql
mysql --host=127.0.0.1 --port=3306 --user=<DB_USER> --password short_drama_analysis < database/ddl/006_create_operation_log.sql
mysql --host=127.0.0.1 --port=3306 --user=<DB_USER> --password short_drama_analysis < database/ddl/007_create_indexes.sql
```

```powershell
# 路径 B：Migration 基线（V001～V006）
# 按文件名顺序对 short_drama_analysis 库执行 database/migrations/ 下 SQL
```

### 2.3 启动 Backend

```powershell
cd backend
Copy-Item .env.example .env      # 编辑填入 DATABASE_URL / SECRET_KEY / TOKEN_EXPIRE_MINUTES，禁止提交
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload        # 默认 http://127.0.0.1:8000
```

验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health   # 期望 {"status":"ok"}，不连库
```

### 2.4 启动 Frontend

```powershell
cd frontend
Copy-Item .env.example .env      # 本地开发填 VITE_API_BASE_URL=http://localhost:8000/api/v1
npm run dev                      # http://localhost:5173
```

### 2.5 访问系统

浏览器打开 `http://localhost:5173`，未登录应被 Router Guard 重定向到 `/login`。

### 2.6 登录测试账号（首次引导）

系统无注册端点、无种子账号脚本，首个账号需手工引导（**真实密码不写入本文档与仓库**）：

1. 使用 backend venv 生成 bcrypt 哈希（交互输入密码，不回显）：
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -c "import getpass; from auth.password import hash_password; print(hash_password(getpass.getpass('Password: ')))"
   ```
2. 对 `short_drama_analysis.users` 执行 INSERT，`role_code='ADMINISTRATOR'`、`status='ACTIVE'`、`password_hash` 填上一步输出。
3. 在登录页使用该账号登录，成功后应进入 `/dashboard` 且显示管理员入口（数据导入等）。

## 3. 联调冒烟清单（执行测试前）

| 编号 | 检查项 | 预期 |
| --- | --- | --- |
| S1 | `GET /health` | 200 `{"status":"ok"}` |
| S2 | `POST /api/v1/auth/login` | 正确凭据返回 token，错误凭据返回 401/业务错误 |
| S3 | `GET /api/v1/dashboard/overview`（带 Bearer） | 200，空库返回 0/空结构 |
| S4 | `/login` 未登录访问 `/dashboard` | 跳转登录页 |
| S5 | 登录后访问 `/analytics` | 页面可加载、短剧下拉可请求 |
