"""Tests for the Phase 9 read-only data governance orchestration service."""

from __future__ import annotations

import ast
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from services.data_governance.contracts import (
    AvailabilityReason,
    AvailabilityStatus,
    CompletenessRuleInput,
    ConsistencyCheckInput,
    ConsistencyRuleInput,
    DataQualityAvailability,
    FreshnessResult,
    FreshnessRuleInput,
    GovernanceScope,
    QualityIssueType,
    QualityStatus,
    EvidenceItem,
)
from services.data_governance.rules import (
    CompletenessRule,
    ConsistencyRule,
    FreshnessRule,
)
from services.data_governance.service import DataGovernanceService
from services.exceptions import ValidationException


AS_OF = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.value


class InputProvider:
    def __init__(self, value: Any, *, method: str, error: Exception | None = None) -> None:
        self.value = value
        self.method = method
        self.error = error
        self.calls: list[datetime] = []

    def get_rule_inputs(self, *, analysis_as_of: datetime):
        assert self.method == "many"
        self.calls.append(analysis_as_of)
        if self.error:
            raise self.error
        return self.value

    def get_rule_input(self, *, analysis_as_of: datetime):
        assert self.method == "one"
        self.calls.append(analysis_as_of)
        if self.error:
            raise self.error
        return self.value


class TrackingRule:
    def __init__(self, delegate: Any, *, error: Exception | None = None) -> None:
        self.delegate = delegate
        self.error = error
        self.calls: list[Any] = []

    def evaluate(self, rule_input: Any):
        self.calls.append(rule_input)
        if self.error:
            raise self.error
        return self.delegate.evaluate(rule_input)


class FixedFreshnessRule:
    def __init__(self, result: FreshnessResult) -> None:
        self.result = result
        self.calls: list[FreshnessRuleInput] = []

    def evaluate(self, rule_input: FreshnessRuleInput) -> FreshnessResult:
        self.calls.append(rule_input)
        return self.result


def _freshness_inputs(as_of: datetime = AS_OF) -> tuple[FreshnessRuleInput, ...]:
    return (
        FreshnessRuleInput(
            entity_type="METRIC_FEED",
            entity_id=1,
            latest_timestamp=as_of - timedelta(hours=2),
            current_timestamp=as_of,
        ),
    )


def _completeness_inputs() -> tuple[CompletenessRuleInput, ...]:
    dates = tuple(date(2026, 9, day) for day in range(16, 23))
    return (
        CompletenessRuleInput(
            expected_fields=("drama_id", "drama_code", "drama_name", "status"),
            available_fields=("drama_id", "drama_code", "drama_name", "status"),
            metric_coverage=(("play_count", True),),
            entity_type="DRAMA_PLATFORM",
            entity_id=1,
            expected_dates=dates,
            available_dates=dates,
        ),
    )


def _consistency_input(as_of: datetime = AS_OF) -> ConsistencyRuleInput:
    check = ConsistencyCheckInput(
        check_code="ACTION_REFERENCE",
        entity_type="OPERATION_ACTION_SOURCE",
        entity_id=1,
        consistent=True,
        source_type="ACTION_SOURCE",
        source_reference_ids=(1,),
        observed_value=True,
        expected_condition="the source reference exists at the analysis cutoff",
    )
    return ConsistencyRuleInput(
        relationship_checks=(check,),
        revision_checks=(),
        as_of_timestamp=as_of,
    )


def _service(
    *,
    clock: FixedClock | None = None,
    freshness_provider: InputProvider | None = None,
    completeness_provider: InputProvider | None = None,
    consistency_provider: InputProvider | None = None,
    freshness_rule: Any | None = None,
    completeness_rule: Any | None = None,
    consistency_rule: Any | None = None,
) -> tuple[DataGovernanceService, tuple[InputProvider, InputProvider, InputProvider], tuple[Any, Any, Any], FixedClock]:
    fixed_clock = clock or FixedClock(AS_OF)
    providers = (
        freshness_provider or InputProvider(_freshness_inputs(), method="many"),
        completeness_provider or InputProvider(_completeness_inputs(), method="many"),
        consistency_provider or InputProvider(_consistency_input(), method="one"),
    )
    rules = (
        freshness_rule or TrackingRule(FreshnessRule()),
        completeness_rule or TrackingRule(CompletenessRule()),
        consistency_rule or TrackingRule(ConsistencyRule()),
    )
    service = DataGovernanceService(
        freshness_provider=providers[0],  # type: ignore[arg-type]
        completeness_provider=providers[1],  # type: ignore[arg-type]
        consistency_provider=providers[2],  # type: ignore[arg-type]
        freshness_rule=rules[0],  # type: ignore[arg-type]
        completeness_rule=rules[1],  # type: ignore[arg-type]
        consistency_rule=rules[2],  # type: ignore[arg-type]
        clock=fixed_clock,
    )
    return service, providers, rules, fixed_clock


def test_overview_freezes_clock_once_and_calls_all_providers_and_rules() -> None:
    service, providers, rules, clock = _service()

    response = service.get_overview()

    assert clock.calls == 1
    assert response.analysis_as_of == AS_OF
    assert response.scope is GovernanceScope.SYSTEM
    assert response.availability.status is AvailabilityStatus.AVAILABLE
    assert [provider.calls for provider in providers] == [[AS_OF], [AS_OF], [AS_OF]]
    assert [len(rule.calls) for rule in rules] == [1, 1, 1]
    assert response.freshness.analysis_as_of == AS_OF
    assert response.completeness.analysis_as_of == AS_OF
    assert response.consistency.analysis_as_of == AS_OF


def test_explicit_analysis_as_of_is_normalized_without_reading_clock() -> None:
    local_as_of = datetime(2026, 9, 23, 16, 0, tzinfo=timezone(timedelta(hours=8)))
    service, providers, _, clock = _service()

    response = service.get_overview(analysis_as_of=local_as_of)

    assert clock.calls == 0
    assert response.analysis_as_of == AS_OF
    assert all(provider.calls == [AS_OF] for provider in providers)


def test_naive_analysis_as_of_is_rejected_before_provider_calls() -> None:
    service, providers, _, clock = _service()

    with pytest.raises(ValidationException, match="timezone-aware"):
        service.get_overview(analysis_as_of=datetime(2026, 9, 23, 8, 0))

    assert clock.calls == 0
    assert all(provider.calls == [] for provider in providers)


def test_public_module_methods_each_use_the_frozen_cutoff() -> None:
    service, providers, _, clock = _service()

    assert service.get_freshness().analysis_as_of == AS_OF
    assert service.get_completeness().analysis_as_of == AS_OF
    assert service.get_consistency().analysis_as_of == AS_OF

    assert clock.calls == 3
    assert [provider.calls for provider in providers] == [[AS_OF], [AS_OF], [AS_OF]]


def test_freshness_provider_failure_is_logged_and_isolated(caplog: pytest.LogCaptureFixture) -> None:
    broken = InputProvider((), method="many", error=RuntimeError("freshness unavailable"))
    service, providers, rules, _ = _service(freshness_provider=broken)

    with caplog.at_level("ERROR"):
        response = service.get_overview()

    assert response.availability.status is AvailabilityStatus.PARTIAL
    assert response.freshness.status is QualityStatus.NOT_AVAILABLE
    assert response.freshness.availability.reasons == (AvailabilityReason.EVALUATION_FAILED,)
    assert response.completeness.status is QualityStatus.HEALTHY
    assert response.consistency.status is QualityStatus.HEALTHY
    assert providers[1].calls == [AS_OF]
    assert providers[2].calls == [AS_OF]
    assert len(rules[0].calls) == 0
    assert len(rules[1].calls) == len(rules[2].calls) == 1
    assert "Freshness governance evaluation failed" in caplog.text


def test_rule_failure_is_isolated_from_other_modules(caplog: pytest.LogCaptureFixture) -> None:
    broken_rule = TrackingRule(CompletenessRule(), error=RuntimeError("rule failed"))
    service, _, rules, _ = _service(completeness_rule=broken_rule)

    with caplog.at_level("ERROR"):
        response = service.get_overview()

    assert response.availability.status is AvailabilityStatus.PARTIAL
    assert response.completeness.status is QualityStatus.NOT_AVAILABLE
    assert response.freshness.status is QualityStatus.HEALTHY
    assert response.consistency.status is QualityStatus.HEALTHY
    assert [len(rule.calls) for rule in rules] == [1, 1, 1]
    assert "Completeness governance evaluation failed" in caplog.text


def test_multiple_module_failures_remain_partial_when_one_module_succeeds() -> None:
    service, _, _, _ = _service(
        freshness_provider=InputProvider((), method="many", error=RuntimeError("a")),
        consistency_provider=InputProvider(None, method="one", error=RuntimeError("b")),
    )

    response = service.get_overview()

    assert response.availability.status is AvailabilityStatus.PARTIAL
    assert response.completeness.status is QualityStatus.HEALTHY
    assert response.freshness.status is QualityStatus.NOT_AVAILABLE
    assert response.consistency.status is QualityStatus.NOT_AVAILABLE


def test_all_module_failures_produce_not_available_overview() -> None:
    service, _, _, _ = _service(
        freshness_provider=InputProvider((), method="many", error=RuntimeError("a")),
        completeness_provider=InputProvider((), method="many", error=RuntimeError("b")),
        consistency_provider=InputProvider(None, method="one", error=RuntimeError("c")),
    )

    response = service.get_overview()

    assert response.availability.status is AvailabilityStatus.NOT_AVAILABLE
    assert response.availability.reasons == (AvailabilityReason.EVALUATION_FAILED,)


def test_insufficient_history_is_preserved_without_none_semantics() -> None:
    evidence = EvidenceItem(
        issue_type=QualityIssueType.FRESHNESS,
        check_code="INSUFFICIENT_HISTORY",
        entity_type="METRIC_FEED",
        entity_id=1,
        observed_value=3,
        expected_condition="at least seven visible history points",
        source_type="METRIC_SNAPSHOT",
        source_reference_ids=(1,),
        message="The visible history is insufficient.",
    )
    insufficient = FreshnessResult(
        status=QualityStatus.NOT_AVAILABLE,
        availability=DataQualityAvailability(
            AvailabilityStatus.INSUFFICIENT,
            (AvailabilityReason.INSUFFICIENT_HISTORY,),
        ),
        delay_seconds=None,
        evidence=(evidence,),
    )
    rule = FixedFreshnessRule(insufficient)
    service, _, _, _ = _service(freshness_rule=rule)

    result = service.get_freshness()

    assert result.availability.status is AvailabilityStatus.INSUFFICIENT
    assert result.availability.reasons == (AvailabilityReason.INSUFFICIENT_HISTORY,)
    assert result.status is QualityStatus.NOT_AVAILABLE
    assert len(rule.calls) == 1


def test_empty_provider_results_still_flow_through_rules() -> None:
    service, _, rules, _ = _service(
        freshness_provider=InputProvider((), method="many"),
        completeness_provider=InputProvider((), method="many"),
    )

    response = service.get_overview()

    assert len(rules[0].calls) == 1
    assert len(rules[1].calls) == 1
    assert response.freshness.status is QualityStatus.NOT_AVAILABLE
    assert response.completeness.status is QualityStatus.NOT_AVAILABLE
    assert response.availability.status is AvailabilityStatus.PARTIAL


def test_service_source_has_no_persistence_or_business_service_dependencies() -> None:
    service_path = Path(__file__).parents[1] / "services" / "data_governance" / "service.py"
    source = service_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    )

    forbidden_import_fragments = (
        "sqlalchemy",
        "models",
        "repositories",
        "score_service",
        "prediction_service",
        "anomaly_service",
        "operation_action_service",
        "drama_profile",
        "explanation",
    )
    assert not any(
        fragment in module
        for module in imported_modules
        for fragment in forbidden_import_fragments
    )
    lowered = source.lower()
    for forbidden_call in ("commit(", "rollback(", "flush(", "session.", "select("):
        assert forbidden_call not in lowered
