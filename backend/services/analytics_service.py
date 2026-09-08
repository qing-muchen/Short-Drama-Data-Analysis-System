"""Analytics Service orchestrating Repository data and frozen V1 calculations."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from analytics.constants import (
    ACTIVE_MASTER_STATUS,
    CURRENT_DRAMA_STATUSES,
    CURRENT_RELEASE_STATUS,
    FRESHNESS_LIMIT,
)
from analytics.context import AnalysisContext
from analytics.growth import calculate_overall_growth, calculate_platform_growth, latest_point
from analytics.heat import HeatCandidate, HeatScore, calculate_heat_scores
from analytics.insight import Insight, generate_insights
from analytics.metrics import (
    MetricResult,
    RawMetrics,
    SnapshotPoint,
    aggregate_raw,
    calculate_engagement,
)
from analytics.potential import PotentialCandidate, PotentialScore, calculate_potential_scores
from repositories.analytics_repository import AnalyticsRecord, AnalyticsRepository
from repositories.drama_repository import DramaRepository
from services.base import BaseService
from services.exceptions import NotFoundException, ValidationException


@dataclass(frozen=True, slots=True)
class AnalyticsSummary:
    context: AnalysisContext
    metrics: MetricResult
    heat: HeatScore | None
    potential: PotentialScore | None
    insights: list[Insight]


class AnalyticsService(BaseService):
    """Build deterministic drama summaries without persisting derived metrics."""

    def __init__(
        self,
        session: Session,
        analytics: AnalyticsRepository,
        dramas: DramaRepository,
    ) -> None:
        super().__init__(session, analytics, dramas)
        self.analytics = analytics
        self.dramas = dramas

    def get_drama_summary(
        self,
        drama_id: int,
        context: AnalysisContext,
    ) -> AnalyticsSummary:
        drama = self.read(self.dramas.get_by_id, drama_id)
        if drama is None:
            raise NotFoundException(
                "Drama was not found",
                details={"drama_id": drama_id},
            )
        if context.granularity == "DRAMA_PLATFORM" and len(context.platform_scope) != 1:
            raise ValidationException(
                "DRAMA_PLATFORM summary requires exactly one platform",
                details={"platform_scope": list(context.platform_scope)},
            )

        records = self.read(
            self.analytics.list_snapshot_records,
            analysis_as_of=context.analysis_as_of,
            platform_ids=context.platform_scope,
            tag_ids=context.tag_scope,
        )
        points = [self._to_point(record) for record in records]
        scoped = [point for point in points if self._in_current_scope(point)]
        grouped = self._group_points(scoped, context.granularity)
        metric_results = {
            key: self._calculate_metrics(key, group, context)
            for key, group in grouped.items()
        }

        heat_scores = calculate_heat_scores(
            HeatCandidate(key, metric.drama_code, metric.raw)
            for key, metric in metric_results.items()
        )
        potential_scores = calculate_potential_scores(
            PotentialCandidate(
                object_key=key,
                drama_code=metric.drama_code,
                play_count=metric.raw.play_count,
                growth_7d=metric.growth_7d,
                quality_engagement=metric.engagement.quality_engagement,
                favorite_rate=metric.engagement.favorite_rate,
                share_rate=metric.engagement.share_rate,
            )
            for key, metric in metric_results.items()
        )
        target_key = drama_id
        if context.granularity == "DRAMA_PLATFORM":
            target_keys = [
                key
                for key, group in grouped.items()
                if group and group[0].drama_id == drama_id
            ]
            if not target_keys:
                raise NotFoundException(
                    "No eligible drama-platform data was found",
                    details={
                        "drama_id": drama_id,
                        "platform_scope": list(context.platform_scope),
                    },
                )
            target_key = target_keys[0]

        metrics = metric_results.get(target_key) or self._empty_metrics(
            object_key=target_key,
            drama_id=drama_id,
            drama_code=drama.drama_code,
            granularity=context.granularity,
        )
        heat = heat_scores.get(target_key)
        potential = potential_scores.get(target_key)
        insights = generate_insights(
            metrics=metrics,
            heat=heat,
            potential=potential,
            context=context,
        )
        return AnalyticsSummary(context, metrics, heat, potential, insights)

    def get_metrics(self, context: AnalysisContext) -> list[MetricResult]:
        """Return all current metrics in one AnalysisContext for Dashboard use."""

        points: list[SnapshotPoint] = []
        for record in self.read(
            self.analytics.list_snapshot_records,
            analysis_as_of=context.analysis_as_of,
            platform_ids=context.platform_scope,
            tag_ids=context.tag_scope,
        ):
            point = self._to_point(record)
            if self._in_current_scope(point):
                points.append(point)
        grouped = self._group_points(points, context.granularity)
        return [
            self._calculate_metrics(key, group, context)
            for key, group in sorted(grouped.items())
        ]

    def get_rankings(
        self, context: AnalysisContext
    ) -> tuple[list[MetricResult], dict[int, HeatScore], dict[int, PotentialScore]]:
        """Return metrics plus V1 rankings; Dashboard only formats these results."""

        metrics = self.get_metrics(context)
        heat_scores = calculate_heat_scores(
            HeatCandidate(metric.object_key, metric.drama_code, metric.raw)
            for metric in metrics
        )
        potential_scores = calculate_potential_scores(
            PotentialCandidate(
                object_key=metric.object_key,
                drama_code=metric.drama_code,
                play_count=metric.raw.play_count,
                growth_7d=metric.growth_7d,
                quality_engagement=metric.engagement.quality_engagement,
                favorite_rate=metric.engagement.favorite_rate,
                share_rate=metric.engagement.share_rate,
            )
            for metric in metrics
        )
        return metrics, heat_scores, potential_scores

    def get_trend(self, context: AnalysisContext) -> list[dict[str, object]]:
        """Build a daily cumulative trend from valid snapshots, not snapshot sums."""

        from analytics.constants import WINDOW_TARGETS

        start = context.analysis_as_of - WINDOW_TARGETS[context.time_window]
        points: list[SnapshotPoint] = []
        for record in self.read(
            self.analytics.list_snapshot_records,
            analysis_as_of=context.analysis_as_of,
            platform_ids=context.platform_scope,
            tag_ids=context.tag_scope,
        ):
            point = self._to_point(record)
            if (
                self._in_current_scope(point)
                and point.is_valid
                and point.snapshot_time >= start
            ):
                points.append(point)
        by_day: dict[object, list[SnapshotPoint]] = defaultdict(list)
        for point in points:
            by_day[point.snapshot_time.date()].append(point)
        result: list[dict[str, object]] = []
        for day in sorted(by_day):
            latest_by_platform: dict[int, SnapshotPoint] = {}
            for point in by_day[day]:
                previous = latest_by_platform.get(point.drama_platform_id)
                if previous is None or point.snapshot_time > previous.snapshot_time:
                    latest_by_platform[point.drama_platform_id] = point
            raw = aggregate_raw(point.raw for point in latest_by_platform.values())
            engagement = calculate_engagement(raw)
            result.append(
                {
                    "date": day,
                    "play_count": raw.play_count,
                    "engagement_rate": engagement.engagement_rate,
                }
            )
        return result

    def get_quality_summary(self, context: AnalysisContext) -> dict[str, object]:
        return self.quality_summary_from_metrics(self.get_metrics(context))

    @staticmethod
    def quality_summary_from_metrics(
        metrics: Iterable[MetricResult],
    ) -> dict[str, object]:
        metrics = list(metrics)
        return {
            "quality_issue_count": sum(
                metric.warning_count + metric.excluded_error_count
                for metric in metrics
            ),
            "warning_count": sum(metric.warning_count for metric in metrics),
            "error_count": sum(metric.excluded_error_count for metric in metrics),
            "freshness_summary": {
                "fresh": sum(metric.freshness == "FRESH" for metric in metrics),
                "stale": sum(metric.freshness == "STALE" for metric in metrics),
                "unknown": sum(metric.freshness is None for metric in metrics),
            },
        }

    @staticmethod
    def _to_point(record: AnalyticsRecord) -> SnapshotPoint:
        return SnapshotPoint(
            drama_id=record.drama_id,
            drama_code=record.drama_code,
            drama_status=record.drama_status,
            drama_platform_id=record.drama_platform_id,
            drama_platform_status=record.drama_platform_status,
            platform_id=record.platform_id,
            platform_status=record.platform_status,
            snapshot_id=record.snapshot_id,
            snapshot_revision_id=record.snapshot_revision_id,
            snapshot_time=record.snapshot_time,
            revision_action=record.revision_action,
            raw=RawMetrics(
                record.play_count,
                record.like_count,
                record.comment_count,
                record.favorite_count,
                record.share_count,
                record.ranking,
            ),
            tag_ids=record.tag_ids,
            warning_count=record.warning_count,
            error_count=record.error_count,
            drama_name=record.drama_name,
        )

    @staticmethod
    def _in_current_scope(point: SnapshotPoint) -> bool:
        return (
            point.drama_status in CURRENT_DRAMA_STATUSES
            and point.drama_platform_status == CURRENT_RELEASE_STATUS
            and point.platform_status == ACTIVE_MASTER_STATUS
        )

    @staticmethod
    def _group_points(
        points: Iterable[SnapshotPoint], granularity: str
    ) -> dict[int, list[SnapshotPoint]]:
        grouped: dict[int, list[SnapshotPoint]] = defaultdict(list)
        for point in points:
            key = (
                point.drama_platform_id
                if granularity == "DRAMA_PLATFORM"
                else point.drama_id
            )
            grouped[key].append(point)
        return dict(grouped)

    @staticmethod
    def _calculate_metrics(
        object_key: int,
        points: list[SnapshotPoint],
        context: AnalysisContext,
    ) -> MetricResult:
        by_platform: dict[int, list[SnapshotPoint]] = defaultdict(list)
        for point in points:
            by_platform[point.drama_platform_id].append(point)
        current = [
            latest_point(platform_points, context.analysis_as_of)
            for platform_points in by_platform.values()
        ]
        current = [point for point in current if point is not None]

        if context.granularity == "DRAMA_PLATFORM":
            raw = current[0].raw if current else RawMetrics(None, None, None, None, None)
            growth = calculate_platform_growth(points, context.analysis_as_of)
        else:
            raw = aggregate_raw(point.raw for point in current)
            growth = calculate_overall_growth(
                by_platform.values(), context.analysis_as_of
            )

        warning_count = sum(point.warning_count for point in current)
        excluded_error_count = sum(point.error_count > 0 for point in points)
        snapshot_time = max((point.snapshot_time for point in current), default=None)
        stale = any(
            context.analysis_as_of - point.snapshot_time > FRESHNESS_LIMIT
            for point in current
        )
        quality_status = (
            "ERROR"
            if excluded_error_count
            else "WARNING"
            if warning_count
            else "NORMAL"
            if current
            else None
        )
        return MetricResult(
            object_key=object_key,
            drama_id=points[0].drama_id,
            drama_code=points[0].drama_code,
            granularity=context.granularity,
            snapshot_time=snapshot_time,
            raw=raw,
            engagement=calculate_engagement(raw),
            adjacent_growth=growth.adjacent,
            growth_24h=growth.growth_24h,
            growth_7d=growth.growth_7d,
            growth_30d=growth.growth_30d,
            freshness="STALE" if stale else "FRESH" if current else None,
            quality_status=quality_status,
            warning_count=warning_count,
            excluded_error_count=excluded_error_count,
            insufficient_history=growth.growth_7d is None,
            included_platform_count=len(current),
            drama_name=points[0].drama_name,
        )

    @staticmethod
    def _empty_metrics(
        *, object_key: int, drama_id: int, drama_code: str, granularity: str
    ) -> MetricResult:
        raw = RawMetrics(None, None, None, None, None)
        return MetricResult(
            object_key=object_key,
            drama_id=drama_id,
            drama_code=drama_code,
            granularity=granularity,
            snapshot_time=None,
            raw=raw,
            engagement=calculate_engagement(raw),
            adjacent_growth=None,
            growth_24h=None,
            growth_7d=None,
            growth_30d=None,
            freshness=None,
            quality_status=None,
            warning_count=0,
            excluded_error_count=0,
            insufficient_history=True,
            included_platform_count=0,
            drama_name="",
        )
