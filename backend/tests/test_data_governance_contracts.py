"""Tests for the pure Phase 9 data governance contracts."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import inspect

import pytest

from services.data_governance.contracts import (
    COMPLETENESS_RULE_VERSION,
    CONSISTENCY_RULE_VERSION,
    FRESHNESS_RULE_VERSION,
    GOVERNANCE_RULE_SET_VERSION,
    AvailabilityReason,
    AvailabilityStatus,
    CompletenessResult,
    CompletenessRuleInput,
    ConsistencyCheckInput,
    ConsistencyResult,
    ConsistencyRuleInput,
    DataGovernanceResponse,
    DataQualityAvailability,
    EvidenceItem,
    FreshnessResult,
    FreshnessRuleInput,
    GovernanceScope,
    QualityIssueType,
    QualityStatus,
)


AS_OF = datetime(2026, 9, 23, tzinfo=timezone.utc)
AVAILABLE = DataQualityAvailability(AvailabilityStatus.AVAILABLE)


def _evidence(
    issue_type: QualityIssueType = QualityIssueType.CONSISTENCY,
) -> EvidenceItem:
    return EvidenceItem(
        issue_type=issue_type,
        check_code="REFERENCE_EXISTS",
        entity_type="OPERATION_ACTION_SOURCE",
        entity_id=7,
        observed_value="missing",
        expected_condition="referenced record exists",
        source_type="ACTION_SOURCE",
        source_reference_ids=(11,),
        message="The referenced record could not be resolved.",
    )


def test_enums_contain_only_the_frozen_values() -> None:
    assert {item.value for item in QualityStatus} == {
        "HEALTHY",
        "WARNING",
        "FAILED",
        "NOT_AVAILABLE",
    }
    assert {item.value for item in AvailabilityStatus} == {
        "AVAILABLE",
        "PARTIAL",
        "INSUFFICIENT",
        "NOT_AVAILABLE",
    }
    assert {item.value for item in QualityIssueType} == {
        "FRESHNESS",
        "COMPLETENESS",
        "CONSISTENCY",
    }
    assert {item.value for item in GovernanceScope} == {"SYSTEM"}
    assert AvailabilityReason.MISSING_SOURCE.value == "MISSING_SOURCE"
    assert AvailabilityReason.EVALUATION_FAILED.value == "EVALUATION_FAILED"


def test_invalid_enum_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        QualityStatus("GOOD")
    with pytest.raises(ValueError):
        AvailabilityStatus("EMPTY")
    with pytest.raises(ValueError):
        GovernanceScope("USER")


def test_availability_has_explicit_consistent_defaults() -> None:
    assert AVAILABLE.reasons == ()
    assert AVAILABLE.message is None

    partial = DataQualityAvailability(
        AvailabilityStatus.PARTIAL,
        (AvailabilityReason.MISSING_SOURCE,),
    )
    assert partial.reasons == (AvailabilityReason.MISSING_SOURCE,)

    with pytest.raises(ValueError):
        DataQualityAvailability(AvailabilityStatus.NOT_AVAILABLE)
    with pytest.raises(ValueError):
        DataQualityAvailability(
            AvailabilityStatus.AVAILABLE,
            (AvailabilityReason.NO_DATA,),
        )
    with pytest.raises(ValueError):
        DataQualityAvailability("AVAILABLE")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        DataQualityAvailability(
            AvailabilityStatus.PARTIAL,
            (
                AvailabilityReason.INSUFFICIENT_HISTORY,
                AvailabilityReason.NO_DATA,
            ),
        )


def test_contracts_are_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        AVAILABLE.status = AvailabilityStatus.NOT_AVAILABLE  # type: ignore[misc]


def test_evidence_is_minimal_and_rejects_business_objects() -> None:
    evidence = _evidence()
    assert evidence.source_reference_ids == (11,)
    assert evidence.issue_type is QualityIssueType.CONSISTENCY

    system_evidence = EvidenceItem(
        issue_type=QualityIssueType.FRESHNESS,
        check_code="NO_VISIBLE_DATA",
        entity_type="SYSTEM",
        entity_id=None,
        observed_value=None,
        expected_condition="at least one visible feed",
        source_type="SNAPSHOT",
        source_reference_ids=(),
        message="No visible data was found.",
    )
    assert system_evidence.entity_id is None

    with pytest.raises(ValueError):
        EvidenceItem(
            issue_type=QualityIssueType.FRESHNESS,
            check_code="INVALID",
            entity_type="DRAMA",
            entity_id=None,
            observed_value=None,
            expected_condition="valid",
            source_type="DRAMA",
            source_reference_ids=(),
            message="Invalid evidence.",
        )
    with pytest.raises(ValueError):
        EvidenceItem(
            issue_type=QualityIssueType.FRESHNESS,
            check_code="FULL_OBJECT",
            entity_type="SYSTEM",
            entity_id=None,
            observed_value={"drama": {"drama_id": 1}},  # type: ignore[arg-type]
            expected_condition="scalar evidence only",
            source_type="DRAMA",
            source_reference_ids=(),
            message="A full object is not allowed.",
        )


def test_freshness_input_validates_time_and_threshold_boundaries() -> None:
    missing = FreshnessRuleInput(
        entity_type="METRIC_FEED",
        entity_id="drama:1:platform:2",
        latest_timestamp=None,
        current_timestamp=AS_OF,
    )
    assert missing.latest_timestamp is None
    assert missing.threshold == timedelta(hours=24)
    assert missing.failure_threshold == timedelta(hours=72)

    with pytest.raises(ValueError):
        FreshnessRuleInput(
            entity_type="METRIC_FEED",
            entity_id=1,
            latest_timestamp=None,
            current_timestamp=datetime(2026, 9, 23),
        )
    with pytest.raises(ValueError):
        FreshnessRuleInput(
            entity_type="METRIC_FEED",
            entity_id=1,
            latest_timestamp=None,
            current_timestamp=AS_OF,
            threshold=timedelta(hours=72),
            failure_threshold=timedelta(hours=24),
        )


def test_completeness_input_preserves_missing_and_zero_semantics() -> None:
    rule_input = CompletenessRuleInput(
        expected_fields=("drama_id", "play_count"),
        available_fields=("drama_id", "play_count"),
        metric_coverage=(("play_count", True),),
        expected_dates=(date(2026, 9, 21), date(2026, 9, 22)),
        available_dates=(date(2026, 9, 21),),
        play_count_available=True,
    )
    assert rule_input.metric_coverage == (("play_count", True),)
    assert rule_input.available_dates == (date(2026, 9, 21),)

    with pytest.raises(ValueError):
        CompletenessRuleInput(
            expected_fields=("drama_id",),
            available_fields=("drama_id",),
            metric_coverage=(("play_count", True), ("play_count", False)),
        )
    with pytest.raises(ValueError):
        CompletenessRuleInput(
            expected_fields=("drama_id",),
            available_fields=("drama_id",),
            metric_coverage=(),
            expected_dates=(date(2026, 9, 22), date(2026, 9, 21)),
        )


def test_consistency_input_contains_facts_without_judgment_logic() -> None:
    unresolved = ConsistencyCheckInput(
        check_code="WEAK_REFERENCE_EXISTS",
        entity_type="OPERATION_ACTION_SOURCE",
        entity_id=9,
        consistent=None,
        source_type="PREDICTION_INPUT",
        source_reference_ids=(22,),
    )
    rule_input = ConsistencyRuleInput(
        relationship_checks=(unresolved,),
        revision_checks=(),
        as_of_timestamp=AS_OF,
    )

    assert rule_input.relationship_checks[0].consistent is None
    with pytest.raises(ValueError):
        ConsistencyRuleInput(
            relationship_checks=(),
            revision_checks=(),
            as_of_timestamp=datetime(2026, 9, 23),
        )


def test_result_defaults_preserve_rule_versions_and_zero_values() -> None:
    freshness = FreshnessResult(
        status=QualityStatus.HEALTHY,
        availability=AVAILABLE,
        delay_seconds=0,
    )
    completeness = CompletenessResult(
        status=QualityStatus.HEALTHY,
        availability=AVAILABLE,
        coverage_ratio=Decimal("1"),
    )
    consistency = ConsistencyResult(
        status=QualityStatus.HEALTHY,
        availability=AVAILABLE,
        issue_count=0,
    )

    assert freshness.delay_seconds == 0
    assert freshness.evidence == ()
    assert freshness.rule_version == FRESHNESS_RULE_VERSION
    assert completeness.missing_items == ()
    assert completeness.rule_version == COMPLETENESS_RULE_VERSION
    assert consistency.issue_count == 0
    assert consistency.rule_version == CONSISTENCY_RULE_VERSION


def test_result_boundaries_reject_invalid_counts_and_coverage() -> None:
    with pytest.raises(ValueError):
        CompletenessResult(
            status=QualityStatus.FAILED,
            availability=AVAILABLE,
            coverage_ratio=Decimal("1.01"),
        )
    with pytest.raises(ValueError):
        ConsistencyResult(
            status=QualityStatus.FAILED,
            availability=AVAILABLE,
            issue_count=0,
            evidence=(_evidence(),),
        )


def test_complete_system_response_constructs_with_orthogonal_statuses() -> None:
    freshness = FreshnessResult(
        status=QualityStatus.WARNING,
        availability=AVAILABLE,
        delay_seconds=90_000,
        evidence=(
            EvidenceItem(
                issue_type=QualityIssueType.FRESHNESS,
                check_code="DATA_DELAYED",
                entity_type="METRIC_FEED",
                entity_id="drama:1:platform:2",
                observed_value=90_000,
                expected_condition="delay_seconds <= 86400",
                source_type="SNAPSHOT",
                source_reference_ids=(101,),
                message="The latest visible data is delayed.",
            ),
        ),
        analysis_as_of=AS_OF,
    )
    completeness = CompletenessResult(
        status=QualityStatus.FAILED,
        availability=AVAILABLE,
        coverage_ratio=Decimal("0.5"),
        missing_items=("2026-09-22",),
        evidence=(
            EvidenceItem(
                issue_type=QualityIssueType.COMPLETENESS,
                check_code="MISSING_BUSINESS_DATE",
                entity_type="DRAMA_PLATFORM",
                entity_id=3,
                observed_value=("2026-09-22",),
                expected_condition="all seven business dates are present",
                source_type="SNAPSHOT",
                source_reference_ids=(101,),
                message="One business date is missing.",
            ),
        ),
        analysis_as_of=AS_OF,
    )
    evidence = _evidence()
    consistency = ConsistencyResult(
        status=QualityStatus.FAILED,
        availability=AVAILABLE,
        issue_count=1,
        evidence=(evidence,),
        analysis_as_of=AS_OF,
    )

    response = DataGovernanceResponse(
        analysis_as_of=AS_OF,
        scope=GovernanceScope.SYSTEM,
        availability=AVAILABLE,
        freshness=freshness,
        completeness=completeness,
        consistency=consistency,
    )

    assert response.scope is GovernanceScope.SYSTEM
    assert response.availability.status is AvailabilityStatus.AVAILABLE
    assert response.completeness.status is QualityStatus.FAILED
    assert response.rule_set_version == GOVERNANCE_RULE_SET_VERSION

    with pytest.raises(ValueError):
        DataGovernanceResponse(
            analysis_as_of=AS_OF,
            scope="SYSTEM",  # type: ignore[arg-type]
            availability=AVAILABLE,
            freshness=freshness,
            completeness=completeness,
            consistency=consistency,
        )


def test_contracts_have_no_forbidden_layer_dependencies() -> None:
    import services.data_governance.contracts as contracts

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
        {
            "sqlalchemy",
            "database",
            "models",
            "repositories",
            "services",
            "fastapi",
            "schemas",
            "routers",
        }
    )


def test_package_exports_contracts_without_later_layers() -> None:
    import services.data_governance as package

    assert package.DataGovernanceResponse is DataGovernanceResponse
    assert not hasattr(package, "DataGovernanceService")
    assert not hasattr(package, "FreshnessRule")
