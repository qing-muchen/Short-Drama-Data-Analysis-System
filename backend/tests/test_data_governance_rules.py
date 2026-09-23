"""Tests for deterministic Phase 9 data governance rule components."""

from __future__ import annotations

import ast
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import inspect

from services.data_governance.contracts import (
    COMPLETENESS_RULE_VERSION,
    CONSISTENCY_RULE_VERSION,
    FRESHNESS_RULE_VERSION,
    AvailabilityReason,
    AvailabilityStatus,
    CompletenessRuleInput,
    ConsistencyCheckInput,
    ConsistencyRuleInput,
    FreshnessRuleInput,
    QualityIssueType,
    QualityStatus,
)
from services.data_governance.rules import (
    CompletenessRule,
    ConsistencyRule,
    FreshnessRule,
)


AS_OF = datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc)


def _freshness_input(delay: timedelta) -> FreshnessRuleInput:
    return FreshnessRuleInput(
        entity_type="METRIC_FEED",
        entity_id="drama:1:platform:2",
        latest_timestamp=AS_OF - delay,
        current_timestamp=AS_OF,
    )


def _complete_input(**changes: object) -> CompletenessRuleInput:
    values: dict[str, object] = {
        "expected_fields": ("drama_id", "drama_code", "drama_name", "status"),
        "available_fields": ("drama_id", "drama_code", "drama_name", "status"),
        "metric_coverage": (("play_count", True),),
        "entity_type": "DRAMA_PLATFORM",
        "entity_id": 5,
        "expected_dates": tuple(date(2026, 9, day) for day in range(16, 23)),
        "available_dates": tuple(date(2026, 9, day) for day in range(16, 23)),
        "platform_relationship_available": True,
        "play_count_available": True,
    }
    values.update(changes)
    return CompletenessRuleInput(**values)  # type: ignore[arg-type]


def _check(
    check_code: str,
    *,
    consistent: bool | None,
    source_type: str = "ACTION_SOURCE",
) -> ConsistencyCheckInput:
    return ConsistencyCheckInput(
        check_code=check_code,
        entity_type="OPERATION_ACTION_SOURCE",
        entity_id=7,
        consistent=consistent,
        source_type=source_type,
        source_reference_ids=(13,),
        observed_value=consistent,
        expected_condition="the source reference is consistent",
    )


def test_freshness_healthy_and_exact_warning_boundary() -> None:
    rule = FreshnessRule()
    below = rule.evaluate(_freshness_input(timedelta(hours=2)))
    boundary = rule.evaluate(_freshness_input(timedelta(hours=24)))

    assert below.status is QualityStatus.HEALTHY
    assert below.delay_seconds == 7_200
    assert below.evidence == ()
    assert boundary.status is QualityStatus.HEALTHY
    assert boundary.delay_seconds == 86_400
    assert boundary.rule_version == FRESHNESS_RULE_VERSION
    assert rule.rule_set_version == FRESHNESS_RULE_VERSION


def test_freshness_warning_and_failure_boundaries() -> None:
    rule = FreshnessRule()
    warning = rule.evaluate(_freshness_input(timedelta(hours=24, seconds=1)))
    upper_warning = rule.evaluate(_freshness_input(timedelta(hours=72)))
    failed = rule.evaluate(_freshness_input(timedelta(hours=72, seconds=1)))

    assert warning.status is QualityStatus.WARNING
    assert upper_warning.status is QualityStatus.WARNING
    assert failed.status is QualityStatus.FAILED
    assert warning.evidence[0].check_code == "DATA_DELAYED"
    assert failed.evidence[0].check_code == "DATA_STALE"
    assert failed.availability.status is AvailabilityStatus.AVAILABLE


def test_freshness_without_timestamp_is_not_available() -> None:
    result = FreshnessRule().evaluate(
        FreshnessRuleInput(
            entity_type="METRIC_FEED",
            entity_id=1,
            latest_timestamp=None,
            current_timestamp=AS_OF,
        )
    )

    assert result.status is QualityStatus.NOT_AVAILABLE
    assert result.delay_seconds is None
    assert result.availability.status is AvailabilityStatus.NOT_AVAILABLE
    assert result.availability.reasons == (AvailabilityReason.NO_DATA,)
    assert result.evidence[0].check_code == "NO_VISIBLE_DATA"


def test_freshness_future_timestamp_fails_without_mutating_input() -> None:
    rule_input = _freshness_input(timedelta(seconds=-1))
    result = FreshnessRule().evaluate(rule_input)

    assert result.status is QualityStatus.FAILED
    assert result.delay_seconds == -1
    assert result.evidence[0].check_code == "FUTURE_TIMESTAMP"
    assert rule_input.latest_timestamp == AS_OF + timedelta(seconds=1)


def test_completeness_all_fields_metrics_and_dates_are_healthy() -> None:
    rule = CompletenessRule()
    result = rule.evaluate(_complete_input())

    assert result.status is QualityStatus.HEALTHY
    assert result.coverage_ratio == Decimal("1")
    assert result.missing_items == ()
    assert result.evidence == ()
    assert result.rule_version == COMPLETENESS_RULE_VERSION
    assert rule.rule_set_version == COMPLETENESS_RULE_VERSION


def test_completeness_partial_noncritical_data_is_warning() -> None:
    expected_dates = tuple(date(2026, 9, day) for day in range(16, 23))
    result = CompletenessRule().evaluate(
        _complete_input(
            expected_fields=("drama_id", "optional_label"),
            available_fields=("drama_id",),
            metric_coverage=(("play_count", True), ("engagement_rate", False)),
            available_dates=expected_dates[:-1],
        )
    )

    assert result.status is QualityStatus.WARNING
    assert Decimal("0") < result.coverage_ratio < Decimal("1")  # type: ignore[operator]
    assert result.missing_items == (
        "field:optional_label",
        "metric:engagement_rate",
        "date:2026-09-22",
    )
    assert {item.check_code for item in result.evidence} == {
        "MISSING_REQUIRED_FIELDS",
        "INCOMPLETE_METRIC_COVERAGE",
        "INCOMPLETE_TIME_SERIES",
    }


def test_completeness_critical_field_and_metric_failures_are_failed() -> None:
    result = CompletenessRule().evaluate(
        _complete_input(
            available_fields=("drama_id", "drama_name", "status"),
            play_count_available=False,
        )
    )

    assert result.status is QualityStatus.FAILED
    assert "field:drama_code" in result.missing_items
    assert "metric:play_count" in result.missing_items
    assert result.availability.status is AvailabilityStatus.AVAILABLE


def test_completeness_empty_scope_is_not_available() -> None:
    result = CompletenessRule().evaluate(
        CompletenessRuleInput(
            expected_fields=(),
            available_fields=(),
            metric_coverage=(),
        )
    )

    assert result.status is QualityStatus.NOT_AVAILABLE
    assert result.coverage_ratio is None
    assert result.availability.reasons == (AvailabilityReason.NO_DATA,)
    assert result.evidence[0].check_code == "NO_COMPLETENESS_SCOPE"


def test_completeness_coverage_ratio_supports_zero_boundary() -> None:
    result = CompletenessRule().evaluate(
        _complete_input(
            expected_fields=("drama_id",),
            available_fields=(),
            metric_coverage=(("play_count", False),),
            expected_dates=(date(2026, 9, 22),),
            available_dates=(),
            platform_relationship_available=False,
            play_count_available=False,
        )
    )

    assert result.coverage_ratio == Decimal("0")
    assert result.status is QualityStatus.FAILED


def test_consistency_all_checks_pass() -> None:
    rule = ConsistencyRule()
    result = rule.evaluate(
        ConsistencyRuleInput(
            relationship_checks=(_check("SOURCE_EXISTS", consistent=True),),
            revision_checks=(_check("REVISION_CHAIN", consistent=True),),
            as_of_timestamp=AS_OF,
        )
    )

    assert result.status is QualityStatus.HEALTHY
    assert result.issue_count == 0
    assert result.evidence == ()
    assert result.rule_version == CONSISTENCY_RULE_VERSION
    assert rule.rule_set_version == CONSISTENCY_RULE_VERSION


def test_consistency_relationship_issue_is_warning() -> None:
    result = ConsistencyRule().evaluate(
        ConsistencyRuleInput(
            relationship_checks=(_check("SOURCE_EXISTS", consistent=False),),
            revision_checks=(),
            as_of_timestamp=AS_OF,
        )
    )

    assert result.status is QualityStatus.WARNING
    assert result.availability.status is AvailabilityStatus.AVAILABLE
    assert result.issue_count == 1
    assert result.evidence[0].issue_type is QualityIssueType.CONSISTENCY


def test_consistency_revision_conflict_is_failed() -> None:
    result = ConsistencyRule().evaluate(
        ConsistencyRuleInput(
            relationship_checks=(),
            revision_checks=(_check("REVISION_CHAIN", consistent=False),),
            as_of_timestamp=AS_OF,
        )
    )

    assert result.status is QualityStatus.FAILED
    assert result.evidence[0].check_code == "REVISION_CHAIN"


def test_consistency_as_of_conflict_is_failed() -> None:
    result = ConsistencyRule().evaluate(
        ConsistencyRuleInput(
            relationship_checks=(_check("SOURCE_AS_OF_VISIBLE", consistent=False),),
            revision_checks=(),
            as_of_timestamp=AS_OF,
        )
    )

    assert result.status is QualityStatus.FAILED
    assert result.analysis_as_of == AS_OF


def test_consistency_unresolved_weak_reference_is_partial_warning() -> None:
    result = ConsistencyRule().evaluate(
        ConsistencyRuleInput(
            relationship_checks=(
                _check(
                    "PREDICTION_INPUT_REFERENCE",
                    consistent=None,
                    source_type="PREDICTION_INPUT",
                ),
            ),
            revision_checks=(),
            as_of_timestamp=AS_OF,
        )
    )

    assert result.status is QualityStatus.WARNING
    assert result.availability.status is AvailabilityStatus.PARTIAL
    assert result.availability.reasons == (
        AvailabilityReason.UNRESOLVED_RELATION,
    )
    assert result.evidence[0].check_code.endswith("_UNRESOLVED")


def test_consistency_empty_scope_is_not_available() -> None:
    result = ConsistencyRule().evaluate(
        ConsistencyRuleInput(
            relationship_checks=(),
            revision_checks=(),
            as_of_timestamp=AS_OF,
        )
    )

    assert result.status is QualityStatus.NOT_AVAILABLE
    assert result.issue_count == 1
    assert result.availability.status is AvailabilityStatus.NOT_AVAILABLE


def test_all_rules_are_deterministic_for_identical_inputs() -> None:
    freshness_input = _freshness_input(timedelta(hours=26))
    completeness_input = _complete_input(available_dates=(date(2026, 9, 16),))
    consistency_input = ConsistencyRuleInput(
        relationship_checks=(_check("SOURCE_EXISTS", consistent=False),),
        revision_checks=(),
        as_of_timestamp=AS_OF,
    )

    for rule, rule_input in (
        (FreshnessRule(), freshness_input),
        (CompletenessRule(), completeness_input),
        (ConsistencyRule(), consistency_input),
    ):
        assert rule.evaluate(rule_input) == rule.evaluate(rule_input)  # type: ignore[arg-type]


def test_rule_modules_have_no_forbidden_layer_dependencies_or_writes() -> None:
    from services.data_governance.rules import completeness, consistency, freshness

    forbidden_imports = {
        "sqlalchemy",
        "database",
        "models",
        "repositories",
        "fastapi",
        "routers",
    }
    forbidden_calls = {"commit", "rollback", "flush", "query", "execute"}

    for module in (freshness, completeness, consistency):
        source = inspect.getsource(module)
        tree = ast.parse(source)
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
        assert imported_roots.isdisjoint(forbidden_imports)
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in forbidden_calls
            for node in ast.walk(tree)
        )
