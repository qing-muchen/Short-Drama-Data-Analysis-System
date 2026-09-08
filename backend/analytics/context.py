"""Deterministic AnalysisContext used by every analytics calculation."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from analytics.constants import (
    ANOMALY_MODEL_VERSION,
    HEAT_MODEL_VERSION,
    INSIGHT_RULE_SET_VERSION,
    METRIC_DICTIONARY_VERSION,
    POTENTIAL_MODEL_VERSION,
)

TimeWindow = Literal["24H", "7D", "30D"]
AnalysisGranularity = Literal["DRAMA_PLATFORM", "DRAMA_OVERALL"]
QualityPolicy = Literal["VALID_WITH_WARNINGS"]


def normalize_utc(value: datetime) -> datetime:
    """Normalize an API time to the naive UTC convention used by MySQL."""

    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class ModelVersions:
    heat: str = HEAT_MODEL_VERSION
    potential: str = POTENTIAL_MODEL_VERSION
    anomaly: str = ANOMALY_MODEL_VERSION
    insight: str = INSIGHT_RULE_SET_VERSION
    metrics: str = METRIC_DICTIONARY_VERSION


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Immutable scope and model identity for one reproducible analysis."""

    analysis_as_of: datetime
    time_window: TimeWindow = "7D"
    granularity: AnalysisGranularity = "DRAMA_OVERALL"
    platform_scope: tuple[int, ...] = ()
    tag_scope: tuple[int, ...] = ()
    quality_policy: QualityPolicy = "VALID_WITH_WARNINGS"
    model_versions: ModelVersions = field(default_factory=ModelVersions)

    def __post_init__(self) -> None:
        object.__setattr__(self, "analysis_as_of", normalize_utc(self.analysis_as_of))
        object.__setattr__(self, "platform_scope", tuple(sorted(set(self.platform_scope))))
        object.__setattr__(self, "tag_scope", tuple(sorted(set(self.tag_scope))))
        if any(identifier < 1 for identifier in self.platform_scope + self.tag_scope):
            raise ValueError("scope identifiers must be positive")

    @property
    def deterministic_key(self) -> tuple[object, ...]:
        return (
            self.analysis_as_of,
            self.time_window,
            self.granularity,
            self.platform_scope,
            self.tag_scope,
            self.quality_policy,
            self.model_versions,
        )

