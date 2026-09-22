"""Read-only providers that map existing repositories to profile DTOs.

Providers intentionally depend on repository-shaped protocols rather than ORM
models or business services.  They never calculate, persist, or manage a
transaction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from services.drama_profile.contracts import (
    ActionProfileSummary,
    AnomalyProfileSummary,
    AvailabilityReason,
    ExplanationProfileSummary,
    ModuleAvailability,
    PredictionProfileSummary,
    QualityProfileSummary,
    ScoreProfileSummary,
)


class ProfileProvider(Protocol):
    """Common read-only provider contract."""

    def get_profile_summary(self, drama_id: int) -> Any: ...


def _value(entity: Any, name: str, default: Any = None) -> Any:
    """Read an attribute from a repository DTO without importing its type."""

    if isinstance(entity, Mapping):
        return entity.get(name, default)
    return getattr(entity, name, default)


def _available() -> ModuleAvailability:
    return ModuleAvailability(available=True)


def _unavailable(reason: AvailabilityReason) -> ModuleAvailability:
    return ModuleAvailability(available=False, reason=reason)


class ScoreProfileProvider:
    """Map the latest ALL-scope drama score to a compact summary."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def get_profile_summary(self, drama_id: int) -> ScoreProfileSummary:
        score = self.repository.get_latest_by_drama(
            drama_id=drama_id,
            algorithm_version="Composite Score V1.0",
            score_scope_type="ALL",
            score_scope_id=0,
        )
        if score is None:
            return ScoreProfileSummary(available=_unavailable(AvailabilityReason.NOT_CALCULATED))
        dimensions = {
            key: float(_value(score, key, 0))
            for key in ("heat_score", "growth_score", "engagement_score", "lifecycle_score")
        }
        return ScoreProfileSummary(
            available=_available(),
            score_level=_value(score, "level"),
            dimensions=dimensions,
            analysis_as_of=_value(score, "analysis_as_of"),
            algorithm_version=_value(score, "algorithm_version"),
        )


class QualityProfileProvider:
    """Read the global quality result; Phase 2 quality is not drama-scoped."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def get_profile_summary(self, drama_id: int) -> QualityProfileSummary:
        del drama_id
        score = self.repository.get_current_score(
            score_scope_type="ALL",
            score_scope_id=0,
        )
        if score is None:
            return QualityProfileSummary(available=_unavailable(AvailabilityReason.NOT_CALCULATED))
        open_issues = _value(score, "open_issue_count", 0)
        risk_message = f"存在 {open_issues} 个开放质量问题" if open_issues else None
        return QualityProfileSummary(
            available=_available(),
            quality_level=_value(score, "quality_grade"),
            quality_status="OPEN_ISSUES" if open_issues else "HEALTHY",
            risk_message=risk_message,
            analysis_as_of=_value(score, "analysis_as_of"),
            rule_set_version=_value(score, "rule_set_version"),
        )


class PredictionProfileProvider:
    """Map an existing PLAY_COUNT prediction without recalculating it."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def get_profile_summary(self, drama_id: int) -> PredictionProfileSummary:
        prediction = self.repository.get_latest_prediction(
            drama_id=drama_id,
            metric_type="PLAY_COUNT",
            algorithm_version="Moving Average V1.0",
        )
        if prediction is not None:
            return PredictionProfileSummary(
                available=_available(),
                trend_direction=_value(prediction, "trend_direction"),
                prediction_status="CALCULATED",
                analysis_as_of=_value(prediction, "analysis_as_of"),
                algorithm_version=_value(prediction, "algorithm_version"),
            )
        reason = AvailabilityReason.NOT_CALCULATED
        status_provider = getattr(self.repository, "get_prediction_status", None)
        if callable(status_provider):
            status = status_provider(drama_id=drama_id, metric_type="PLAY_COUNT")
            if status == AvailabilityReason.INSUFFICIENT_HISTORY.value:
                reason = AvailabilityReason.INSUFFICIENT_HISTORY
        return PredictionProfileSummary(available=_unavailable(reason))


class AnomalyProfileProvider:
    """Summarize persisted findings; it does not run anomaly detection."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def get_profile_summary(self, drama_id: int) -> AnomalyProfileSummary:
        records: Sequence[Any] = self.repository.get_by_drama(drama_id=drama_id)
        active = [record for record in records if _value(record, "status") in {"OPEN", "ACKNOWLEDGED"}]
        if not records:
            detected_provider = getattr(self.repository, "has_detection_for_drama", None)
            if callable(detected_provider) and not detected_provider(drama_id=drama_id):
                reason = AvailabilityReason.NOT_DETECTED
            else:
                reason = AvailabilityReason.NO_ANOMALY
            return AnomalyProfileSummary(available=_unavailable(reason))
        severity_rank = {"A": 3, "B": 2, "C": 1}
        highest = max((_value(item, "severity") for item in active), key=lambda value: severity_rank.get(value, 0), default=None)
        latest = tuple(
            {
                "anomaly_id": _value(item, "anomaly_id"),
                "anomaly_type": _value(item, "anomaly_type"),
                "severity": _value(item, "severity"),
                "status": _value(item, "status"),
                "analysis_as_of": _value(item, "analysis_as_of"),
            }
            for item in records[:5]
        )
        return AnomalyProfileSummary(
            available=_available(),
            active_count=len(active),
            highest_severity=highest,
            latest_anomalies=latest,
            analysis_as_of=_value(records[0], "analysis_as_of"),
        )


class ActionProfileProvider:
    """Summarize open actions for one drama."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def get_profile_summary(self, drama_id: int) -> ActionProfileSummary:
        page = self.repository.list_actions(page=1, page_size=20, drama_id=drama_id)
        actions = list(_value(page, "items", page if isinstance(page, Sequence) else []))
        return ActionProfileSummary(
            available=_available(),
            open_count=sum(_value(item, "status") == "OPEN" for item in actions),
            in_progress_count=sum(_value(item, "status") == "IN_PROGRESS" for item in actions),
            recent_actions=tuple(
                {
                    "action_id": _value(item, "action_id"),
                    "title": _value(item, "title"),
                    "status": _value(item, "status"),
                    "priority": _value(item, "priority"),
                    "updated_at": _value(item, "updated_at"),
                }
                for item in actions[:5]
            ),
        )


class ExplanationProfileProvider:
    """Read an existing explanation snapshot and its lineage availability."""

    def __init__(self, repository: Any, lineage_repository: Any | None = None) -> None:
        self.repository = repository
        self.lineage_repository = lineage_repository

    def get_profile_summary(self, drama_id: int) -> ExplanationProfileSummary:
        explanation = self.repository.get_latest_explanation(
            entity_type="ANOMALY",
            entity_id=drama_id,
            module_type="ANOMALY",
        )
        if explanation is None:
            return ExplanationProfileSummary(available=_unavailable(AvailabilityReason.NOT_AVAILABLE))
        lineage_available = False
        if self.lineage_repository is not None:
            lineage = self.lineage_repository.get_lineage_by_target(
                target_type="EXPLANATION",
                target_id=_value(explanation, "explanation_id"),
            )
            lineage_available = bool(lineage)
        latest = {
            "explanation_id": _value(explanation, "explanation_id"),
            "summary": _value(explanation, "summary"),
            "analysis_as_of": _value(explanation, "analysis_as_of"),
            "algorithm_version": _value(explanation, "algorithm_version"),
        }
        return ExplanationProfileSummary(
            available=_available(),
            latest_explanation=latest,
            lineage_available=lineage_available,
        )


__all__ = [
    "ActionProfileProvider",
    "AnomalyProfileProvider",
    "ExplanationProfileProvider",
    "PredictionProfileProvider",
    "ProfileProvider",
    "QualityProfileProvider",
    "ScoreProfileProvider",
]
