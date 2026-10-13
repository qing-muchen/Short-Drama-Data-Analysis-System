"""Pydantic DTOs for the fixed-scope Phase 2 data-quality API."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from schemas.common import SchemaModel

QualityGrade = Literal["S", "A", "B", "C"]
QualityAlgorithmVersion = Literal["Quality Score V1.0", "Quality Score V2.0"]
QualityScopeType = Literal["ALL"]
QualityDimension = Literal[
    "COMPLETENESS",
    "ACCURACY",
    "CONSISTENCY",
    "TIMELINESS",
]
QualityRuleStatus = Literal["DRAFT", "ACTIVE", "INACTIVE"]
QualityResultStatus = Literal["APPLIED", "NOT_APPLICABLE"]
QualityScoringMethod = Literal["PASS_RATE", "BUCKET_AVERAGE"]
QualitySeverity = Literal["INFO", "WARNING", "ERROR"]
QualityTargetEntityType = Literal[
    "DRAMA",
    "DRAMA_PLATFORM",
    "SNAPSHOT",
    "IMPORT_JOB",
]


class DataQualityCalculateRequest(SchemaModel):
    """Administrator-selected score date and released algorithm version."""

    score_date: date
    algorithm_version: QualityAlgorithmVersion = "Quality Score V2.0"


class DataQualityCalculationResponse(SchemaModel):
    quality_score_id: int = Field(ge=1)
    score_date: date
    analysis_as_of: datetime
    algorithm_version: QualityAlgorithmVersion
    rule_set_version: Literal["DQ Rules 1.0"]
    rule_set_hash: str = Field(min_length=64, max_length=64)
    score_scope_type: QualityScopeType
    score_scope_id: Literal[0]
    rule_count: int = Field(ge=0)
    applied_rule_count: int = Field(ge=0)
    not_applicable_rule_count: int = Field(ge=0)
    evaluated_entity_count: int = Field(ge=0)
    total_score: float = Field(ge=0, le=100)
    quality_grade: QualityGrade


class DataQualityRuleResultResponse(SchemaModel):
    quality_rule_result_id: int = Field(ge=1)
    quality_rule_id: int = Field(ge=1)
    rule_code: str = Field(min_length=1, max_length=64)
    rule_version: str = Field(min_length=1, max_length=32)
    rule_name: str = Field(min_length=1, max_length=200)
    dimension: QualityDimension
    result_status: QualityResultStatus
    applicable_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    rule_score: float | None = Field(default=None, ge=0, le=100)
    not_applicable_reason: str | None = Field(default=None, max_length=255)
    evidence_summary: str | None = Field(default=None, max_length=1000)
    created_at: datetime


class DataQualityScoreResponse(SchemaModel):
    quality_score_id: int = Field(ge=1)
    score_date: date
    score_scope_type: QualityScopeType
    score_scope_id: Literal[0]
    analysis_as_of: datetime
    completeness_score: float = Field(ge=0, le=100)
    accuracy_score: float = Field(ge=0, le=100)
    consistency_score: float = Field(ge=0, le=100)
    timeliness_score: float = Field(ge=0, le=100)
    total_score: float = Field(ge=0, le=100)
    quality_grade: QualityGrade
    algorithm_version: QualityAlgorithmVersion
    rule_set_version: Literal["DQ Rules 1.0"]
    rule_set_hash: str = Field(min_length=64, max_length=64)
    evaluated_entity_count: int = Field(ge=0)
    open_issue_count: int = Field(ge=0)
    source_watermark: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    rule_results: list[DataQualityRuleResultResponse]


class DataQualityHistoryItemResponse(SchemaModel):
    quality_score_id: int = Field(ge=1)
    score_date: date
    analysis_as_of: datetime
    completeness_score: float = Field(ge=0, le=100)
    accuracy_score: float = Field(ge=0, le=100)
    consistency_score: float = Field(ge=0, le=100)
    timeliness_score: float = Field(ge=0, le=100)
    total_score: float = Field(ge=0, le=100)
    quality_grade: QualityGrade
    algorithm_version: QualityAlgorithmVersion
    rule_set_version: Literal["DQ Rules 1.0"]
    rule_set_hash: str = Field(min_length=64, max_length=64)
    score_scope_type: QualityScopeType
    score_scope_id: Literal[0]
    evaluated_entity_count: int = Field(ge=0)
    open_issue_count: int = Field(ge=0)


class DataQualityHistoryResponse(SchemaModel):
    total: int = Field(ge=0)
    items: list[DataQualityHistoryItemResponse]


class DataQualityRuleResponse(SchemaModel):
    quality_rule_id: int = Field(ge=1)
    rule_code: str = Field(min_length=1, max_length=64)
    rule_version: str = Field(min_length=1, max_length=32)
    rule_name: str = Field(min_length=1, max_length=200)
    dimension: QualityDimension
    target_entity_type: QualityTargetEntityType
    evaluator_key: str = Field(min_length=1, max_length=64)
    scoring_method: QualityScoringMethod
    weight: float = Field(gt=0, le=1)
    severity: QualitySeverity
    configuration: dict[str, Any]
    status: QualityRuleStatus
    valid_from: datetime
    valid_to: datetime | None = None
    description: str | None = None


class DataQualityRuleListResponse(SchemaModel):
    rule_set_version: Literal["DQ Rules 1.0"]
    rule_set_hash: str | None = Field(default=None, min_length=64, max_length=64)
    total: int = Field(ge=0)
    items: list[DataQualityRuleResponse]


__all__ = (
    "DataQualityCalculateRequest",
    "DataQualityCalculationResponse",
    "DataQualityHistoryItemResponse",
    "DataQualityHistoryResponse",
    "DataQualityRuleListResponse",
    "DataQualityRuleResponse",
    "DataQualityRuleResultResponse",
    "DataQualityScoreResponse",
    "QualityDimension",
    "QualityAlgorithmVersion",
    "QualityGrade",
    "QualityResultStatus",
    "QualityRuleStatus",
    "QualityScopeType",
    "QualityScoringMethod",
    "QualitySeverity",
    "QualityTargetEntityType",
)
