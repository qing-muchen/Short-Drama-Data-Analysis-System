"""HTTP schemas for the Phase 8 read-only operation analytics API."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field

from schemas.common import SchemaModel


class AvailabilityStatusSchema(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class AvailabilityReasonSchema(str, Enum):
    NOT_CALCULATED = "NOT_CALCULATED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INCOMPLETE_BEFORE_WINDOW = "INCOMPLETE_BEFORE_WINDOW"
    INCOMPLETE_AFTER_WINDOW = "INCOMPLETE_AFTER_WINDOW"
    INCOMPARABLE_SCOPE = "INCOMPARABLE_SCOPE"
    MISSING_METRIC = "MISSING_METRIC"
    ZERO_BASELINE = "ZERO_BASELINE"
    OVERLAPPING_ACTIONS = "OVERLAPPING_ACTIONS"
    MIXED_SOURCE_VERSIONS = "MIXED_SOURCE_VERSIONS"
    INVALID_CUMULATIVE_SEQUENCE = "INVALID_CUMULATIVE_SEQUENCE"
    NOT_COMPLETED = "NOT_COMPLETED"
    GLOBAL_ACTION_UNSUPPORTED = "GLOBAL_ACTION_UNSUPPORTED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class AnalysisAvailabilitySchema(SchemaModel):
    status: AvailabilityStatusSchema
    reasons: list[AvailabilityReasonSchema] = Field(default_factory=list)


class AnalysisWindowSchema(SchemaModel):
    start_date: date
    end_date: date
    day_count: int = Field(ge=1)


class MetricChangeSchema(SchemaModel):
    metric_type: str
    before_value: Decimal | int | None
    after_value: Decimal | int | None
    absolute_change: Decimal | int | None
    relative_change: Decimal | None
    direction: str
    unit: str
    availability: AnalysisAvailabilitySchema


class OperationEffectivenessResponseSchema(SchemaModel):
    action_id: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    before_window: AnalysisWindowSchema
    after_window: AnalysisWindowSchema
    metric_changes: list[MetricChangeSchema]
    availability: AnalysisAvailabilitySchema
    anchor_time: datetime
    overlapping_action_ids: list[int] = Field(default_factory=list)
    action_effect_rule_version: str
    analysis_revision: str | None = None
    analysis_as_of: datetime | None = None
    disclaimer: str


class OperationEffectivenessPageResponseSchema(SchemaModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    items: list[OperationEffectivenessResponseSchema]
    availability: AnalysisAvailabilitySchema
    analysis_as_of: datetime


class LifecycleEvidenceSchema(SchemaModel):
    previous_window: AnalysisWindowSchema
    current_window: AnalysisWindowSchema
    previous_average: Decimal | None
    current_average: Decimal | None
    window_change_rate: Decimal | None


class LifecycleResponseSchema(SchemaModel):
    drama_id: int = Field(ge=1)
    lifecycle_stage: str | None
    rule_version: str
    evaluated_as_of: datetime
    availability: AnalysisAvailabilitySchema
    evidence: LifecycleEvidenceSchema | None = None
    analysis_revision: str | None = None


class ComparisonScopeSchema(SchemaModel):
    drama_ids: list[int] = Field(min_length=2, max_length=20)
    platform_id: int = Field(ge=1)


class BenchmarkMetricSchema(SchemaModel):
    metric_type: str
    value: Decimal | str | None
    group_median: Decimal | None
    unit: str
    availability: AnalysisAvailabilitySchema


class BenchmarkMemberResponseSchema(SchemaModel):
    drama_id: int = Field(ge=1)
    metrics: list[BenchmarkMetricSchema]
    availability: AnalysisAvailabilitySchema


class BenchmarkResponseSchema(SchemaModel):
    target_drama_id: int | None
    comparison_scope: ComparisonScopeSchema
    window: AnalysisWindowSchema
    metrics: list[BenchmarkMemberResponseSchema]
    availability: AnalysisAvailabilitySchema
    benchmark_version: str
    lifecycle_rule_version: str
    analysis_revision: str | None
    analysis_as_of: datetime


__all__ = [
    "AnalysisAvailabilitySchema",
    "AnalysisWindowSchema",
    "AvailabilityReasonSchema",
    "AvailabilityStatusSchema",
    "BenchmarkMemberResponseSchema",
    "BenchmarkMetricSchema",
    "BenchmarkResponseSchema",
    "ComparisonScopeSchema",
    "LifecycleEvidenceSchema",
    "LifecycleResponseSchema",
    "MetricChangeSchema",
    "OperationEffectivenessPageResponseSchema",
    "OperationEffectivenessResponseSchema",
]
