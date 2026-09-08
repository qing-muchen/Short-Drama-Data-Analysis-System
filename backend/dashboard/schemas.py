"""DTOs for Dashboard aggregate and ranking responses."""

from datetime import date, datetime
from typing import Any

from pydantic import Field

from schemas.common import SchemaModel


class DashboardOverviewResponse(SchemaModel):
    analysis_as_of: datetime
    drama_count: int = Field(ge=0)
    actor_count: int = Field(ge=0)
    director_count: int = Field(ge=0)
    company_count: int = Field(ge=0)
    platform_count: int = Field(ge=0)
    tag_count: int = Field(ge=0)
    total_play_count: int = Field(ge=0)
    average_engagement_rate: float | None = None
    quality_issue_count: int = Field(ge=0)


class RankingResponse(SchemaModel):
    drama_id: int = Field(ge=1)
    drama_name: str
    platform_count: int = Field(default=0, ge=0)
    heat_score: float | None = Field(default=None, ge=0, le=100)
    growth_rate: float | None = None
    current_play_count: int | None = Field(default=None, ge=0)
    potential_score: float | None = Field(default=None, ge=0, le=100)
    growth_7d: float | None = None


class TrendResponse(SchemaModel):
    date: date
    play_count: int | None = Field(default=None, ge=0)
    engagement_rate: float | None = None


class QualitySummaryResponse(SchemaModel):
    analysis_as_of: datetime
    quality_issue_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    freshness_summary: dict[str, int]


__all__ = [
    "DashboardOverviewResponse",
    "QualitySummaryResponse",
    "RankingResponse",
    "TrendResponse",
]

