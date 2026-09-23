"""Read semantics and transaction-boundary tests for Phase 9 governance."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.orm import Session

from repositories.data_governance_repository import (
    DataGovernanceRepository,
)


AS_OF = datetime(2026, 9, 23, tzinfo=timezone.utc)
START = datetime(2026, 9, 16, tzinfo=timezone.utc)
END = datetime(2026, 9, 23, tzinfo=timezone.utc)


def make_session() -> Session:
    return create_autospec(Session, instance=True)


def _compiled_execute_statement(session: Session) -> tuple[str, dict[str, object]]:
    statement = session.execute.call_args.args[0]
    compiled = statement.compile(dialect=dialect())
    return str(compiled), compiled.params


def test_freshness_query_reads_latest_visible_revision_as_of() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (3, 1, 2, datetime(2026, 9, 22, 6, 0))
    ]

    records = DataGovernanceRepository(session).list_freshness_records(
        analysis_as_of=AS_OF
    )

    assert records[0].drama_platform_id == 3
    assert records[0].latest_snapshot_time == datetime(2026, 9, 22, 6, 0)
    sql, params = _compiled_execute_statement(session)
    assert "max(drama_metric_snapshot_revisions.version_no)" in sql
    assert "drama_metric_snapshot_revisions.changed_at <= %s" in sql
    assert "drama_metric_snapshot_revisions.revision_action != %s" in sql
    assert "drama_metric_snapshots.snapshot_time <= %s" in sql
    assert "drama_platforms.status = %s" in sql
    assert "platforms.status = %s" in sql
    assert "current_revision_id" not in sql
    assert all(
        value.tzinfo is None
        for value in params.values()
        if isinstance(value, datetime)
    )


def test_freshness_projection_can_represent_a_feed_without_data() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [(3, 1, 2, None)]

    record = DataGovernanceRepository(session).list_freshness_records(
        analysis_as_of=AS_OF
    )[0]

    assert record.latest_snapshot_time is None
    with pytest.raises(FrozenInstanceError):
        record.latest_snapshot_time = datetime(2026, 9, 1)  # type: ignore[misc]


def test_completeness_target_query_returns_field_and_relation_projection() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (1, "D001", "Drama", "SERIALIZING", 7, 3),
        (2, "D002", "No Platform", "COMPLETED", None, None),
    ]

    records = DataGovernanceRepository(session).list_completeness_targets(
        analysis_as_of=AS_OF
    )

    assert records[0].drama_platform_id == 7
    assert records[1].platform_id is None
    sql, _ = _compiled_execute_statement(session)
    assert "LEFT OUTER JOIN drama_platforms" in sql
    assert "LEFT OUTER JOIN platforms" in sql
    assert "dramas.created_at <= %s" in sql
    assert "dramas.updated_at <= %s" in sql


def test_metric_coverage_selects_latest_revision_and_filters_void() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (
            7,
            10,
            12,
            datetime(2026, 9, 20),
            2,
            "CORRECTION",
            100,
            datetime(2026, 9, 21),
        )
    ]

    records = DataGovernanceRepository(session).list_metric_coverage_records(
        drama_platform_ids=(7,),
        start_time=START,
        end_time=END,
        analysis_as_of=AS_OF,
    )

    assert records[0].snapshot_revision_id == 12
    assert records[0].play_count == 100
    sql, _ = _compiled_execute_statement(session)
    assert "max(drama_metric_snapshot_revisions.version_no)" in sql
    assert "drama_metric_snapshot_revisions.changed_at <= %s" in sql
    assert "drama_metric_snapshot_revisions.revision_action != %s" in sql
    assert "drama_metric_snapshots.snapshot_time >= %s" in sql
    assert "drama_metric_snapshots.snapshot_time < %s" in sql
    assert "current_revision_id" not in sql


def test_metric_coverage_empty_scope_short_circuits_and_range_is_validated() -> None:
    session = make_session()
    repository = DataGovernanceRepository(session)

    assert repository.list_metric_coverage_records(
        drama_platform_ids=(),
        start_time=START,
        end_time=END,
        analysis_as_of=AS_OF,
    ) == ()
    session.execute.assert_not_called()

    with pytest.raises(ValueError, match="start_time"):
        repository.list_metric_coverage_records(
            drama_platform_ids=(1,),
            start_time=END,
            end_time=START,
            analysis_as_of=AS_OF,
        )
    session.execute.assert_not_called()


def test_action_source_query_returns_raw_weak_reference_existence() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [(4, 8, "ANOMALY", 12, True)]

    record = DataGovernanceRepository(session).list_action_source_records(
        analysis_as_of=AS_OF
    )[0]

    assert record.source_reference_id == 12
    assert record.target_exists is True
    sql, _ = _compiled_execute_statement(session)
    assert "operation_action_sources.source_type" in sql
    assert "data_anomaly_records.anomaly_id" in sql
    assert "data_quality_scores.quality_score_id" in sql
    assert "drama_scores.score_id" in sql
    assert "operation_action_sources.created_at <= %s" in sql


def test_action_status_query_uses_latest_history_before_cutoff() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [(8, "IN_PROGRESS", 14, "IN_PROGRESS")]

    record = DataGovernanceRepository(session).list_action_status_records(
        analysis_as_of=AS_OF
    )[0]

    assert record.latest_history_id == 14
    assert record.latest_history_status == "IN_PROGRESS"
    sql, _ = _compiled_execute_statement(session)
    assert "max(operation_action_history.history_id)" in sql
    assert "operation_action_history.created_at <= %s" in sql
    assert "operation_action_history.new_status IS NOT NULL" in sql


def test_lineage_query_returns_target_source_and_as_of_facts() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (
            1,
            "EXPLANATION",
            2,
            "SNAPSHOT",
            3,
            datetime(2026, 9, 20),
            True,
            True,
            True,
            True,
        )
    ]

    record = DataGovernanceRepository(session).list_lineage_records(
        analysis_as_of=AS_OF
    )[0]

    assert record.target_exists is True
    assert record.source_visible_as_of is True
    sql, _ = _compiled_execute_statement(session)
    assert "analysis_lineage_records.analysis_as_of <= %s" in sql
    assert "analysis_explanations.analysis_as_of = analysis_lineage_records.analysis_as_of" in sql
    assert "drama_metric_snapshots.snapshot_time <= analysis_lineage_records.analysis_as_of" in sql
    assert "data_quality_rules.valid_from <= analysis_lineage_records.analysis_as_of" in sql
    assert "data_anomaly_records.analysis_as_of <= analysis_lineage_records.analysis_as_of" in sql


def test_revision_query_keeps_void_latest_revision_for_chain_validation() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (
            10,
            datetime(2026, 9, 20),
            12,
            3,
            "VOID",
            11,
            10,
            2,
            datetime(2026, 9, 22),
        )
    ]

    record = DataGovernanceRepository(session).list_revision_records(
        analysis_as_of=AS_OF
    )[0]

    assert record.revision_action == "VOID"
    assert record.previous_version_no == 2
    sql, _ = _compiled_execute_statement(session)
    assert "max(drama_metric_snapshot_revisions.version_no)" in sql
    assert "drama_metric_snapshot_revisions.changed_at <= %s" in sql
    assert "revision_action !=" not in sql
    assert "current_revision_id" not in sql


def test_repository_is_strictly_read_only_and_has_no_rule_or_service_dependency() -> None:
    source = (
        Path(__file__).parents[1]
        / "repositories"
        / "data_governance_repository.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        ".commit(",
        ".rollback(",
        ".flush(",
        "sessionmaker",
        "data_governance.rules",
        "data_governance.service",
    ):
        assert forbidden not in source
