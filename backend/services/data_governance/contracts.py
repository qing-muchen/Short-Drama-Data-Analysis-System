"""Pure data contracts for the Phase 9 data governance read model.

The module intentionally contains no persistence, query, service or web-layer
dependencies.  It defines only immutable values exchanged by later providers,
rules, the orchestration service and API adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TypeAlias


FRESHNESS_RULE_VERSION = "Freshness Rules V1.0"
COMPLETENESS_RULE_VERSION = "Completeness Rules V1.0"
CONSISTENCY_RULE_VERSION = "Consistency Rules V1.0"
GOVERNANCE_RULE_SET_VERSION = "Governance Rule Set V1.0"

EvidenceScalar: TypeAlias = str | int | float | bool | None
EvidenceValue: TypeAlias = EvidenceScalar | tuple[EvidenceScalar, ...]
EntityId: TypeAlias = int | str


class QualityStatus(str, Enum):
    """Observed quality state, separate from input availability."""

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class AvailabilityStatus(str, Enum):
    """Completeness of the data required for an evaluation."""

    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class AvailabilityReason(str, Enum):
    """Closed reason set for incomplete or unavailable governance inputs."""

    NO_DATA = "NO_DATA"
    MISSING_SOURCE = "MISSING_SOURCE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INCOMPLETE_TIME_SERIES = "INCOMPLETE_TIME_SERIES"
    UNRESOLVED_RELATION = "UNRESOLVED_RELATION"
    REVISION_NOT_VISIBLE = "REVISION_NOT_VISIBLE"
    UNSUPPORTED_SCOPE = "UNSUPPORTED_SCOPE"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class QualityIssueType(str, Enum):
    FRESHNESS = "FRESHNESS"
    COMPLETENESS = "COMPLETENESS"
    CONSISTENCY = "CONSISTENCY"


class GovernanceScope(str, Enum):
    """Phase 9 V1 supports system-wide governance checks only."""

    SYSTEM = "SYSTEM"


def _require_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{field_name} must be a {enum_type.__name__}")


def _require_nonblank(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_aware(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_entity_id(value: EntityId | None, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{field_name} must be an integer or string")
    if isinstance(value, int) and value <= 0:
        raise ValueError(f"{field_name} integer values must be positive")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{field_name} string values must not be blank")


def _require_evidence_value(value: EvidenceValue, field_name: str) -> None:
    scalar_types = (str, int, float, bool, type(None))
    if isinstance(value, tuple):
        if any(not isinstance(item, scalar_types) for item in value):
            raise ValueError(f"{field_name} tuples must contain scalar values")
        return
    if not isinstance(value, scalar_types):
        raise ValueError(f"{field_name} must be a scalar or tuple of scalars")


def _require_string_tuple(value: tuple[str, ...], field_name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{field_name} must be an immutable tuple")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field_name} must contain non-blank strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{field_name} must not contain duplicates")


def _require_evidence_tuple(
    value: tuple["EvidenceItem", ...],
    field_name: str = "evidence",
) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{field_name} must be an immutable tuple")
    if any(not isinstance(item, EvidenceItem) for item in value):
        raise ValueError(f"{field_name} must contain only EvidenceItem values")


@dataclass(frozen=True, slots=True)
class DataQualityAvailability:
    """Explicit availability state; missing data is never encoded as zero."""

    status: AvailabilityStatus
    reasons: tuple[AvailabilityReason, ...] = ()
    message: str | None = None

    def __post_init__(self) -> None:
        _require_enum(self.status, AvailabilityStatus, "status")
        if not isinstance(self.reasons, tuple):
            raise ValueError("reasons must be an immutable tuple")
        if any(not isinstance(reason, AvailabilityReason) for reason in self.reasons):
            raise ValueError("reasons must contain only AvailabilityReason values")
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("availability reasons must be unique")
        reason_order = {reason: index for index, reason in enumerate(AvailabilityReason)}
        if self.reasons != tuple(sorted(self.reasons, key=reason_order.__getitem__)):
            raise ValueError("availability reasons must follow enum order")
        if self.status is AvailabilityStatus.AVAILABLE and self.reasons:
            raise ValueError("AVAILABLE cannot contain availability reasons")
        if self.status is not AvailabilityStatus.AVAILABLE and not self.reasons:
            raise ValueError("non-AVAILABLE status requires at least one reason")
        if self.message is not None:
            _require_nonblank(self.message, "message")


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """Minimal, JSON-safe evidence used to locate and explain an issue."""

    issue_type: QualityIssueType
    check_code: str
    entity_type: str
    entity_id: EntityId | None
    observed_value: EvidenceValue
    expected_condition: str
    source_type: str
    source_reference_ids: tuple[EntityId, ...]
    message: str

    def __post_init__(self) -> None:
        _require_enum(self.issue_type, QualityIssueType, "issue_type")
        _require_nonblank(self.check_code, "check_code")
        _require_nonblank(self.entity_type, "entity_type")
        _require_entity_id(self.entity_id, "entity_id")
        if self.entity_id is None and self.entity_type != GovernanceScope.SYSTEM.value:
            raise ValueError("entity_id may be omitted only for SYSTEM evidence")
        _require_evidence_value(self.observed_value, "observed_value")
        _require_nonblank(self.expected_condition, "expected_condition")
        _require_nonblank(self.source_type, "source_type")
        if not isinstance(self.source_reference_ids, tuple):
            raise ValueError("source_reference_ids must be an immutable tuple")
        for source_id in self.source_reference_ids:
            _require_entity_id(source_id, "source_reference_ids")
        if len(set(self.source_reference_ids)) != len(self.source_reference_ids):
            raise ValueError("source_reference_ids must be unique")
        _require_nonblank(self.message, "message")


@dataclass(frozen=True, slots=True)
class FreshnessRuleInput:
    """Timestamp facts supplied to FreshnessRule without a quality judgment."""

    entity_type: str
    entity_id: EntityId
    latest_timestamp: datetime | None
    current_timestamp: datetime
    threshold: timedelta = timedelta(hours=24)
    failure_threshold: timedelta = timedelta(hours=72)

    def __post_init__(self) -> None:
        _require_nonblank(self.entity_type, "entity_type")
        _require_entity_id(self.entity_id, "entity_id")
        if self.entity_id is None and self.entity_type != GovernanceScope.SYSTEM.value:
            raise ValueError("entity_id may be omitted only for SYSTEM inputs")
        if self.latest_timestamp is not None:
            _require_aware(self.latest_timestamp, "latest_timestamp")
        _require_aware(self.current_timestamp, "current_timestamp")
        if not isinstance(self.threshold, timedelta) or self.threshold <= timedelta(0):
            raise ValueError("threshold must be a positive timedelta")
        if (
            not isinstance(self.failure_threshold, timedelta)
            or self.failure_threshold <= self.threshold
        ):
            raise ValueError("failure_threshold must be greater than threshold")


@dataclass(frozen=True, slots=True)
class CompletenessRuleInput:
    """Coverage facts supplied to CompletenessRule without filling missing data."""

    expected_fields: tuple[str, ...]
    available_fields: tuple[str, ...]
    metric_coverage: tuple[tuple[str, bool], ...]
    entity_type: str = GovernanceScope.SYSTEM.value
    entity_id: EntityId | None = None
    expected_dates: tuple[date, ...] = ()
    available_dates: tuple[date, ...] = ()
    platform_relationship_available: bool = True
    play_count_available: bool = True

    def __post_init__(self) -> None:
        _require_string_tuple(self.expected_fields, "expected_fields")
        _require_string_tuple(self.available_fields, "available_fields")
        if not isinstance(self.metric_coverage, tuple):
            raise ValueError("metric_coverage must be an immutable tuple")
        metric_names: list[str] = []
        for entry in self.metric_coverage:
            if (
                not isinstance(entry, tuple)
                or len(entry) != 2
                or not isinstance(entry[1], bool)
            ):
                raise ValueError("metric_coverage entries must be (name, bool) tuples")
            _require_nonblank(entry[0], "metric_coverage name")
            metric_names.append(entry[0])
        if len(set(metric_names)) != len(metric_names):
            raise ValueError("metric_coverage names must be unique")
        _require_nonblank(self.entity_type, "entity_type")
        _require_entity_id(self.entity_id, "entity_id")
        for field_name in ("expected_dates", "available_dates"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or any(
                not isinstance(value, date) for value in values
            ):
                raise ValueError(f"{field_name} must contain only date values")
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must not contain duplicates")
            if values != tuple(sorted(values)):
                raise ValueError(f"{field_name} must be sorted")
        if not isinstance(self.platform_relationship_available, bool):
            raise ValueError("platform_relationship_available must be a bool")
        if not isinstance(self.play_count_available, bool):
            raise ValueError("play_count_available must be a bool")


@dataclass(frozen=True, slots=True)
class ConsistencyCheckInput:
    """One preloaded consistency fact; None means it cannot be resolved."""

    check_code: str
    entity_type: str
    entity_id: EntityId | None
    consistent: bool | None
    source_type: str
    source_reference_ids: tuple[EntityId, ...] = ()
    observed_value: EvidenceValue = None
    expected_condition: str = "consistent"

    def __post_init__(self) -> None:
        _require_nonblank(self.check_code, "check_code")
        _require_nonblank(self.entity_type, "entity_type")
        _require_entity_id(self.entity_id, "entity_id")
        if self.entity_id is None and self.entity_type != GovernanceScope.SYSTEM.value:
            raise ValueError("entity_id may be omitted only for SYSTEM checks")
        if self.consistent is not None and not isinstance(self.consistent, bool):
            raise ValueError("consistent must be bool or None")
        _require_nonblank(self.source_type, "source_type")
        if not isinstance(self.source_reference_ids, tuple):
            raise ValueError("source_reference_ids must be an immutable tuple")
        for source_id in self.source_reference_ids:
            _require_entity_id(source_id, "source_reference_ids")
        if len(set(self.source_reference_ids)) != len(self.source_reference_ids):
            raise ValueError("source_reference_ids must be unique")
        _require_evidence_value(self.observed_value, "observed_value")
        _require_nonblank(self.expected_condition, "expected_condition")


@dataclass(frozen=True, slots=True)
class ConsistencyRuleInput:
    """Relationship and revision facts supplied to ConsistencyRule."""

    relationship_checks: tuple[ConsistencyCheckInput, ...]
    revision_checks: tuple[ConsistencyCheckInput, ...]
    as_of_timestamp: datetime

    def __post_init__(self) -> None:
        for field_name in ("relationship_checks", "revision_checks"):
            checks = getattr(self, field_name)
            if not isinstance(checks, tuple):
                raise ValueError(f"{field_name} must be an immutable tuple")
            if any(not isinstance(check, ConsistencyCheckInput) for check in checks):
                raise ValueError(
                    f"{field_name} must contain only ConsistencyCheckInput values"
                )
        _require_aware(self.as_of_timestamp, "as_of_timestamp")


@dataclass(frozen=True, slots=True)
class FreshnessResult:
    status: QualityStatus
    availability: DataQualityAvailability
    delay_seconds: int | None
    evidence: tuple[EvidenceItem, ...] = ()
    analysis_as_of: datetime | None = None
    rule_version: str = FRESHNESS_RULE_VERSION
    summary: str | None = None

    def __post_init__(self) -> None:
        _require_enum(self.status, QualityStatus, "status")
        if not isinstance(self.availability, DataQualityAvailability):
            raise ValueError("availability must be DataQualityAvailability")
        if self.delay_seconds is not None and (
            isinstance(self.delay_seconds, bool)
            or not isinstance(self.delay_seconds, int)
        ):
            raise ValueError("delay_seconds must be an integer or None")
        _require_evidence_tuple(self.evidence)
        if self.status is not QualityStatus.HEALTHY and not self.evidence:
            raise ValueError("non-HEALTHY results require evidence")
        if (
            self.status is QualityStatus.NOT_AVAILABLE
            and self.availability.status is AvailabilityStatus.AVAILABLE
        ):
            raise ValueError("NOT_AVAILABLE quality cannot have AVAILABLE inputs")
        if self.analysis_as_of is not None:
            _require_aware(self.analysis_as_of, "analysis_as_of")
        _require_nonblank(self.rule_version, "rule_version")
        if self.summary is not None:
            _require_nonblank(self.summary, "summary")


@dataclass(frozen=True, slots=True)
class CompletenessResult:
    status: QualityStatus
    availability: DataQualityAvailability
    coverage_ratio: Decimal | None
    missing_items: tuple[str, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    analysis_as_of: datetime | None = None
    rule_version: str = COMPLETENESS_RULE_VERSION
    summary: str | None = None

    def __post_init__(self) -> None:
        _require_enum(self.status, QualityStatus, "status")
        if not isinstance(self.availability, DataQualityAvailability):
            raise ValueError("availability must be DataQualityAvailability")
        if self.coverage_ratio is not None:
            if not isinstance(self.coverage_ratio, Decimal):
                raise ValueError("coverage_ratio must be Decimal or None")
            if not Decimal("0") <= self.coverage_ratio <= Decimal("1"):
                raise ValueError("coverage_ratio must be between zero and one")
        _require_string_tuple(self.missing_items, "missing_items")
        _require_evidence_tuple(self.evidence)
        if self.status is not QualityStatus.HEALTHY and not self.evidence:
            raise ValueError("non-HEALTHY results require evidence")
        if (
            self.status is QualityStatus.NOT_AVAILABLE
            and self.availability.status is AvailabilityStatus.AVAILABLE
        ):
            raise ValueError("NOT_AVAILABLE quality cannot have AVAILABLE inputs")
        if self.analysis_as_of is not None:
            _require_aware(self.analysis_as_of, "analysis_as_of")
        _require_nonblank(self.rule_version, "rule_version")
        if self.summary is not None:
            _require_nonblank(self.summary, "summary")


@dataclass(frozen=True, slots=True)
class ConsistencyResult:
    status: QualityStatus
    availability: DataQualityAvailability
    issue_count: int
    evidence: tuple[EvidenceItem, ...] = ()
    analysis_as_of: datetime | None = None
    rule_version: str = CONSISTENCY_RULE_VERSION
    summary: str | None = None

    def __post_init__(self) -> None:
        _require_enum(self.status, QualityStatus, "status")
        if not isinstance(self.availability, DataQualityAvailability):
            raise ValueError("availability must be DataQualityAvailability")
        if (
            isinstance(self.issue_count, bool)
            or not isinstance(self.issue_count, int)
            or self.issue_count < 0
        ):
            raise ValueError("issue_count must be a non-negative integer")
        _require_evidence_tuple(self.evidence)
        if self.issue_count != len(self.evidence):
            raise ValueError("issue_count must equal the number of evidence items")
        if self.status is not QualityStatus.HEALTHY and not self.evidence:
            raise ValueError("non-HEALTHY results require evidence")
        if (
            self.status is QualityStatus.NOT_AVAILABLE
            and self.availability.status is AvailabilityStatus.AVAILABLE
        ):
            raise ValueError("NOT_AVAILABLE quality cannot have AVAILABLE inputs")
        if self.analysis_as_of is not None:
            _require_aware(self.analysis_as_of, "analysis_as_of")
        _require_nonblank(self.rule_version, "rule_version")
        if self.summary is not None:
            _require_nonblank(self.summary, "summary")


@dataclass(frozen=True, slots=True)
class DataGovernanceResponse:
    analysis_as_of: datetime
    scope: GovernanceScope
    availability: DataQualityAvailability
    freshness: FreshnessResult
    completeness: CompletenessResult
    consistency: ConsistencyResult
    rule_set_version: str = GOVERNANCE_RULE_SET_VERSION

    def __post_init__(self) -> None:
        _require_aware(self.analysis_as_of, "analysis_as_of")
        _require_enum(self.scope, GovernanceScope, "scope")
        if self.scope is not GovernanceScope.SYSTEM:
            raise ValueError("Phase 9 V1 supports SYSTEM scope only")
        if not isinstance(self.availability, DataQualityAvailability):
            raise ValueError("availability must be DataQualityAvailability")
        if not isinstance(self.freshness, FreshnessResult):
            raise ValueError("freshness must be FreshnessResult")
        if not isinstance(self.completeness, CompletenessResult):
            raise ValueError("completeness must be CompletenessResult")
        if not isinstance(self.consistency, ConsistencyResult):
            raise ValueError("consistency must be ConsistencyResult")
        _require_nonblank(self.rule_set_version, "rule_set_version")


__all__ = [
    "COMPLETENESS_RULE_VERSION",
    "CONSISTENCY_RULE_VERSION",
    "FRESHNESS_RULE_VERSION",
    "GOVERNANCE_RULE_SET_VERSION",
    "AvailabilityReason",
    "AvailabilityStatus",
    "CompletenessResult",
    "CompletenessRuleInput",
    "ConsistencyCheckInput",
    "ConsistencyResult",
    "ConsistencyRuleInput",
    "DataGovernanceResponse",
    "DataQualityAvailability",
    "EntityId",
    "EvidenceItem",
    "EvidenceScalar",
    "EvidenceValue",
    "FreshnessResult",
    "FreshnessRuleInput",
    "GovernanceScope",
    "QualityIssueType",
    "QualityStatus",
]
