"""Data quality issue DTOs preserving mutually exclusive real targets."""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from schemas.common import SchemaModel

QualityIssueType = Literal[
    "MISSING_REQUIRED_DATA",
    "INVALID_NEGATIVE_VALUE",
    "INVALID_RANKING",
    "INVALID_TIMESTAMP",
    "UNKNOWN_REFERENCE",
    "DUPLICATE_RECORD",
    "CONFLICTING_SNAPSHOT",
    "CUMULATIVE_REGRESSION",
    "STATISTICAL_SPIKE",
    "STATISTICAL_DROP",
    "OTHER",
]
QualitySeverity = Literal["INFO", "WARNING", "ERROR"]
QualityStatus = Literal["OPEN", "CONFIRMED", "RESOLVED", "IGNORED"]
QualitySource = Literal[
    "MANUAL_ENTRY",
    "IMPORT",
    "STATISTICAL_DETECTION",
    "BUSINESS_RULE",
]


class QualityTargetMixin(SchemaModel):
    """Require exactly one of the frozen quality target foreign keys."""

    target_snapshot_revision_id: int | None = Field(default=None, ge=1)
    target_drama_platform_id: int | None = Field(default=None, ge=1)
    target_drama_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_one_target(self) -> Self:
        targets = (
            self.target_snapshot_revision_id,
            self.target_drama_platform_id,
            self.target_drama_id,
        )
        if sum(target is not None for target in targets) != 1:
            raise ValueError("exactly one quality issue target is required")
        return self


class DataQualityIssueCreate(QualityTargetMixin):
    issue_type: QualityIssueType
    severity: QualitySeverity
    status: QualityStatus = "OPEN"
    source: QualitySource
    rule_code: str = Field(min_length=1, max_length=64)
    evidence_summary: str = Field(min_length=1)
    first_detected_at: datetime
    last_detected_at: datetime
    occurrence_count: int = Field(default=1, ge=1)


class DataQualityIssueUpdate(SchemaModel):
    """Human handling input; handler identity and time are Service-owned."""

    status: QualityStatus | None = None
    handling_note: str | None = Field(default=None, min_length=1)


class DataQualityIssueResponse(QualityTargetMixin):
    data_quality_issue_id: int = Field(ge=1)
    issue_type: QualityIssueType
    severity: QualitySeverity
    status: QualityStatus
    source: QualitySource
    rule_code: str = Field(min_length=1, max_length=64)
    evidence_summary: str = Field(min_length=1)
    first_detected_at: datetime
    last_detected_at: datetime
    occurrence_count: int = Field(ge=1)
    handled_by_user_id: int | None = Field(default=None, ge=1)
    handled_at: datetime | None = None
    handling_note: str | None = None
    created_at: datetime
    updated_at: datetime
