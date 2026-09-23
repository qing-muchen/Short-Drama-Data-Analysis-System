"""Read-only input providers for Phase 8 deterministic rule components."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol, Sequence
from zoneinfo import ZoneInfo

from repositories.operation_analytics_repository import (
    ActionReadPage,
    AnomalyReadRecord,
    DramaReadRecord,
    MetricRevisionReadRecord,
)
from services.operation_analytics.contracts import (
    AnalysisAvailability,
    AnalysisWindow,
    AvailabilityReason,
    AvailabilityStatus,
    BenchmarkInput,
    BenchmarkMemberInput,
    ComparisonScope,
    DailyCumulativePoint,
    LifecycleInput,
    OperationEffectivenessInput,
)


BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


class OperationAnalyticsReadRepository(Protocol):
    """Structural read contract required by the three providers."""

    def list_completed_actions(self, **kwargs) -> ActionReadPage: ...

    def list_completed_actions_in_range(self, **kwargs): ...

    def list_drama_records(self, **kwargs) -> tuple[DramaReadRecord, ...]: ...

    def list_metric_revisions(
        self, **kwargs
    ) -> tuple[MetricRevisionReadRecord, ...]: ...

    def list_anomalies(self, **kwargs) -> tuple[AnomalyReadRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class OperationEffectivenessInputPage:
    """Provider batch that preserves stable Repository pagination metadata."""

    page: int
    page_size: int
    total: int
    items: tuple[OperationEffectivenessInput, ...]


class OperationEffectivenessProvider:
    """Prepare completed-action inputs; calculation remains a Service concern."""

    def __init__(self, repository: OperationAnalyticsReadRepository) -> None:
        self.repository = repository

    def get_inputs(
        self,
        *,
        analysis_as_of: datetime,
        action_id: int | None = None,
        drama_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> OperationEffectivenessInputPage:
        _require_aware(analysis_as_of)
        action_page = self.repository.list_completed_actions(
            analysis_as_of=analysis_as_of,
            action_id=action_id,
            drama_id=drama_id,
            page=page,
            page_size=page_size,
        )
        eligible = tuple(item for item in action_page.items if item.drama_id is not None)
        if not eligible:
            return OperationEffectivenessInputPage(
                page=action_page.page,
                page_size=action_page.page_size,
                total=action_page.total,
                items=(),
            )

        windows = {
            item.action_id: _action_windows(_as_aware_utc(item.anchor_time))
            for item in eligible
        }
        earliest_date = min(pair[0].start_date - timedelta(days=1) for pair in windows.values())
        latest_date = max(pair[1].end_date for pair in windows.values())
        drama_ids = tuple(sorted({int(item.drama_id) for item in eligible}))
        start_time, end_time = _utc_bounds(earliest_date, latest_date)
        revisions = self.repository.list_metric_revisions(
            drama_ids=drama_ids,
            start_time=start_time,
            end_time=end_time,
            analysis_as_of=analysis_as_of,
        )
        anomalies = self.repository.list_anomalies(
            drama_ids=drama_ids,
            start_time=start_time,
            end_time=end_time,
            analysis_as_of=analysis_as_of,
        )
        actions = self.repository.list_completed_actions_in_range(
            drama_ids=drama_ids,
            start_time=start_time,
            end_time=end_time,
            analysis_as_of=analysis_as_of,
        )
        points_by_drama = _points_by_drama(revisions)
        anomalies_by_drama = _anomalies_by_drama(anomalies)
        actions_by_drama = defaultdict(list)
        for other in actions:
            if other.drama_id is not None:
                actions_by_drama[other.drama_id].append(other)

        results = []
        for item in eligible:
            current_drama_id = int(item.drama_id)
            anchor_time = _as_aware_utc(item.anchor_time).astimezone(
                BUSINESS_TIMEZONE
            )
            before, after = windows[item.action_id]
            points = points_by_drama.get(current_drama_id, ())
            before_points = _points_for_window(points, before)
            after_points = _points_for_window(points, after)
            before_anomalies = _anomalies_for_window(
                anomalies_by_drama.get(current_drama_id, ()), before
            )
            after_anomalies = _anomalies_for_window(
                anomalies_by_drama.get(current_drama_id, ()), after
            )
            overlapping = tuple(
                other.action_id
                for other in actions_by_drama.get(current_drama_id, ())
                if other.action_id != item.action_id
                and before.start_date
                <= _business_date(other.anchor_time)
                <= after.end_date
            )
            versions = tuple(
                sorted(
                    {
                        record.algorithm_version
                        for record in (*before_anomalies, *after_anomalies)
                    }
                )
            )
            results.append(
                OperationEffectivenessInput(
                    action_id=item.action_id,
                    drama_id=current_drama_id,
                    anchor_time=anchor_time,
                    before_window=before,
                    after_window=after,
                    before_points=before_points,
                    after_points=after_points,
                    before_anomaly_ids=tuple(
                        record.anomaly_id for record in before_anomalies
                    ),
                    after_anomaly_ids=tuple(
                        record.anomaly_id for record in after_anomalies
                    ),
                    anomaly_algorithm_versions=versions,
                    overlapping_action_ids=overlapping,
                )
            )
        return OperationEffectivenessInputPage(
            page=action_page.page,
            page_size=action_page.page_size,
            total=action_page.total,
            items=tuple(results),
        )


class LifecycleInputProvider:
    """Prepare one double-seven-day lifecycle input without classifying it."""

    def __init__(self, repository: OperationAnalyticsReadRepository) -> None:
        self.repository = repository

    def get_input(
        self, *, drama_id: int, analysis_as_of: datetime
    ) -> LifecycleInput | None:
        _require_aware(analysis_as_of)
        records = self.repository.list_drama_records(
            drama_ids=(drama_id,), analysis_as_of=analysis_as_of
        )
        if not records:
            return None
        drama = records[0]
        end_date = _business_date(analysis_as_of) - timedelta(days=1)
        start_date = end_date - timedelta(days=14)
        start_time, end_time = _utc_bounds(start_date, end_date)
        revisions = self.repository.list_metric_revisions(
            drama_ids=(drama_id,),
            start_time=start_time,
            end_time=end_time,
            analysis_as_of=analysis_as_of,
        )
        release_time = _release_time(drama)
        return LifecycleInput(
            drama_id=drama_id,
            drama_status=drama.status,
            release_time=release_time,
            points=_points_by_drama(revisions).get(drama_id, ()),
            analysis_as_of=analysis_as_of.astimezone(BUSINESS_TIMEZONE),
        )


class BenchmarkProvider:
    """Prepare an explicit same-platform 30-day comparison input."""

    def __init__(self, repository: OperationAnalyticsReadRepository) -> None:
        self.repository = repository

    def get_input(
        self,
        *,
        drama_ids: Sequence[int],
        platform_id: int,
        analysis_as_of: datetime,
    ) -> BenchmarkInput:
        _require_aware(analysis_as_of)
        scope = ComparisonScope(tuple(drama_ids), platform_id)
        end_date = _business_date(analysis_as_of) - timedelta(days=1)
        window = AnalysisWindow(end_date - timedelta(days=29), end_date, 30)
        start_time, end_time = _utc_bounds(
            window.start_date - timedelta(days=1), window.end_date
        )
        known = {
            record.drama_id
            for record in self.repository.list_drama_records(
                drama_ids=scope.drama_ids,
                analysis_as_of=analysis_as_of,
                platform_id=platform_id,
            )
        }
        revisions = self.repository.list_metric_revisions(
            drama_ids=scope.drama_ids,
            platform_id=platform_id,
            start_time=start_time,
            end_time=end_time,
            analysis_as_of=analysis_as_of,
        )
        anomalies = self.repository.list_anomalies(
            drama_ids=scope.drama_ids,
            start_time=start_time,
            end_time=end_time,
            analysis_as_of=analysis_as_of,
        )
        points_by_drama = _points_by_drama(revisions)
        anomalies_by_drama = _anomalies_by_drama(anomalies)
        members = []
        for drama_id in scope.drama_ids:
            points = points_by_drama.get(drama_id, ())
            member_anomalies = anomalies_by_drama.get(drama_id, ())
            availability = (
                AnalysisAvailability(AvailabilityStatus.AVAILABLE)
                if drama_id in known and points
                else AnalysisAvailability(
                    AvailabilityStatus.INSUFFICIENT,
                    (AvailabilityReason.INSUFFICIENT_HISTORY,),
                )
            )
            members.append(
                BenchmarkMemberInput(
                    drama_id=drama_id,
                    points=points,
                    anomaly_ids=tuple(item.anomaly_id for item in member_anomalies),
                    anomaly_algorithm_versions=tuple(
                        sorted({item.algorithm_version for item in member_anomalies})
                    ),
                    lifecycle_result=None,
                    availability=availability,
                )
            )
        return BenchmarkInput(
            comparison_scope=scope,
            window=window,
            members=tuple(members),
            analysis_as_of=analysis_as_of.astimezone(BUSINESS_TIMEZONE),
        )


def _action_windows(anchor_time: datetime) -> tuple[AnalysisWindow, AnalysisWindow]:
    anchor_date = _business_date(anchor_time)
    return (
        AnalysisWindow(anchor_date - timedelta(days=7), anchor_date - timedelta(days=1), 7),
        AnalysisWindow(anchor_date + timedelta(days=1), anchor_date + timedelta(days=7), 7),
    )


def _points_by_drama(
    records: Sequence[MetricRevisionReadRecord],
) -> dict[int, tuple[DailyCumulativePoint, ...]]:
    latest: dict[tuple[int, int, date], MetricRevisionReadRecord] = {}
    for record in records:
        key = (record.drama_id, record.platform_id, _business_date(record.snapshot_time))
        previous = latest.get(key)
        if previous is None or (
            _as_aware_utc(record.snapshot_time), record.snapshot_id
        ) > (_as_aware_utc(previous.snapshot_time), previous.snapshot_id):
            latest[key] = record
    grouped = defaultdict(list)
    for (drama_id, platform_id, business_date), record in latest.items():
        grouped[drama_id].append(
            DailyCumulativePoint(
                business_date=business_date,
                platform_id=platform_id,
                snapshot_revision_id=record.snapshot_revision_id,
                play_count=record.play_count,
                like_count=record.like_count,
                comment_count=record.comment_count,
                favorite_count=record.favorite_count,
                share_count=record.share_count,
            )
        )
    return {
        drama_id: tuple(
            sorted(points, key=lambda point: (point.business_date, point.platform_id))
        )
        for drama_id, points in grouped.items()
    }


def _points_for_window(
    points: Sequence[DailyCumulativePoint], window: AnalysisWindow
) -> tuple[DailyCumulativePoint, ...]:
    base_date = window.start_date - timedelta(days=1)
    return tuple(
        point for point in points if base_date <= point.business_date <= window.end_date
    )


def _anomalies_by_drama(
    records: Sequence[AnomalyReadRecord],
) -> dict[int, tuple[AnomalyReadRecord, ...]]:
    grouped = defaultdict(list)
    for record in records:
        grouped[record.drama_id].append(record)
    return {drama_id: tuple(items) for drama_id, items in grouped.items()}


def _anomalies_for_window(
    records: Sequence[AnomalyReadRecord], window: AnalysisWindow
) -> tuple[AnomalyReadRecord, ...]:
    return tuple(
        record
        for record in records
        if window.start_date <= _business_date(record.analysis_as_of) <= window.end_date
    )


def _release_time(record: DramaReadRecord) -> datetime | None:
    if record.online_at is not None:
        return _as_aware_utc(record.online_at).astimezone(BUSINESS_TIMEZONE)
    if record.premiere_date is None:
        return None
    local = datetime.combine(record.premiere_date, time.min, tzinfo=BUSINESS_TIMEZONE)
    return local


def _utc_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(start_date, time.min, tzinfo=BUSINESS_TIMEZONE)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=BUSINESS_TIMEZONE)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _business_date(value: datetime) -> date:
    return _as_aware_utc(value).astimezone(BUSINESS_TIMEZONE).date()


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("analysis_as_of must be timezone-aware")


__all__ = [
    "BenchmarkProvider",
    "LifecycleInputProvider",
    "OperationAnalyticsReadRepository",
    "OperationEffectivenessInputPage",
    "OperationEffectivenessProvider",
]
