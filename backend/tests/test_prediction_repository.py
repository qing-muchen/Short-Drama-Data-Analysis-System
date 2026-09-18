"""Statement and transaction-boundary tests for PredictionRepository."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import create_autospec

import pytest
from sqlalchemy import UniqueConstraint, inspect
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Delete

from models.prediction import PredictionResult
from repositories.prediction_repository import PredictionRepository

DRAMA_ID = 7
METRIC_TYPE = "PLAY_COUNT"
ALGORITHM_VERSION = "Moving Average V1.0"


def make_session() -> Session:
    return create_autospec(Session, instance=True)


def prediction_values(
    *, target_date: date = date(2026, 9, 20), analysis_day: int = 19
) -> dict[str, object]:
    return {
        "drama_id": DRAMA_ID,
        "metric_type": METRIC_TYPE,
        "prediction_date": date(2026, 9, analysis_day),
        "target_date": target_date,
        "predicted_value": Decimal("1200.50"),
        "algorithm_version": ALGORITHM_VERSION,
        "analysis_as_of": datetime(2026, 9, analysis_day, 12, 0),
    }


def test_save_prediction_adds_flushes_and_does_not_commit() -> None:
    session = make_session()
    repository = PredictionRepository(session)

    result = repository.save_prediction(prediction_values())

    assert isinstance(result, PredictionResult)
    assert result.drama_id == DRAMA_ID
    assert result.target_date == date(2026, 9, 20)
    session.add.assert_called_once_with(result)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_save_prediction_accepts_an_orm_object() -> None:
    session = make_session()
    entity = PredictionResult(**prediction_values())

    result = PredictionRepository(session).save_prediction(entity)

    assert result is entity
    session.add.assert_called_once_with(entity)
    session.flush.assert_called_once_with()


def test_replace_prediction_deletes_same_target_then_flushes_new_value() -> None:
    session = make_session()
    entity = PredictionResult(**prediction_values())

    result = PredictionRepository(session).replace_prediction(entity)

    assert result is entity
    delete_statement = session.execute.call_args.args[0]
    assert isinstance(delete_statement, Delete)
    compiled = str(delete_statement.compile(dialect=dialect()))
    assert "DELETE FROM prediction_results" in compiled
    assert "prediction_results.drama_id = %s" in compiled
    assert "prediction_results.metric_type = %s" in compiled
    assert "prediction_results.algorithm_version = %s" in compiled
    assert "prediction_results.target_date = %s" in compiled
    session.add.assert_called_once_with(entity)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_get_latest_prediction_uses_required_descending_order() -> None:
    session = make_session()
    expected = PredictionResult(**prediction_values())
    session.scalar.return_value = expected

    result = PredictionRepository(session).get_latest_prediction(
        drama_id=DRAMA_ID,
        metric_type=METRIC_TYPE,
        algorithm_version=ALGORITHM_VERSION,
    )

    assert result is expected
    statement = session.scalar.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "prediction_results.drama_id = %s" in compiled
    assert "prediction_results.analysis_as_of DESC" in compiled
    assert "prediction_results.created_at DESC" in compiled
    assert "prediction_results.prediction_id DESC" in compiled
    assert statement._limit_clause.value == 1


def test_get_predictions_by_drama_orders_target_date_ascending_and_limits() -> None:
    session = make_session()
    expected = [PredictionResult(**prediction_values())]
    session.scalars.return_value.all.return_value = expected

    result = PredictionRepository(session).get_predictions_by_drama(
        drama_id=DRAMA_ID,
        metric_type=METRIC_TYPE,
        algorithm_version=ALGORITHM_VERSION,
        limit=10,
    )

    assert result == expected
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "prediction_results.target_date ASC" in compiled
    assert statement._limit_clause.value == 10


def test_get_prediction_range_filters_inclusive_dates_and_orders() -> None:
    session = make_session()
    session.scalars.return_value.all.return_value = []

    result = PredictionRepository(session).get_prediction_range(
        drama_id=DRAMA_ID,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
        metric_type=METRIC_TYPE,
        algorithm_version=ALGORITHM_VERSION,
    )

    assert result == []
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "prediction_results.target_date >= %s" in compiled
    assert "prediction_results.target_date <= %s" in compiled
    assert "prediction_results.target_date ASC" in compiled


def test_get_prediction_range_rejects_reversed_dates() -> None:
    session = make_session()

    with pytest.raises(ValueError, match="start_date"):
        PredictionRepository(session).get_prediction_range(
            drama_id=DRAMA_ID,
            start_date=date(2026, 9, 30),
            end_date=date(2026, 9, 1),
        )
    session.scalars.assert_not_called()


def test_delete_prediction_scope_flushes_and_returns_rowcount() -> None:
    session = make_session()
    session.execute.return_value.rowcount = 3

    result = PredictionRepository(session).delete_prediction_scope(
        drama_id=DRAMA_ID,
        metric_type=METRIC_TYPE,
        algorithm_version=ALGORITHM_VERSION,
    )

    assert result == 3
    statement = session.execute.call_args.args[0]
    assert isinstance(statement, Delete)
    compiled = str(statement.compile(dialect=dialect()))
    assert "DELETE FROM prediction_results" in compiled
    assert "prediction_results.drama_id = %s" in compiled
    assert "prediction_results.algorithm_version = %s" in compiled
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_empty_queries_return_empty_or_none() -> None:
    session = make_session()
    session.scalar.return_value = None
    session.scalars.return_value.all.return_value = []
    repository = PredictionRepository(session)

    assert repository.get_latest_prediction(
        drama_id=DRAMA_ID,
        metric_type=METRIC_TYPE,
        algorithm_version=ALGORITHM_VERSION,
    ) is None
    assert repository.get_predictions_by_drama(
        drama_id=DRAMA_ID,
        metric_type=METRIC_TYPE,
        algorithm_version=ALGORITHM_VERSION,
        limit=20,
    ) == []
    assert repository.get_prediction_range(
        drama_id=DRAMA_ID,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
    ) == []


def test_duplicate_identity_is_enforced_by_v010_unique_constraint() -> None:
    identity = next(
        constraint
        for constraint in inspect(PredictionResult).local_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_prediction_results_identity"
    )

    assert tuple(identity.columns.keys()) == (
        "drama_id",
        "metric_type",
        "target_date",
        "algorithm_version",
    )


def test_repository_propagates_flush_errors_without_rollback() -> None:
    session = make_session()
    session.flush.side_effect = IntegrityError(
        "INSERT", {}, RuntimeError("duplicate prediction")
    )

    with pytest.raises(IntegrityError):
        PredictionRepository(session).save_prediction(prediction_values())

    session.commit.assert_not_called()
    session.rollback.assert_not_called()
