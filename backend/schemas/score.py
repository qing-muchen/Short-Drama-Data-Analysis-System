"""Pydantic DTOs for the fixed-scope Composite Score V1.0 API."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from schemas.common import SchemaModel

ScoreLevel = Literal["S", "A", "B", "C"]
ScoreScopeType = Literal["ALL"]
ScoreSkipReason = Literal[
    "NO_VALID_SNAPSHOT",
    "INCOMPLETE_METRICS",
    "ZERO_PLAY_COUNT",
    "INSUFFICIENT_HISTORY",
    "MISSING_RELEASE_DATE",
    "DATA_QUALITY_ERROR",
]
NonNegativeCount = Annotated[int, Field(ge=0)]


class ScoreCalculateRequest(SchemaModel):
    """Only the score date is client-controlled in Phase 1."""

    score_date: date


class ScoreCalculationResponse(SchemaModel):
    score_date: date
    analysis_as_of: datetime
    algorithm_version: Literal["Composite Score V1.0"]
    score_scope_type: ScoreScopeType
    score_scope_id: Literal[0]
    calculated_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    skipped_reasons: dict[ScoreSkipReason, NonNegativeCount]


class DramaScoreResponse(SchemaModel):
    score_id: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    drama_code: str = Field(min_length=1, max_length=32)
    drama_name: str = Field(min_length=1, max_length=200)
    score_date: date
    score_scope_type: ScoreScopeType
    score_scope_id: Literal[0]
    analysis_as_of: datetime
    heat_score: float = Field(ge=0, le=100)
    growth_score: float = Field(ge=0, le=100)
    engagement_score: float = Field(ge=0, le=100)
    lifecycle_score: float = Field(ge=0, le=100)
    total_score: float = Field(ge=0, le=100)
    level: ScoreLevel
    algorithm_version: Literal["Composite Score V1.0"]
    created_at: datetime
    updated_at: datetime


class ScoreRankingItemResponse(DramaScoreResponse):
    rank: int = Field(ge=1)


class ScoreLevelCountResponse(SchemaModel):
    level: ScoreLevel
    count: int = Field(ge=0)


class ScoreLevelDistributionResponse(SchemaModel):
    score_date: date
    algorithm_version: Literal["Composite Score V1.0"]
    score_scope_type: ScoreScopeType
    score_scope_id: Literal[0]
    total: int = Field(ge=0)
    items: list[ScoreLevelCountResponse] = Field(min_length=4, max_length=4)
