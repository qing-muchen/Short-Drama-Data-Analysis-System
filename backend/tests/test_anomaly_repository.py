"""Repository tests for Phase 4 anomaly findings."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.orm import Session

from analytics.anomaly_detection import AnomalyFinding
from models.anomaly import DataAnomalyRecord
from models.drama import Drama
from repositories.anomaly_repository import (
    AnomalyRepository,
    AnomalyStatistics,
    AnomalyTrendPoint,
)


ANALYSIS_AS_OF = datetime(2026, 9, 19, 15, 59, 59, tzinfo=timezone.utc)


def make_session() -> Session:
    """Return a Session-shaped mock without connecting to MySQL."""

    return create_autospec(Session, instance=True)


def make_finding(
    *,
    drama_id: int = 11,
    severity: str = "A",
) -> AnomalyFinding:
    return AnomalyFinding(
        drama_id=drama_id,
        metric_type="PLAY_COUNT",
        anomaly_type="PLAY_COUNT_GROWTH_ANOMALY",
        severity=severity,  # type: ignore[arg-type]
        analysis_as_of=ANALYSIS_AS_OF,
        baseline_value=Decimal("100.0000"),
        actual_value=Decimal("260.0000"),
        deviation_value=Decimal("160.0000"),
        evidence_summary="current_value=260; baseline_mean=100; z_score=4",
    )


def test_save_single_anomaly_maps_all_persistence_fields() -> None:
    session = make_session()
    detected_at = datetime(2026, 9, 19, 16, 30, tzinfo=timezone.utc)

    saved = AnomalyRepository(session).save_anomalies(
        [make_finding()],
        detected_at=detected_at,
    )

    assert len(saved) == 1
    entity = saved[0]
    assert entity.drama_id == 11
    assert entity.metric_type == "PLAY_COUNT"
    assert entity.anomaly_type == "PLAY_COUNT_GROWTH_ANOMALY"
    assert entity.status == "OPEN"
    assert entity.analysis_as_of == ANALYSIS_AS_OF
    assert entity.detected_at == detected_at
    assert entity.algorithm_version == "Rule-based Detection V1.0"
    assert entity.baseline_value == Decimal("100.0000")
    assert entity.actual_value == Decimal("260.0000")
    assert entity.deviation_value == Decimal("160.0000")


def test_save_anomalies_adds_all_and_flushes_without_commit() -> None:
    session = make_session()
    repository = AnomalyRepository(session)

    detected_at = datetime(2026, 9, 19, 16, 30, tzinfo=timezone.utc)
    saved = repository.save_anomalies(
        [make_finding(), make_finding(drama_id=12)],
        detected_at=detected_at,
    )

    assert len(saved) == 2
    assert all(isinstance(entity, DataAnomalyRecord) for entity in saved)
    assert saved[0].status == "OPEN"
    assert all(entity.detected_at == detected_at for entity in saved)
    session.add_all.assert_called_once_with(saved)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_save_empty_collection_still_flushes_and_returns_empty() -> None:
    session = make_session()

    result = AnomalyRepository(session).save_anomalies([])

    assert result == []
    session.add_all.assert_called_once_with([])
    session.flush.assert_called_once_with()


def test_get_anomalies_builds_filters_pagination_and_eager_load() -> None:
    session = make_session()
    session.scalar.return_value = 1
    record = DataAnomalyRecord(anomaly_id=1, drama_id=11)
    session.scalars.return_value.all.return_value = [record]
    repository = AnomalyRepository(session)

    page = repository.get_anomalies(
        page=2,
        page_size=10,
        analysis_as_of=ANALYSIS_AS_OF,
        status="OPEN",
        severity="A",
        metric_type="PLAY_COUNT",
        anomaly_type="PLAY_COUNT_GROWTH_ANOMALY",
    )

    assert page.page == 2
    assert page.page_size == 10
    assert page.total == 1
    assert page.items == [record]
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "data_anomaly_records.analysis_as_of = %s" in compiled
    assert "data_anomaly_records.status = %s" in compiled
    assert "data_anomaly_records.severity = %s" in compiled
    assert "data_anomaly_records.metric_type = %s" in compiled
    assert "data_anomaly_records.anomaly_type = %s" in compiled
    assert "data_anomaly_records.severity DESC" in compiled
    assert "data_anomaly_records.detected_at DESC" in compiled
    assert "data_anomaly_records.anomaly_id DESC" in compiled
    assert statement._with_options


def test_get_anomalies_validates_page_arguments() -> None:
    repository = AnomalyRepository(make_session())

    with pytest.raises(ValueError, match="page"):
        repository.get_anomalies(page=0, page_size=20)
    with pytest.raises(ValueError, match="page_size"):
        repository.get_anomalies(page=1, page_size=0)


def test_get_by_drama_orders_history_and_eager_loads_drama() -> None:
    session = make_session()
    record = DataAnomalyRecord(anomaly_id=1, drama_id=11)
    session.scalars.return_value.unique.return_value.all.return_value = [record]

    result = AnomalyRepository(session).get_by_drama(drama_id=11, limit=20)

    assert result == [record]
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "data_anomaly_records.drama_id = %s" in compiled
    assert "data_anomaly_records.analysis_as_of DESC" in compiled
    assert statement._with_options


def test_get_latest_anomalies_uses_max_analysis_cutoff() -> None:
    session = make_session()
    session.scalar.return_value = ANALYSIS_AS_OF
    latest = DataAnomalyRecord(anomaly_id=2, drama_id=11)
    session.scalars.return_value.unique.return_value.all.return_value = [latest]

    result = AnomalyRepository(session).get_latest_anomalies()

    assert result == [latest]
    assert session.scalar.call_count == 1
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "data_anomaly_records.analysis_as_of = %s" in compiled


def test_get_latest_anomalies_returns_empty_without_data() -> None:
    session = make_session()
    session.scalar.return_value = None

    assert AnomalyRepository(session).get_latest_anomalies() == []
    session.scalars.assert_not_called()


def test_get_trend_groups_by_analysis_date() -> None:
    session = make_session()
    session.execute.return_value.all.return_value = [
        ("2026-09-18", 3),
        ("2026-09-19", 5),
    ]

    result = AnomalyRepository(session).get_trend(
        start_as_of=ANALYSIS_AS_OF,
        metric_type="PLAY_COUNT",
    )

    assert result == [
        AnomalyTrendPoint(datetime(2026, 9, 18).date(), 3),
        AnomalyTrendPoint(datetime(2026, 9, 19).date(), 5),
    ]
    statement = session.execute.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "date(data_anomaly_records.analysis_as_of)" in compiled.lower()
    assert "GROUP BY" in compiled


def test_update_status_fetches_entity_sets_value_and_flushes() -> None:
    session = make_session()
    entity = DataAnomalyRecord(anomaly_id=7, drama_id=11, status="OPEN")
    session.scalar.return_value = entity

    result = AnomalyRepository(session).update_status(
        anomaly_id=7,
        new_status="ACKNOWLEDGED",
    )

    assert result is entity
    assert entity.status == "ACKNOWLEDGED"
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_update_status_returns_none_for_missing_anomaly() -> None:
    session = make_session()
    session.scalar.return_value = None

    assert AnomalyRepository(session).update_status(
        anomaly_id=99,
        new_status="RESOLVED",
    ) is None
    session.flush.assert_not_called()


def test_get_statistics_returns_total_and_all_distributions() -> None:
    session = make_session()
    session.scalar.return_value = 5
    grouped_results = []
    for rows in (
        [("A", 2), ("C", 3)],
        [("OPEN", 4), ("RESOLVED", 1)],
        [("PLAY_COUNT", 4), ("ENGAGEMENT_RATE", 1)],
    ):
        result = MagicMock()
        result.all.return_value = rows
        grouped_results.append(result)
    session.execute.side_effect = grouped_results

    result = AnomalyRepository(session).get_statistics()

    assert result == AnomalyStatistics(
        total_count=5,
        severity_distribution={"A": 2, "B": 0, "C": 3},
        status_distribution={
            "OPEN": 4,
            "ACKNOWLEDGED": 0,
            "RESOLVED": 1,
            "IGNORED": 0,
        },
        metric_distribution={
            "PLAY_COUNT": 4,
            "ENGAGEMENT_RATE": 1,
        },
    )


def test_repository_does_not_manage_transactions() -> None:
    session = make_session()
    repository = AnomalyRepository(session)

    repository.save_anomalies([make_finding()])

    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.close.assert_not_called()
