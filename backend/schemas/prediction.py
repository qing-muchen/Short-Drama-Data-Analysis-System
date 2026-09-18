"""Pydantic DTOs for the fixed Moving Average V1.0 prediction API."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from schemas.common import SchemaModel

PredictionMetric = Literal["PLAY_COUNT"]
PredictionAlgorithmVersion = Literal["Moving Average V1.0"]


class PredictionCalculateRequest(SchemaModel):
    """Client-controlled input for one drama prediction calculation."""

    drama_id: int = Field(ge=1)
    analysis_as_of: datetime | None = None


class PredictionResponse(SchemaModel):
    """Public persisted prediction; internal calculation details are omitted."""

    prediction_id: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    metric_type: PredictionMetric
    algorithm_version: PredictionAlgorithmVersion
    analysis_as_of: datetime
    target_date: date
    predicted_value: float = Field(ge=0)
    created_at: datetime


class PredictionHistoryResponse(SchemaModel):
    """Chronological prediction history for one drama."""

    drama_id: int = Field(ge=1)
    metric_type: PredictionMetric
    algorithm_version: PredictionAlgorithmVersion
    items: list[PredictionResponse]


__all__ = (
    "PredictionAlgorithmVersion",
    "PredictionCalculateRequest",
    "PredictionHistoryResponse",
    "PredictionMetric",
    "PredictionResponse",
)
