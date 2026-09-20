"""Pydantic DTOs for the Phase 4 anomaly-detection API."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from schemas.common import SchemaModel

AnomalySeverity = Literal["A", "B", "C"]
AnomalyStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED", "IGNORED"]
AnomalyType = Literal[
    "PLAY_COUNT_GROWTH_ANOMALY",
    "PLAY_COUNT_DROP_ANOMALY",
    "ENGAGEMENT_RATE_ANOMALY",
    "DATA_SPIKE_ANOMALY",
]
MetricType = Literal["PLAY_COUNT", "ENGAGEMENT_RATE"]
AnomalyAlgorithmVersion = Literal["Rule-based Detection V1.0"]
AnomalySkipReason = Literal[
    "NO_HISTORY",
    "INSUFFICIENT_HISTORY",
    "DATA_QUALITY_BLOCKED",
    "INSUFFICIENT_METRICS",
    "NOT_APPLICABLE",
]


class AnomalyCalculateRequest(SchemaModel):
    """Only the as-of cutoff is client-controlled for detection."""

    analysis_as_of: datetime | None = None


class AnomalyDetectionResponse(SchemaModel):
    analysis_as_of: datetime
    algorithm_version: AnomalyAlgorithmVersion
    detected_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    skip_reasons: dict[AnomalySkipReason, int] = Field(default_factory=dict)


class AnomalyResponse(SchemaModel):
    record_id: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    drama_code: str = Field(min_length=1, max_length=32)
    drama_name: str = Field(min_length=1, max_length=200)
    metric_type: MetricType
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    status: AnomalyStatus
    analysis_as_of: datetime
    algorithm_version: AnomalyAlgorithmVersion
    evidence_summary: str = Field(min_length=1, max_length=5000)
    created_at: datetime
    updated_at: datetime


class AnomalyStatusUpdateRequest(SchemaModel):
    status: AnomalyStatus


class AnomalyStatisticsResponse(SchemaModel):
    total_count: int = Field(ge=0)
    severity_distribution: dict[AnomalySeverity, int]
    status_distribution: dict[AnomalyStatus, int]
    type_distribution: dict[str, int]


__all__ = (
    "AnomalyAlgorithmVersion",
    "AnomalyCalculateRequest",
    "AnomalyDetectionResponse",
    "AnomalyResponse",
    "AnomalySeverity",
    "AnomalySkipReason",
    "AnomalyStatisticsResponse",
    "AnomalyStatus",
    "AnomalyStatusUpdateRequest",
    "AnomalyType",
    "MetricType",
)
