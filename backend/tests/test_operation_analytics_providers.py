"""DTO preparation and boundary tests for Phase 8 providers."""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from repositories.operation_analytics_repository import (
    ActionReadPage,
    ActionReadRecord,
    AnomalyReadRecord,
    DramaReadRecord,
    MetricRevisionReadRecord,
)
from services.operation_analytics.contracts import (
    AvailabilityReason,
    AvailabilityStatus,
    BenchmarkInput,
    LifecycleInput,
    OperationEffectivenessInput,
)
from services.operation_analytics.providers import (
    BenchmarkProvider,
    LifecycleInputProvider,
    OperationEffectivenessProvider,
)


UTC = timezone.utc
AS_OF = datetime(2026, 9, 22, tzinfo=UTC)


def metric_record(
    *,
    drama_id: int,
    platform_id: int,
    day: date,
    revision_id: int,
    play_count: int,
) -> MetricRevisionReadRecord:
    return MetricRevisionReadRecord(
        drama_id=drama_id,
        platform_id=platform_id,
        snapshot_id=revision_id,
        snapshot_revision_id=revision_id,
        snapshot_time=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
        version_no=1,
        revision_action="INITIAL",
        play_count=play_count,
        like_count=play_count // 10,
        comment_count=play_count // 20,
        favorite_count=play_count // 25,
        share_count=play_count // 50,
        changed_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
    )


class FakeRepository:
    def __init__(self) -> None:
        self.actions = ActionReadPage(1, 20, 0, ())
        self.range_actions = ()
        self.dramas = ()
        self.metrics = ()
        self.anomalies = ()
        self.calls = []

    def list_completed_actions(self, **kwargs):
        self.calls.append(("actions", kwargs))
        return self.actions

    def list_completed_actions_in_range(self, **kwargs):
        self.calls.append(("range_actions", kwargs))
        return self.range_actions

    def list_drama_records(self, **kwargs):
        self.calls.append(("dramas", kwargs))
        return self.dramas

    def list_metric_revisions(self, **kwargs):
        self.calls.append(("metrics", kwargs))
        return self.metrics

    def list_anomalies(self, **kwargs):
        self.calls.append(("anomalies", kwargs))
        return self.anomalies


def test_action_provider_constructs_windows_points_anomalies_and_overlap() -> None:
    repository = FakeRepository()
    anchor = datetime(2026, 9, 11, tzinfo=UTC)
    repository.actions = ActionReadPage(
        1, 20, 1, (ActionReadRecord(8, 3, anchor),)
    )
    repository.range_actions = (
        ActionReadRecord(8, 3, anchor),
        ActionReadRecord(9, 3, anchor + timedelta(days=2)),
    )
    repository.metrics = tuple(
        metric_record(
            drama_id=3,
            platform_id=2,
            day=date(2026, 9, 3) + timedelta(days=index),
            revision_id=index + 1,
            play_count=index * 100,
        )
        for index in range(16)
    )
    repository.anomalies = (
        AnomalyReadRecord(4, 3, datetime(2026, 9, 6, tzinfo=UTC), "A1"),
        AnomalyReadRecord(5, 3, datetime(2026, 9, 14, tzinfo=UTC), "A1"),
    )

    result = OperationEffectivenessProvider(repository).get_inputs(
        analysis_as_of=AS_OF
    )

    assert result.total == 1
    assert isinstance(result.items[0], OperationEffectivenessInput)
    assert result.items[0].before_window.day_count == 7
    assert result.items[0].after_window.day_count == 7
    assert result.items[0].before_anomaly_ids == (4,)
    assert result.items[0].after_anomaly_ids == (5,)
    assert result.items[0].overlapping_action_ids == (9,)


def test_action_provider_empty_data_returns_empty_tuple() -> None:
    repository = FakeRepository()
    assert OperationEffectivenessProvider(repository).get_inputs(
        analysis_as_of=AS_OF
    ).items == ()
    assert [name for name, _ in repository.calls] == ["actions"]


def test_lifecycle_provider_maps_drama_and_fifteen_day_input() -> None:
    repository = FakeRepository()
    repository.dramas = (
        DramaReadRecord(3, "SERIALIZING", date(2026, 8, 1), None),
    )
    repository.metrics = tuple(
        metric_record(
            drama_id=3,
            platform_id=2,
            day=date(2026, 9, 7) + timedelta(days=index),
            revision_id=index + 1,
            play_count=index * 100,
        )
        for index in range(15)
    )

    result = LifecycleInputProvider(repository).get_input(
        drama_id=3, analysis_as_of=AS_OF
    )

    assert isinstance(result, LifecycleInput)
    assert len(result.points) == 15
    assert result.release_time is not None


def test_lifecycle_provider_missing_drama_returns_none() -> None:
    assert LifecycleInputProvider(FakeRepository()).get_input(
        drama_id=3, analysis_as_of=AS_OF
    ) is None


def test_benchmark_provider_builds_same_platform_members() -> None:
    repository = FakeRepository()
    repository.dramas = (
        DramaReadRecord(1, "COMPLETED", date(2026, 1, 1), None),
        DramaReadRecord(2, "COMPLETED", date(2026, 1, 1), None),
    )
    start = date(2026, 8, 22)
    repository.metrics = tuple(
        metric_record(
            drama_id=drama_id,
            platform_id=5,
            day=start + timedelta(days=index),
            revision_id=drama_id * 100 + index,
            play_count=index * 100,
        )
        for drama_id in (1, 2)
        for index in range(31)
    )

    result = BenchmarkProvider(repository).get_input(
        drama_ids=(1, 2), platform_id=5, analysis_as_of=AS_OF
    )

    assert isinstance(result, BenchmarkInput)
    assert result.window.day_count == 30
    assert len(result.members) == 2
    assert all(
        member.availability.status is AvailabilityStatus.AVAILABLE
        for member in result.members
    )
    assert all(member.lifecycle_result is None for member in result.members)


def test_benchmark_provider_marks_missing_member_as_insufficient() -> None:
    repository = FakeRepository()
    repository.dramas = (DramaReadRecord(1, "COMPLETED", None, None),)

    result = BenchmarkProvider(repository).get_input(
        drama_ids=(1, 2), platform_id=5, analysis_as_of=AS_OF
    )

    missing = next(member for member in result.members if member.drama_id == 2)
    assert missing.availability.status is AvailabilityStatus.INSUFFICIENT
    assert missing.availability.reasons == (
        AvailabilityReason.INSUFFICIENT_HISTORY,
    )


def test_providers_are_deterministic_dto_mappers_without_forbidden_layers() -> None:
    source = (
        Path(__file__).parents[1]
        / "services"
        / "operation_analytics"
        / "providers.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "ScoreService",
        "PredictionService",
        "AnomalyService",
        "OperationActionService",
        "DramaProfileService",
        ".commit(",
        ".rollback(",
        ".flush(",
        "sqlalchemy",
        "models.",
        "operation_analytics.rules",
    ):
        assert forbidden not in source
