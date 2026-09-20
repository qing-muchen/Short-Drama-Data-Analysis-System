"""Service-layer tests for Phase 4 anomaly orchestration."""

from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.orm import Session

from analytics.anomaly_detection import (
    AnomalyDetectionResult,
    AnomalyFinding,
)
from repositories.anomaly_repository import AnomalyRepository
from repositories.import_repository import OperationLogRepository
from services.anomaly_service import (
    ANOMALY_HISTORY_WINDOW,
    DATA_QUALITY_BLOCKED,
    INSUFFICIENT_HISTORY,
    NOT_APPLICABLE,
    AnomalyObservation,
    AnomalyService,
)
from services.exceptions import NotFoundException, ValidationException


ANALYSIS_AS_OF = datetime(2026, 9, 19, 12, 0)


def make_observations(
    *,
    drama_id: int = 7,
    error_count: int = 0,
    warning_count: int = 0,
    start: date = date(2026, 9, 11),
) -> list[AnomalyObservation]:
    return [
        AnomalyObservation(
            drama_id=drama_id,
            observation_date=start + timedelta(days=index),
            changed_at=datetime(2026, 9, 19, 10),
            platform_id=1,
            play_count=100 + index,
            like_count=10,
            comment_count=5,
            favorite_count=3,
            share_count=2,
            revision_id=index + 1,
            error_count=error_count,
            warning_count=warning_count,
        )
        for index in range(ANOMALY_HISTORY_WINDOW)
    ]


def make_finding(*, drama_id: int = 7) -> AnomalyFinding:
    return AnomalyFinding(
        drama_id=drama_id,
        metric_type="PLAY_COUNT",
        anomaly_type="PLAY_COUNT_GROWTH_ANOMALY",
        severity="C",
        analysis_as_of=ANALYSIS_AS_OF,
        baseline_value=Decimal("1"),
        actual_value=Decimal("3"),
        deviation_value=Decimal("2"),
        evidence_summary="current_value=3; baseline_mean=1; z_score=2",
    )


def make_service(
    *,
    history: list[AnomalyObservation] | None = None,
    detector: object | None = None,
) -> tuple[
    AnomalyService,
    Session,
    MagicMock,
    AnomalyRepository,
    OperationLogRepository,
    object,
]:
    session = create_autospec(Session, instance=True)
    history_provider = MagicMock()
    history_provider.get_anomaly_history.return_value = history or []
    anomalies = AnomalyRepository(session)
    anomalies.save_anomalies = MagicMock(return_value=[])
    anomalies.get_anomalies = MagicMock(return_value="page")
    anomalies.get_by_drama = MagicMock(return_value=["drama-anomaly"])
    anomalies.get_latest_anomalies = MagicMock(return_value=["latest"])
    anomalies.get_statistics = MagicMock(return_value={"total_count": 1})
    anomalies.update_status = MagicMock(
        return_value=SimpleNamespace(anomaly_id=9, drama_id=7, status="RESOLVED")
    )
    operation_logs = OperationLogRepository(session)
    operation_logs.create = MagicMock()

    detector = detector or make_normal_detector()
    service = AnomalyService(
        session,
        history_provider,
        anomalies,
        operation_logs,
        detector=detector,
    )
    return service, session, history_provider, anomalies, operation_logs, detector


def make_normal_detector() -> SimpleNamespace:
    normal = AnomalyDetectionResult(status="NORMAL")
    return SimpleNamespace(
        play_count_growth=MagicMock(return_value=normal),
        play_count_drop=MagicMock(return_value=normal),
        engagement_rate=MagicMock(return_value=normal),
        data_spike=MagicMock(return_value=normal),
    )


def test_normal_detection_prepares_history_calls_detector_saves_and_audits() -> None:
    detector = make_normal_detector()
    detector.play_count_growth.return_value = AnomalyDetectionResult(
        status="ANOMALY",
        finding=make_finding(),
    )
    service, session, history, anomalies, logs, detector = make_service(
        history=make_observations(),
        detector=detector,
    )

    result = service.detect_anomalies(
        analysis_as_of=ANALYSIS_AS_OF,
        operator_user_id=3,
        request_id="anomaly-request",
    )

    assert result.detected_count == 1
    assert result.skipped_count == 0
    assert result.algorithm_version == "Rule-based Detection V1.0"
    history.get_anomaly_history.assert_called_once_with(
        analysis_as_of=ANALYSIS_AS_OF,
    )
    detector.play_count_growth.assert_called_once()
    growth_kwargs = detector.play_count_growth.call_args.kwargs
    assert len(growth_kwargs["historical_growth"]) == 7
    assert growth_kwargs["current_growth"] == 1
    anomalies.save_anomalies.assert_called_once_with([make_finding()])
    audit = logs.create.call_args.args[0]
    assert audit["actor_user_id"] == 3
    assert audit["target_user_id"] == 3
    assert audit["operation_type"] == "ANOMALY_DETECT"
    assert '"detected_count":1' in audit["summary"]
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_no_anomaly_result_still_flushes_empty_batch_and_audits() -> None:
    service, session, _, anomalies, logs, _ = make_service(
        history=make_observations()
    )

    result = service.detect_anomalies(
        analysis_as_of=ANALYSIS_AS_OF,
        operator_user_id=3,
    )

    assert result.detected_count == 0
    anomalies.save_anomalies.assert_called_once_with([])
    assert logs.create.call_count == 1
    session.commit.assert_called_once_with()


def test_no_history_is_reported_and_does_not_call_detector() -> None:
    service, session, _, anomalies, _, detector = make_service(history=[])

    result = service.detect_anomalies(
        analysis_as_of=ANALYSIS_AS_OF,
        operator_user_id=3,
    )

    assert result.skip_reasons == {"NO_HISTORY": 1}
    detector.play_count_growth.assert_not_called()
    anomalies.save_anomalies.assert_called_once_with([])
    session.commit.assert_called_once_with()


def test_revision_as_of_cutoff_selects_latest_visible_revision() -> None:
    history = make_observations()
    history.append(replace(
        history[0],
        changed_at=datetime(2026, 9, 20),
        play_count=999,
        revision_id=99,
    ))
    detector = make_normal_detector()
    service, _, _, _, _, detector = make_service(
        history=history,
        detector=detector,
    )

    service.detect_anomalies(analysis_as_of=ANALYSIS_AS_OF, operator_user_id=3)

    assert detector.data_spike.call_args_list[0].kwargs["current_value"] == 108


def test_error_quality_blocks_detection_but_warning_continues() -> None:
    detector = make_normal_detector()
    blocked, _, _, blocked_repo, _, blocked_detector = make_service(
        history=make_observations(error_count=1),
        detector=detector,
    )
    blocked_result = blocked.detect_anomalies(
        analysis_as_of=ANALYSIS_AS_OF,
        operator_user_id=3,
    )
    assert blocked_result.skip_reasons == {DATA_QUALITY_BLOCKED: 1}
    blocked_detector.play_count_growth.assert_not_called()
    blocked_repo.save_anomalies.assert_called_once_with([])

    warning_service, _, _, _, _, warning_detector = make_service(
        history=make_observations(warning_count=1),
        detector=detector,
    )
    warning_service.detect_anomalies(
        analysis_as_of=ANALYSIS_AS_OF,
        operator_user_id=3,
    )
    warning_detector.play_count_growth.assert_called_once()


def test_decreasing_cumulative_play_count_is_quality_blocked() -> None:
    history = make_observations()
    history[-1] = replace(history[-1], play_count=50)
    service, _, _, anomalies, _, detector = make_service(history=history)

    result = service.detect_anomalies(
        analysis_as_of=ANALYSIS_AS_OF,
        operator_user_id=3,
    )

    assert result.skip_reasons == {DATA_QUALITY_BLOCKED: 1}
    detector.play_count_growth.assert_not_called()
    anomalies.save_anomalies.assert_called_once_with([])


def test_insufficient_history_returns_skip_reason_without_detector_call() -> None:
    service, session, _, anomalies, _, detector = make_service(
        history=make_observations()[:8]
    )

    result = service.detect_anomalies(
        analysis_as_of=ANALYSIS_AS_OF,
        operator_user_id=3,
    )

    assert result.skip_reasons == {INSUFFICIENT_HISTORY: 1}
    detector.play_count_growth.assert_not_called()
    anomalies.save_anomalies.assert_called_once_with([])
    session.commit.assert_called_once_with()


@pytest.mark.parametrize("failure", [RuntimeError("calculator"), ValueError("calculator")])
def test_calculator_failure_rolls_back_and_does_not_save(
    failure: Exception,
) -> None:
    detector = make_normal_detector()
    detector.play_count_growth.side_effect = failure
    service, session, _, anomalies, logs, _ = make_service(
        history=make_observations(),
        detector=detector,
    )

    with pytest.raises(type(failure)):
        service.detect_anomalies(analysis_as_of=ANALYSIS_AS_OF, operator_user_id=3)

    anomalies.save_anomalies.assert_not_called()
    logs.create.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_repository_failure_rolls_back_and_operation_log_is_not_written() -> None:
    service, session, _, anomalies, logs, _ = make_service(
        history=make_observations()
    )
    anomalies.save_anomalies.side_effect = RuntimeError("repository")

    with pytest.raises(RuntimeError, match="repository"):
        service.detect_anomalies(analysis_as_of=ANALYSIS_AS_OF, operator_user_id=3)

    logs.create.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_operation_log_failure_rolls_back_after_anomaly_save() -> None:
    service, session, _, anomalies, logs, _ = make_service(
        history=make_observations()
    )
    logs.create.side_effect = RuntimeError("operation log")

    with pytest.raises(RuntimeError, match="operation log"):
        service.detect_anomalies(analysis_as_of=ANALYSIS_AS_OF, operator_user_id=3)

    anomalies.save_anomalies.assert_called_once_with([])
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_multiple_dramas_are_saved_as_one_batch() -> None:
    detector = make_normal_detector()
    detector.play_count_growth.side_effect = [
        AnomalyDetectionResult(status="ANOMALY", finding=make_finding(drama_id=7)),
        AnomalyDetectionResult(status="ANOMALY", finding=make_finding(drama_id=8)),
    ]
    history = make_observations(drama_id=7) + make_observations(drama_id=8)
    service, _, _, anomalies, _, _ = make_service(
        history=history,
        detector=detector,
    )

    result = service.detect_anomalies(analysis_as_of=ANALYSIS_AS_OF, operator_user_id=3)

    assert result.detected_count == 2
    saved = anomalies.save_anomalies.call_args.args[0]
    assert [finding.drama_id for finding in saved] == [7, 8]


def test_query_methods_delegate_without_reordering_or_recalculation() -> None:
    service, _, _, anomalies, _, _ = make_service()

    assert service.get_anomalies(page=2, page_size=10, severity="A") == "page"
    assert service.get_drama_anomalies(7, limit=5) == ["drama-anomaly"]
    assert service.get_latest_anomalies() == ["latest"]
    assert service.get_statistics() == {"total_count": 1}
    anomalies.get_anomalies.assert_called_once_with(page=2, page_size=10, severity="A")
    anomalies.get_by_drama.assert_called_once_with(drama_id=7, limit=5)


def test_status_update_writes_operation_log_and_commits_once() -> None:
    service, session, _, anomalies, logs, _ = make_service()

    entity = service.update_status(
        9,
        "RESOLVED",
        operator_user_id=3,
        request_id="status-request",
    )

    assert entity.status == "RESOLVED"
    anomalies.update_status.assert_called_once_with(
        anomaly_id=9,
        new_status="RESOLVED",
    )
    values = logs.create.call_args.args[0]
    assert values["operation_type"] == "ANOMALY_STATUS_UPDATE"
    assert values["actor_user_id"] == 3
    assert values["target_drama_id"] == 7
    assert values["request_id"] == "status-request"
    session.commit.assert_called_once_with()


def test_status_update_invalid_or_missing_rolls_back() -> None:
    service, session, _, anomalies, logs, _ = make_service()

    with pytest.raises(ValidationException):
        service.update_status(9, "UNKNOWN", operator_user_id=3)
    session.rollback.assert_not_called()

    anomalies.update_status.return_value = None
    with pytest.raises(NotFoundException):
        service.update_status(99, "RESOLVED", operator_user_id=3)
    logs.create.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()
