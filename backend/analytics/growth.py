"""Frozen adjacent and window Growth calculations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from analytics.constants import WINDOW_TARGETS, WINDOW_TOLERANCES
from analytics.metrics import SnapshotPoint


@dataclass(frozen=True, slots=True)
class GrowthResult:
    adjacent: float | None
    growth_24h: float | None
    growth_7d: float | None
    growth_30d: float | None


def growth_rate(current: int | None, previous: int | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous


def valid_points(
    points: Iterable[SnapshotPoint], analysis_as_of: datetime
) -> list[SnapshotPoint]:
    return sorted(
        (
            point
            for point in points
            if point.is_valid and point.snapshot_time <= analysis_as_of
        ),
        key=lambda point: (point.snapshot_time, point.snapshot_revision_id),
    )


def latest_point(
    points: Iterable[SnapshotPoint], analysis_as_of: datetime
) -> SnapshotPoint | None:
    eligible = valid_points(points, analysis_as_of)
    return eligible[-1] if eligible else None


def _baseline(
    points: list[SnapshotPoint],
    *,
    target: datetime,
    tolerance_key: str,
) -> SnapshotPoint | None:
    earliest = target - WINDOW_TOLERANCES[tolerance_key]
    eligible = [point for point in points if earliest <= point.snapshot_time <= target]
    return eligible[-1] if eligible else None


def calculate_platform_growth(
    points: Iterable[SnapshotPoint], analysis_as_of: datetime
) -> GrowthResult:
    eligible = valid_points(points, analysis_as_of)
    if not eligible:
        return GrowthResult(None, None, None, None)
    current = eligible[-1]
    previous = eligible[-2] if len(eligible) >= 2 else None

    window_values: dict[str, float | None] = {}
    for key, offset in WINDOW_TARGETS.items():
        baseline = _baseline(
            eligible,
            target=analysis_as_of - offset,
            tolerance_key=key,
        )
        window_values[key] = growth_rate(
            current.raw.play_count,
            baseline.raw.play_count if baseline else None,
        )
    return GrowthResult(
        adjacent=growth_rate(
            current.raw.play_count,
            previous.raw.play_count if previous else None,
        ),
        growth_24h=window_values["24H"],
        growth_7d=window_values["7D"],
        growth_30d=window_values["30D"],
    )


def calculate_overall_growth(
    platform_points: Iterable[Iterable[SnapshotPoint]],
    analysis_as_of: datetime,
) -> GrowthResult:
    """Aggregate current/baseline counts over comparable platform sets."""

    groups = [valid_points(points, analysis_as_of) for points in platform_points]
    groups = [points for points in groups if points]

    def comparable_growth(window_key: str) -> float | None:
        current_total = 0
        baseline_total = 0
        comparable = False
        target = analysis_as_of - WINDOW_TARGETS[window_key]
        for points in groups:
            current = points[-1]
            baseline = _baseline(points, target=target, tolerance_key=window_key)
            if baseline is None:
                continue
            if current.raw.play_count is None or baseline.raw.play_count is None:
                continue
            current_total += current.raw.play_count
            baseline_total += baseline.raw.play_count
            comparable = True
        return growth_rate(current_total, baseline_total) if comparable else None

    adjacent_current = 0
    adjacent_previous = 0
    adjacent_comparable = False
    for points in groups:
        if len(points) < 2:
            continue
        current, previous = points[-1], points[-2]
        if current.raw.play_count is None or previous.raw.play_count is None:
            continue
        adjacent_current += current.raw.play_count
        adjacent_previous += previous.raw.play_count
        adjacent_comparable = True

    return GrowthResult(
        adjacent=(
            growth_rate(adjacent_current, adjacent_previous)
            if adjacent_comparable
            else None
        ),
        growth_24h=comparable_growth("24H"),
        growth_7d=comparable_growth("7D"),
        growth_30d=comparable_growth("30D"),
    )

