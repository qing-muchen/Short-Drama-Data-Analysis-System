"""Read-only aggregation service for the Drama 360° profile."""

from __future__ import annotations

from typing import Any

from services.drama_profile.contracts import (
    ActionProfileSummary,
    AnomalyProfileSummary,
    AvailabilityReason,
    DramaProfileBasic,
    DramaProfileResponse,
    ExplanationProfileSummary,
    ModuleAvailability,
    PredictionProfileSummary,
    QualityProfileSummary,
    ScoreProfileSummary,
)


class DramaProfileService:
    """Aggregate provider DTOs without calculating or persisting business facts."""

    def __init__(
        self,
        score_provider: Any,
        quality_provider: Any,
        prediction_provider: Any,
        anomaly_provider: Any,
        action_provider: Any,
        explanation_provider: Any,
        basic_provider: Any | None = None,
    ) -> None:
        self.score_provider = score_provider
        self.quality_provider = quality_provider
        self.prediction_provider = prediction_provider
        self.anomaly_provider = anomaly_provider
        self.action_provider = action_provider
        self.explanation_provider = explanation_provider
        self.basic_provider = basic_provider

    def get_profile(self, drama_id: int) -> DramaProfileResponse:
        """Return one profile, isolating failures of individual read providers."""

        if drama_id <= 0:
            raise ValueError("drama_id must be greater than zero")
        drama = self._get_basic(drama_id)
        performance = self._safe_summary(
            self.score_provider, drama_id, ScoreProfileSummary,
        )
        quality = self._safe_summary(
            self.quality_provider, drama_id, QualityProfileSummary,
        )
        trend = self._safe_summary(
            self.prediction_provider, drama_id, PredictionProfileSummary,
        )
        risk = self._safe_summary(
            self.anomaly_provider, drama_id, AnomalyProfileSummary,
        )
        operations = self._safe_summary(
            self.action_provider, drama_id, ActionProfileSummary,
        )
        explanations = self._safe_summary(
            self.explanation_provider, drama_id, ExplanationProfileSummary,
        )

        return DramaProfileResponse(
            drama=drama,
            availability={
                "score": performance.available,
                "quality": quality.available,
                "prediction": trend.available,
                "anomaly": risk.available,
                "action": operations.available,
                "explanation": explanations.available,
            },
            performance=performance,
            quality=quality,
            trend=trend,
            risk=risk,
            operations=operations,
            explanations=explanations,
        )

    def _get_basic(self, drama_id: int) -> DramaProfileBasic:
        if self.basic_provider is None:
            # V1 has no dedicated basic-data provider.  This explicit placeholder
            # keeps the service independent from ORM while preserving identity.
            return DramaProfileBasic(drama_id=drama_id, title=f"Drama {drama_id}")
        result = self.basic_provider.get_profile_basic(drama_id)
        if isinstance(result, DramaProfileBasic):
            return result
        return DramaProfileBasic(
            drama_id=drama_id,
            title=str(_read(result, "title", f"Drama {drama_id}")),
            platform=_read(result, "platform"),
            tags=tuple(_read(result, "tags", ()) or ()),
        )

    @staticmethod
    def _safe_summary(provider: Any, drama_id: int, summary_type: Any) -> Any:
        try:
            summary = provider.get_profile_summary(drama_id)
            if not isinstance(summary, summary_type):
                raise TypeError(
                    f"provider returned {type(summary).__name__}, "
                    f"expected {summary_type.__name__}"
                )
            return summary
        except Exception:
            return summary_type(
                available=ModuleAvailability(
                    available=False,
                    reason=AvailabilityReason.NOT_AVAILABLE,
                )
            )


def _read(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


__all__ = ["DramaProfileService"]
