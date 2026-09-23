"""HTTP schemas and explicit DTO mappings for Phase 9 data governance."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field

from schemas.common import SchemaModel
from services.data_governance.contracts import (
    CompletenessResult,
    ConsistencyResult,
    DataGovernanceResponse,
    DataQualityAvailability,
    EvidenceItem,
    FreshnessResult,
)


class QualityStatusSchema(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class AvailabilityStatusSchema(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class AvailabilityReasonSchema(str, Enum):
    NO_DATA = "NO_DATA"
    MISSING_SOURCE = "MISSING_SOURCE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INCOMPLETE_TIME_SERIES = "INCOMPLETE_TIME_SERIES"
    UNRESOLVED_RELATION = "UNRESOLVED_RELATION"
    REVISION_NOT_VISIBLE = "REVISION_NOT_VISIBLE"
    UNSUPPORTED_SCOPE = "UNSUPPORTED_SCOPE"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class GovernanceScopeSchema(str, Enum):
    SYSTEM = "SYSTEM"


class QualityIssueTypeSchema(str, Enum):
    FRESHNESS = "FRESHNESS"
    COMPLETENESS = "COMPLETENESS"
    CONSISTENCY = "CONSISTENCY"


class DataQualityAvailabilitySchema(SchemaModel):
    status: AvailabilityStatusSchema
    reasons: list[AvailabilityReasonSchema] = Field(default_factory=list)
    message: str | None = None


class EvidenceItemSchema(SchemaModel):
    """Transport-safe evidence without exposing internal dataclasses."""

    evidence_type: QualityIssueTypeSchema
    message: str
    source: str
    metadata: dict[str, Any]


class FreshnessSchema(SchemaModel):
    status: QualityStatusSchema
    availability: DataQualityAvailabilitySchema
    delay_seconds: int | None
    evidence: list[EvidenceItemSchema]
    rule_version: str
    analysis_as_of: datetime | None = None
    summary: str | None = None
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class CompletenessSchema(SchemaModel):
    status: QualityStatusSchema
    availability: DataQualityAvailabilitySchema
    coverage_ratio: Decimal | None
    missing_items: list[str]
    evidence: list[EvidenceItemSchema]
    rule_version: str
    analysis_as_of: datetime | None = None
    summary: str | None = None
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class ConsistencySchema(SchemaModel):
    status: QualityStatusSchema
    availability: DataQualityAvailabilitySchema
    issue_count: int = Field(ge=0)
    evidence: list[EvidenceItemSchema]
    rule_version: str
    analysis_as_of: datetime | None = None
    summary: str | None = None
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class DataGovernanceResponseSchema(SchemaModel):
    scope: GovernanceScopeSchema
    analysis_as_of: datetime
    availability: DataQualityAvailabilitySchema
    freshness: FreshnessSchema
    completeness: CompletenessSchema
    consistency: ConsistencySchema
    rule_set_version: str


def availability_schema(
    value: DataQualityAvailability,
) -> DataQualityAvailabilitySchema:
    return DataQualityAvailabilitySchema(
        status=value.status.value,
        reasons=[reason.value for reason in value.reasons],
        message=value.message,
    )


def evidence_schema(value: EvidenceItem) -> EvidenceItemSchema:
    return EvidenceItemSchema(
        evidence_type=value.issue_type.value,
        message=value.message,
        source=value.source_type,
        metadata={
            "check_code": value.check_code,
            "entity_type": value.entity_type,
            "entity_id": value.entity_id,
            "observed_value": value.observed_value,
            "expected_condition": value.expected_condition,
            "source_reference_ids": list(value.source_reference_ids),
        },
    )


def freshness_schema(
    value: FreshnessResult,
    *,
    page: int = 1,
    page_size: int = 100,
) -> FreshnessSchema:
    evidence, total = _evidence_page(value.evidence, page, page_size)
    return FreshnessSchema(
        status=value.status.value,
        availability=availability_schema(value.availability),
        delay_seconds=value.delay_seconds,
        evidence=[evidence_schema(item) for item in evidence],
        rule_version=value.rule_version,
        analysis_as_of=value.analysis_as_of,
        summary=value.summary,
        page=page,
        page_size=page_size,
        total=total,
    )


def completeness_schema(
    value: CompletenessResult,
    *,
    page: int = 1,
    page_size: int = 100,
) -> CompletenessSchema:
    evidence, total = _evidence_page(value.evidence, page, page_size)
    return CompletenessSchema(
        status=value.status.value,
        availability=availability_schema(value.availability),
        coverage_ratio=value.coverage_ratio,
        missing_items=list(value.missing_items),
        evidence=[evidence_schema(item) for item in evidence],
        rule_version=value.rule_version,
        analysis_as_of=value.analysis_as_of,
        summary=value.summary,
        page=page,
        page_size=page_size,
        total=total,
    )


def consistency_schema(
    value: ConsistencyResult,
    *,
    page: int = 1,
    page_size: int = 100,
) -> ConsistencySchema:
    evidence, total = _evidence_page(value.evidence, page, page_size)
    return ConsistencySchema(
        status=value.status.value,
        availability=availability_schema(value.availability),
        issue_count=value.issue_count,
        evidence=[evidence_schema(item) for item in evidence],
        rule_version=value.rule_version,
        analysis_as_of=value.analysis_as_of,
        summary=value.summary,
        page=page,
        page_size=page_size,
        total=total,
    )


def data_governance_response_schema(
    value: DataGovernanceResponse,
) -> DataGovernanceResponseSchema:
    return DataGovernanceResponseSchema(
        scope=value.scope.value,
        analysis_as_of=value.analysis_as_of,
        availability=availability_schema(value.availability),
        freshness=freshness_schema(value.freshness, page_size=5),
        completeness=completeness_schema(value.completeness, page_size=5),
        consistency=consistency_schema(value.consistency, page_size=5),
        rule_set_version=value.rule_set_version,
    )


def _evidence_page(
    values: tuple[EvidenceItem, ...],
    page: int,
    page_size: int,
) -> tuple[tuple[EvidenceItem, ...], int]:
    start = (page - 1) * page_size
    return values[start : start + page_size], len(values)


__all__ = [
    "AvailabilityReasonSchema",
    "AvailabilityStatusSchema",
    "CompletenessSchema",
    "ConsistencySchema",
    "DataGovernanceResponseSchema",
    "DataQualityAvailabilitySchema",
    "EvidenceItemSchema",
    "FreshnessSchema",
    "GovernanceScopeSchema",
    "QualityIssueTypeSchema",
    "QualityStatusSchema",
    "completeness_schema",
    "consistency_schema",
    "data_governance_response_schema",
    "freshness_schema",
]
