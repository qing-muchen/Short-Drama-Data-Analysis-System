"""Potential Model V1 candidate filtering and deterministic scoring."""

from dataclasses import dataclass
from typing import Iterable

from analytics.constants import POTENTIAL_MODEL_VERSION, POTENTIAL_WEIGHTS


@dataclass(frozen=True, slots=True)
class PotentialCandidate:
    object_key: int
    drama_code: str
    play_count: int | None
    growth_7d: float | None
    quality_engagement: float | None
    favorite_rate: float | None
    share_rate: float | None

    @property
    def eligible(self) -> bool:
        return self.play_count is not None and self.play_count > 0 and all(
            value is not None
            for value in (
                self.growth_7d,
                self.quality_engagement,
                self.favorite_rate,
                self.share_rate,
            )
        )


@dataclass(frozen=True, slots=True)
class PotentialScore:
    object_key: int
    score: float
    rank: int
    candidate_count: int
    model_version: str = POTENTIAL_MODEL_VERSION


def _normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 0.0
    return (value - minimum) / (maximum - minimum)


def calculate_potential_scores(
    candidates: Iterable[PotentialCandidate],
) -> dict[int, PotentialScore]:
    eligible = [candidate for candidate in candidates if candidate.eligible]
    if not eligible:
        return {}
    ranges = {
        metric: (
            min(getattr(candidate, metric) for candidate in eligible),
            max(getattr(candidate, metric) for candidate in eligible),
        )
        for metric in POTENTIAL_WEIGHTS
    }
    raw_scores = {
        candidate.object_key: 100
        * sum(
            weight
            * _normalize(
                getattr(candidate, metric),
                ranges[metric][0],
                ranges[metric][1],
            )
            for metric, weight in POTENTIAL_WEIGHTS.items()
        )
        for candidate in eligible
    }
    ordered = sorted(
        eligible,
        key=lambda candidate: (
            -raw_scores[candidate.object_key],
            -candidate.growth_7d,
            -candidate.quality_engagement,
            candidate.drama_code,
        ),
    )
    return {
        candidate.object_key: PotentialScore(
            object_key=candidate.object_key,
            score=raw_scores[candidate.object_key],
            rank=index,
            candidate_count=len(eligible),
        )
        for index, candidate in enumerate(ordered, start=1)
    }

