"""Heat Model V1 deterministic Min-Max implementation."""

from dataclasses import dataclass
from typing import Iterable

from analytics.constants import HEAT_MODEL_VERSION, HEAT_WEIGHTS
from analytics.metrics import RawMetrics


@dataclass(frozen=True, slots=True)
class HeatCandidate:
    object_key: int
    drama_code: str
    raw: RawMetrics


@dataclass(frozen=True, slots=True)
class HeatScore:
    object_key: int
    score: float
    rank: int
    candidate_count: int
    model_version: str = HEAT_MODEL_VERSION


def _normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 0.0
    return (value - minimum) / (maximum - minimum)


def calculate_heat_scores(candidates: Iterable[HeatCandidate]) -> dict[int, HeatScore]:
    eligible = [candidate for candidate in candidates if candidate.raw.heat_complete]
    if not eligible:
        return {}
    ranges = {
        metric: (
            min(getattr(candidate.raw, metric) for candidate in eligible),
            max(getattr(candidate.raw, metric) for candidate in eligible),
        )
        for metric in HEAT_WEIGHTS
    }
    raw_scores = {
        candidate.object_key: 100
        * sum(
            weight
            * _normalize(
                getattr(candidate.raw, metric),
                ranges[metric][0],
                ranges[metric][1],
            )
            for metric, weight in HEAT_WEIGHTS.items()
        )
        for candidate in eligible
    }
    ordered = sorted(
        eligible,
        key=lambda candidate: (
            -raw_scores[candidate.object_key],
            -(candidate.raw.play_count or 0),
            candidate.drama_code,
        ),
    )
    return {
        candidate.object_key: HeatScore(
            object_key=candidate.object_key,
            score=raw_scores[candidate.object_key],
            rank=index,
            candidate_count=len(eligible),
        )
        for index, candidate in enumerate(ordered, start=1)
    }

