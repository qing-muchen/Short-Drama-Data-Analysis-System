"""Import parsing, validation, transaction, and authorization tests."""

import asyncio
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy.exc import SQLAlchemyError

from auth.dependencies import get_current_user
from imports.importer import StagedImportStore
from imports.parser import ImportFileError, parse_import_file
from imports.validator import ImportValidationContext, ImportValidator
from main import app
from repositories.base import Page
from routers.dependencies import get_import_service
from schemas.import_job import ImportJobCreate
from services.exceptions import PersistenceException
from services.import_service import ImportService

MASTER_HEADER = (
    "entity_type,name,status,drama_code,description,episode_count,"
    "episode_duration_seconds,premiere_date\n"
)


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeJobRepository:
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.rows: dict[int, SimpleNamespace] = {}

    def create(self, values: dict[str, Any]) -> SimpleNamespace:
        now = datetime.now(UTC).replace(tzinfo=None)
        entity = SimpleNamespace(
            import_job_id=len(self.rows) + 1,
            created_at=now,
            updated_at=now,
            **values,
        )
        self.rows[entity.import_job_id] = entity
        return entity

    def get_by_id(self, entity_id: int) -> SimpleNamespace | None:
        return self.rows.get(entity_id)

    def update(self, entity_id: int, values: dict[str, Any]) -> SimpleNamespace | None:
        entity = self.rows.get(entity_id)
        if entity is not None:
            for key, value in values.items():
                setattr(entity, key, value)
            entity.updated_at = datetime.now(UTC).replace(tzinfo=None)
        return entity

    def claim_ready(self, entity_id: int) -> bool:
        entity = self.rows.get(entity_id)
        if entity is None or entity.status != "READY":
            return False
        entity.status = "IMPORTING"
        return True


class FakeErrorRepository:
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.rows: list[SimpleNamespace] = []

    def create(self, values: dict[str, Any]) -> SimpleNamespace:
        entity = self._entity(values)
        self.rows.append(entity)
        return entity

    def create_many(self, values: list[dict[str, Any]]) -> list[SimpleNamespace]:
        return [self.create(item) for item in values]

    def list_by_job(self, import_job_id: int, *, page: int, page_size: int) -> Page[Any]:
        rows = [item for item in self.rows if item.import_job_id == import_job_id]
        return Page(page=page, page_size=page_size, total=len(rows), items=rows)

    def _entity(self, values: dict[str, Any]) -> SimpleNamespace:
        return SimpleNamespace(
            import_error_id=len(self.rows) + 1,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            **values,
        )


class FakeDataRepository:
    def __init__(self, session: FakeSession, *, fail_write: bool = False) -> None:
        self.session = session
        self.fail_write = fail_write
        self.created: list[tuple[str, dict[str, Any]]] = []

    def master_uniqueness_context(self) -> tuple[set[str], set[str], set[str]]:
        return set(), set(), set()

    def snapshot_release_context(self, **_kwargs: Any) -> dict[Any, Any]:
        return {
            ("drm000001", "platform one"): {
                "drama_status": "SERIALIZING",
                "platform_status": "ACTIVE",
                "drama_platform_id": 9,
                "release_status": "ONLINE",
            }
        }

    def existing_snapshot_keys(self, **_kwargs: Any) -> set[Any]:
        return set()

    def create_master(self, entity_type: str, values: dict[str, Any]) -> None:
        if self.fail_write:
            raise SQLAlchemyError("test database failure")
        self.created.append((entity_type, values))

    def get_release_state(self, drama_platform_id: int) -> dict[str, str] | None:
        if drama_platform_id != 9:
            return None
        return {
            "drama_status": "SERIALIZING",
            "platform_status": "ACTIVE",
            "release_status": "ONLINE",
        }

    def snapshot_exists(self, **_kwargs: Any) -> bool:
        return False

    def create_initial_snapshot(self, *, values: dict[str, Any], **_kwargs: Any) -> None:
        if self.fail_write:
            raise SQLAlchemyError("test database failure")
        self.created.append(("SNAPSHOT", values))


class FakeOperationLogRepository:
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.rows: list[SimpleNamespace] = []

    def create(self, values: dict[str, Any]) -> SimpleNamespace:
        entity = SimpleNamespace(**values)
        self.rows.append(entity)
        return entity


def _service(tmp_path: Path, *, fail_write: bool = False) -> tuple[ImportService, Any, Any, Any]:
    session = FakeSession()
    jobs = FakeJobRepository(session)
    errors = FakeErrorRepository(session)
    data = FakeDataRepository(session, fail_write=fail_write)
    logs = FakeOperationLogRepository(session)
    service = ImportService(
        session,  # type: ignore[arg-type]
        jobs,  # type: ignore[arg-type]
        errors,  # type: ignore[arg-type]
        data,  # type: ignore[arg-type]
        logs,  # type: ignore[arg-type]
        stage_store=StagedImportStore(tmp_path / "stage"),
    )
    return service, jobs, errors, data


def _master_csv(*rows: str) -> bytes:
    return (MASTER_HEADER + "\n".join(rows) + "\n").encode("utf-8")


def test_csv_and_xlsx_fixed_templates_parse() -> None:
    csv_content = _master_csv("DRAMA,Sample,DRAFT,DRM000001,,12,120,2026-01-01")
    parsed_csv = parse_import_file(
        filename="master.csv",
        file_format="CSV",
        content=csv_content,
        import_type="MASTER_DATA",
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(MASTER_HEADER.strip().split(","))
    sheet.append(["ACTOR", "Actor One", "ACTIVE", None, None, None, None, None])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    parsed_xlsx = parse_import_file(
        filename="master.xlsx",
        file_format="XLSX",
        content=buffer.getvalue(),
        import_type="MASTER_DATA",
    )

    assert parsed_csv.rows[0].source_row_number == 2
    assert parsed_csv.rows[0].values["drama_code"] == "DRM000001"
    assert parsed_xlsx.rows[0].values["name"] == "Actor One"


def test_file_security_rejects_xls_path_traversal_and_fake_xlsx() -> None:
    with pytest.raises(ImportFileError, match="safe"):
        parse_import_file(
            filename="../master.csv",
            file_format="CSV",
            content=b"x",
            import_type="MASTER_DATA",
        )
    with pytest.raises(ImportFileError, match="Only matching"):
        parse_import_file(
            filename="master.xls",
            file_format="XLSX",
            content=b"x",
            import_type="MASTER_DATA",
        )
    with pytest.raises(ImportFileError, match="valid XLSX"):
        parse_import_file(
            filename="master.xlsx",
            file_format="XLSX",
            content=b"not-a-workbook",
            import_type="MASTER_DATA",
        )


def test_validation_records_row_errors_without_quality_issues() -> None:
    parsed = parse_import_file(
        filename="master.csv",
        file_format="CSV",
        content=_master_csv("DRAMA,Sample,UNKNOWN,DRM000001,,12,120,2026-01-01"),
        import_type="MASTER_DATA",
    )
    result = ImportValidator().validate(
        parsed,
        import_type="MASTER_DATA",
        context=ImportValidationContext(),
    )

    assert result.valid_rows == 0
    assert result.error_rows == 1
    assert result.errors[0].error_type == "FIELD_VALIDATION"


def test_file_level_failure_is_preserved_as_import_error(tmp_path: Path) -> None:
    service, _, errors, _ = _service(tmp_path)
    job = service.create_import_job(
        ImportJobCreate(
            import_type="MASTER_DATA",
            original_filename="empty.csv",
            file_format="CSV",
        ),
        content=b"",
        administrator_id=1,
    )

    assert job.status == "VALIDATION_FAILED"
    assert job.total_rows == 0 and job.error_rows == 0
    assert errors.rows[0].error_code == "EMPTY_FILE"
    assert errors.rows[0].source_row_number is None


def test_job_lifecycle_and_atomic_confirm(tmp_path: Path) -> None:
    service, jobs, errors, data = _service(tmp_path)
    request = ImportJobCreate(
        import_type="MASTER_DATA",
        original_filename="master.csv",
        file_format="CSV",
    )
    ready = service.create_import_job(
        request,
        content=_master_csv("DRAMA,Sample,DRAFT,DRM000001,,12,120,2026-01-01"),
        administrator_id=1,
    )
    completed = service.confirm_import(ready.import_job_id, administrator_id=1)

    assert ready.status == "COMPLETED"
    assert completed.status == "COMPLETED"
    assert completed.imported_rows == 1
    assert jobs.rows[1].status == "COMPLETED"
    assert errors.rows == []
    assert data.created[0][0] == "DRAMA"
    assert not (tmp_path / "stage" / "1.json").exists()


def test_partial_validation_errors_become_completed_with_errors(tmp_path: Path) -> None:
    service, _, errors, _ = _service(tmp_path)
    job = service.create_import_job(
        ImportJobCreate(
            import_type="MASTER_DATA",
            original_filename="master.csv",
            file_format="CSV",
        ),
        content=_master_csv(
            "DRAMA,Valid,DRAFT,DRM000001,,12,120,2026-01-01",
            "DRAMA,Invalid,UNKNOWN,DRM000002,,12,120,2026-01-01",
        ),
        administrator_id=1,
    )

    assert job.status == "READY"
    assert job.valid_rows == 1 and job.error_rows == 1
    assert errors.rows[0].source_row_number == 3
    result = service.confirm_import(job.import_job_id, administrator_id=1)
    assert result.status == "COMPLETED_WITH_ERRORS"
    assert result.imported_rows == 1


def test_snapshot_import_resolves_release_and_creates_initial_revision(tmp_path: Path) -> None:
    service, _, _, data = _service(tmp_path)
    content = (
        "drama_code,platform_name,snapshot_time,play_count,like_count,"
        "comment_count,favorite_count,share_count,ranking\n"
        "DRM000001,Platform One,2026-01-01T08:00:00+08:00,1000,100,20,30,10,1\n"
    ).encode("utf-8")

    ready = service.create_import_job(
        ImportJobCreate(
            import_type="SNAPSHOT",
            original_filename="snapshot.csv",
            file_format="CSV",
        ),
        content=content,
        administrator_id=1,
    )
    completed = service.confirm_import(ready.import_job_id, administrator_id=1)

    assert completed.status == "COMPLETED"
    assert data.created[0][0] == "SNAPSHOT"
    assert data.created[0][1]["drama_platform_id"] == 9
    assert data.created[0][1]["snapshot_time"].tzinfo is None


def test_formal_write_failure_rolls_back_and_marks_job_failed(tmp_path: Path) -> None:
    service, jobs, _, data = _service(tmp_path, fail_write=True)
    job = service.create_import_job(
        ImportJobCreate(
            import_type="MASTER_DATA",
            original_filename="master.csv",
            file_format="CSV",
        ),
        content=_master_csv("TAG,Urban,ACTIVE,,,,,"),
        administrator_id=1,
    )

    with pytest.raises(PersistenceException):
        service.confirm_import(job.import_job_id, administrator_id=1)

    assert jobs.rows[job.import_job_id].status == "FAILED"
    assert data.created == []
    assert service._session.rollbacks == 1


def _identity(role: str) -> SimpleNamespace:
    return SimpleNamespace(user_id=1, role_code=role, status="ACTIVE")


def _http_request(method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async def perform() -> tuple[int, Any]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.request(method, path, **kwargs)
            return response.status_code, response.json()

    return asyncio.run(perform())


def test_import_routes_are_admin_only() -> None:
    app.dependency_overrides[get_current_user] = lambda: _identity("USER")
    try:
        status_code, body = _http_request("GET", "/api/v1/import/jobs/1")
    finally:
        app.dependency_overrides.clear()

    assert status_code == 403
    assert body["code"] == "FORBIDDEN"


def test_import_routes_call_service_with_admin_identity() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    job = SimpleNamespace(
        import_job_id=1,
        initiated_by_user_id=7,
        import_type="MASTER_DATA",
        status="READY",
        original_filename="master.csv",
        file_format="CSV",
        file_hash="a" * 64,
        total_rows=1,
        valid_rows=1,
        error_rows=0,
        imported_rows=0,
        started_at=now,
        finished_at=None,
        created_at=now,
        updated_at=now,
    )

    class FakeImportService:
        def create_import_job(self, request: Any, **kwargs: Any) -> Any:
            assert request.file_format == "CSV"
            assert kwargs["administrator_id"] == 7
            return job

        def get_import_job(self, import_job_id: int) -> Any:
            assert import_job_id == 1
            return job

        def list_import_errors(self, import_job_id: int, **kwargs: Any) -> Page[Any]:
            assert import_job_id == 1 and kwargs["page"] == 1
            return Page(page=1, page_size=20, total=0, items=[])

        def confirm_import(self, import_job_id: int, **kwargs: Any) -> Any:
            assert import_job_id == 1 and kwargs["administrator_id"] == 7
            job.status = "COMPLETED"
            job.imported_rows = 1
            job.finished_at = now
            return job

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        user_id=7, role_code="ADMINISTRATOR", status="ACTIVE"
    )
    app.dependency_overrides[get_import_service] = FakeImportService
    try:
        create_status, _ = _http_request(
            "POST",
            "/api/v1/import/jobs",
            data={"import_type": "MASTER_DATA"},
            files={"file": ("master.csv", _master_csv("TAG,Urban,ACTIVE,,,,,"), "text/csv")},
        )
        get_status, _ = _http_request("GET", "/api/v1/import/jobs/1")
        errors_status, _ = _http_request("GET", "/api/v1/import/jobs/1/errors")
        confirm_status, confirm_body = _http_request(
            "POST", "/api/v1/import/jobs/1/confirm", json={"confirm": True}
        )
    finally:
        app.dependency_overrides.clear()

    assert (create_status, get_status, errors_status, confirm_status) == (201, 200, 200, 200)
    assert confirm_body["data"]["status"] == "COMPLETED"
