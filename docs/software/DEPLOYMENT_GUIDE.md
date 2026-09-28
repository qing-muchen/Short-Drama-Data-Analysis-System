# 短剧数据管理与分析系统部署说明

## 1. 文档范围

本文档说明短剧数据管理与分析系统 V1.0 的本地验收环境和基础生产部署方式，包括 MySQL 初始化、Backend/Frontend 安装、环境变量、启动、构建和健康检查。

项目当前不包含 Docker Compose、容器镜像、自动备份、异步任务服务或 Alembic 业务 revision。部署人员不应将本文档未列出的基础设施视为已提供能力。

## 2. 环境要求

| 组件 | 要求 | 说明 |
| --- | --- | --- |
| 操作系统 | Windows 10/11、主流 Linux | 需支持 Python、Node.js 和 MySQL |
| Python | 3.12+ | 项目本地验证版本为 Python 3.12 |
| Node.js | `^20.19.0` 或 `>=22.12.0` | 来自当前 Vite 7 engine 要求 |
| npm | 与 Node.js 配套版本 | 用于安装和构建前端 |
| MySQL | 8.x | 需要 `utf8mb4_0900_ai_ci` 与 CHECK 支持 |
| 浏览器 | 当前版本 Chrome、Edge 等 | 需要支持 Blob 下载和现代 JavaScript |

推荐为 Backend、Frontend 和 Database 使用同一 UTC 时间基线。

## 3. 目录说明

```text
Short Drama Data Analysis System/
├── backend/                  # FastAPI、Service、Repository、ORM、测试
├── frontend/                 # Vue 3、TypeScript、Vite
├── database/
│   ├── ddl/                  # 数据库初始化参考 DDL
│   └── migrations/           # V001–V013 有序 Migration
├── docs/                     # 设计、开发和软件文档
└── PROJECT_MASTER.md         # 项目设计基线
```

## 4. 获取与准备项目

1. 将代码检出到本地工作目录；
2. 确认当前检出版本包含 `database/migrations/V001–V013`；
3. 不要将生产密码、JWT Secret 或数据库备份提交到 Git；
4. 分别为 Backend 和 Frontend 安装依赖。

以下命令默认从项目根目录开始执行。

## 5. 数据库初始化

### 5.1 创建数据库

使用 MySQL 8 客户端或 MySQL Workbench 执行：

```text
database/ddl/001_create_database.sql
```

该脚本创建 `short_drama_analysis` 数据库，使用 `utf8mb4` 和 `utf8mb4_0900_ai_ci`，并设置 UTC 会话时间。

命令行示例（Bash）：

```bash
mysql -u root -p < database/ddl/001_create_database.sql
```

### 5.2 执行 Migration

严格按版本顺序执行：

```text
database/migrations/V001__create_core_tables.sql
database/migrations/V002__create_relation_tables.sql
database/migrations/V003__create_snapshot_tables.sql
database/migrations/V004__create_import_quality_tables.sql
database/migrations/V005__create_operation_log.sql
database/migrations/V006__create_indexes.sql
database/migrations/V007__create_import_batches.sql
database/migrations/V008__create_drama_scores.sql
database/migrations/V009__create_data_quality_tables.sql
database/migrations/V010__create_prediction_results.sql
database/migrations/V011__create_data_anomaly_records.sql
database/migrations/V012__create_operation_actions.sql
database/migrations/V013__create_analysis_explanation_tables.sql
```

Bash 示例：

```bash
for file in database/migrations/V*.sql; do
  mysql -u root -p short_drama_analysis < "$file" || exit 1
done
```

Windows 环境可在 MySQL Workbench 中按文件名顺序执行，或使用适合本机 Shell 的 MySQL 客户端脚本。任何文件失败后应停止后续执行并处理错误，不应跳过版本。

### 5.3 Alembic 边界

`backend/alembic/versions` 当前没有业务 revision。不要执行 `alembic upgrade head` 来替代根目录 SQL Migration，也不要对已初始化数据库执行未经审查的自动生成 Migration。

## 6. Backend 配置与启动

### 6.1 创建虚拟环境

Windows PowerShell：

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux/macOS Shell：

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 6.2 配置环境变量

复制示例文件：

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

Linux/macOS：

```bash
cp .env.example .env
```

编辑 `backend/.env`：

```dotenv
APP_NAME=Short Drama Data Management and Analysis System
APP_ENV=development
DATABASE_URL=mysql+pymysql://APP_USER:APP_PASSWORD@127.0.0.1:3306/short_drama_analysis?charset=utf8mb4
SECRET_KEY=replace-with-a-strong-random-secret-at-least-32-characters
TOKEN_EXPIRE_MINUTES=30
```

配置项说明：

| 配置项 | 必填 | 说明 |
| --- | --- | --- |
| `APP_NAME` | 否 | OpenAPI 和应用显示名称 |
| `APP_ENV` | 是 | `development`、`test` 或 `production` |
| `DATABASE_URL` | 是 | SQLAlchemy MySQL/PyMySQL 连接字符串 |
| `SECRET_KEY` | 是 | JWT Secret，至少 32 个字符，生产环境必须随机生成 |
| `TOKEN_EXPIRE_MINUTES` | 否 | Token 有效期，范围 1–1440，默认 30 |

注意：密码包含 `@`、`:`、`/` 等字符时需要进行 URL 编码。不要提交真实 `.env`。

### 6.3 创建首个登录用户

V1.0 不提供公开注册，也不附带固定默认密码。部署人员必须通过受控初始化过程在 `users` 表创建首个 ACTIVE 管理员。

可在已激活的 Backend 虚拟环境中交互生成 bcrypt 哈希，避免在命令历史中写明文密码：

```powershell
python
```

```python
from getpass import getpass
from auth.password import hash_password
print(hash_password(getpass("Initial administrator password: ")))
```

将输出哈希作为参数写入 `users.password_hash`，并设置：

```text
role_code = ADMINISTRATOR
status = ACTIVE
```

禁止将明文密码写入数据库、SQL 文件、文档或 Git。首个账户创建完成后，应按组织安全规则保存凭据。

### 6.4 启动 Backend

开发/验收环境：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Linux/macOS：

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

生产环境不要启用 `--reload`，并应由进程管理器负责重启和日志：

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

### 6.5 Backend 验证

```text
GET http://127.0.0.1:8000/health
```

预期响应：

```json
{"status":"ok"}
```

`/health` 只确认应用进程，不访问数据库。还应使用有效账号登录并访问一个受保护查询接口，以验证数据库和认证链路。

开发环境可查看：

```text
http://127.0.0.1:8000/docs
```

生产环境是否公开 OpenAPI 文档应由部署方根据安全要求控制；当前代码未内置关闭开关。

## 7. Frontend 配置与启动

### 7.1 安装依赖

```powershell
cd frontend
npm install
```

若验收要求严格复现 lockfile，且仓库中存在有效 `package-lock.json`，可使用：

```powershell
npm ci
```

不要在验收部署过程中无目的升级依赖。

### 7.2 API 地址配置

Frontend 读取：

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

该值来自 `frontend/.env.example`，属于 Vite 构建时配置。若不设置，Axios 默认使用相对路径 `/api/v1`。

本地开发推荐使用以下二选一方式：

1. 不创建 Frontend `.env`，使用 Vite 已配置的 `/api` → `http://127.0.0.1:8000` 代理；
2. 设置 `VITE_API_BASE_URL` 指向可访问且已正确处理跨域的 API。

当前 Backend 未配置通用 CORS Middleware，因此直接从 `localhost:5173` 调用 `localhost:8000` 可能被浏览器视为跨域。验收环境推荐使用 Vite 代理；生产环境推荐使用同源反向代理。

### 7.3 启动开发服务器

```powershell
cd frontend
npm run dev
```

默认访问：

```text
http://localhost:5173
```

### 7.4 类型检查与生产构建

```powershell
npm exec vue-tsc -- --noEmit
npm run build
```

构建输出目录：

```text
frontend/dist/
```

本地预览构建结果：

```powershell
npm run preview
```

Vite 的 chunk-size warning 为构建提示，不等同于构建失败；验收应以命令退出状态和页面功能验证为准。

## 8. 生产部署建议

### 8.1 推荐拓扑

```text
Browser
   ↓ HTTPS
Nginx / IIS / Equivalent Reverse Proxy
   ├── /              → frontend/dist
   ├── /api/          → http://127.0.0.1:8000/api/
   └── /health        → http://127.0.0.1:8000/health
                              ↓
                           MySQL 8
```

### 8.2 Vue Router History 回退

前端使用 `createWebHistory`。静态服务器必须将 `/dashboard`、`/reports`、`/dramas/...` 等未知静态路径回退到 `index.html`，否则浏览器直接刷新业务路由会返回 404。

### 8.3 API 反向代理

推荐前端和 API 使用同一域名：

```text
https://example.test/       → Frontend
https://example.test/api/   → Backend
```

反向代理应保留下载响应的 `Content-Type`、`Content-Disposition`、`Content-Length` 和 `X-*` 报告头，不缓冲或截断大于普通 JSON 的 CSV/XLSX 响应。

### 8.4 TLS 与 Secret

- 对外环境必须使用 HTTPS；
- `SECRET_KEY` 使用独立随机值，不同环境不得复用；
- 数据库账号采用最小必要权限；
- `.env` 只对运行账户可读；
- 不在前端配置数据库密码或 JWT Secret；
- 不将生产数据库暴露给浏览器或公网。

## 9. 测试命令

Backend：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Frontend：

```powershell
cd frontend
npm exec vue-tsc -- --noEmit
npm run build
```

全量 Backend 测试可能包含工作区既有兼容性或环境依赖问题。部署验收应记录失败用例、复现条件和是否属于本次变更，不应通过修改生产代码掩盖测试环境问题。

## 10. 启动顺序

推荐验收环境启动顺序：

1. 启动 MySQL 8；
2. 确认 V001–V013 已按顺序初始化；
3. 确认至少一个 ACTIVE 登录用户；
4. 配置并启动 Backend；
5. 请求 `/health`；
6. 启动 Frontend 或部署 `dist`；
7. 使用浏览器登录；
8. 依次验证 Dashboard、Profile、Operation Analytics、Data Governance 和 Reports。

## 11. 常见问题

### 11.1 Backend 启动时提示 SECRET_KEY

检查 `backend/.env` 是否存在，`SECRET_KEY` 是否至少 32 个字符。不要使用示例值部署生产环境。

### 11.2 数据库连接失败

检查 MySQL 服务、主机、端口、数据库名、用户名、密码和 URL 编码。确认应用账号有访问 `short_drama_analysis` 的权限。

### 11.3 表不存在或字段不存在

核对 V001–V013 是否全部按顺序执行。不要仅执行早期 DDL，也不要使用空 Alembic revision 目录代替 Migration。

### 11.4 前端 API 请求失败

检查 `VITE_API_BASE_URL`、Vite Proxy、反向代理和 Backend 端口。浏览器 Network 面板中的请求地址应以 `/api/v1` 为业务 API 前缀。

### 11.5 刷新业务路由返回 404

配置静态服务器将非文件路径回退到 `index.html`。

### 11.6 登录返回 401

检查用户是否存在、`status` 是否为 ACTIVE、密码是否与 bcrypt 哈希匹配，以及 Backend 的 `SECRET_KEY` 是否在运行期间发生变化。

### 11.7 报告导出被拒绝

检查 Filter、确认行数和导出格式。CSV 上限为 10,000 行，XLSX 上限为 5,000 行，文件上限为 25 MiB。V1 不支持绕过限制或后台异步导出。

## 12. 升级与数据保护

- 升级前备份数据库；
- 不重复执行不具备幂等保证的 Migration；
- 新 Migration 必须经独立 Migration Review；
- 不直接修改历史分析结果、Revision 或操作记录；
- Frontend/Backend 版本应成套部署；
- 回滚应用版本前确认数据库 Schema 兼容性；
- 当前项目不提供自动备份恢复工具，数据库备份由部署环境负责。
