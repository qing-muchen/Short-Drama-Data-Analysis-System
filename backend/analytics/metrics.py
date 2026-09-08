"""Raw and engagement metric calculations without persistence side effects."""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True, slots=True)
class RawMetrics:
    play_count: int | None
    like_count: int | None
    comment_count: int | None
    favorite_count: int | None
    share_count: int | None
    ranking: int | None = None

    @property
    def heat_complete(self) -> bool:
        return all(
            value is not None
            for value in (
                self.play_count,
                self.like_count,
                self.comment_count,
                self.favorite_count,
                self.share_count,
            )
        )


@dataclass(frozen=True, slots=True)
class EngagementMetrics:
    like_rate: float | None
    comment_rate: float | None
    favorite_rate: float | None
    share_rate: float | None
    engagement_rate: float | None
    quality_engagement: float | None


@dataclass(frozen=True, slots=True)
class SnapshotPoint:
    drama_id: int
    drama_code: str
    drama_status: str
    drama_platform_id: int
    drama_platform_status: str
    platform_id: int
    platform_status: str
    snapshot_id: int
    snapshot_revision_id: int
    snapshot_time: datetime
    revision_action: str
    raw: RawMetrics
    tag_ids: tuple[int, ...] = ()
    drama_name: str = ""
    warning_count: int = 0
    error_count: int = 0

    @property
    def is_valid(self) -> bool:
        return self.revision_action != "VOID" and self.error_count == 0


@dataclass(frozen=True, slots=True)
class MetricResult:
    object_key: int
    drama_id: int
    drama_code: str
    granularity: str
    snapshot_time: datetime | None
    raw: RawMetrics
    engagement: EngagementMetrics
    adjacent_growth: float | None
    growth_24h: float | None
    growth_7d: float | None
    growth_30d: float | None
    freshness: str | None
    quality_status: str | None
    warning_count: int
    excluded_error_count: int
    insufficient_history: bool
    included_platform_count: int
    drama_name: str = ""


def _safe_rate(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def calculate_engagement(raw: RawMetrics) -> EngagementMetrics:
    play = raw.play_count
    like_rate = _safe_rate(raw.like_count, play)
    comment_rate = _safe_rate(raw.comment_count, play)
    favorite_rate = _safe_rate(raw.favorite_count, play)
    share_rate = _safe_rate(raw.share_count, play)
    interactions = (
        raw.like_count,
        raw.comment_count,
        raw.favorite_count,
        raw.share_count,
    )
    engagement_rate = (
        _safe_rate(sum(value for value in interactions if value is not None), play)
        if all(value is not None for value in interactions)
        else None
    )
    quality_engagement = (
        _safe_rate(raw.like_count + raw.comment_count, play)
        if raw.like_count is not None and raw.comment_count is not None
        else None
    )
    return EngagementMetrics(
        like_rate=like_rate,
        comment_rate=comment_rate,
        favorite_rate=favorite_rate,
        share_rate=share_rate,
        engagement_rate=engagement_rate,
        quality_engagement=quality_engagement,
    )


def aggregate_raw(metrics: Iterable[RawMetrics]) -> RawMetrics:
    """Aggregate platform raw values before calculating ratios.

    Unknown component values remain unknown instead of being silently replaced by zero.
    Ranking is platform-scoped and therefore never aggregated.
    """

    rows = list(metrics)

    def total(attribute: str) -> int | None:
        values = [getattr(row, attribute) for row in rows]
        if not rows or any(value is None for value in values):
            return None
        return sum(values)

    return RawMetrics(
        play_count=total("play_count"),
        like_count=total("like_count"),
        comment_count=total("comment_count"),
        favorite_count=total("favorite_count"),
        share_count=total("share_count"),
        ranking=None,
    )
