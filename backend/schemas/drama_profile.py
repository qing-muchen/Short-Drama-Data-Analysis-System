"""API response schemas for the read-only Drama 360° profile."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from schemas.common import SchemaModel


class AvailabilityReasonSchema(str, Enum):
    NOT_CALCULATED = "NOT_CALCULATED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    NO_ANOMALY = "NO_ANOMALY"
    NOT_DETECTED = "NOT_DETECTED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class ModuleAvailabilitySchema(SchemaModel):
    available: bool
    reason: AvailabilityReasonSchema | None = None


class DramaProfileBasicSchema(SchemaModel):
    drama_id: int = Field(ge=1)
    title: str
    platform: str | None = None
    tags: list[str] = Field(default_factory=list)


class ScoreProfileSummarySchema(SchemaModel):
    available: ModuleAvailabilitySchema
    score_level: str | None = None
    dimensions: dict[str, float] = Field(default_factory=dict)
    analysis_as_of: datetime | None = None
    algorithm_version: str | None = None
    rule_set_version: str | None = None


class QualityProfileSummarySchema(SchemaModel):
    available: ModuleAvailabilitySchema
    quality_level: str | None = None
    quality_status: str | None = None
    risk_message: str | None = None
    analysis_as_of: datetime | None = None
    rule_set_version: str | None = None


class PredictionProfileSummarySchema(SchemaModel):
    available: ModuleAvailabilitySchema
    trend_direction: str | None = None
    prediction_status: str | None = None
    analysis_as_of: datetime | None = None
    algorithm_version: str | None = None


class AnomalyProfileSummarySchema(SchemaModel):
    available: ModuleAvailabilitySchema
    active_count: int = Field(default=0, ge=0)
    highest_severity: str | None = None
    latest_anomalies: list[dict[str, Any]] = Field(default_factory=list)
    analysis_as_of: datetime | None = None


class ActionProfileSummarySchema(SchemaModel):
    available: ModuleAvailabilitySchema
    open_count: int = Field(default=0, ge=0)
    in_progress_count: int = Field(default=0, ge=0)
    recent_actions: list[dict[str, Any]] = Field(default_factory=list)


class ExplanationProfileSummarySchema(SchemaModel):
    available: ModuleAvailabilitySchema
    latest_explanation: dict[str, Any] | None = None
    lineage_available: bool = False


class DramaProfileResponseSchema(SchemaModel):
    drama: DramaProfileBasicSchema
    availability: dict[str, ModuleAvailabilitySchema]
    performance: ScoreProfileSummarySchema | None = None
    quality: QualityProfileSummarySchema | None = None
    trend: PredictionProfileSummarySchema | None = None
    risk: AnomalyProfileSummarySchema | None = None
    operations: ActionProfileSummarySchema | None = None
    explanations: ExplanationProfileSummarySchema | None = None


__all__ = [
    "ActionProfileSummarySchema",
    "AnomalyProfileSummarySchema",
    "AvailabilityReasonSchema",
    "DramaProfileBasicSchema",
    "DramaProfileResponseSchema",
    "ExplanationProfileSummarySchema",
    "ModuleAvailabilitySchema",
    "PredictionProfileSummarySchema",
    "QualityProfileSummarySchema",
    "ScoreProfileSummarySchema",
]
