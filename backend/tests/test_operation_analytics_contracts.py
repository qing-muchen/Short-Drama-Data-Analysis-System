"""Tests for the pure Phase 8 operation analytics contracts."""

from dataclasses import FrozenInstanceError, fields
from datetime import date, datetime, timezone
import ast
import inspect

import pytest

from services.operation_analytics.contracts import (
    ACTION_EFFECT_RULE_VERSION,
    BENCHMARK_VERSION,
    LIFECYCLE_RULE_VERSION,
    AnalysisAvailability,
    AnalysisWindow,
    AvailabilityReason,
    AvailabilityStatus,
    BenchmarkMemberResult,
    BenchmarkMetric,
    BenchmarkMetricType,
    BenchmarkResult,
    ComparisonScope,
    LifecycleResult,
    LifecycleStage,
    MetricChange,
    MetricDirection,
    OperationEffectivenessResult,
    OperationMetricType,
)


AS_OF = datetime(2026, 9, 22, tzinfo=timezone.utc)
AVAILABLE = AnalysisAvailability(AvailabilityStatus.AVAILABLE)


def test_closed_enums_contain_the_frozen_values() -> None:
    assert {item.value for item in AvailabilityStatus} == {
        "AVAILABLE",
        "PARTIAL",
        "INSUFFICIENT",
        "NOT_AVAILABLE",
    }
    assert AvailabilityReason.INSUFFICIENT_HISTORY.value == "INSUFFICIENT_HISTORY"
    assert AvailabilityReason.NOT_CALCULATED.value == "NOT_CALCULATED"
    assert {item.value for item in LifecycleStage} == {
        "LAUNCH",
        "GROWTH",
        "STABLE",
        "DECLINE",
        "ARCHIVED",
    }
    assert {item.value for item in OperationMetricType} >= {
        "PLAY_COUNT",
        "ENGAGEMENT_RATE",
    }
    with pytest.raises(ValueError):
        AvailabilityStatus("MISSING")


def test_availability_requires_a_consistent_explicit_state() -> None:
    assert AVAILABLE.reasons == ()
    insufficient = AnalysisAvailability(
        AvailabilityStatus.INSUFFICIENT,
        (AvailabilityReason.INSUFFICIENT_HISTORY,),
    )
    assert insufficient.status is AvailabilityStatus.INSUFFICIENT
    with pytest.raises(ValueError):
        AnalysisAvailability(AvailabilityStatus.NOT_AVAILABLE)
    with pytest.raises(ValueError):
        AnalysisAvailability(
            AvailabilityStatus.AVAILABLE,
            (AvailabilityReason.NOT_CALCULATED,),
        )
    with pytest.raises(ValueError):
        AnalysisAvailability("AVAILABLE")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        AnalysisAvailability(
            AvailabilityStatus.PARTIAL,
            (
                AvailabilityReason.OVERLAPPING_ACTIONS,
                AvailabilityReason.ZERO_BASELINE,
            ),
        )


def test_analysis_window_validates_inclusive_boundaries() -> None:
    window = AnalysisWindow(date(2026, 9, 1), date(2026, 9, 7), 7)
    assert window.day_count == 7
    with pytest.raises(ValueError):
        AnalysisWindow(date(2026, 9, 7), date(2026, 9, 1), 7)
    with pytest.raises(ValueError):
        AnalysisWindow(date(2026, 9, 1), date(2026, 9, 7), 6)


def test_operation_effectiveness_result_constructs_without_causal_fields() -> None:
    before = AnalysisWindow(date(2026, 9, 1), date(2026, 9, 7), 7)
    after = AnalysisWindow(date(2026, 9, 9), date(2026, 9, 15), 7)
    change = MetricChange(
        metric_type=OperationMetricType.PLAY_COUNT,
        before_value=100,
        after_value=120,
        absolute_change=20,
        relative_change=None,
        direction=MetricDirection.INCREASED,
        unit="count",
        availability=AVAILABLE,
    )
    result = OperationEffectivenessResult(
        action_id=1,
        drama_id=2,
        before_window=before,
        after_window=after,
        metric_changes=(change,),
        availability=AVAILABLE,
        anchor_time=datetime(2026, 9, 8, tzinfo=timezone.utc),
        analysis_as_of=AS_OF,
    )

    assert result.action_effect_rule_version == ACTION_EFFECT_RULE_VERSION
    assert result.action_type is None
    forbidden = {"success", "failure", "causal_result", "recommendation"}
    assert forbidden.isdisjoint(field.name for field in fields(result))
    with pytest.raises(ValueError):
        OperationEffectivenessResult(
            action_id=1,
            drama_id=2,
            before_window=before,
            after_window=after,
            metric_changes=(),
            availability=AVAILABLE,
            anchor_time=datetime(2026, 9, 8, tzinfo=timezone.utc),
            action_type="promotion",  # type: ignore[arg-type]
        )


def test_lifecycle_result_supports_available_and_insufficient_states() -> None:
    available = LifecycleResult(
        drama_id=7,
        lifecycle_stage=LifecycleStage.GROWTH,
        rule_version=LIFECYCLE_RULE_VERSION,
        evaluated_as_of=AS_OF,
        availability=AVAILABLE,
    )
    unavailable = LifecycleResult(
        drama_id=7,
        lifecycle_stage=None,
        rule_version=LIFECYCLE_RULE_VERSION,
        evaluated_as_of=AS_OF,
        availability=AnalysisAvailability(
            AvailabilityStatus.INSUFFICIENT,
            (AvailabilityReason.INSUFFICIENT_HISTORY,),
        ),
    )

    assert available.lifecycle_stage is LifecycleStage.GROWTH
    assert unavailable.lifecycle_stage is None
    with pytest.raises(ValueError):
        LifecycleResult(
            drama_id=7,
            lifecycle_stage=None,
            rule_version=LIFECYCLE_RULE_VERSION,
            evaluated_as_of=AS_OF,
            availability=AVAILABLE,
        )


def test_benchmark_result_has_scope_without_ranking_fields() -> None:
    scope = ComparisonScope((1, 2), platform_id=3)
    window = AnalysisWindow(date(2026, 8, 23), date(2026, 9, 21), 30)
    metric = BenchmarkMetric(
        metric_type=BenchmarkMetricType.PLAY_INCREMENT_TOTAL,
        value=100,
        group_median=None,
        unit="count",
        availability=AVAILABLE,
    )
    result = BenchmarkResult(
        target_drama_id=None,
        comparison_scope=scope,
        window=window,
        metrics=(BenchmarkMemberResult(1, (metric,), AVAILABLE),),
        availability=AVAILABLE,
        benchmark_version=BENCHMARK_VERSION,
        lifecycle_rule_version=LIFECYCLE_RULE_VERSION,
        analysis_revision=None,
        analysis_as_of=AS_OF,
    )

    assert result.comparison_scope.drama_ids == (1, 2)
    forbidden = {"ranking", "score_rank", "recommendation", "best_drama"}
    assert forbidden.isdisjoint(field.name for field in fields(result))
    with pytest.raises(ValueError):
        ComparisonScope((1,), platform_id=3)
    with pytest.raises(ValueError):
        ComparisonScope((1, 1), platform_id=3)


def test_zero_is_preserved_and_missing_is_none() -> None:
    zero = MetricChange(
        metric_type=OperationMetricType.PLAY_COUNT,
        before_value=0,
        after_value=0,
        absolute_change=0,
        relative_change=None,
        direction=MetricDirection.UNCHANGED,
        unit="count",
        availability=AVAILABLE,
    )
    missing = MetricChange(
        metric_type=OperationMetricType.ENGAGEMENT_RATE,
        before_value=None,
        after_value=None,
        absolute_change=None,
        relative_change=None,
        direction=MetricDirection.UNAVAILABLE,
        unit="ratio",
        availability=AnalysisAvailability(
            AvailabilityStatus.INSUFFICIENT,
            (AvailabilityReason.MISSING_METRIC,),
        ),
    )

    assert zero.before_value == 0
    assert missing.before_value is None
    assert missing.availability.status is AvailabilityStatus.INSUFFICIENT


def test_contracts_are_frozen_and_have_no_layer_dependencies() -> None:
    window = AnalysisWindow(date(2026, 9, 1), date(2026, 9, 7), 7)
    with pytest.raises(FrozenInstanceError):
        window.day_count = 8  # type: ignore[misc]

    import services.operation_analytics.contracts as contracts

    tree = ast.parse(inspect.getsource(contracts))
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert imported_roots.isdisjoint(
        {"sqlalchemy", "database", "models", "repositories", "fastapi"}
    )
