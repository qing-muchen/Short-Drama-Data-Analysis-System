"""Read semantics and transaction-boundary tests for reporting projections."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from sqlalchemy import inspect
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.orm import Session

from repositories.reporting_repository import (
    AnomalyRecordsProjection,
    DataQualityResultsProjection,
    DramaCatalogProjection,
    OperationActionsProjection,
    PredictionResultsProjection,
    ReportingRepository,
    ScoreResultsProjection,
)
from services.reporting.contracts import ReportFilter, ReportRequest, ReportType


AS_OF = datetime(2026, 9, 23, 8, tzinfo=UTC)
START = datetime(2026, 9, 1, tzinfo=UTC)
END = datetime(2026, 9, 22, tzinfo=UTC)


def make_session() -> Session:
    return create_autospec(Session, instance=True)


def request(
    report_type: ReportType,
    *filters: ReportFilter,
) -> ReportRequest:
    return ReportRequest(report_type, tuple(sorted(filters, key=lambda item: item.key)), AS_OF)


def compiled_execute(session: Session) -> tuple[str, dict[str, object]]:
    statement = session.execute.call_args.args[0]
    compiled = statement.compile(dialect=dialect())
    return str(compiled), compiled.params


def test_drama_catalog_returns_immutable_projection_and_current_state_query() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (1, "D-001", "Drama", "COMPLETED", None, None, None, None, None)
    ]
    result = ReportingRepository(session).list_drama_catalog(
        request(
            ReportType.DRAMA_CATALOG,
            ReportFilter("platform_id", 2),
            ReportFilter("tag_id", 3),
        ),
        limit=20,
    )

    assert result == (
        DramaCatalogProjection(
            1, "D-001", "Drama", "COMPLETED", None, None, None, None, None
        ),
    )
    assert result[0].platforms is None
    assert inspect(result[0], raiseerr=False) is None
    with pytest.raises(FrozenInstanceError):
        result[0].status = "DRAFT"  # type: ignore[misc]
    sql, _ = compiled_execute(session)
    assert "EXISTS" in sql
    assert "drama_platforms.platform_id" in sql
    assert "drama_tags.tag_id" in sql
    assert "ORDER BY dramas.drama_id ASC" in sql


def test_score_query_applies_cutoff_filters_and_keeps_all_versions() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (
            4,
            1,
            date(2026, 9, 20),
            "ALL",
            0,
            datetime(2026, 9, 20),
            Decimal("70"),
            Decimal("71"),
            Decimal("72"),
            Decimal("73"),
            Decimal("72"),
            "A",
            "score-v1",
        )
    ]
    result = ReportingRepository(session).list_score_results(
        request(
            ReportType.SCORE_RESULTS,
            ReportFilter("algorithm_version", "score-v1"),
            ReportFilter("drama_id", 1),
            ReportFilter("end_time", END),
            ReportFilter("start_time", START),
        )
    )

    assert isinstance(result[0], ScoreResultsProjection)
    assert result[0].algorithm_version == "score-v1"
    sql, params = compiled_execute(session)
    assert "drama_scores.analysis_as_of <= %s" in sql
    assert "drama_scores.analysis_as_of >= %s" in sql
    assert "drama_scores.algorithm_version = %s" in sql
    assert "max(" not in sql.lower()
    assert "current_revision" not in sql
    assert all(
        value.tzinfo is None
        for value in params.values()
        if isinstance(value, datetime)
    )


def test_quality_query_preserves_distinct_rule_versions_without_collapsing() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (
            5,
            date(2026, 9, 20),
            "ALL",
            0,
            datetime(2026, 9, 20),
            Decimal("90"),
            Decimal("91"),
            Decimal("92"),
            Decimal("93"),
            Decimal("91.5"),
            "A",
            20,
            1,
            "quality-v1",
            "rules-v1",
            "a" * 64,
        )
    ]
    result = ReportingRepository(session).list_data_quality_results(
        request(
            ReportType.DATA_QUALITY_RESULTS,
            ReportFilter("rule_set_version", "rules-v1"),
        )
    )

    assert isinstance(result[0], DataQualityResultsProjection)
    assert result[0].rule_set_version == "rules-v1"
    sql, _ = compiled_execute(session)
    assert "data_quality_scores.analysis_as_of <= %s" in sql
    assert "data_quality_scores.rule_set_version = %s" in sql
    assert "max(" not in sql.lower()


def test_prediction_projection_preserves_zero_value() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (
            6,
            1,
            "PLAY_COUNT",
            date(2026, 9, 20),
            date(2026, 9, 21),
            Decimal("0"),
            "prediction-v1",
            datetime(2026, 9, 20),
        )
    ]
    result = ReportingRepository(session).list_prediction_results(
        request(ReportType.PREDICTION_RESULTS)
    )
    assert isinstance(result[0], PredictionResultsProjection)
    assert result[0].predicted_value == Decimal("0")
    sql, _ = compiled_execute(session)
    assert "prediction_results.analysis_as_of <= %s" in sql


def test_anomaly_query_bounds_detection_time_but_reads_current_status() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (
            7,
            1,
            "PLAY_COUNT",
            "DATA_SPIKE_ANOMALY",
            "A",
            "ACKNOWLEDGED",
            datetime(2026, 9, 20),
            datetime(2026, 9, 20),
            "anomaly-v1",
            None,
            Decimal("100"),
            None,
            "Observed spike",
        )
    ]
    result = ReportingRepository(session).list_anomaly_records(
        request(
            ReportType.ANOMALY_RECORDS,
            ReportFilter("status", "ACKNOWLEDGED"),
        )
    )
    assert isinstance(result[0], AnomalyRecordsProjection)
    assert result[0].baseline_value is None
    assert result[0].deviation_value is None
    sql, _ = compiled_execute(session)
    assert "data_anomaly_records.detected_at <= %s" in sql
    assert "data_anomaly_records.status = %s" in sql
    assert "operation_action_history" not in sql


def test_action_query_counts_visible_sources_and_history_without_reconstruction() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        (
            8,
            None,
            "Review action",
            None,
            "MEDIUM",
            "OPEN",
            None,
            3,
            None,
            datetime(2026, 9, 20),
            datetime(2026, 9, 21),
            0,
            1,
        )
    ]
    result = ReportingRepository(session).list_operation_actions(
        request(ReportType.OPERATION_ACTIONS)
    )
    assert isinstance(result[0], OperationActionsProjection)
    assert result[0].drama_id is None
    assert result[0].description is None
    assert result[0].source_count == 0
    sql, _ = compiled_execute(session)
    assert "operation_actions.created_at <= %s" in sql
    assert "operation_action_sources.created_at <= %s" in sql
    assert "operation_action_history.created_at <= %s" in sql
    assert "max(operation_action_history" not in sql.lower()


def test_count_uses_the_same_projection_statement_without_returning_models() -> None:
    session = make_session()
    session.scalar.return_value = 12
    total = ReportingRepository(session).count_prediction_results(
        request(ReportType.PREDICTION_RESULTS)
    )
    assert total == 12
    sql = str(session.scalar.call_args.args[0].compile(dialect=dialect()))
    assert "count(*)" in sql
    assert "prediction_results.analysis_as_of <= %s" in sql


def test_repository_rejects_invalid_window_and_unknown_filters() -> None:
    session = make_session()
    repository = ReportingRepository(session)
    with pytest.raises(ValueError, match="offset"):
        repository.list_drama_catalog(
            request(ReportType.DRAMA_CATALOG), offset=-1
        )
    with pytest.raises(ValueError, match="unsupported repository filter"):
        repository.list_score_results(
            request(
                ReportType.SCORE_RESULTS,
                ReportFilter("status", "OPEN"),
            )
        )
    session.execute.assert_not_called()


def test_repository_is_strictly_read_only_and_has_no_rule_or_service_dependency() -> None:
    source = (
        Path(__file__).parents[1] / "repositories" / "reporting_repository.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        ".commit(",
        ".rollback(",
        ".flush(",
        "sessionmaker",
        "serializers",
        ".rules",
        ".service",
        "datetime.now",
        "func.now",
    ):
        assert forbidden not in source
