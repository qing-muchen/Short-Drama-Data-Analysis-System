"""Deterministic Analytics V1 calculation and API tests with fixed data."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from analytics.constants import HEAT_MODEL_VERSION, POTENTIAL_MODEL_VERSION
from analytics.context import AnalysisContext
from analytics.growth import calculate_platform_growth
from analytics.heat import HeatCandidate, HeatScore, calculate_heat_scores
from analytics.insight import generate_group_insight, generate_insights
from analytics.metrics import (
    MetricResult,
    RawMetrics,
    SnapshotPoint,
    calculate_engagement,
)
from analytics.potential import (
    PotentialCandidate,
    calculate_potential_scores,
)
from auth.dependencies import get_current_user
from main import app
from routers.dependencies import get_analytics_service
from services.analytics_service import AnalyticsSummary

AS_OF = datetime(2026, 9, 8, 4, 0, 0)


def _point(
    *,
    at: datetime,
    play_count: int,
    revision_id: int,
    action: str = "INITIAL",
) -> SnapshotPoint:
    return SnapshotPoint(
        drama_id=1,
        drama_code="DRM000001",
        drama_status="COMPLETED",
        drama_platform_id=10,
        drama_platform_status="ONLINE",
        platform_id=2,
        platform_status="ACTIVE",
        snapshot_id=revision_id,
        snapshot_revision_id=revision_id,
        snapshot_time=at,
        revision_action=action,
        raw=RawMetrics(
            play_count=play_count,
            like_count=play_count // 10,
            comment_count=play_count // 20,
            favorite_count=play_count // 25,
            share_count=play_count // 50,
            ranking=1,
        ),
    )


def _metric(*, growth_7d: float | None = 0.3) -> MetricResult:
    raw = RawMetrics(200, 20, 10, 8, 4)
    return MetricResult(
        object_key=1,
        drama_id=1,
        drama_code="DRM000001",
        granularity="DRAMA_OVERALL",
        snapshot_time=AS_OF,
        raw=raw,
        engagement=calculate_engagement(raw),
        adjacent_growth=0.1,
        growth_24h=0.1,
        growth_7d=growth_7d,
        growth_30d=0.8,
        freshness="FRESH",
        quality_status="NORMAL",
        warning_count=0,
        excluded_error_count=0,
        insufficient_history=growth_7d is None,
        included_platform_count=1,
    )


def test_analysis_context_is_normalized_and_deterministic() -> None:
    aware = AS_OF.replace(tzinfo=UTC)
    first = AnalysisContext(
        analysis_as_of=aware,
        platform_scope=(3, 1, 3),
        tag_scope=(9, 4),
    )
    second = AnalysisContext(
        analysis_as_of=AS_OF,
        platform_scope=(1, 3),
        tag_scope=(4, 9),
    )

    assert first == second
    assert first.deterministic_key == second.deterministic_key
    assert first.analysis_as_of.tzinfo is None


def test_growth_uses_latest_valid_baseline_and_zero_returns_null() -> None:
    points = [
        _point(at=AS_OF - timedelta(days=7), play_count=100, revision_id=1),
        _point(at=AS_OF, play_count=200, revision_id=2),
        _point(
            at=AS_OF + timedelta(minutes=1),
            play_count=999,
            revision_id=3,
            action="VOID",
        ),
    ]
    result = calculate_platform_growth(points, AS_OF)
    assert result.adjacent == pytest.approx(1.0)
    assert result.growth_7d == pytest.approx(1.0)
    assert result.growth_24h is None

    zero_baseline = [
        _point(at=AS_OF - timedelta(days=7), play_count=0, revision_id=4),
        _point(at=AS_OF, play_count=10, revision_id=5),
    ]
    assert calculate_platform_growth(zero_baseline, AS_OF).growth_7d is None


def test_heat_model_uses_frozen_weights_and_zero_range_rule() -> None:
    low = HeatCandidate(1, "DRM000001", RawMetrics(0, 0, 0, 0, 0))
    high = HeatCandidate(2, "DRM000002", RawMetrics(10, 10, 10, 10, 10))
    missing = HeatCandidate(3, "DRM000003", RawMetrics(10, None, 10, 10, 10))
    scores = calculate_heat_scores([low, high, missing])

    assert scores[1].score == pytest.approx(0.0)
    assert scores[2].score == pytest.approx(100.0)
    assert scores[2].rank == 1
    assert scores[2].model_version == HEAT_MODEL_VERSION
    assert 3 not in scores

    identical = calculate_heat_scores(
        [
            HeatCandidate(1, "DRM000001", RawMetrics(5, 5, 5, 5, 5)),
            HeatCandidate(2, "DRM000002", RawMetrics(5, 5, 5, 5, 5)),
        ]
    )
    assert {score.score for score in identical.values()} == {0.0}


def test_potential_filters_ineligible_candidates_and_is_not_prediction() -> None:
    candidates = [
        PotentialCandidate(1, "DRM000001", 100, 0.1, 0.1, 0.02, 0.01),
        PotentialCandidate(2, "DRM000002", 100, 0.8, 0.3, 0.08, 0.04),
        PotentialCandidate(3, "DRM000003", 100, None, 0.4, 0.10, 0.05),
    ]
    scores = calculate_potential_scores(candidates)

    assert scores[2].score == pytest.approx(100.0)
    assert scores[2].rank == 1
    assert scores[2].model_version == POTENTIAL_MODEL_VERSION
    assert 3 not in scores


def test_insight_merges_high_heat_and_decline_with_evidence() -> None:
    context = AnalysisContext(analysis_as_of=AS_OF)
    metrics = _metric(growth_7d=-0.2)
    heat = HeatScore(object_key=1, score=95.5, rank=1, candidate_count=10)
    insights = generate_insights(
        metrics=metrics,
        heat=heat,
        potential=None,
        context=context,
    )

    combined = next(
        insight
        for insight in insights
        if insight.rule_code == "PERFORMANCE_HIGH_GROWTH_DECLINE_V1"
    )
    assert combined.evidence["heat_score"] == 95.5
    assert combined.evidence["growth_7d"] == -0.2
    assert "但" in combined.conclusion
    assert not any(
        forbidden in insight.conclusion
        for insight in insights
        for forbidden in ("一定成功", "建议投资", "推荐观看")
    )


def test_platform_and_tag_insight_framework_enforces_group_sample_rule() -> None:
    context = AnalysisContext(analysis_as_of=AS_OF)
    platform = generate_group_insight(
        insight_type="PLATFORM",
        subject_name="平台A",
        metric_name="平均Heat",
        metric_value=76.5,
        sample_size=8,
        context=context,
    )
    small_tag = generate_group_insight(
        insight_type="TAG",
        subject_name="悬疑",
        metric_name="平均Heat",
        metric_value=80.0,
        sample_size=3,
        context=context,
    )

    assert platform.insight_type == "PLATFORM"
    assert platform.evidence["sample_size"] == 8
    assert small_tag.insight_type == "RISK"
    assert "样本较少" in small_tag.conclusion


class FakeAnalyticsService:
    def get_drama_summary(
        self, drama_id: int, context: AnalysisContext
    ) -> AnalyticsSummary:
        metrics = _metric()
        return AnalyticsSummary(
            context=context,
            metrics=metrics,
            heat=HeatScore(1, 88.0, 2, 10),
            potential=None,
            insights=generate_insights(
                metrics=metrics,
                heat=HeatScore(1, 88.0, 2, 10),
                potential=None,
                context=context,
            ),
        )


def _request(path: str) -> tuple[int, dict[str, object]]:
    async def perform() -> tuple[int, dict[str, object]]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(path)
            return response.status_code, response.json()

    return asyncio.run(perform())


def test_analytics_summary_api_is_authenticated_and_schema_bound() -> None:
    app.dependency_overrides[get_analytics_service] = FakeAnalyticsService
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role_code="USER", status="ACTIVE"
    )
    try:
        status_code, body = _request(
            "/api/v1/analytics/dramas/1/summary"
            "?analysis_as_of=2026-09-08T04:00:00Z&time_window=7D"
        )
    finally:
        app.dependency_overrides.clear()

    assert status_code == 200
    data = body["data"]
    assert data["context"]["model_versions"]["heat"] == HEAT_MODEL_VERSION
    assert data["metrics"]["growth_7d"] == pytest.approx(0.3)
    assert data["heat"]["score"] == pytest.approx(88.0)
    assert len(data["insights"]) <= 5
