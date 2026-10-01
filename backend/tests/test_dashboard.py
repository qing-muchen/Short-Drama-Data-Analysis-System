"""Dashboard Service and Router tests using isolated Analytics doubles."""

import asyncio
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from analytics.context import AnalysisContext
from analytics.heat import HeatScore
from analytics.metrics import MetricResult, RawMetrics, calculate_engagement
from analytics.potential import PotentialScore
from auth.dependencies import get_current_user
from dashboard.service import (
    DashboardOverview,
    DashboardRanking,
    DashboardService,
    DashboardTagDistribution,
)
from main import app
from repositories.dashboard_repository import (
    DashboardCounts,
    DashboardRepository,
    DashboardTagCount,
)
from routers.dependencies import get_dashboard_service

AS_OF = datetime(2026, 9, 8, 4, 0, 0)


def _metric(
    drama_id: int,
    name: str,
    play_count: int,
    growth_7d: float,
    *,
    warning_count: int = 0,
    excluded_error_count: int = 0,
) -> MetricResult:
    raw = RawMetrics(play_count, play_count // 10, play_count // 20, play_count // 25, play_count // 50)
    return MetricResult(
        object_key=drama_id,
        drama_id=drama_id,
        drama_code=f"DRM{drama_id:06d}",
        granularity="DRAMA_OVERALL",
        snapshot_time=AS_OF,
        raw=raw,
        engagement=calculate_engagement(raw),
        adjacent_growth=growth_7d,
        growth_24h=growth_7d,
        growth_7d=growth_7d,
        growth_30d=growth_7d,
        freshness="FRESH",
        quality_status="WARNING" if warning_count else "ERROR" if excluded_error_count else "NORMAL",
        warning_count=warning_count,
        excluded_error_count=excluded_error_count,
        insufficient_history=False,
        included_platform_count=2,
        drama_name=name,
    )


def _context() -> AnalysisContext:
    return AnalysisContext(analysis_as_of=AS_OF, time_window="30D")


def test_dashboard_service_composes_analytics_without_recomputing_scores() -> None:
    session = create_autospec(Session, instance=True)
    repository = DashboardRepository(session)
    repository.get_counts = MagicMock(
        return_value=DashboardCounts(2, 4, 3, 2, 2, 5)
    )
    repository.get_tag_distribution = MagicMock(
        return_value=[DashboardTagCount("都市", 1, 2)]
    )
    metrics = [
        _metric(1, "Drama One", 1000, 0.3, warning_count=1),
        _metric(2, "Drama Two", 500, 0.1, excluded_error_count=1),
    ]
    analytics = MagicMock()
    analytics.get_metrics.return_value = metrics
    analytics.get_rankings.return_value = (
        metrics,
        {1: HeatScore(1, 90.0, 1, 2)},
        {1: PotentialScore(1, 80.0, 1, 1)},
    )
    analytics.get_trend.return_value = [
        {"date": date(2026, 9, 7), "play_count": 900, "engagement_rate": 0.2}
    ]
    service = DashboardService(session, repository, analytics)

    overview = service.overview(_context())
    assert overview.drama_count == 2
    assert overview.total_play_count == 1500
    assert overview.quality_issue_count == 2
    assert overview.average_engagement_rate is not None

    heat = service.heat_ranking(_context(), 10)
    growth = service.growth_ranking(_context(), 10)
    potential = service.potential_ranking(_context(), 10)
    assert heat[0].drama_name == "Drama One"
    assert growth[0].drama_id == 1
    assert potential[0].potential_score == 80.0
    analytics.get_rankings.assert_called()
    assert service.trend(_context())[0]["play_count"] == 900
    tags = service.tag_distribution(10)
    assert tags == [DashboardTagDistribution("都市", 1, 50.0)]
    repository.get_tag_distribution.assert_called_once_with(10)


class FakeDashboardService:
    def overview(self, context: AnalysisContext) -> DashboardOverview:
        return DashboardOverview(AS_OF, 2, 4, 3, 2, 2, 5, 1500, 0.2, 1)

    def heat_ranking(self, context: AnalysisContext, limit: int) -> list[DashboardRanking]:
        return [DashboardRanking(1, "Drama One", 2, heat_score=90.0)]

    def growth_ranking(self, context: AnalysisContext, limit: int) -> list[DashboardRanking]:
        return [DashboardRanking(1, "Drama One", 2, growth_rate=0.3, current_play_count=1000, growth_7d=0.3)]

    def potential_ranking(self, context: AnalysisContext, limit: int) -> list[DashboardRanking]:
        return [DashboardRanking(1, "Drama One", 2, potential_score=80.0, growth_7d=0.3)]

    def trend(self, context: AnalysisContext) -> list[dict[str, object]]:
        return [{"date": date(2026, 9, 7), "play_count": 900, "engagement_rate": 0.2}]

    def quality(self, context: AnalysisContext) -> dict[str, object]:
        return {
            "analysis_as_of": AS_OF,
            "quality_issue_count": 1,
            "warning_count": 1,
            "error_count": 0,
            "freshness_summary": {"fresh": 2, "stale": 0, "unknown": 0},
        }

    def tag_distribution(self, limit: int) -> list[DashboardTagDistribution]:
        return [DashboardTagDistribution("都市", 1, 50.0)][:limit]


def _request(method: str, path: str) -> tuple[int, dict[str, object]]:
    async def perform() -> tuple[int, dict[str, object]]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.request(method, path)
            return response.status_code, response.json()

    return asyncio.run(perform())


def test_dashboard_routes_are_authenticated_and_use_response_schemas() -> None:
    app.dependency_overrides[get_dashboard_service] = FakeDashboardService
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role_code="USER", status="ACTIVE"
    )
    try:
        paths = (
            "/api/v1/dashboard/overview",
            "/api/v1/dashboard/rankings/heat?limit=3",
            "/api/v1/dashboard/rankings/growth?limit=3",
            "/api/v1/dashboard/rankings/potential?limit=3",
            "/api/v1/dashboard/trend",
            "/api/v1/dashboard/quality",
            "/api/v1/dashboard/tags",
        )
        responses = [_request("GET", path) for path in paths]
    finally:
        app.dependency_overrides.clear()

    assert all(status == 200 for status, _ in responses)
    assert responses[0][1]["data"]["total_play_count"] == 1500
    assert responses[1][1]["data"][0]["heat_score"] == 90.0
    assert responses[4][1]["data"][0]["play_count"] == 900
    assert responses[5][1]["data"]["warning_count"] == 1
    assert responses[6][1]["data"][0] == {
        "tag_name": "都市",
        "drama_count": 1,
        "percentage": 50.0,
    }
