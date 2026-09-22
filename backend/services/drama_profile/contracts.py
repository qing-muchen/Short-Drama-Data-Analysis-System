"""Pure DTO contracts for the Drama 360° aggregation layer.

This module deliberately has no ORM, repository, session, query or database
dependency.  It describes the read model exchanged between profile providers,
the profile service and the future HTTP layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class AvailabilityReason(str, Enum):
    """Standard reasons for a module being unavailable in a profile."""

    NOT_CALCULATED = "NOT_CALCULATED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    NO_ANOMALY = "NO_ANOMALY"
    NOT_DETECTED = "NOT_DETECTED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True, slots=True)
class ModuleAvailability:
    """Availability protocol shared by all profile modules."""

    available: bool
    reason: AvailabilityReason | None = None

    def __post_init__(self) -> None:
        if self.available and self.reason is not None:
            raise ValueError("available modules cannot have an availability reason")
        if not self.available and self.reason is None:
            raise ValueError("unavailable modules require an availability reason")


@dataclass(frozen=True, slots=True)
class DramaProfileBasic:
    """Minimal Drama identity used by the profile header."""

    drama_id: int
    title: str
    platform: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.drama_id <= 0:
            raise ValueError("drama_id must be greater than zero")
        if not self.title.strip():
            raise ValueError("title must not be blank")


@dataclass(frozen=True, slots=True)
class ScoreProfileSummary:
    available: ModuleAvailability
    score_level: str | None = None
    dimensions: Mapping[str, float] = field(default_factory=dict)
    analysis_as_of: datetime | None = None
    algorithm_version: str | None = None
    rule_set_version: str | None = None


@dataclass(frozen=True, slots=True)
class QualityProfileSummary:
    available: ModuleAvailability
    quality_level: str | None = None
    quality_status: str | None = None
    risk_message: str | None = None
    analysis_as_of: datetime | None = None
    rule_set_version: str | None = None


@dataclass(frozen=True, slots=True)
class PredictionProfileSummary:
    available: ModuleAvailability
    trend_direction: str | None = None
    prediction_status: str | None = None
    analysis_as_of: datetime | None = None
    algorithm_version: str | None = None


@dataclass(frozen=True, slots=True)
class AnomalyProfileSummary:
    available: ModuleAvailability
    active_count: int = 0
    highest_severity: str | None = None
    latest_anomalies: tuple[Mapping[str, Any], ...] = ()
    analysis_as_of: datetime | None = None

    def __post_init__(self) -> None:
        if self.active_count < 0:
            raise ValueError("active_count must not be negative")


@dataclass(frozen=True, slots=True)
class ActionProfileSummary:
    available: ModuleAvailability
    open_count: int = 0
    in_progress_count: int = 0
    recent_actions: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.open_count < 0 or self.in_progress_count < 0:
            raise ValueError("action counts must not be negative")


@dataclass(frozen=True, slots=True)
class ExplanationProfileSummary:
    available: ModuleAvailability
    latest_explanation: Mapping[str, Any] | None = None
    lineage_available: bool = False


@dataclass(frozen=True, slots=True)
class DramaProfileResponse:
    """Aggregated read model returned by DramaProfileService."""

    drama: DramaProfileBasic
    availability: Mapping[str, ModuleAvailability]
    performance: ScoreProfileSummary | None = None
    quality: QualityProfileSummary | None = None
    trend: PredictionProfileSummary | None = None
    risk: AnomalyProfileSummary | None = None
    operations: ActionProfileSummary | None = None
    explanations: ExplanationProfileSummary | None = None


__all__ = [
    "ActionProfileSummary",
    "AnomalyProfileSummary",
    "AvailabilityReason",
    "DramaProfileBasic",
    "DramaProfileResponse",
    "ExplanationProfileSummary",
    "ModuleAvailability",
    "PredictionProfileSummary",
    "QualityProfileSummary",
    "ScoreProfileSummary",
]
