# FastAPI Backend Engineering Baseline

This directory contains the infrastructure-only backend baseline for the Short
Drama Data Management and Analysis System. TASK-P4-01 does not implement any
business model, CRUD operation, authentication flow, import flow, analytics
logic, or business API.

## Runtime baseline

- Python 3.12+
- FastAPI
- Pydantic v2 and pydantic-settings
- SQLAlchemy 2.x
- Alembic
- MySQL 8.x through PyMySQL
- pytest and HTTPX for the test baseline

## Directory responsibilities

| Path | Responsibility |
| --- | --- |
| `app/` | Future application assembly owned by explicit later tasks |
| `core/` | Cross-cutting infrastructure such as security and lifecycle hooks |
| `config/` | Typed environment-variable settings |
| `database/` | SQLAlchemy Base, lazy Engine, and session lifecycle |
| `models/` | Future ORM mappings of the frozen 18-table schema |
| `schemas/` | Future Pydantic request and response contracts |
| `repositories/` | Persistence operations; no HTTP concerns |
| `services/` | Business rules, transaction boundaries, and orchestration |
| `routers/` | HTTP protocol handling; no direct SQL |
| `tests/` | Automated backend tests |
| `alembic/` | Alembic integration baseline; currently no business revisions |

The required dependency direction is:

```text
Router -> Service -> Repository -> ORM / Database
```

Routers must not execute SQL or contain transaction/business rules. Services
own cross-row validation and transactions. Repositories own persistence access.
ORM mappings must follow `PROJECT_MASTER.md` and the frozen MySQL schema without
renaming or redesigning database objects for convenience.

## Local setup

Run these commands from `backend/` using a Python 3.12+ interpreter:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload
```

The example configuration contains placeholders only. Replace them in the
ignored local `.env`; never commit a real database password, Token, or Secret.
The health endpoint is available at `GET /health` and does not connect to the
database.

Run the infrastructure test with:

```powershell
python -m pytest
```

## Database and Alembic boundary

`database/` at the repository root contains the validated MySQL DDL and
Migration baseline. The backend `alembic/` directory is initialized only for
future ORM integration planning. It contains no business revision, and no
Alembic command should be used to alter or stamp a database until an explicit
task defines how Alembic will adopt the existing SQL baseline.
