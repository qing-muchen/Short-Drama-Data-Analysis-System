"""Pure Python contracts for deterministic analysis explanations.

This module intentionally has no persistence or web-layer dependencies.  The
service layer will later translate these contracts to the V013 ORM models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Protocol


class ExplanationType(str, Enum):
    """Internal handler keys, deliberately separate from database enums."""

    METRIC = "METRIC"
    TREND = "TREND"
    ANOMALY = "ANOMALY"


@dataclass(frozen=True, slots=True)
class LineageSource:
    """One logical source used while producing an explanation."""

    source_type: str
    source_id: int
    relationship_type: str

    def __post_init__(self) -> None:
        if not self.source_type.strip():
            raise ValueError("source_type must not be blank")
        if self.source_id <= 0:
            raise ValueError("source_id must be greater than zero")
        if not self.relationship_type.strip():
            raise ValueError("relationship_type must not be blank")


@dataclass(frozen=True, slots=True)
class ExplanationContext:
    """Input snapshot supplied to a pure explanation Generator."""

    entity_type: str
    entity_id: int
    module_type: str
    analysis_as_of: datetime
    algorithm_version: str
    rule_set_version: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    lineage_sources: tuple[LineageSource, ...] = ()

    def __post_init__(self) -> None:
        if not self.entity_type.strip():
            raise ValueError("entity_type must not be blank")
        if self.entity_id <= 0:
            raise ValueError("entity_id must be greater than zero")
        if not self.module_type.strip():
            raise ValueError("module_type must not be blank")
        if not self.algorithm_version.strip():
            raise ValueError("algorithm_version must not be blank")
        if not self.rule_set_version.strip():
            raise ValueError("rule_set_version must not be blank")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")


_FORBIDDEN_DETAIL_KEYS = {
    "score_value",
    "prediction_value",
    "complete_business_object",
}


def _contains_forbidden_key(value: Any) -> bool:
    """Reject forbidden persisted-value keys at any nested detail level."""

    if isinstance(value, Mapping):
        return any(
            str(key) in _FORBIDDEN_DETAIL_KEYS
            or _contains_forbidden_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(item) for item in value)
    return False


@dataclass(frozen=True, slots=True)
class GeneratedExplanation:
    """Pure Generator output before persistence."""

    summary: str
    detail: dict[str, Any]
    lineage_sources: tuple[LineageSource, ...] = ()

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("summary must not be blank")
        if not isinstance(self.detail, dict):
            raise TypeError("detail must be a dict")
        if _contains_forbidden_key(self.detail):
            raise ValueError(
                "detail must not contain score_value, prediction_value, "
                "or complete business object data"
            )


class ExplanationGenerator(Protocol):
    """Protocol implemented by a deterministic explanation handler."""

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        """Generate explanation data without I/O or persistence side effects."""


__all__ = [
    "ExplanationContext",
    "ExplanationGenerator",
    "ExplanationType",
    "GeneratedExplanation",
    "LineageSource",
]
