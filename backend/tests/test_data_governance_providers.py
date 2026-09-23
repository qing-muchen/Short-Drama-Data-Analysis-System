"""Projection-to-contract mapping tests for Phase 9 governance providers."""

from __future__ import annotations

import ast
from datetime import date, datetime, timezone
import inspect

from repositories.data_governance_repository import (
    ActionSourceReadRecord,
    ActionStatusReadRecord,
    CompletenessTargetRecord,
    FreshnessReadRecord,
    LineageReadRecord,
    MetricCoverageReadRecord,
    RevisionReadRecord,
)
from services.data_governance.contracts import (
    CompletenessRuleInput,
    ConsistencyRuleInput,
    FreshnessRuleInput,
)
from services.data_governance.providers import (
    CompletenessProvider,
    ConsistencyProvider,
    FreshnessProvider,
)


AS_OF = datetime(2026, 9, 23, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self) -> None:
        self.freshness_records: tuple[FreshnessReadRecord, ...] = ()
        self.completeness_targets: tuple[CompletenessTargetRecord, ...] = ()
        self.metric_records: tuple[MetricCoverageReadRecord, ...] = ()
        self.action_sources: tuple[ActionSourceReadRecord, ...] = ()
        self.action_statuses: tuple[ActionStatusReadRecord, ...] = ()
        self.lineage_records: tuple[LineageReadRecord, ...] = ()
        self.revision_records: tuple[RevisionReadRecord, ...] = ()
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_freshness_records(self, **kwargs):
        self.calls.append(("freshness", kwargs))
        return self.freshness_records

    def list_completeness_targets(self, **kwargs):
        self.calls.append(("completeness_targets", kwargs))
        return self.completeness_targets

    def list_metric_coverage_records(self, **kwargs):
        self.calls.append(("metric_coverage", kwargs))
        return self.metric_records

    def list_action_source_records(self, **kwargs):
        self.calls.append(("action_sources", kwargs))
        return self.action_sources

    def list_action_status_records(self, **kwargs):
        self.calls.append(("action_statuses", kwargs))
        return self.action_statuses

    def list_lineage_records(self, **kwargs):
        self.calls.append(("lineage", kwargs))
        return self.lineage_records

    def list_revision_records(self, **kwargs):
        self.calls.append(("revisions", kwargs))
        return self.revision_records


def _metric_record(
    *,
    snapshot_id: int,
    snapshot_time: datetime,
    play_count: int | None = 100,
) -> MetricCoverageReadRecord:
    return MetricCoverageReadRecord(
        drama_platform_id=7,
        snapshot_id=snapshot_id,
        snapshot_revision_id=100 + snapshot_id,
        snapshot_time=snapshot_time,
        version_no=1,
        revision_action="INITIAL",
        play_count=play_count,
        changed_at=snapshot_time,
    )


def test_freshness_provider_maps_repository_records_to_rule_inputs() -> None:
    repository = FakeRepository()
    repository.freshness_records = (
        FreshnessReadRecord(7, 1, 2, datetime(2026, 9, 22, 12, 0)),
        FreshnessReadRecord(8, 2, 2, None),
    )

    results = FreshnessProvider(repository).get_rule_inputs(
        analysis_as_of=AS_OF
    )

    assert all(isinstance(item, FreshnessRuleInput) for item in results)
    assert results[0].entity_id == 7
    assert results[0].latest_timestamp == datetime(
        2026, 9, 22, 12, 0, tzinfo=timezone.utc
    )
    assert results[1].latest_timestamp is None
    assert repository.calls == [("freshness", {"analysis_as_of": AS_OF})]


def test_completeness_provider_maps_fields_and_seven_complete_business_dates() -> None:
    repository = FakeRepository()
    repository.completeness_targets = (
        CompletenessTargetRecord(
            drama_id=1,
            drama_code="D001",
            drama_name="Drama",
            drama_status="SERIALIZING",
            drama_platform_id=7,
            platform_id=2,
        ),
    )
    # UTC 16:00 is the next calendar day at UTC+08:00.
    repository.metric_records = tuple(
        _metric_record(
            snapshot_id=index,
            snapshot_time=datetime(2026, 9, 14 + index, 16, 0),
        )
        for index in range(1, 8)
    )

    results = CompletenessProvider(repository).get_rule_inputs(
        analysis_as_of=AS_OF
    )

    assert len(results) == 1
    rule_input = results[0]
    assert isinstance(rule_input, CompletenessRuleInput)
    assert rule_input.expected_dates == tuple(
        date(2026, 9, day) for day in range(16, 23)
    )
    # At 2026-09-23 08:00 Asia/Shanghai, the current local date is excluded.
    assert rule_input.expected_dates[-1] == date(2026, 9, 22)
    assert rule_input.available_dates == rule_input.expected_dates
    assert rule_input.metric_coverage == (("play_count", True),)
    assert rule_input.platform_relationship_available is True
    metric_call = repository.calls[1]
    assert metric_call[0] == "metric_coverage"
    assert metric_call[1]["drama_platform_ids"] == (7,)


def test_completeness_provider_excludes_current_local_business_date() -> None:
    repository = FakeRepository()
    repository.completeness_targets = (
        CompletenessTargetRecord(1, "D001", "Drama", "SERIALIZING", 7, 2),
    )

    result = CompletenessProvider(repository).get_rule_inputs(
        analysis_as_of=datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc)
    )[0]

    assert result.expected_dates == tuple(
        date(2026, 9, day) for day in range(16, 23)
    )
    metric_call = repository.calls[1][1]
    assert metric_call["start_time"] == datetime(
        2026, 9, 15, 16, 0, tzinfo=timezone.utc
    )
    assert metric_call["end_time"] == datetime(
        2026, 9, 22, 16, 0, tzinfo=timezone.utc
    )


def test_completeness_provider_preserves_missing_relation_and_metric_facts() -> None:
    repository = FakeRepository()
    repository.completeness_targets = (
        CompletenessTargetRecord(
            drama_id=2,
            drama_code="D002",
            drama_name="No Platform",
            drama_status="COMPLETED",
            drama_platform_id=None,
            platform_id=None,
        ),
    )

    rule_input = CompletenessProvider(repository).get_rule_inputs(
        analysis_as_of=AS_OF
    )[0]

    assert rule_input.entity_type == "DRAMA"
    assert rule_input.entity_id == 2
    assert rule_input.platform_relationship_available is False
    assert rule_input.play_count_available is False
    assert rule_input.metric_coverage == (("play_count", False),)
    assert repository.calls[1][1]["drama_platform_ids"] == ()


def test_consistency_provider_maps_action_relationship_facts() -> None:
    repository = FakeRepository()
    repository.action_sources = (
        ActionSourceReadRecord(4, 8, "ANOMALY", 12, True),
    )
    repository.action_statuses = (
        ActionStatusReadRecord(8, "IN_PROGRESS", 14, "OPEN"),
    )

    result = ConsistencyProvider(repository).get_rule_input(
        analysis_as_of=AS_OF
    )

    assert isinstance(result, ConsistencyRuleInput)
    assert result.relationship_checks[0].check_code == "ACTION_SOURCE_REFERENCE"
    assert result.relationship_checks[0].consistent is True
    assert result.relationship_checks[1].check_code == "ACTION_STATUS_HISTORY"
    assert result.relationship_checks[1].consistent is False
    assert result.as_of_timestamp == AS_OF


def test_consistency_provider_maps_lineage_without_guessing_unsupported_sources() -> None:
    repository = FakeRepository()
    repository.lineage_records = (
        LineageReadRecord(
            lineage_id=5,
            target_type="EXPLANATION",
            target_id=6,
            source_type="PREDICTION_INPUT",
            source_id=7,
            lineage_analysis_as_of=datetime(2026, 9, 20),
            target_exists=True,
            target_as_of_matches=True,
            source_exists=None,
            source_visible_as_of=None,
        ),
    )

    result = ConsistencyProvider(repository).get_rule_input(
        analysis_as_of=AS_OF
    )

    checks = {check.check_code: check for check in result.relationship_checks}
    assert checks["LINEAGE_TARGET_EXISTS"].consistent is True
    assert checks["LINEAGE_SOURCE_EXISTS"].consistent is None
    assert checks["LINEAGE_SOURCE_AS_OF_VISIBLE"].consistent is None


def test_consistency_provider_maps_initial_and_corrected_revision_chains() -> None:
    repository = FakeRepository()
    repository.revision_records = (
        RevisionReadRecord(
            snapshot_id=1,
            snapshot_time=datetime(2026, 9, 20),
            snapshot_revision_id=10,
            version_no=1,
            revision_action="INITIAL",
            previous_revision_id=None,
            previous_snapshot_id=None,
            previous_version_no=None,
            changed_at=datetime(2026, 9, 20),
        ),
        RevisionReadRecord(
            snapshot_id=2,
            snapshot_time=datetime(2026, 9, 20),
            snapshot_revision_id=21,
            version_no=2,
            revision_action="CORRECTION",
            previous_revision_id=20,
            previous_snapshot_id=2,
            previous_version_no=1,
            changed_at=datetime(2026, 9, 21),
        ),
        RevisionReadRecord(
            snapshot_id=3,
            snapshot_time=datetime(2026, 9, 20),
            snapshot_revision_id=31,
            version_no=2,
            revision_action="CORRECTION",
            previous_revision_id=30,
            previous_snapshot_id=99,
            previous_version_no=1,
            changed_at=datetime(2026, 9, 21),
        ),
    )

    result = ConsistencyProvider(repository).get_rule_input(
        analysis_as_of=AS_OF
    )

    assert tuple(check.consistent for check in result.revision_checks) == (
        True,
        True,
        False,
    )


def test_providers_return_contracts_and_have_no_rule_service_or_orm_dependency() -> None:
    import services.data_governance.providers as providers

    tree = ast.parse(inspect.getsource(providers))
    imported_modules = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(module.endswith(".rules") for module in imported_modules)
    assert not any(module.endswith(".service") for module in imported_modules)
    assert "sqlalchemy" not in imported_modules
    assert not any(module.startswith("models") for module in imported_modules)

    repository = FakeRepository()
    assert FreshnessProvider(repository).get_rule_inputs(analysis_as_of=AS_OF) == ()
    assert CompletenessProvider(repository).get_rule_inputs(analysis_as_of=AS_OF) == ()
    result = ConsistencyProvider(repository).get_rule_input(analysis_as_of=AS_OF)
    assert isinstance(result, ConsistencyRuleInput)
