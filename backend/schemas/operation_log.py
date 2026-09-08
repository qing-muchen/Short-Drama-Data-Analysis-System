"""Operation log DTOs with fixed real targets and no sensitive credentials."""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from schemas.common import SchemaModel

OperationResult = Literal["SUCCESS", "FAILURE"]

TARGET_FIELDS = (
    "target_user_id",
    "target_drama_id",
    "target_actor_id",
    "target_director_id",
    "target_company_id",
    "target_platform_id",
    "target_tag_id",
    "target_drama_actor_id",
    "target_drama_director_id",
    "target_drama_company_id",
    "target_drama_tag_id",
    "target_drama_platform_id",
    "target_snapshot_id",
    "target_snapshot_revision_id",
    "target_import_job_id",
    "target_data_quality_issue_id",
)


class OperationTargetMixin(SchemaModel):
    """Require exactly one of the frozen audit target foreign keys."""

    target_user_id: int | None = Field(default=None, ge=1)
    target_drama_id: int | None = Field(default=None, ge=1)
    target_actor_id: int | None = Field(default=None, ge=1)
    target_director_id: int | None = Field(default=None, ge=1)
    target_company_id: int | None = Field(default=None, ge=1)
    target_platform_id: int | None = Field(default=None, ge=1)
    target_tag_id: int | None = Field(default=None, ge=1)
    target_drama_actor_id: int | None = Field(default=None, ge=1)
    target_drama_director_id: int | None = Field(default=None, ge=1)
    target_drama_company_id: int | None = Field(default=None, ge=1)
    target_drama_tag_id: int | None = Field(default=None, ge=1)
    target_drama_platform_id: int | None = Field(default=None, ge=1)
    target_snapshot_id: int | None = Field(default=None, ge=1)
    target_snapshot_revision_id: int | None = Field(default=None, ge=1)
    target_import_job_id: int | None = Field(default=None, ge=1)
    target_data_quality_issue_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_one_target(self) -> Self:
        if sum(getattr(self, field) is not None for field in TARGET_FIELDS) != 1:
            raise ValueError("exactly one operation log target is required")
        return self


class OperationLogCreate(OperationTargetMixin):
    """Internal audit command; actor identity is derived by the Service."""

    operation_type: str = Field(min_length=1, max_length=64)
    result_status: OperationResult
    summary: str = Field(min_length=1, max_length=1000)
    request_id: str | None = Field(default=None, max_length=64)


class OperationLogUpdate(SchemaModel):
    """Operation logs are immutable and expose no update fields."""


class OperationLogResponse(OperationTargetMixin):
    operation_log_id: int = Field(ge=1)
    actor_user_id: int = Field(ge=1)
    operation_type: str = Field(min_length=1, max_length=64)
    result_status: OperationResult
    summary: str = Field(min_length=1, max_length=1000)
    request_id: str | None = Field(default=None, max_length=64)
    occurred_at: datetime
