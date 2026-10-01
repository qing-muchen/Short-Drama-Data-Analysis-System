"""Batch Import V1 detection, dependency validation, and atomicity tests."""

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

# Match the application's normal module loading order; the existing imports
# package exposes Service-backed symbols from its package initializer.
import main  # noqa: F401
from auth.dependencies import get_current_user
from main import app

from imports.batch import (
    BatchImportWriter,
    BatchReferenceProjection,
    BatchRelationValidator,
    BatchUploadStore,
    build_snapshot_validation_context,
    detect_batch_file_type,
)
from imports.importer import StagedImportStore
from imports.parser import ParsedFile, ParsedRow, parse_import_file
from imports.validator import ImportValidationContext, ImportValidator, ValidatedRecord
from services.batch_import_service import BatchImportService
from services.exceptions import PersistenceException

MASTER_HEADER = "entity_type,name,status,drama_code,description,episode_count,episode_duration_seconds,premiere_date\n"
MASTER_HEADER_WITH_IDS = (
    "entity_type,name,status,drama_code,description,episode_count,"
    "episode_duration_seconds,premiere_date,drama_id,actor_id,director_id,"
    "company_id,platform_id,tag_id\n"
)


def test_batch_file_types_are_detected_from_headers() -> None:
    samples = {
        "MASTER_DATA": MASTER_HEADER + "TAG,都市,ACTIVE,,,,,\n",
        "DRAMA_TAGS": "drama_code,tag_name,relation_status\nDRM001,都市,ACTIVE\n",
        "DRAMA_PLATFORMS": "drama_code,platform_name,platform_drama_code,online_at,status\nDRM001,平台,P001,2026-01-01T08:00:00+08:00,ONLINE\n",
        "SNAPSHOT": "drama_code,platform_name,snapshot_time,play_count,like_count,comment_count,favorite_count,share_count,ranking\nDRM001,平台,2026-01-02T08:00:00+08:00,10,1,1,1,1,1\n",
    }
    for expected, content in samples.items():
        assert detect_batch_file_type(
            filename=f"{expected.lower()}.csv", content=content.encode()
        ) == expected


def test_master_file_with_optional_primary_key_columns_is_detected() -> None:
    content = MASTER_HEADER_WITH_IDS + "TAG,霸总,ACTIVE,,,,,,,,,,,7\n"
    assert detect_batch_file_type(
        filename="master_with_ids.csv", content=content.encode()
    ) == "MASTER_DATA"


def test_existing_master_primary_key_is_skipped_before_insert_validation() -> None:
    parsed = parse_import_file(
        filename="master.csv",
        file_format="CSV",
        content=(MASTER_HEADER_WITH_IDS + "TAG,,ACTIVE,,,,,,,,,,,7\n").encode(),
        import_type="MASTER_DATA",
    )
    result = ImportValidator().validate(
        parsed,
        import_type="MASTER_DATA",
        context=ImportValidationContext(
            existing_master_primary_keys={"TAG": frozenset({7})},
            use_master_primary_keys=True,
            skip_existing_master_data=True,
        ),
    )
    assert result.valid_rows == 0
    assert result.skipped_rows == 1
    assert result.error_rows == 0
    assert result.skipped_records[0].status == "SKIPPED_EXISTING"
    assert result.skipped_records[0].reason == "Already exists"


@pytest.mark.parametrize(
    ("entity_type", "primary_key_field"),
    [
        ("DRAMA", "drama_id"),
        ("ACTOR", "actor_id"),
        ("DIRECTOR", "director_id"),
        ("COMPANY", "company_id"),
        ("PLATFORM", "platform_id"),
        ("TAG", "tag_id"),
    ],
)
def test_all_master_entity_primary_keys_use_the_same_skip_rule(
    entity_type: str,
    primary_key_field: str,
) -> None:
    parsed = ParsedFile(
        original_filename="master.csv",
        file_format="CSV",
        headers=("entity_type", "name", primary_key_field),
        rows=(
            ParsedRow(
                source_row_number=2,
                values={
                    "entity_type": entity_type,
                    "name": "existing",
                    primary_key_field: "17",
                },
            ),
        ),
    )
    result = ImportValidator().validate(
        parsed,
        import_type="MASTER_DATA",
        context=ImportValidationContext(
            existing_master_primary_keys={entity_type: frozenset({17})},
            use_master_primary_keys=True,
            skip_existing_master_data=True,
        ),
    )

    assert result.valid_rows == 0
    assert result.skipped_rows == 1
    assert result.error_rows == 0
    assert result.skipped_records[0].identity_field == primary_key_field


def test_new_explicit_master_primary_key_remains_insertable() -> None:
    parsed = parse_import_file(
        filename="master.csv",
        file_format="CSV",
        content=(MASTER_HEADER_WITH_IDS + "TAG,甜宠,ACTIVE,,,,,,,,,,,91\n").encode(),
        import_type="MASTER_DATA",
    )
    result = ImportValidator().validate(
        parsed,
        import_type="MASTER_DATA",
        context=ImportValidationContext(
            existing_master_primary_keys={"TAG": frozenset()},
            use_master_primary_keys=True,
            skip_existing_master_data=True,
        ),
    )
    assert result.valid_rows == 1
    assert result.skipped_rows == 0
    assert result.error_rows == 0
    assert result.records[0].values["tag_id"] == 91


def test_existing_master_business_key_is_skipped_without_import_error() -> None:
    parsed = parse_import_file(
        filename="master.csv",
        file_format="CSV",
        content=(MASTER_HEADER + "TAG,霸总,ACTIVE,,,,,\n").encode(),
        import_type="MASTER_DATA",
    )
    result = ImportValidator().validate(
        parsed,
        import_type="MASTER_DATA",
        context=ImportValidationContext(
            existing_tag_names=frozenset({"霸总"}),
            use_master_primary_keys=True,
            skip_existing_master_data=True,
        ),
    )
    assert result.valid_rows == 0
    assert result.skipped_rows == 1
    assert result.error_rows == 0
    assert result.errors == ()
    assert result.skipped_records[0].status == "SKIPPED_EXISTING"


def test_batch_routes_are_registered_and_admin_only() -> None:
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/import/batches"]) == {"post"}
    assert set(paths["/api/v1/import/batches/{import_batch_id}/files"]) == {"post"}
    assert set(paths["/api/v1/import/batches/{import_batch_id}/validate"]) == {"post"}
    assert set(paths["/api/v1/import/batches/{import_batch_id}/confirm"]) == {"post"}
    assert set(paths["/api/v1/import/batches/{import_batch_id}"]) == {"get"}

    async def request() -> int:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return (await client.get("/api/v1/import/batches/1")).status_code

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        user_id=1, role_code="USER", status="ACTIVE"
    )
    try:
        assert asyncio.run(request()) == 403
    finally:
        app.dependency_overrides.clear()


def test_relationships_and_snapshots_resolve_projected_batch_references() -> None:
    projection = BatchReferenceProjection(
        dramas={"drm001": {"id": None, "status": "SERIALIZING"}},
        platforms={"平台": {"id": None, "status": "ACTIVE"}},
        tags={"都市": {"id": None, "status": "ACTIVE"}},
    )
    tag_content = b"drama_code,tag_name,relation_status\nDRM001,\xe9\x83\xbd\xe5\xb8\x82,ACTIVE\n"
    platform_content = (
        "drama_code,platform_name,platform_drama_code,online_at,status\n"
        "DRM001,平台,P001,2026-01-01T08:00:00+08:00,ONLINE\n"
    ).encode()
    tag_result = BatchRelationValidator().validate(
        parse_import_file(
            filename="tags.csv", file_format="CSV", content=tag_content, import_type="DRAMA_TAGS"
        ),
        file_type="DRAMA_TAGS",
        projection=projection,
    )
    platform_result = BatchRelationValidator().validate(
        parse_import_file(
            filename="platforms.csv",
            file_format="CSV",
            content=platform_content,
            import_type="DRAMA_PLATFORMS",
        ),
        file_type="DRAMA_PLATFORMS",
        projection=projection,
    )
    assert tag_result.valid_rows == 1 and not tag_result.errors
    assert platform_result.valid_rows == 1 and not platform_result.errors

    snapshot_content = (
        "drama_code,platform_name,snapshot_time,play_count,like_count,comment_count,"
        "favorite_count,share_count,ranking\n"
        "DRM001,平台,2026-01-02T08:00:00+08:00,100,10,2,3,1,1\n"
    ).encode()
    snapshot = parse_import_file(
        filename="snapshots.csv",
        file_format="CSV",
        content=snapshot_content,
        import_type="SNAPSHOT",
    )
    context = build_snapshot_validation_context(
        database_releases={},
        projected_releases=platform_result.records,
        projection=projection,
        existing_snapshot_keys=frozenset(),
    )
    result = ImportValidator().validate(snapshot, import_type="SNAPSHOT", context=context)
    assert result.valid_rows == 1 and result.records[0].values["drama_platform_id"] < 0


class WriterData:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.order: list[str] = []
        self.master_values: list[tuple[str, dict[str, Any]]] = []

    def create_masters(self, values: Any) -> None:
        self.order.append("MASTER_DATA")
        self.master_values.extend(values)
        if self.fail:
            raise SQLAlchemyError("forced failure")

    def resolve_drama_ids(self, _values: Any) -> dict[str, int]:
        return {"drm001": 1}

    def resolve_tag_ids(self, _values: Any) -> dict[str, int]:
        return {"都市": 2}

    def resolve_platform_ids(self, _values: Any) -> dict[str, int]:
        return {"平台": 3}

    def create_drama_tags(self, _values: Any) -> None:
        self.order.append("DRAMA_TAGS")

    def create_drama_platforms(self, _values: Any) -> None:
        self.order.append("DRAMA_PLATFORMS")

    def snapshot_release_context(self, **_kwargs: Any) -> dict[Any, Any]:
        return {("drm001", "平台"): {"drama_status": "SERIALIZING", "platform_status": "ACTIVE", "drama_platform_id": 4, "release_status": "ONLINE"}}

    def existing_snapshot_keys(self, **_kwargs: Any) -> set[Any]:
        return set()

    def create_initial_snapshots(self, _values: Any, **_kwargs: Any) -> None:
        self.order.append("SNAPSHOT")


def staged(entity_type: str, values: dict[str, Any]) -> dict[str, Any]:
    return {"source_row_number": 2, "entity_type": entity_type, "values": values}


def test_batch_writer_uses_dependency_order() -> None:
    data = WriterData()
    files = [
        (1, "MASTER_DATA", [staged("DRAMA", {"drama_code": "DRM001", "drama_name": "剧", "status": "SERIALIZING"})]),
        (2, "DRAMA_TAGS", [staged("DRAMA_TAGS", {"drama_code": "DRM001", "tag_name": "都市", "relation_status": "ACTIVE"})]),
        (3, "DRAMA_PLATFORMS", [staged("DRAMA_PLATFORMS", {"drama_code": "DRM001", "platform_name": "平台", "platform_drama_code": "P1", "online_at": "2026-01-01T00:00:00", "status": "ONLINE"})]),
        (4, "SNAPSHOT", [staged("SNAPSHOT", {"drama_code": "DRM001", "platform_name": "平台", "drama_platform_id": -1, "snapshot_time": "2026-01-02T00:00:00", "play_count": 1, "like_count": 1, "comment_count": 0, "favorite_count": 0, "share_count": 0, "ranking": 1})]),
    ]
    counts = BatchImportWriter(data).write(files=files, administrator_id=1)  # type: ignore[arg-type]
    assert data.order == ["MASTER_DATA", "DRAMA_TAGS", "DRAMA_PLATFORMS", "SNAPSHOT"]
    assert counts == {1: 1, 2: 1, 3: 1, 4: 1}


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeBatchRepository:
    def __init__(self, session: FakeSession, batch: SimpleNamespace) -> None:
        self.session = session
        self.batch = batch

    def get_by_id(self, _identifier: int) -> SimpleNamespace:
        return self.batch

    def claim_status(self, _identifier: int, expected: str, next_status: str) -> bool:
        if self.batch.status != expected:
            return False
        self.batch.status = next_status
        return True

    def update(self, _identifier: int, values: dict[str, Any]) -> SimpleNamespace:
        for key, value in values.items():
            setattr(self.batch, key, value)
        return self.batch


class FakeJobRepository:
    def __init__(self, session: FakeSession, jobs: list[SimpleNamespace]) -> None:
        self.session = session
        self.jobs = jobs

    def list_by_batch(self, _identifier: int) -> list[SimpleNamespace]:
        return self.jobs

    def update(self, identifier: int, values: dict[str, Any]) -> SimpleNamespace:
        job = next(item for item in self.jobs if item.import_job_id == identifier)
        for key, value in values.items():
            setattr(job, key, value)
        return job


class FakeErrors:
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.rows: list[dict[str, Any]] = []

    def create(self, values: dict[str, Any]) -> SimpleNamespace:
        self.rows.append(values)
        return SimpleNamespace(**values)

    def create_many(self, values: list[dict[str, Any]]) -> list[SimpleNamespace]:
        return [self.create(item) for item in values]


class ValidationData:
    def __init__(
        self,
        session: FakeSession,
        *,
        existing_tag_names: set[str] | None = None,
        existing_primary_keys: dict[str, set[int]] | None = None,
    ) -> None:
        self.session = session
        self.existing_tag_names = existing_tag_names or set()
        self.existing_primary_keys = existing_primary_keys or {}

    def master_uniqueness_context(self) -> tuple[set[str], set[str], set[str]]:
        return set(), set(), self.existing_tag_names

    def existing_master_primary_keys(
        self, requested: dict[str, set[int]]
    ) -> dict[str, set[int]]:
        return {
            entity_type: set(values).intersection(requested.get(entity_type, set()))
            for entity_type, values in self.existing_primary_keys.items()
        }

    def batch_reference_context(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "dramas": {}, "platforms": {}, "tags": {},
            "drama_tag_pairs": set(), "drama_platform_pairs": set(),
            "platform_external_codes": set(),
        }

    def snapshot_release_context(self, **_kwargs: Any) -> dict[Any, Any]:
        return {}

    def existing_snapshot_keys(self, **_kwargs: Any) -> set[Any]:
        return set()


def test_batch_service_validates_all_four_phases_with_projected_references(tmp_path: Path) -> None:
    session = FakeSession()
    contents = {
        "MASTER_DATA": (
            MASTER_HEADER
            + "DRAMA,示例剧,SERIALIZING,DRM001,,12,120,2026-01-01\n"
            + "PLATFORM,平台,ACTIVE,,,,,\n"
            + "TAG,都市,ACTIVE,,,,,\n"
        ).encode(),
        "DRAMA_TAGS": "drama_code,tag_name,relation_status\nDRM001,都市,ACTIVE\n".encode(),
        "DRAMA_PLATFORMS": (
            "drama_code,platform_name,platform_drama_code,online_at,status\n"
            "DRM001,平台,P001,2026-01-01T08:00:00+08:00,ONLINE\n"
        ).encode(),
        "SNAPSHOT": (
            "drama_code,platform_name,snapshot_time,play_count,like_count,comment_count,"
            "favorite_count,share_count,ranking\n"
            "DRM001,平台,2026-01-02T08:00:00+08:00,100,10,2,3,1,1\n"
        ).encode(),
    }
    jobs = [
        SimpleNamespace(
            import_job_id=index,
            batch_file_type=file_type,
            original_filename=f"{file_type.lower()}.csv",
            file_hash=hashlib.sha256(content).hexdigest(),
            status="PENDING_VALIDATION",
            started_at=None,
        )
        for index, (file_type, content) in enumerate(contents.items(), start=1)
    ]
    batch = SimpleNamespace(import_batch_id=1, status="UPLOADING", files=jobs)
    uploads = BatchUploadStore(tmp_path / "uploads")
    stages = StagedImportStore(tmp_path / "stages")
    for job, content in zip(jobs, contents.values()):
        uploads.save(import_job_id=job.import_job_id, content=content)
    service = BatchImportService(
        session,  # type: ignore[arg-type]
        FakeBatchRepository(session, batch),  # type: ignore[arg-type]
        FakeJobRepository(session, jobs),  # type: ignore[arg-type]
        FakeErrors(session),  # type: ignore[arg-type]
        ValidationData(session),  # type: ignore[arg-type]
        stage_store=stages,
        upload_store=uploads,
    )
    result = service.validate_batch(1, administrator_id=1)
    assert result.status == "READY"
    assert all(job.status == "READY" for job in jobs)
    assert all((tmp_path / "stages" / f"{job.import_job_id}.json").exists() for job in jobs)


def _master_batch_service(
    tmp_path: Path,
    content: bytes,
    data: ValidationData,
) -> tuple[BatchImportService, SimpleNamespace, SimpleNamespace, FakeErrors, StagedImportStore]:
    source_hash = hashlib.sha256(content).hexdigest()
    job = SimpleNamespace(
        import_job_id=1,
        batch_file_type="MASTER_DATA",
        original_filename="master.csv",
        file_hash=source_hash,
        status="PENDING_VALIDATION",
        started_at=None,
        total_rows=0,
        valid_rows=0,
        error_rows=0,
        imported_rows=0,
    )
    batch = SimpleNamespace(
        import_batch_id=1,
        status="UPLOADING",
        files=[job],
        total_rows=0,
        valid_rows=0,
        error_rows=0,
        imported_rows=0,
    )
    uploads = BatchUploadStore(tmp_path / "uploads")
    uploads.save(import_job_id=job.import_job_id, content=content)
    stages = StagedImportStore(tmp_path / "stages")
    errors = FakeErrors(data.session)
    service = BatchImportService(
        data.session,  # type: ignore[arg-type]
        FakeBatchRepository(data.session, batch),  # type: ignore[arg-type]
        FakeJobRepository(data.session, [job]),  # type: ignore[arg-type]
        errors,  # type: ignore[arg-type]
        data,  # type: ignore[arg-type]
        stage_store=stages,
        upload_store=uploads,
    )
    return service, batch, job, errors, stages


def test_batch_with_all_existing_primary_keys_is_ready_and_stages_nothing(
    tmp_path: Path,
) -> None:
    content = (MASTER_HEADER_WITH_IDS + "TAG,霸总,ACTIVE,,,,,,,,,,,7\n").encode()
    session = FakeSession()
    data = ValidationData(session, existing_primary_keys={"TAG": {7}})
    service, batch, job, errors, stages = _master_batch_service(tmp_path, content, data)

    result = service.validate_batch(1, administrator_id=1)

    assert result.status == batch.status == "READY"
    assert (job.total_rows, job.valid_rows, job.error_rows) == (1, 0, 0)
    assert job.total_rows - job.valid_rows - job.error_rows == 1
    assert errors.rows == []
    assert stages.load(
        import_job_id=1,
        import_type="MASTER_DATA",
        source_file_hash=job.file_hash,
    ) == []


def test_batch_business_duplicate_is_skipped_and_only_new_row_is_inserted(
    tmp_path: Path,
) -> None:
    content = (
        MASTER_HEADER
        + "TAG,霸总,ACTIVE,,,,,\n"
        + "TAG,甜宠,ACTIVE,,,,,\n"
    ).encode()
    session = FakeSession()
    validation_data = ValidationData(session, existing_tag_names={"霸总"})
    service, batch, job, errors, _ = _master_batch_service(
        tmp_path, content, validation_data
    )

    validated = service.validate_batch(1, administrator_id=1)
    assert validated.status == "READY"
    assert (job.total_rows, job.valid_rows, job.error_rows) == (2, 1, 0)
    assert errors.rows == []

    writer_data = WriterData()
    writer_data.session = session  # type: ignore[attr-defined]
    service.data = writer_data  # type: ignore[assignment]
    completed = service.confirm_batch(1, administrator_id=1)

    assert completed.status == batch.status == "COMPLETED"
    assert job.imported_rows == 1
    assert writer_data.master_values == [
        ("TAG", {"tag_name": "甜宠", "status": "ACTIVE"})
    ]


def test_batch_with_real_invalid_master_data_fails_validation(tmp_path: Path) -> None:
    content = (MASTER_HEADER + "TAG,,ACTIVE,,,,,\n").encode()
    session = FakeSession()
    data = ValidationData(session)
    service, batch, job, errors, _ = _master_batch_service(tmp_path, content, data)

    result = service.validate_batch(1, administrator_id=1)

    assert result.status == batch.status == "VALIDATION_FAILED"
    assert (job.total_rows, job.valid_rows, job.error_rows) == (1, 0, 1)
    assert len(errors.rows) == 1
    assert errors.rows[0]["error_code"] == "MISSING_REQUIRED_DATA"


def test_confirm_failure_rolls_back_business_transaction_and_marks_batch_failed(tmp_path: Path) -> None:
    session = FakeSession()
    job = SimpleNamespace(import_job_id=1, batch_file_type="MASTER_DATA", file_hash="a" * 64, status="READY")
    batch = SimpleNamespace(import_batch_id=1, status="READY", files=[job])
    stages = StagedImportStore(tmp_path / "stages")
    stages.save(
        import_job_id=1,
        import_type="MASTER_DATA",
        source_file_hash="a" * 64,
        records=(ValidatedRecord(2, "TAG", {"tag_name": "都市", "status": "ACTIVE"}),),
    )
    data = WriterData(fail=True)
    data.session = session  # type: ignore[attr-defined]
    service = BatchImportService(
        session,  # type: ignore[arg-type]
        FakeBatchRepository(session, batch),  # type: ignore[arg-type]
        FakeJobRepository(session, [job]),  # type: ignore[arg-type]
        FakeErrors(session),  # type: ignore[arg-type]
        data,  # type: ignore[arg-type]
        stage_store=stages,
        upload_store=BatchUploadStore(tmp_path / "uploads"),
    )
    with pytest.raises(PersistenceException):
        service.confirm_batch(1, administrator_id=1)
    assert session.rollbacks == 1
    assert batch.status == "IMPORT_FAILED"
    assert job.status == "FAILED"
    assert not (tmp_path / "stages" / "1.json").exists()
