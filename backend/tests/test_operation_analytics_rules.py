"""Tests for the pure Phase 8 operation analytics rule components."""

from __future__ import annotations

import ast
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import inspect

import pytest

from services.operation_analytics.contracts import (
    BENCHMARK_VERSION,
    LIFECYCLE_RULE_VERSION,
    AnalysisAvailability,
    AnalysisRevisionInput,
    AnalysisWindow,
    AvailabilityReason,
    AvailabilityStatus,
    BenchmarkInput,
    BenchmarkMemberInput,
    ComparisonScope,
    DailyCumulativePoint,
    LifecycleInput,
    LifecycleResult,
    LifecycleStage,
    MetricDirection,
    OperationEffectivenessInput,
    OperationMetricType,
)
from services.operation_analytics.rules import (
    ActionEffectCalculator,
    AnalysisRevisionBuilder,
    BenchmarkCalculator,
    LifecycleClassifier,
)


AS_OF = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
AVAILABLE = AnalysisAvailability(AvailabilityStatus.AVAILABLE)


def _points(
    start_date: date,
    increments: list[int],
    *,
    platform_id: int = 1,
    base_play: int = 1_000,
    interaction_step: int | None = 1,
) -> tuple[DailyCumulativePoint, ...]:
    play = base_play
    interactions = 100
    result = [
        DailyCumulativePoint(
            business_date=start_date,
            platform_id=platform_id,
            snapshot_revision_id=1,
            play_count=play,
            like_count=interactions if interaction_step is not None else None,
            comment_count=interactions if interaction_step is not None else None,
            favorite_count=interactions if interaction_step is not None else None,
            share_count=interactions if interaction_step is not None else None,
        )
    ]
    for index, increment in enumerate(increments, start=1):
        play += increment
        if interaction_step is not None:
            interactions += interaction_step
        result.append(
            DailyCumulativePoint(
                business_date=start_date + timedelta(days=index),
                platform_id=platform_id,
                snapshot_revision_id=index + 1,
                play_count=play,
                like_count=interactions if interaction_step is not None else None,
                comment_count=interactions if interaction_step is not None else None,
                favorite_count=interactions if interaction_step is not None else None,
                share_count=interactions if interaction_step is not None else None,
            )
        )
    return tuple(result)


def _effect_input(
    *,
    before_step: int = 10,
    after_step: int = 20,
    before_points: tuple[DailyCumulativePoint, ...] | None = None,
    after_points: tuple[DailyCumulativePoint, ...] | None = None,
    overlaps: tuple[int, ...] = (),
) -> OperationEffectivenessInput:
    return OperationEffectivenessInput(
        action_id=11,
        drama_id=7,
        anchor_time=datetime(2026, 9, 8, 10, tzinfo=timezone.utc),
        before_window=AnalysisWindow(date(2026, 9, 1), date(2026, 9, 7), 7),
        after_window=AnalysisWindow(date(2026, 9, 9), date(2026, 9, 15), 7),
        before_points=(
            _points(date(2026, 8, 31), [before_step] * 7)
            if before_points is None
            else before_points
        ),
        after_points=(
            _points(date(2026, 9, 8), [after_step] * 7, base_play=2_000)
            if after_points is None
            else after_points
        ),
        before_anomaly_ids=(1,),
        after_anomaly_ids=(2, 3),
        overlapping_action_ids=overlaps,
    )


def _metric(result, metric_type: OperationMetricType):
    return next(
        metric for metric in result.metric_changes if metric.metric_type is metric_type
    )


def test_action_effect_calculates_normal_growth_without_causal_result() -> None:
    result = ActionEffectCalculator().calculate(_effect_input())

    views = _metric(result, OperationMetricType.PLAY_COUNT)
    assert views.before_value == 70
    assert views.after_value == 140
    assert views.absolute_change == 70
    assert views.relative_change == Decimal("1")
    assert views.direction is MetricDirection.INCREASED
    assert result.availability.status is AvailabilityStatus.AVAILABLE
    assert "causation" in result.disclaimer
    assert not hasattr(result, "action_success")
    assert not hasattr(result, "effectiveness_score")


def test_action_effect_reports_decrease_and_stable_directions() -> None:
    decreased = ActionEffectCalculator().calculate(
        _effect_input(before_step=20, after_step=10)
    )
    stable = ActionEffectCalculator().calculate(
        _effect_input(before_step=10, after_step=10)
    )

    assert _metric(
        decreased, OperationMetricType.PLAY_COUNT
    ).direction is MetricDirection.DECREASED
    assert _metric(
        stable, OperationMetricType.PLAY_COUNT
    ).direction is MetricDirection.UNCHANGED


def test_action_effect_empty_and_incomplete_windows_are_explicit() -> None:
    empty = ActionEffectCalculator().calculate(
        _effect_input(before_points=(), after_points=())
    )
    incomplete = ActionEffectCalculator().calculate(
        _effect_input(
            before_points=_points(date(2026, 9, 1), [10] * 6),
        )
    )

    assert empty.metric_changes == ()
    assert empty.availability.status is AvailabilityStatus.INSUFFICIENT
    assert empty.availability.reasons == (
        AvailabilityReason.INCOMPLETE_BEFORE_WINDOW,
    )
    assert incomplete.availability.reasons == (
        AvailabilityReason.INCOMPLETE_BEFORE_WINDOW,
    )


def test_action_effect_windows_must_be_adjacent_to_anchor_day() -> None:
    input_data = _effect_input()
    shifted = OperationEffectivenessInput(
        action_id=input_data.action_id,
        drama_id=input_data.drama_id,
        anchor_time=input_data.anchor_time,
        before_window=AnalysisWindow(date(2026, 8, 31), date(2026, 9, 6), 7),
        after_window=input_data.after_window,
        before_points=input_data.before_points,
        after_points=input_data.after_points,
    )

    result = ActionEffectCalculator().calculate(shifted)
    assert result.availability.reasons == (
        AvailabilityReason.INCOMPLETE_BEFORE_WINDOW,
    )


def test_action_effect_overlap_is_partial_and_deterministic() -> None:
    calculator = ActionEffectCalculator()
    input_data = _effect_input(overlaps=(99,))

    first = calculator.calculate(input_data)
    second = calculator.calculate(input_data)

    assert first == second
    assert first.availability.status is AvailabilityStatus.PARTIAL
    assert AvailabilityReason.OVERLAPPING_ACTIONS in first.availability.reasons


def _lifecycle_input(
    increments: list[int],
    *,
    status: str = "COMPLETED",
    release_days_ago: int = 100,
    points: tuple[DailyCumulativePoint, ...] | None = None,
) -> LifecycleInput:
    return LifecycleInput(
        drama_id=7,
        drama_status=status,
        release_time=AS_OF - timedelta(days=release_days_ago),
        points=(
            _points(date(2026, 9, 7), increments)
            if points is None
            else points
        ),
        analysis_as_of=AS_OF,
    )


def test_lifecycle_launch_and_archived_priority() -> None:
    classifier = LifecycleClassifier()
    launch = classifier.classify(
        _lifecycle_input([], release_days_ago=3, points=())
    )
    archived = classifier.classify(
        LifecycleInput(
            drama_id=7,
            drama_status="INACTIVE",
            release_time=None,
            points=(),
            analysis_as_of=AS_OF,
        )
    )

    assert launch.lifecycle_stage is LifecycleStage.LAUNCH
    assert archived.lifecycle_stage is LifecycleStage.ARCHIVED


@pytest.mark.parametrize(
    ("current_step", "expected"),
    [
        (11, LifecycleStage.GROWTH),
        (10, LifecycleStage.STABLE),
        (9, LifecycleStage.DECLINE),
    ],
)
def test_lifecycle_growth_stable_decline_and_ten_percent_boundaries(
    current_step: int,
    expected: LifecycleStage,
) -> None:
    result = LifecycleClassifier().classify(
        _lifecycle_input([10] * 7 + [current_step] * 7)
    )

    assert result.lifecycle_stage is expected
    assert result.rule_version == LIFECYCLE_RULE_VERSION
    assert result.availability.status is AvailabilityStatus.AVAILABLE


def test_lifecycle_history_gap_and_negative_sequence_are_not_classified() -> None:
    gap_points = list(_points(date(2026, 9, 7), [10] * 14))
    del gap_points[5]
    insufficient = LifecycleClassifier().classify(
        _lifecycle_input([], points=tuple(gap_points))
    )
    invalid = LifecycleClassifier().classify(
        _lifecycle_input([10] * 7 + [-1] + [10] * 6)
    )

    assert insufficient.lifecycle_stage is None
    assert insufficient.availability.reasons == (
        AvailabilityReason.INSUFFICIENT_HISTORY,
    )
    assert invalid.lifecycle_stage is None
    assert invalid.availability.reasons == (
        AvailabilityReason.INVALID_CUMULATIVE_SEQUENCE,
    )


def _lifecycle_result(drama_id: int) -> LifecycleResult:
    return LifecycleResult(
        drama_id=drama_id,
        lifecycle_stage=LifecycleStage.STABLE,
        rule_version=LIFECYCLE_RULE_VERSION,
        evaluated_as_of=AS_OF,
        availability=AVAILABLE,
    )


def _benchmark_input(
    drama_count: int,
    *,
    members_count: int | None = None,
    day_count: int = 30,
) -> BenchmarkInput:
    ids = tuple(range(1, drama_count + 1))
    scope = ComparisonScope(ids, platform_id=9)
    end = date(2026, 9, 21)
    start = end - timedelta(days=day_count - 1)
    included = drama_count if members_count is None else members_count
    members = tuple(
        BenchmarkMemberInput(
            drama_id=drama_id,
            points=_points(
                start - timedelta(days=1),
                [drama_id * 10] * day_count,
                platform_id=9,
            ),
            anomaly_ids=(drama_id,),
            anomaly_algorithm_versions=("Rule-based Detection V1.0",),
            lifecycle_result=_lifecycle_result(drama_id),
        )
        for drama_id in ids[:included]
    )
    return BenchmarkInput(
        comparison_scope=scope,
        window=AnalysisWindow(start, end, day_count),
        members=members,
        analysis_as_of=AS_OF,
    )


def test_benchmark_compares_two_dramas_and_returns_medians_without_ranks() -> None:
    result = BenchmarkCalculator().compare(_benchmark_input(2))

    assert result.availability.status is AvailabilityStatus.AVAILABLE
    assert result.benchmark_version == BENCHMARK_VERSION
    assert len(result.metrics) == 2
    play_metrics = [member.metrics[0] for member in result.metrics]
    assert [metric.value for metric in play_metrics] == [Decimal(300), Decimal(600)]
    assert all(metric.group_median == Decimal(450) for metric in play_metrics)
    assert not hasattr(result, "rank")
    assert not hasattr(result, "winner")
    assert not hasattr(result, "recommendation")


def test_benchmark_accepts_twenty_dramas_deterministically() -> None:
    calculator = BenchmarkCalculator()
    input_data = _benchmark_input(20)

    first = calculator.compare(input_data)
    second = calculator.compare(input_data)

    assert first == second
    assert len(first.metrics) == 20


def test_benchmark_requires_two_comparable_members() -> None:
    result = BenchmarkCalculator().compare(_benchmark_input(2, members_count=1))

    assert result.availability.status is AvailabilityStatus.INSUFFICIENT
    assert result.availability.reasons == (
        AvailabilityReason.INCOMPARABLE_SCOPE,
    )


def test_benchmark_scope_and_thirty_day_window_boundaries() -> None:
    with pytest.raises(ValueError):
        ComparisonScope((1,), platform_id=9)
    with pytest.raises(ValueError):
        ComparisonScope(tuple(range(1, 22)), platform_id=9)

    result = BenchmarkCalculator().compare(
        _benchmark_input(2, day_count=29)
    )
    assert result.availability.status is AvailabilityStatus.NOT_AVAILABLE
    assert result.availability.reasons == (
        AvailabilityReason.INCOMPARABLE_SCOPE,
    )

    stale_window = BenchmarkInput(
        comparison_scope=ComparisonScope((1, 2), platform_id=9),
        window=AnalysisWindow(date(2026, 8, 22), date(2026, 9, 20), 30),
        members=(),
        analysis_as_of=AS_OF,
    )
    stale_result = BenchmarkCalculator().compare(stale_window)
    assert stale_result.availability.status is AvailabilityStatus.NOT_AVAILABLE


def test_analysis_revision_is_stable_and_changes_with_inputs() -> None:
    builder = AnalysisRevisionBuilder()
    first = AnalysisRevisionInput(
        analysis_type="BENCHMARK",
        entity_ids=(2, 1),
        parameters=(("platform_id", "9"), ("window", "30")),
        analysis_as_of=AS_OF,
        snapshot_revision_ids=(3, 1, 2),
        source_result_versions=((2, "v2"), (1, "v1")),
        rule_versions=(BENCHMARK_VERSION, LIFECYCLE_RULE_VERSION),
    )
    reordered = AnalysisRevisionInput(
        analysis_type="BENCHMARK",
        entity_ids=(1, 2),
        parameters=(("window", "30"), ("platform_id", "9")),
        analysis_as_of=AS_OF,
        snapshot_revision_ids=(1, 2, 3),
        source_result_versions=((1, "v1"), (2, "v2")),
        rule_versions=(LIFECYCLE_RULE_VERSION, BENCHMARK_VERSION),
    )
    changed = AnalysisRevisionInput(
        analysis_type="BENCHMARK",
        entity_ids=(1, 2),
        parameters=(("window", "30"), ("platform_id", "9")),
        analysis_as_of=AS_OF + timedelta(seconds=1),
        snapshot_revision_ids=(1, 2, 3),
        source_result_versions=((1, "v1"), (2, "v2")),
        rule_versions=(LIFECYCLE_RULE_VERSION, BENCHMARK_VERSION),
    )

    assert builder.build(first) == builder.build(reordered)
    assert builder.build(first).startswith("sha256:")
    assert builder.build(first) != builder.build(changed)


def test_rule_modules_have_no_io_or_layer_dependencies() -> None:
    modules = (
        __import__(
            "services.operation_analytics.rules.action_effect",
            fromlist=["action_effect"],
        ),
        __import__(
            "services.operation_analytics.rules.lifecycle",
            fromlist=["lifecycle"],
        ),
        __import__(
            "services.operation_analytics.rules.benchmark",
            fromlist=["benchmark"],
        ),
        __import__(
            "services.operation_analytics.rules.revision",
            fromlist=["revision"],
        ),
    )
    forbidden = {
        "sqlalchemy",
        "database",
        "models",
        "repositories",
        "fastapi",
        "requests",
        "httpx",
    }
    for module in modules:
        tree = ast.parse(inspect.getsource(module))
        roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        roots.update(
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        assert roots.isdisjoint(forbidden)
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert calls.isdisjoint({"commit", "rollback", "flush", "query"})
