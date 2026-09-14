"""ScoreService orchestration, delegation, and atomic transaction tests."""

from datetime import UTC, date, datetime, timedelta
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from analytics.heat import HeatScore
from analytics.metrics import EngagementMetrics, MetricResult, RawMetrics
from repositories.base import Page
from repositories.drama_repository import DramaRepository
from repositories.import_repository import OperationLogRepository
from repositories.score_repository import ScoreRepository
from services.analytics_service import AnalyticsService
from services.exceptions import PersistenceException
from services.score_service import (
    COMPOSITE_SCORE_VERSION,
    SCORE_SCOPE_ID,
    SCORE_SCOPE_TYPE,
    ScoreService,
)

SCORE_DATE = date(2026, 9, 14)
NOW = datetime(2026, 9, 14, 12, 30, tzinfo=UTC)


def _metric(
    drama_id: int,
    *,
    snapshot: bool = True,
    play_count: int | None = 1000,
    like_count: int | None = 100,
    growth_7d: float | None = 0.2,
    engagement_rate: float | None = 0.12,
    insufficient_history: bool = False,
    quality_status: str | None = "VALID",
    excluded_error_count: int = 0,
) -> MetricResult:
    raw = RawMetrics(
        play_count=play_count,
        like_count=like_count,
        comment_count=10,
        favorite_count=5,
        share_count=5,
    )
    return MetricResult(
        object_key=drama_id,
        drama_id=drama_id,
        drama_code=f"DRM{drama_id:04d}",
        granularity="DRAMA_OVERALL",
        snapshot_time=datetime(2026, 9, 14, 3) if snapshot else None,
        raw=raw,
        engagement=EngagementMetrics(
            like_rate=None,
            comment_rate=None,
            favorite_rate=None,
            share_rate=None,
            engagement_rate=engagement_rate,
            quality_engagement=None,
        ),
        adjacent_growth=None,
        growth_24h=None,
        growth_7d=growth_7d,
        growth_30d=None,
        freshness="FRESH",
        quality_status=quality_status,
        warning_count=0,
        excluded_error_count=excluded_error_count,
        insufficient_history=insufficient_history,
        included_platform_count=1,
        drama_name=f"Drama {drama_id}",
    )


def _heat(metrics: list[MetricResult]) -> dict[int, HeatScore]:
    count = len(metrics)
    return {
        metric.object_key: HeatScore(
            object_key=metric.object_key,
            score=float(20 + metric.drama_id % 80),
            rank=index,
            candidate_count=count,
        )
        for index, metric in enumerate(metrics, start=1)
        if metric.raw.heat_complete
    }


def _service() -> tuple[
    ScoreService,
    Session,
    MagicMock,
    ScoreRepository,
    DramaRepository,
    OperationLogRepository,
]:
    session = create_autospec(Session, instance=True)
    analytics = MagicMock(spec=AnalyticsService)
    scores = ScoreRepository(session)
    dramas = DramaRepository(session)
    operation_logs = OperationLogRepository(session)
    scores.replace_scope_scores = MagicMock(return_value=[])
    scores.paginate_ranking = MagicMock()
    scores.get_latest_by_drama = MagicMock()
    scores.get_level_distribution = MagicMock()
    dramas.get_by_id = MagicMock(
        side_effect=lambda drama_id: SimpleNamespace(
            drama_id=drama_id,
            premiere_date=SCORE_DATE - timedelta(days=20),
            platform_relations=[],
        )
    )
    operation_logs.create = MagicMock()
    return (
        ScoreService(session, analytics, scores, dramas, operation_logs),
        session,
        analytics,
        scores,
        dramas,
        operation_logs,
    )


def test_calculate_scores_runs_complete_pipeline_once() -> None:
    service, session, analytics, scores, _, operation_logs = _service()
    metrics = [
        _metric(1, growth_7d=0.1, engagement_rate=0.1),
        _metric(2, growth_7d=0.3, engagement_rate=0.2),
    ]
    analytics.get_rankings.return_value = (metrics, _heat(metrics), {})

    from analytics.composite_score import calculate_composite_score as real_calculator

    with patch(
        "services.score_service.calculate_composite_score",
        wraps=real_calculator,
    ) as calculator:
        result = service.calculate_scores(
            SCORE_DATE,
            administrator_id=7,
            now=NOW,
            request_id="request-1",
        )

    assert result.calculated_count == 2
    assert result.skipped_count == 0
    assert result.skipped_reasons == {}
    analytics.get_rankings.assert_called_once()
    context = analytics.get_rankings.call_args.args[0]
    assert context.granularity == "DRAMA_OVERALL"
    assert context.time_window == "7D"
    assert calculator.call_count == 2
    call = scores.replace_scope_scores.call_args.kwargs
    assert call["score_date"] == SCORE_DATE
    assert call["algorithm_version"] == COMPOSITE_SCORE_VERSION
    assert call["score_scope_type"] == SCORE_SCOPE_TYPE
    assert call["score_scope_id"] == SCORE_SCOPE_ID
    assert len(call["scores"]) == 2
    assert set(call["scores"][0]) == {
        "drama_id",
        "analysis_as_of",
        "heat_score",
        "growth_score",
        "engagement_score",
        "lifecycle_score",
        "total_score",
        "level",
    }
    operation_logs.create.assert_called_once()
    audit = operation_logs.create.call_args.args[0]
    assert audit["actor_user_id"] == 7
    assert audit["target_user_id"] == 7
    assert audit["operation_type"] == "SCORE_CALCULATE"
    assert audit["request_id"] == "request-1"
    detail = json.loads(audit["summary"])
    assert detail["success_count"] == 2
    assert detail["failed_count"] == 0
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_empty_analytics_result_replaces_scope_with_empty_collection() -> None:
    service, session, analytics, scores, dramas, operation_logs = _service()
    analytics.get_rankings.return_value = ([], {}, {})

    result = service.calculate_scores(SCORE_DATE, administrator_id=7, now=NOW)

    assert result.calculated_count == 0
    assert result.skipped_count == 0
    assert scores.replace_scope_scores.call_args.kwargs["scores"] == []
    dramas.get_by_id.assert_not_called()
    operation_logs.create.assert_called_once()
    session.commit.assert_called_once_with()


def test_partial_failures_return_counts_and_stable_reasons() -> None:
    service, _, analytics, scores, dramas, operation_logs = _service()
    valid = [
        _metric(
            index,
            growth_7d=index / 100,
            engagement_rate=index / 1000,
        )
        for index in range(1, 91)
    ]
    invalid = [
        _metric(91, snapshot=False),
        _metric(92, snapshot=False),
        _metric(93, like_count=None),
        _metric(94, like_count=None),
        _metric(95, play_count=0),
        _metric(96, play_count=0),
        _metric(97, growth_7d=None, insufficient_history=True),
        _metric(98, growth_7d=None, insufficient_history=True),
        _metric(99, quality_status="ERROR"),
        _metric(100, quality_status="ERROR"),
    ]
    metrics = valid + invalid
    analytics.get_rankings.return_value = (metrics, _heat(metrics), {})

    result = service.calculate_scores(SCORE_DATE, administrator_id=7, now=NOW)

    assert result.calculated_count == 90
    assert result.skipped_count == 10
    assert result.skipped_reasons == {
        "DATA_QUALITY_ERROR": 2,
        "INCOMPLETE_METRICS": 2,
        "INSUFFICIENT_HISTORY": 2,
        "NO_VALID_SNAPSHOT": 2,
        "ZERO_PLAY_COUNT": 2,
    }
    assert len(scores.replace_scope_scores.call_args.kwargs["scores"]) == 90
    assert dramas.get_by_id.call_count == 90
    detail = json.loads(operation_logs.create.call_args.args[0]["summary"])
    assert detail["success_count"] == 90
    assert detail["failed_count"] == 10
    assert detail["skipped_reasons"] == result.skipped_reasons


def test_repeated_calculation_uses_replace_instead_of_creating_duplicates() -> None:
    service, session, analytics, scores, _, _ = _service()
    metrics = [_metric(1)]
    analytics.get_rankings.return_value = (metrics, _heat(metrics), {})

    service.calculate_scores(SCORE_DATE, administrator_id=7, now=NOW)
    service.calculate_scores(SCORE_DATE, administrator_id=7, now=NOW)

    assert scores.replace_scope_scores.call_count == 2
    for call in scores.replace_scope_scores.call_args_list:
        assert call.kwargs["score_date"] == SCORE_DATE
        assert call.kwargs["algorithm_version"] == COMPOSITE_SCORE_VERSION
        assert call.kwargs["score_scope_type"] == "ALL"
        assert call.kwargs["score_scope_id"] == 0
    assert session.commit.call_count == 2


def test_repository_failure_rolls_back_and_does_not_write_log() -> None:
    service, session, analytics, scores, _, operation_logs = _service()
    metrics = [_metric(1)]
    analytics.get_rankings.return_value = (metrics, _heat(metrics), {})
    scores.replace_scope_scores.side_effect = SQLAlchemyError("write failed")

    with pytest.raises(PersistenceException):
        service.calculate_scores(SCORE_DATE, administrator_id=7, now=NOW)

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()
    operation_logs.create.assert_not_called()


def test_analytics_failure_is_propagated_and_transaction_rolls_back() -> None:
    service, session, analytics, scores, _, operation_logs = _service()
    expected = RuntimeError("analytics unavailable")
    analytics.get_rankings.side_effect = expected

    with pytest.raises(RuntimeError) as raised:
        service.calculate_scores(SCORE_DATE, administrator_id=7, now=NOW)

    assert raised.value is expected
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()
    scores.replace_scope_scores.assert_not_called()
    operation_logs.create.assert_not_called()


def test_operation_log_failure_rolls_back_score_replacement() -> None:
    service, session, analytics, scores, _, operation_logs = _service()
    metrics = [_metric(1)]
    analytics.get_rankings.return_value = (metrics, _heat(metrics), {})
    operation_logs.create.side_effect = SQLAlchemyError("audit failed")

    with pytest.raises(PersistenceException):
        service.calculate_scores(SCORE_DATE, administrator_id=7, now=NOW)

    scores.replace_scope_scores.assert_called_once()
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_historical_score_uses_local_end_of_day_as_utc_cutoff() -> None:
    service, _, analytics, _, _, _ = _service()
    analytics.get_rankings.return_value = ([], {}, {})

    result = service.calculate_scores(
        date(2026, 9, 13),
        administrator_id=7,
        now=NOW,
    )

    assert result.analysis_as_of == datetime(2026, 9, 13, 15, 59, 59, 999999)


def test_missing_release_date_is_skipped() -> None:
    service, _, analytics, scores, dramas, _ = _service()
    metrics = [_metric(1)]
    analytics.get_rankings.return_value = (metrics, _heat(metrics), {})
    dramas.get_by_id.side_effect = None
    dramas.get_by_id.return_value = SimpleNamespace(
        premiere_date=None,
        platform_relations=[],
    )

    result = service.calculate_scores(SCORE_DATE, administrator_id=7, now=NOW)

    assert result.skipped_reasons == {"MISSING_RELEASE_DATE": 1}
    assert scores.replace_scope_scores.call_args.kwargs["scores"] == []


def test_future_release_date_is_reported_as_data_quality_error() -> None:
    service, _, analytics, scores, dramas, _ = _service()
    metrics = [_metric(1)]
    analytics.get_rankings.return_value = (metrics, _heat(metrics), {})
    dramas.get_by_id.side_effect = None
    dramas.get_by_id.return_value = SimpleNamespace(
        premiere_date=SCORE_DATE + timedelta(days=1),
        platform_relations=[],
    )

    result = service.calculate_scores(SCORE_DATE, administrator_id=7, now=NOW)

    assert result.skipped_reasons == {"DATA_QUALITY_ERROR": 1}
    assert scores.replace_scope_scores.call_args.kwargs["scores"] == []


def test_query_methods_delegate_without_sorting_or_recalculation() -> None:
    service, _, analytics, scores, dramas, _ = _service()
    page = Page(page=2, page_size=10, total=1, items=[SimpleNamespace(score_id=1)])
    latest = SimpleNamespace(score_id=2)
    distribution = {"S": 1, "A": 2, "B": 3, "C": 4}
    scores.paginate_ranking.return_value = page
    scores.get_latest_by_drama.return_value = latest
    scores.get_level_distribution.return_value = distribution

    assert service.get_ranking(SCORE_DATE, page=2, page_size=10, level="A") is page
    assert service.get_drama_score(11) is latest
    assert service.get_level_distribution(SCORE_DATE) is distribution

    assert scores.paginate_ranking.call_args.kwargs == {
        "score_date": SCORE_DATE,
        "algorithm_version": COMPOSITE_SCORE_VERSION,
        "score_scope_type": SCORE_SCOPE_TYPE,
        "score_scope_id": SCORE_SCOPE_ID,
        "page": 2,
        "page_size": 10,
        "level": "A",
    }
    analytics.get_rankings.assert_not_called()
    dramas.get_by_id.assert_not_called()
