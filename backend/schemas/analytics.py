"""Pydantic v2 DTOs for deterministic Analytics Service results."""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from analytics.constants import (
    ANOMALY_MODEL_VERSION,
    HEAT_MODEL_VERSION,
    INSIGHT_RULE_SET_VERSION,
    METRIC_DICTIONARY_VERSION,
    POTENTIAL_MODEL_VERSION,
)
from analytics.context import AnalysisContext, ModelVersions
from schemas.common import SchemaModel


class ModelVersionsSchema(SchemaModel):
    heat: str = HEAT_MODEL_VERSION
    potential: str = POTENTIAL_MODEL_VERSION
    anomaly: str = ANOMALY_MODEL_VERSION
    insight: str = INSIGHT_RULE_SET_VERSION
    metrics: str = METRIC_DICTIONARY_VERSION

    @model_validator(mode="after")
    def validate_frozen_versions(self) -> Self:
        expected = (
            HEAT_MODEL_VERSION,
            POTENTIAL_MODEL_VERSION,
            ANOMALY_MODEL_VERSION,
            INSIGHT_RULE_SET_VERSION,
            METRIC_DICTIONARY_VERSION,
        )
        actual = (self.heat, self.potential, self.anomaly, self.insight, self.metrics)
        if actual != expected:
            raise ValueError("Analytics V1 model versions are frozen")
        return self


class AnalysisContextRequest(SchemaModel):
    analysis_as_of: datetime
    time_window: Literal["24H", "7D", "30D"] = "7D"
    granularity: Literal["DRAMA_PLATFORM", "DRAMA_OVERALL"] = "DRAMA_OVERALL"
    platform_scope: list[int] = Field(default_factory=list)
    tag_scope: list[int] = Field(default_factory=list)
    quality_policy: Literal["VALID_WITH_WARNINGS"] = "VALID_WITH_WARNINGS"
    model_versions: ModelVersionsSchema = Field(default_factory=ModelVersionsSchema)

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if any(identifier < 1 for identifier in self.platform_scope + self.tag_scope):
            raise ValueError("scope identifiers must be positive")
        return self

    def to_domain(self) -> AnalysisContext:
        return AnalysisContext(
            analysis_as_of=self.analysis_as_of,
            time_window=self.time_window,
            granularity=self.granularity,
            platform_scope=tuple(self.platform_scope),
            tag_scope=tuple(self.tag_scope),
            quality_policy=self.quality_policy,
            model_versions=ModelVersions(**self.model_versions.model_dump()),
        )


class AnalysisContextResponse(SchemaModel):
    analysis_as_of: datetime
    time_window: Literal["24H", "7D", "30D"]
    granularity: Literal["DRAMA_PLATFORM", "DRAMA_OVERALL"]
    platform_scope: list[int]
    tag_scope: list[int]
    quality_policy: Literal["VALID_WITH_WARNINGS"]
    model_versions: ModelVersionsSchema


class RawMetricResponse(SchemaModel):
    play_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    favorite_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    ranking: int | None = Field(default=None, gt=0)


class EngagementMetricResponse(SchemaModel):
    like_rate: float | None = None
    comment_rate: float | None = None
    favorite_rate: float | None = None
    share_rate: float | None = None
    engagement_rate: float | None = None
    quality_engagement: float | None = None


class MetricResponse(SchemaModel):
    object_key: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    drama_code: str
    granularity: Literal["DRAMA_PLATFORM", "DRAMA_OVERALL"]
    snapshot_time: datetime | None = None
    raw: RawMetricResponse
    engagement: EngagementMetricResponse
    adjacent_growth: float | None = None
    growth_24h: float | None = None
    growth_7d: float | None = None
    growth_30d: float | None = None
    freshness: Literal["FRESH", "STALE"] | None = None
    quality_status: Literal["NORMAL", "WARNING", "ERROR"] | None = None
    warning_count: int = Field(ge=0)
    excluded_error_count: int = Field(ge=0)
    insufficient_history: bool
    included_platform_count: int = Field(ge=0)


class HeatResponse(SchemaModel):
    object_key: int = Field(ge=1)
    score: float = Field(ge=0, le=100)
    rank: int = Field(ge=1)
    candidate_count: int = Field(ge=1)
    model_version: Literal["Heat Model V1"]


class PotentialResponse(SchemaModel):
    object_key: int = Field(ge=1)
    score: float = Field(ge=0, le=100)
    rank: int = Field(ge=1)
    candidate_count: int = Field(ge=1)
    model_version: Literal["Potential Model V1"]


class InsightResponse(SchemaModel):
    insight_type: Literal[
        "PERFORMANCE",
        "GROWTH",
        "POTENTIAL",
        "RISK",
        "PLATFORM",
        "TAG",
        "DATA_QUALITY",
    ]
    rule_code: str
    trigger: str
    evidence: dict[str, Any]
    conclusion: str
    priority: int = Field(ge=1)
    rule_set_version: Literal["Insight Rule Set V1"]


class AnalyticsSummaryResponse(SchemaModel):
    context: AnalysisContextResponse
    metrics: MetricResponse
    heat: HeatResponse | None = None
    potential: PotentialResponse | None = None
    insights: list[InsightResponse] = Field(max_length=5)

