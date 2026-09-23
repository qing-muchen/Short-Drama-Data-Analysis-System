"""Orchestration and boundary tests for OperationAnalyticsService."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.exceptions import ValidationException
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
from services.operation_analytics.providers import OperationEffectivenessInputPage
from services.operation_analytics.rules import (
    ActionEffectCalculator,
    AnalysisRevisionBuilder,
    BenchmarkCalculator,
    LifecycleClassifier,
)
from services.operation_analytics.service import OperationAnalyticsService


AS_OF = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)


def points(
    start_date: date,
    increments: list[int],
    *,
    platform_id: int = 1,
    revision_offset: int = 0,
) -> tuple[DailyCumulativePoint, ...]:
    play_count = 1_000
    result = [
        DailyCumulativePoint(
            business_date=start_date,
            platform_id=platform_id,
            snapshot_revision_id=revision_offset + 1,
            play_count=play_count,
            like_count=100,
            comment_count=100,
            favorite_count=100,
            share_count=100,
        )
    ]
    for index, increment in enumerate(increments, start=1):
        play_count += increment
        result.append(
            DailyCumulativePoint(
                business_date=start_date + timedelta(days=index),
                platform_id=platform_id,
                snapshot_revision_id=revision_offset + index + 1,
                play_count=play_count,
                like_count=100 + index,
                comment_count=100 + index,
                favorite_count=100 + index,
                share_count=100 + index,
            )
        )
    return tuple(result)


def effect_input() -> OperationEffectivenessInput:
    return OperationEffectivenessInput(
        action_id=11,
        drama_id=7,
        anchor_time=datetime(2026, 9, 8, 10, tzinfo=timezone.utc),
        before_window=AnalysisWindow(date(2026, 9, 1), date(2026, 9, 7), 7),
        after_window=AnalysisWindow(date(2026, 9, 9), date(2026, 9, 15), 7),
        before_points=points(date(2026, 8, 31), [10] * 7),
        after_points=points(
            date(2026, 9, 8), [20] * 7, revision_offset=20
        ),
    )


def lifecycle_input(drama_id: int = 7) -> LifecycleInput:
    return LifecycleInput(
        drama_id=drama_id,
        drama_status="COMPLETED",
        release_time=AS_OF - timedelta(days=100),
        points=points(date(2026, 9, 7), [10] * 7 + [11] * 7),
        analysis_as_of=AS_OF,
    )


def benchmark_input() -> BenchmarkInput:
    window = AnalysisWindow(date(2026, 8, 23), date(2026, 9, 21), 30)
    return BenchmarkInput(
        comparison_scope=ComparisonScope((7, 8), 1),
        window=window,
        members=(
            BenchmarkMemberInput(
                drama_id=7,
                points=points(date(2026, 8, 22), [10] * 30),
            ),
            BenchmarkMemberInput(
                drama_id=8,
                points=points(
                    date(2026, 8, 22),
                    [12] * 30,
                    revision_offset=100,
                ),
            ),
        ),
        analysis_as_of=AS_OF,
    )


class FixedClock:
    def __init__(self, value: datetime = AS_OF) -> None:
        self.value = value
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.value


class EffectProvider:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = []

    def get_inputs(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return OperationEffectivenessInputPage(1, 20, 1, (effect_input(),))


class LifecycleProvider:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = []

    def get_input(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return lifecycle_input(kwargs["drama_id"])


class BenchmarkInputProvider:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = []

    def get_input(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return benchmark_input()


def make_service(
    *,
    effect_provider=None,
    lifecycle_provider=None,
    benchmark_provider=None,
    action_calculator=None,
    lifecycle_classifier=None,
    benchmark_calculator=None,
    clock=None,
) -> OperationAnalyticsService:
    return OperationAnalyticsService(
        effect_provider or EffectProvider(),
        lifecycle_provider or LifecycleProvider(),
        benchmark_provider or BenchmarkInputProvider(),
        action_calculator or ActionEffectCalculator(),
        lifecycle_classifier or LifecycleClassifier(),
        benchmark_calculator or BenchmarkCalculator(),
        AnalysisRevisionBuilder(),
        clock or FixedClock(),
    )


def test_complete_operation_effectiveness_flow_and_revision() -> None:
    provider = EffectProvider()
    clock = FixedClock()
    result = make_service(effect_provider=provider, clock=clock).get_operation_effectiveness()

    assert result.total == 1
    assert result.availability.status is AvailabilityStatus.AVAILABLE
    assert result.items[0].analysis_as_of == AS_OF
    assert result.items[0].analysis_revision.startswith("sha256:")
    assert provider.calls[0]["analysis_as_of"] == AS_OF
    assert clock.calls == 1


def test_complete_lifecycle_flow_uses_same_frozen_as_of() -> None:
    provider = LifecycleProvider()
    result = make_service(lifecycle_provider=provider).get_lifecycle(drama_id=7)

    assert result.lifecycle_stage is not None
    assert result.evaluated_as_of == AS_OF
    assert result.analysis_revision.startswith("sha256:")
    assert provider.calls[0]["analysis_as_of"] == AS_OF


def test_complete_benchmark_flow_enriches_lifecycle_before_calculation() -> None:
    lifecycle_provider = LifecycleProvider()
    result = make_service(
        lifecycle_provider=lifecycle_provider
    ).get_benchmark(drama_ids=(7, 8), platform_id=1)

    assert result.availability.status is AvailabilityStatus.AVAILABLE
    assert result.analysis_revision.startswith("sha256:")
    assert [call["drama_id"] for call in lifecycle_provider.calls] == [7, 8]
    assert all(call["analysis_as_of"] == AS_OF for call in lifecycle_provider.calls)


def test_explicit_as_of_is_reused_without_reading_clock() -> None:
    explicit = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
    provider = EffectProvider()
    clock = FixedClock()

    result = make_service(effect_provider=provider, clock=clock).get_operation_effectiveness(
        analysis_as_of=explicit
    )

    assert clock.calls == 0
    assert provider.calls[0]["analysis_as_of"] == explicit
    assert result.analysis_as_of == explicit


def test_provider_failure_is_isolated_as_not_available() -> None:
    service = make_service(
        effect_provider=EffectProvider(RuntimeError("read failed")),
        lifecycle_provider=LifecycleProvider(RuntimeError("read failed")),
        benchmark_provider=BenchmarkInputProvider(RuntimeError("read failed")),
    )

    effect = service.get_operation_effectiveness()
    lifecycle = service.get_lifecycle(drama_id=7)
    benchmark = service.get_benchmark(drama_ids=(7, 8), platform_id=1)

    assert effect.availability.reasons == (AvailabilityReason.NOT_AVAILABLE,)
    assert lifecycle.availability.reasons == (AvailabilityReason.NOT_AVAILABLE,)
    assert benchmark.availability.reasons == (AvailabilityReason.NOT_AVAILABLE,)


def test_rule_failure_is_isolated_without_losing_result_identity() -> None:
    class BrokenCalculator:
        def calculate(self, input_data):
            raise RuntimeError("rule failed")

    result = make_service(
        action_calculator=BrokenCalculator()
    ).get_operation_effectiveness()

    assert result.items[0].action_id == 11
    assert result.items[0].availability.status is AvailabilityStatus.NOT_AVAILABLE
    assert result.items[0].analysis_revision.startswith("sha256:")


def test_one_benchmark_lifecycle_failure_does_not_drop_other_member() -> None:
    class PartiallyBrokenLifecycleProvider(LifecycleProvider):
        def get_input(self, **kwargs):
            if kwargs["drama_id"] == 8:
                raise RuntimeError("one member failed")
            return super().get_input(**kwargs)

    result = make_service(
        lifecycle_provider=PartiallyBrokenLifecycleProvider()
    ).get_benchmark(drama_ids=(7, 8), platform_id=1)

    assert len(result.metrics) == 2
    assert result.availability.status is AvailabilityStatus.INSUFFICIENT
    failed_member = next(item for item in result.metrics if item.drama_id == 8)
    assert failed_member.availability.status is AvailabilityStatus.NOT_AVAILABLE


@pytest.mark.parametrize(
    "call",
    [
        lambda service: service.get_lifecycle(drama_id=0),
        lambda service: service.get_benchmark(drama_ids=(1,), platform_id=1),
        lambda service: service.get_benchmark(
            drama_ids=(1, 2), platform_id=0
        ),
        lambda service: service.get_operation_effectiveness(page_size=101),
        lambda service: service.get_lifecycle(
            drama_id=1, analysis_as_of=datetime(2026, 9, 1)
        ),
    ],
)
def test_invalid_parameters_are_rejected(call) -> None:
    with pytest.raises(ValidationException):
        call(make_service())


def test_service_has_no_persistence_or_business_service_dependencies() -> None:
    source = (
        Path(__file__).parents[1]
        / "services"
        / "operation_analytics"
        / "service.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "ScoreService",
        "PredictionService",
        "AnomalyService",
        "OperationActionService",
        "DramaProfileService",
        "sqlalchemy",
        "Session",
        "from models",
        "commit(",
        "rollback(",
        "flush(",
    ):
        assert forbidden not in source
