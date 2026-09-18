"""Service-layer tests for as-of prediction orchestration."""

from datetime import date, datetime
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from analytics.prediction import (
    PREDICTION_ALGORITHM_VERSION,
    CumulativePlayCountPoint,
    PredictionCalculationError,
    PredictionCalculationResult,
)
from repositories.import_repository import OperationLogRepository
from repositories.prediction_repository import PredictionRepository
from services.exceptions import PersistenceException
from services.prediction_service import (
    DATE_GAP,
    INSUFFICIENT_HISTORY,
    INVALID_METRIC,
    INVALID_REVISION,
    NO_HISTORY,
    PredictionObservation,
    PredictionService,
)

ANALYSIS_AS_OF = datetime(2026, 9, 16, 12, 0)
DRAMA_ID = 7


def make_points() -> list[CumulativePlayCountPoint]:
    return [
        CumulativePlayCountPoint(date(2026, 9, 9 + index), 100 + index * 10)
        for index in range(8)
    ]


def make_observations() -> list[PredictionObservation]:
    return [
        PredictionObservation(
            observation_date=point.observation_date,
            platform_id=1,
            play_count=int(point.play_count),
            changed_at=datetime(2026, 9, 15, 12),
            revision_id=index + 1,
        )
        for index, point in enumerate(make_points())
    ]


def make_service(
    *,
    history: list[PredictionObservation | CumulativePlayCountPoint] | None = None,
    calculator: MagicMock | None = None,
) -> tuple[PredictionService, Session, MagicMock, PredictionRepository, OperationLogRepository]:
    session = create_autospec(Session, instance=True)
    history_provider = MagicMock()
    history_provider.get_prediction_history.return_value = history or []
    predictions = PredictionRepository(session)
    predictions.replace_prediction = MagicMock(
        return_value=SimpleNamespace(prediction_id=11)
    )
    operation_logs = OperationLogRepository(session)
    operation_logs.create = MagicMock()
    service = PredictionService(
        session,
        history_provider,
        predictions,
        operation_logs,
        calculator=calculator or MagicMock(
            return_value=PredictionCalculationResult(
                prediction_date=date(2026, 9, 16),
                target_date=date(2026, 9, 17),
                predicted_value=Decimal("190.00"),
                predicted_increment=Decimal("10.00"),
            )
        ),
    )
    return service, session, history_provider, predictions, operation_logs


def test_normal_prediction_builds_window_calls_calculator_repository_and_log() -> None:
    calculator = MagicMock(
        return_value=PredictionCalculationResult(
            prediction_date=date(2026, 9, 16),
            target_date=date(2026, 9, 17),
            predicted_value=Decimal("190.00"),
            predicted_increment=Decimal("10.00"),
        )
    )
    service, session, history, predictions, operation_logs = make_service(
        history=make_observations(), calculator=calculator
    )

    result = service.calculate_prediction(
        DRAMA_ID,
        analysis_as_of=ANALYSIS_AS_OF,
        administrator_id=3,
        request_id="prediction-request",
    )

    assert result.predicted_count == 1
    assert result.skipped_count == 0
    history.get_prediction_history.assert_called_once_with(
        drama_id=DRAMA_ID,
        analysis_as_of=ANALYSIS_AS_OF,
    )
    calculator.assert_called_once()
    calculator_points = calculator.call_args.args[0]
    assert [point.play_count for point in calculator_points] == [100, 110, 120, 130, 140, 150, 160, 170]
    predictions.replace_prediction.assert_called_once()
    values = predictions.replace_prediction.call_args.args[0]
    assert values["drama_id"] == DRAMA_ID
    assert values["metric_type"] == "PLAY_COUNT"
    assert values["algorithm_version"] == PREDICTION_ALGORITHM_VERSION
    assert values["analysis_as_of"] == ANALYSIS_AS_OF
    operation_logs.create.assert_called_once()
    audit = operation_logs.create.call_args.args[0]
    assert audit["actor_user_id"] == 3
    assert audit["target_drama_id"] == DRAMA_ID
    assert audit["operation_type"] == "PREDICTION_CALCULATE"
    assert json.loads(audit["summary"])["predicted_count"] == 1
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_analysis_as_of_excludes_future_revision_and_uses_latest_eligible_revision() -> None:
    observations = make_observations()
    observations[0] = PredictionObservation(
        observation_date=observations[0].observation_date,
        platform_id=1,
        play_count=999,
        changed_at=datetime(2026, 9, 17),
        revision_id=99,
    )
    observations.insert(
        1,
        PredictionObservation(
            observation_date=date(2026, 9, 9),
            platform_id=1,
            play_count=100,
            changed_at=datetime(2026, 9, 15),
            revision_id=1,
        ),
    )
    calculator = MagicMock(
        return_value=PredictionCalculationResult(
            prediction_date=date(2026, 9, 16),
            target_date=date(2026, 9, 17),
            predicted_value=Decimal("190.00"),
            predicted_increment=Decimal("10.00"),
        )
    )
    service, _, _, _, _ = make_service(history=observations, calculator=calculator)

    service.calculate_prediction(
        DRAMA_ID,
        analysis_as_of=ANALYSIS_AS_OF,
        administrator_id=3,
    )

    assert calculator.call_args.args[0][0].play_count == 100


def test_visible_void_revision_does_not_fall_back_to_older_value() -> None:
    observations = make_observations()
    observations.append(
        PredictionObservation(
            observation_date=observations[0].observation_date,
            platform_id=1,
            play_count=None,
            changed_at=datetime(2026, 9, 16),
            revision_id=99,
            revision_action="VOID",
        )
    )
    service, _, _, predictions, _ = make_service(history=observations)

    result = service.calculate_prediction(
        DRAMA_ID,
        analysis_as_of=ANALYSIS_AS_OF,
        administrator_id=3,
    )

    assert result.skipped_reason == INSUFFICIENT_HISTORY
    predictions.replace_prediction.assert_not_called()


@pytest.mark.parametrize(
    ("history", "reason"),
    [
        ([], NO_HISTORY),
        (make_points()[:7], INSUFFICIENT_HISTORY),
    ],
)
def test_history_shortfalls_are_skipped_without_prediction(
    history: list[CumulativePlayCountPoint], reason: str
) -> None:
    service, session, _, predictions, operation_logs = make_service(history=history)

    result = service.calculate_prediction(
        DRAMA_ID,
        analysis_as_of=ANALYSIS_AS_OF,
        administrator_id=3,
    )

    assert result.prediction is None
    assert result.skipped_reason == reason
    predictions.replace_prediction.assert_not_called()
    detail = json.loads(operation_logs.create.call_args.args[0]["summary"])
    assert detail["skipped_count"] == 1
    session.commit.assert_called_once_with()


def test_date_gap_is_skipped_without_zero_prediction() -> None:
    history = make_points()
    history[4] = CumulativePlayCountPoint(date(2026, 9, 20), 140)
    service, session, _, predictions, _ = make_service(history=history)

    result = service.calculate_prediction(
        DRAMA_ID,
        analysis_as_of=ANALYSIS_AS_OF,
        administrator_id=3,
    )

    assert result.skipped_reason == DATE_GAP
    predictions.replace_prediction.assert_not_called()
    session.commit.assert_called_once_with()


def test_invalid_revision_and_metric_are_skipped() -> None:
    invalid_revision = [
        PredictionObservation(
            observation_date=date(2026, 9, 9),
            platform_id=1,
            play_count=100,
            changed_at=datetime(2026, 9, 17),
        )
    ]
    service, _, _, _, _ = make_service(history=invalid_revision)
    assert service.calculate_prediction(
        DRAMA_ID,
        analysis_as_of=ANALYSIS_AS_OF,
        administrator_id=3,
    ).skipped_reason == INVALID_REVISION

    invalid_metric = make_observations()
    invalid_metric[2] = PredictionObservation(
        observation_date=invalid_metric[2].observation_date,
        platform_id=1,
        play_count=None,
        changed_at=datetime(2026, 9, 15),
    )
    service, _, _, _, _ = make_service(history=invalid_metric)
    assert service.calculate_prediction(
        DRAMA_ID,
        analysis_as_of=ANALYSIS_AS_OF,
        administrator_id=3,
    ).skipped_reason == INVALID_METRIC


def test_calculator_exception_propagates_and_rolls_back() -> None:
    calculator = MagicMock(side_effect=RuntimeError("calculator unavailable"))
    service, session, _, predictions, operation_logs = make_service(
        history=make_observations(), calculator=calculator
    )

    with pytest.raises(RuntimeError, match="calculator unavailable"):
        service.calculate_prediction(
            DRAMA_ID,
            analysis_as_of=ANALYSIS_AS_OF,
            administrator_id=3,
        )

    predictions.replace_prediction.assert_not_called()
    operation_logs.create.assert_not_called()
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_repository_failure_rolls_back_and_does_not_log() -> None:
    service, session, _, predictions, operation_logs = make_service(
        history=make_observations()
    )
    predictions.replace_prediction.side_effect = SQLAlchemyError("write failed")

    with pytest.raises(PersistenceException):
        service.calculate_prediction(
            DRAMA_ID,
            analysis_as_of=ANALYSIS_AS_OF,
            administrator_id=3,
        )

    operation_logs.create.assert_not_called()
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_operation_log_failure_rolls_back_prediction() -> None:
    service, session, _, predictions, operation_logs = make_service(
        history=make_observations()
    )
    operation_logs.create.side_effect = SQLAlchemyError("audit failed")

    with pytest.raises(PersistenceException):
        service.calculate_prediction(
            DRAMA_ID,
            analysis_as_of=ANALYSIS_AS_OF,
            administrator_id=3,
        )

    predictions.replace_prediction.assert_called_once()
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_query_methods_delegate_repository_without_calculation() -> None:
    service, _, _, predictions, _ = make_service()
    latest = SimpleNamespace(prediction_id=1)
    history = [SimpleNamespace(prediction_id=2)]
    predictions.get_latest_prediction = MagicMock(return_value=latest)
    predictions.get_predictions_by_drama = MagicMock(return_value=history)
    predictions.get_prediction_range = MagicMock(return_value=history)

    assert service.get_latest_prediction(DRAMA_ID) is latest
    assert service.get_prediction_history(DRAMA_ID, limit=12) == history
    assert service.get_prediction_range(
        DRAMA_ID,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
    ) == history
    predictions.get_latest_prediction.assert_called_once_with(
        drama_id=DRAMA_ID,
        metric_type="PLAY_COUNT",
        algorithm_version=PREDICTION_ALGORITHM_VERSION,
    )
    predictions.get_predictions_by_drama.assert_called_once()
    predictions.get_prediction_range.assert_called_once()
