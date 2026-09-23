"""Query semantics and transaction-boundary tests for Phase 8 reads."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.orm import Session

from repositories.operation_analytics_repository import (
    OperationAnalyticsRepository,
)


AS_OF = datetime(2026, 9, 22, tzinfo=timezone.utc)
START = datetime(2026, 9, 1, tzinfo=timezone.utc)
END = datetime(2026, 9, 22, tzinfo=timezone.utc)


def make_session() -> Session:
    return create_autospec(Session, instance=True)


def test_metric_query_selects_latest_effective_revision_as_of() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = []

    result = OperationAnalyticsRepository(session).list_metric_revisions(
        drama_ids=(1, 2),
        platform_id=3,
        start_time=START,
        end_time=END,
        analysis_as_of=AS_OF,
    )

    assert result == ()
    statement = session.execute.call_args.args[0]
    compiled = statement.compile(dialect=dialect())
    sql = str(compiled)
    assert "max(drama_metric_snapshot_revisions.version_no)" in sql
    assert "drama_metric_snapshot_revisions.changed_at <= %s" in sql
    assert "drama_metric_snapshots.snapshot_time <= %s" in sql
    assert "drama_metric_snapshot_revisions.revision_action != %s" in sql
    assert "drama_platforms.platform_id = %s" in sql
    assert "current_revision_id" not in sql
    assert all(
        value.tzinfo is None
        for value in compiled.params.values()
        if isinstance(value, datetime)
    )


def test_metric_query_maps_projection_and_empty_scope_short_circuits() -> None:
    session = make_session()
    row = (
        1,
        2,
        3,
        4,
        datetime(2026, 9, 5),
        2,
        "CORRECTION",
        100,
        10,
        5,
        2,
        1,
        datetime(2026, 9, 6),
    )
    session.execute.return_value.all.return_value = [row]
    repository = OperationAnalyticsRepository(session)

    result = repository.list_metric_revisions(
        drama_ids=(1,), start_time=START, end_time=END, analysis_as_of=AS_OF
    )

    assert result[0].snapshot_revision_id == 4
    assert result[0].play_count == 100
    session.reset_mock()
    assert repository.list_metric_revisions(
        drama_ids=(), start_time=START, end_time=END, analysis_as_of=AS_OF
    ) == ()
    session.execute.assert_not_called()


def test_completed_action_query_uses_history_anchor_and_as_of() -> None:
    session = make_session()
    session.scalar.return_value = 1
    session.execute.return_value.all.return_value = [
        (7, 9, datetime(2026, 9, 10))
    ]

    page = OperationAnalyticsRepository(session).list_completed_actions(
        analysis_as_of=AS_OF, drama_id=9, page=1, page_size=20
    )

    assert page.total == 1
    assert page.items[0].anchor_time == datetime(2026, 9, 10)
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=dialect()))
    assert "operation_action_history.created_at <= %s" in sql
    assert "operation_action_history.new_status = %s" in sql
    assert "min(operation_action_history.created_at)" in sql


def test_anomaly_query_is_bounded_by_window_and_analysis_cutoff() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = []

    OperationAnalyticsRepository(session).list_anomalies(
        drama_ids=(1,), start_time=START, end_time=END, analysis_as_of=AS_OF
    )

    sql = str(session.execute.call_args.args[0].compile(dialect=dialect()))
    assert "data_anomaly_records.analysis_as_of >= %s" in sql
    assert "data_anomaly_records.analysis_as_of < %s" in sql
    assert sql.count("data_anomaly_records.analysis_as_of <= %s") == 1


def test_drama_query_conservatively_rejects_future_mutable_rows() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = []

    OperationAnalyticsRepository(session).list_drama_records(
        drama_ids=(1,), analysis_as_of=AS_OF
    )

    sql = str(session.execute.call_args.args[0].compile(dialect=dialect()))
    assert "dramas.created_at <= %s" in sql
    assert "dramas.updated_at <= %s" in sql
    assert "drama_platforms.updated_at <= %s" in sql


def test_repository_is_strictly_read_only() -> None:
    source = (
        Path(__file__).parents[1]
        / "repositories"
        / "operation_analytics_repository.py"
    ).read_text(encoding="utf-8")
    for forbidden in (".commit(", ".rollback(", ".flush(", "sessionmaker"):
        assert forbidden not in source


def test_repository_rejects_reversed_or_empty_time_window() -> None:
    session = make_session()

    with pytest.raises(ValueError, match="start_time"):
        OperationAnalyticsRepository(session).list_metric_revisions(
            drama_ids=(1,),
            start_time=END,
            end_time=START,
            analysis_as_of=AS_OF,
        )

    session.execute.assert_not_called()
