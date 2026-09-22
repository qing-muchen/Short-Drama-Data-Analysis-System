"""Pure data contracts for the Phase 8 operation analytics read model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TypeAlias


ACTION_EFFECT_RULE_VERSION = "Action Effect Analysis V1.0"
LIFECYCLE_RULE_VERSION = "Lifecycle Rules V1.0"
BENCHMARK_VERSION = "Benchmark Comparison V1.0"
NON_CAUSAL_DISCLAIMER = (
    "Observed post-action metric movement does not establish causation."
)

NumericValue: TypeAlias = Decimal | int


class AvailabilityStatus(str, Enum):
    """Top-level completeness of an analysis or one of its metrics."""

    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class AvailabilityReason(str, Enum):
    """Closed reason set used with an unavailable or incomplete status."""

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


class LifecycleStage(str, Enum):
    LAUNCH = "LAUNCH"
    GROWTH = "GROWTH"
    STABLE = "STABLE"
    DECLINE = "DECLINE"
    ARCHIVED = "ARCHIVED"


class MetricDirection(str, Enum):
    INCREASED = "INCREASED"
    UNCHANGED = "UNCHANGED"
    DECREASED = "DECREASED"
    UNAVAILABLE = "UNAVAILABLE"


class OperationMetricType(str, Enum):
    """Supported observable metrics for before/after comparison."""

    PLAY_COUNT = "PLAY_COUNT"
    ENGAGEMENT_RATE = "ENGAGEMENT_RATE"
    GROWTH_RATE = "GROWTH_RATE"
    ANOMALY_COUNT = "ANOMALY_COUNT"


class BenchmarkMetricType(str, Enum):
    PLAY_INCREMENT_TOTAL = "PLAY_INCREMENT_TOTAL"
    MEAN_DAILY_PLAY_INCREMENT = "MEAN_DAILY_PLAY_INCREMENT"
    ENGAGEMENT_RATE = "ENGAGEMENT_RATE"
    ANOMALY_FREQUENCY = "ANOMALY_FREQUENCY"
    LIFECYCLE_STATE = "LIFECYCLE_STATE"


def _require_positive(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_nonblank(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{field_name} must be a {enum_type.__name__}")


@dataclass(frozen=True, slots=True)
class AnalysisAvailability:
    status: AvailabilityStatus
    reasons: tuple[AvailabilityReason, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(self.status, AvailabilityStatus, "status")
        if not isinstance(self.reasons, tuple):
            raise ValueError("reasons must be an immutable tuple")
        if any(not isinstance(reason, AvailabilityReason) for reason in self.reasons):
            raise ValueError("reasons must contain only AvailabilityReason values")
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("availability reasons must be unique")
        reason_order = {reason: index for index, reason in enumerate(AvailabilityReason)}
        if self.reasons != tuple(
            sorted(self.reasons, key=reason_order.__getitem__)
        ):
            raise ValueError("availability reasons must follow enum order")
        if self.status is AvailabilityStatus.AVAILABLE and self.reasons:
            raise ValueError("AVAILABLE cannot contain availability reasons")
        if self.status is not AvailabilityStatus.AVAILABLE and not self.reasons:
            raise ValueError("non-AVAILABLE status requires at least one reason")


@dataclass(frozen=True, slots=True)
class AnalysisWindow:
    """Inclusive business-date window; it does not perform metric work."""

    start_date: date
    end_date: date
    day_count: int

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        if self.day_count <= 0:
            raise ValueError("day_count must be greater than zero")
        if (self.end_date - self.start_date).days + 1 != self.day_count:
            raise ValueError("day_count must match the inclusive date range")


@dataclass(frozen=True, slots=True)
class DailyCumulativePoint:
    business_date: date
    platform_id: int
    snapshot_revision_id: int
    play_count: int
    like_count: int | None = None
    comment_count: int | None = None
    favorite_count: int | None = None
    share_count: int | None = None

    def __post_init__(self) -> None:
        _require_positive(self.platform_id, "platform_id")
        _require_positive(self.snapshot_revision_id, "snapshot_revision_id")
        for field_name in (
            "play_count",
            "like_count",
            "comment_count",
            "favorite_count",
            "share_count",
        ):
            value = getattr(self, field_name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{field_name} must not be negative")


@dataclass(frozen=True, slots=True)
class AnalysisVersionInfo:
    rule_version: str
    source_versions: tuple[str, ...]
    analysis_revision: str
    analysis_as_of: datetime

    def __post_init__(self) -> None:
        _require_nonblank(self.rule_version, "rule_version")
        _require_nonblank(self.analysis_revision, "analysis_revision")
        _require_aware(self.analysis_as_of, "analysis_as_of")
        if any(not version.strip() for version in self.source_versions):
            raise ValueError("source_versions must not contain blank values")


@dataclass(frozen=True, slots=True)
class MetricChange:
    metric_type: OperationMetricType
    before_value: NumericValue | None
    after_value: NumericValue | None
    absolute_change: NumericValue | None
    relative_change: Decimal | None
    direction: MetricDirection
    unit: str
    availability: AnalysisAvailability

    def __post_init__(self) -> None:
        _require_enum(self.metric_type, OperationMetricType, "metric_type")
        _require_enum(self.direction, MetricDirection, "direction")
        _require_nonblank(self.unit, "unit")


@dataclass(frozen=True, slots=True)
class OperationEffectivenessInput:
    action_id: int
    drama_id: int
    anchor_time: datetime
    before_window: AnalysisWindow
    after_window: AnalysisWindow
    before_points: tuple[DailyCumulativePoint, ...]
    after_points: tuple[DailyCumulativePoint, ...]
    before_anomaly_ids: tuple[int, ...] = ()
    after_anomaly_ids: tuple[int, ...] = ()
    anomaly_algorithm_versions: tuple[str, ...] = ()
    overlapping_action_ids: tuple[int, ...] = ()
    availability: AnalysisAvailability = AnalysisAvailability(
        AvailabilityStatus.AVAILABLE
    )

    def __post_init__(self) -> None:
        _require_positive(self.action_id, "action_id")
        _require_positive(self.drama_id, "drama_id")
        _require_aware(self.anchor_time, "anchor_time")
        for field_name in (
            "before_anomaly_ids",
            "after_anomaly_ids",
            "overlapping_action_ids",
        ):
            for value in getattr(self, field_name):
                _require_positive(value, field_name)


@dataclass(frozen=True, slots=True)
class OperationEffectivenessResult:
    action_id: int
    drama_id: int
    before_window: AnalysisWindow
    after_window: AnalysisWindow
    metric_changes: tuple[MetricChange, ...]
    availability: AnalysisAvailability
    anchor_time: datetime
    action_type: None = None
    overlapping_action_ids: tuple[int, ...] = ()
    action_effect_rule_version: str = ACTION_EFFECT_RULE_VERSION
    analysis_revision: str | None = None
    analysis_as_of: datetime | None = None
    disclaimer: str = NON_CAUSAL_DISCLAIMER

    def __post_init__(self) -> None:
        _require_positive(self.action_id, "action_id")
        _require_positive(self.drama_id, "drama_id")
        _require_aware(self.anchor_time, "anchor_time")
        _require_nonblank(
            self.action_effect_rule_version,
            "action_effect_rule_version",
        )
        _require_nonblank(self.disclaimer, "disclaimer")
        if self.action_type is not None:
            raise ValueError("action_type is not supported in Phase 8 V1")
        if self.analysis_as_of is not None:
            _require_aware(self.analysis_as_of, "analysis_as_of")
        for action_id in self.overlapping_action_ids:
            _require_positive(action_id, "overlapping_action_ids")


@dataclass(frozen=True, slots=True)
class LifecycleInput:
    drama_id: int
    drama_status: str
    release_time: datetime | None
    points: tuple[DailyCumulativePoint, ...]
    analysis_as_of: datetime

    def __post_init__(self) -> None:
        _require_positive(self.drama_id, "drama_id")
        _require_nonblank(self.drama_status, "drama_status")
        if self.release_time is not None:
            _require_aware(self.release_time, "release_time")
        _require_aware(self.analysis_as_of, "analysis_as_of")


@dataclass(frozen=True, slots=True)
class LifecycleEvidence:
    previous_window: AnalysisWindow
    current_window: AnalysisWindow
    previous_average: Decimal | None
    current_average: Decimal | None
    window_change_rate: Decimal | None


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    drama_id: int
    lifecycle_stage: LifecycleStage | None
    rule_version: str
    evaluated_as_of: datetime
    availability: AnalysisAvailability
    evidence: LifecycleEvidence | None = None
    analysis_revision: str | None = None

    def __post_init__(self) -> None:
        _require_positive(self.drama_id, "drama_id")
        if self.lifecycle_stage is not None:
            _require_enum(self.lifecycle_stage, LifecycleStage, "lifecycle_stage")
        _require_nonblank(self.rule_version, "rule_version")
        _require_aware(self.evaluated_as_of, "evaluated_as_of")
        if (
            self.availability.status is AvailabilityStatus.AVAILABLE
            and self.lifecycle_stage is None
        ):
            raise ValueError("AVAILABLE lifecycle result requires a stage")


@dataclass(frozen=True, slots=True)
class ComparisonScope:
    drama_ids: tuple[int, ...]
    platform_id: int

    def __post_init__(self) -> None:
        _require_positive(self.platform_id, "platform_id")
        if not 2 <= len(self.drama_ids) <= 20:
            raise ValueError("comparison scope requires 2 to 20 drama IDs")
        if len(set(self.drama_ids)) != len(self.drama_ids):
            raise ValueError("comparison drama IDs must be unique")
        for drama_id in self.drama_ids:
            _require_positive(drama_id, "drama_ids")


@dataclass(frozen=True, slots=True)
class BenchmarkMemberInput:
    drama_id: int
    points: tuple[DailyCumulativePoint, ...]
    anomaly_ids: tuple[int, ...] = ()
    anomaly_algorithm_versions: tuple[str, ...] = ()
    lifecycle_result: LifecycleResult | None = None
    availability: AnalysisAvailability = AnalysisAvailability(
        AvailabilityStatus.AVAILABLE
    )

    def __post_init__(self) -> None:
        _require_positive(self.drama_id, "drama_id")
        for anomaly_id in self.anomaly_ids:
            _require_positive(anomaly_id, "anomaly_ids")


@dataclass(frozen=True, slots=True)
class BenchmarkInput:
    comparison_scope: ComparisonScope
    window: AnalysisWindow
    members: tuple[BenchmarkMemberInput, ...]
    analysis_as_of: datetime

    def __post_init__(self) -> None:
        _require_aware(self.analysis_as_of, "analysis_as_of")
        member_ids = tuple(member.drama_id for member in self.members)
        if len(set(member_ids)) != len(member_ids):
            raise ValueError("benchmark members must have unique drama IDs")
        if any(
            drama_id not in self.comparison_scope.drama_ids
            for drama_id in member_ids
        ):
            raise ValueError("benchmark members must belong to comparison scope")


@dataclass(frozen=True, slots=True)
class BenchmarkMetric:
    metric_type: BenchmarkMetricType
    value: Decimal | str | None
    group_median: Decimal | None
    unit: str
    availability: AnalysisAvailability

    def __post_init__(self) -> None:
        _require_enum(self.metric_type, BenchmarkMetricType, "metric_type")
        _require_nonblank(self.unit, "unit")


@dataclass(frozen=True, slots=True)
class BenchmarkMemberResult:
    drama_id: int
    metrics: tuple[BenchmarkMetric, ...]
    availability: AnalysisAvailability

    def __post_init__(self) -> None:
        _require_positive(self.drama_id, "drama_id")


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    target_drama_id: int | None
    comparison_scope: ComparisonScope
    window: AnalysisWindow
    metrics: tuple[BenchmarkMemberResult, ...]
    availability: AnalysisAvailability
    benchmark_version: str
    lifecycle_rule_version: str
    analysis_revision: str | None
    analysis_as_of: datetime

    def __post_init__(self) -> None:
        if self.target_drama_id is not None:
            _require_positive(self.target_drama_id, "target_drama_id")
            if self.target_drama_id not in self.comparison_scope.drama_ids:
                raise ValueError("target_drama_id must belong to comparison scope")
        _require_nonblank(self.benchmark_version, "benchmark_version")
        _require_nonblank(self.lifecycle_rule_version, "lifecycle_rule_version")
        _require_aware(self.analysis_as_of, "analysis_as_of")


@dataclass(frozen=True, slots=True)
class AnalysisRevisionInput:
    analysis_type: str
    entity_ids: tuple[int, ...]
    parameters: tuple[tuple[str, str], ...]
    analysis_as_of: datetime
    snapshot_revision_ids: tuple[int, ...] = ()
    source_result_versions: tuple[tuple[int, str], ...] = ()
    rule_versions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonblank(self.analysis_type, "analysis_type")
        _require_aware(self.analysis_as_of, "analysis_as_of")
        for entity_id in self.entity_ids:
            _require_positive(entity_id, "entity_ids")
        for revision_id in self.snapshot_revision_ids:
            _require_positive(revision_id, "snapshot_revision_ids")
        if any(not key.strip() for key, _ in self.parameters):
            raise ValueError("revision parameter names must not be blank")
        if any(not version.strip() for version in self.rule_versions):
            raise ValueError("rule_versions must not contain blank values")


__all__ = [
    "ACTION_EFFECT_RULE_VERSION",
    "AnalysisAvailability",
    "AnalysisRevisionInput",
    "AnalysisVersionInfo",
    "AnalysisWindow",
    "AvailabilityReason",
    "AvailabilityStatus",
    "BENCHMARK_VERSION",
    "BenchmarkInput",
    "BenchmarkMemberInput",
    "BenchmarkMemberResult",
    "BenchmarkMetric",
    "BenchmarkMetricType",
    "BenchmarkResult",
    "ComparisonScope",
    "DailyCumulativePoint",
    "LIFECYCLE_RULE_VERSION",
    "LifecycleEvidence",
    "LifecycleInput",
    "LifecycleResult",
    "LifecycleStage",
    "MetricChange",
    "MetricDirection",
    "NON_CAUSAL_DISCLAIMER",
    "NumericValue",
    "OperationEffectivenessInput",
    "OperationEffectivenessResult",
    "OperationMetricType",
]
