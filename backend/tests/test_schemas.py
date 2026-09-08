"""DTO boundary tests without HTTP or database side effects."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from models import (
    Actor,
    Company,
    DataQualityIssue,
    Director,
    Drama,
    DramaActor,
    DramaCompany,
    DramaDirector,
    DramaMetricSnapshot,
    DramaMetricSnapshotRevision,
    DramaPlatform,
    DramaTag,
    ImportError,
    ImportJob,
    OperationLog,
    Platform,
    Tag,
    User,
)
from schemas import (
    ActorCreate,
    ActorResponse,
    ActorUpdate,
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    DataQualityIssueCreate,
    DataQualityIssueResponse,
    DataQualityIssueUpdate,
    DirectorCreate,
    DirectorResponse,
    DirectorUpdate,
    DramaActorCreate,
    DramaActorResponse,
    DramaActorUpdate,
    DramaCompanyCreate,
    DramaCompanyResponse,
    DramaCompanyUpdate,
    DramaCreate,
    DramaDirectorCreate,
    DramaDirectorResponse,
    DramaDirectorUpdate,
    DramaMetricSnapshotCreate,
    DramaMetricSnapshotResponse,
    DramaMetricSnapshotRevisionCreate,
    DramaMetricSnapshotRevisionResponse,
    DramaMetricSnapshotRevisionUpdate,
    DramaMetricSnapshotUpdate,
    DramaPlatformCreate,
    DramaPlatformResponse,
    DramaPlatformUpdate,
    DramaResponse,
    DramaTagCreate,
    DramaTagResponse,
    DramaTagUpdate,
    DramaUpdate,
    ImportErrorCreate,
    ImportErrorResponse,
    ImportErrorUpdate,
    ImportJobCreate,
    ImportJobResponse,
    ImportJobUpdate,
    OperationLogCreate,
    OperationLogResponse,
    OperationLogUpdate,
    PageResponse,
    PlatformCreate,
    PlatformResponse,
    PlatformUpdate,
    TagCreate,
    TagResponse,
    TagUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)

SCHEMA_MODEL_PAIRS = (
    ((UserCreate, UserUpdate, UserResponse), User),
    ((DramaCreate, DramaUpdate, DramaResponse), Drama),
    ((ActorCreate, ActorUpdate, ActorResponse), Actor),
    ((DirectorCreate, DirectorUpdate, DirectorResponse), Director),
    ((CompanyCreate, CompanyUpdate, CompanyResponse), Company),
    ((PlatformCreate, PlatformUpdate, PlatformResponse), Platform),
    ((TagCreate, TagUpdate, TagResponse), Tag),
    ((DramaActorCreate, DramaActorUpdate, DramaActorResponse), DramaActor),
    ((DramaDirectorCreate, DramaDirectorUpdate, DramaDirectorResponse), DramaDirector),
    ((DramaCompanyCreate, DramaCompanyUpdate, DramaCompanyResponse), DramaCompany),
    ((DramaTagCreate, DramaTagUpdate, DramaTagResponse), DramaTag),
    ((DramaPlatformCreate, DramaPlatformUpdate, DramaPlatformResponse), DramaPlatform),
    (
        (DramaMetricSnapshotCreate, DramaMetricSnapshotUpdate, DramaMetricSnapshotResponse),
        DramaMetricSnapshot,
    ),
    (
        (
            DramaMetricSnapshotRevisionCreate,
            DramaMetricSnapshotRevisionUpdate,
            DramaMetricSnapshotRevisionResponse,
        ),
        DramaMetricSnapshotRevision,
    ),
    ((ImportJobCreate, ImportJobUpdate, ImportJobResponse), ImportJob),
    ((ImportErrorCreate, ImportErrorUpdate, ImportErrorResponse), ImportError),
    (
        (DataQualityIssueCreate, DataQualityIssueUpdate, DataQualityIssueResponse),
        DataQualityIssue,
    ),
    ((OperationLogCreate, OperationLogUpdate, OperationLogResponse), OperationLog),
)


def test_all_entity_schema_fields_come_from_orm_columns() -> None:
    """DTOs may expose subsets, but never fields invented outside the ORM contract."""

    for schema_group, orm_model in SCHEMA_MODEL_PAIRS:
        orm_columns = set(orm_model.__table__.columns.keys())
        for schema_type in schema_group:
            assert set(schema_type.model_fields) <= orm_columns


def test_response_schemas_support_from_attributes() -> None:
    for schema_group, _ in SCHEMA_MODEL_PAIRS:
        response_type = schema_group[-1]
        assert response_type.model_config["from_attributes"] is True


def test_user_response_converts_from_orm_without_credentials() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    orm_user = User(
        user_id=1,
        username="analyst",
        password_hash="never-expose-this",
        display_name="Analyst",
        role_code="USER",
        status="ACTIVE",
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )

    dto = UserResponse.model_validate(orm_user)

    assert dto.username == "analyst"
    assert "password_hash" not in dto.model_dump()


def test_basic_validation_and_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DramaCreate(drama_name="   ")
    with pytest.raises(ValidationError):
        DramaCreate(drama_name="Sample", status="UNKNOWN")
    with pytest.raises(ValidationError):
        DramaCreate(drama_name="Sample", heat_score=90)
    with pytest.raises(ValidationError):
        UserCreate(username="user", password_hash="client-value")


def test_page_response_preserves_typed_items() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    page = PageResponse[DramaResponse](
        page=1,
        page_size=20,
        total=1,
        items=[
            {
                "drama_id": 1,
                "drama_code": "DRM000001",
                "drama_name": "Sample Drama",
                "status": "DRAFT",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    assert page.total == 1
    assert isinstance(page.items[0], DramaResponse)


def test_quality_issue_requires_exactly_one_real_target() -> None:
    payload = {
        "issue_type": "CUMULATIVE_REGRESSION",
        "severity": "WARNING",
        "source": "STATISTICAL_DETECTION",
        "rule_code": "QUALITY-001",
        "evidence_summary": "play_count decreased",
        "first_detected_at": datetime.now(UTC),
        "last_detected_at": datetime.now(UTC),
    }

    with pytest.raises(ValidationError):
        DataQualityIssueCreate(**payload)
    with pytest.raises(ValidationError):
        DataQualityIssueCreate(
            **payload,
            target_drama_id=1,
            target_drama_platform_id=1,
        )

    dto = DataQualityIssueCreate(**payload, target_snapshot_revision_id=1)
    assert dto.target_snapshot_revision_id == 1


def test_operation_log_requires_one_target_and_never_accepts_secrets() -> None:
    payload = {
        "operation_type": "DRAMA_UPDATE",
        "result_status": "SUCCESS",
        "summary": "Updated drama metadata",
    }

    with pytest.raises(ValidationError):
        OperationLogCreate(**payload)
    with pytest.raises(ValidationError):
        OperationLogCreate(**payload, target_drama_id=1, target_user_id=1)
    with pytest.raises(ValidationError):
        OperationLogCreate(**payload, target_drama_id=1, token="secret")

    dto = OperationLogCreate(**payload, target_drama_id=1)
    assert dto.target_drama_id == 1


def test_snapshot_slot_and_revision_write_boundaries_remain_separate() -> None:
    now = datetime.now(UTC)
    slot = DramaMetricSnapshotCreate(drama_platform_id=1, snapshot_time=now)
    revision = DramaMetricSnapshotRevisionCreate(play_count=100, like_count=10)

    assert slot.drama_platform_id == 1
    assert revision.play_count == 100
    with pytest.raises(ValidationError):
        DramaMetricSnapshotCreate(
            drama_platform_id=1,
            snapshot_time=now,
            current_revision_id=2,
        )
    with pytest.raises(ValidationError):
        DramaMetricSnapshotRevisionCreate(play_count=100, version_no=2)
    with pytest.raises(ValidationError):
        DramaMetricSnapshotRevisionUpdate(play_count=100)
