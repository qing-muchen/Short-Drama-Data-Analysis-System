"""Dashboard aggregation service delegating metrics to AnalyticsService."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from analytics.context import AnalysisContext
from analytics.heat import HeatScore
from analytics.potential import PotentialScore
from repositories.dashboard_repository import DashboardCounts, DashboardRepository
from services.analytics_service import AnalyticsService
from services.base import BaseService


@dataclass(frozen=True, slots=True)
class DashboardOverview:
    analysis_as_of: datetime
    drama_count: int
    actor_count: int
    director_count: int
    company_count: int
    platform_count: int
    tag_count: int
    total_play_count: int
    average_engagement_rate: float | None
    quality_issue_count: int


@dataclass(frozen=True, slots=True)
class DashboardRanking:
    drama_id: int
    drama_name: str
    platform_count: int = 0
    heat_score: float | None = None
    growth_rate: float | None = None
    current_play_count: int | None = None
    potential_score: float | None = None
    growth_7d: float | None = None


@dataclass(frozen=True, slots=True)
class DashboardTagDistribution:
    tag_name: str
    drama_count: int
    percentage: float


class DashboardService(BaseService):
    """Compose Dashboard views; all metric calculations stay in AnalyticsService."""

    def __init__(
        self,
        session: Session,
        dashboard: DashboardRepository,
        analytics: AnalyticsService,
    ) -> None:
        super().__init__(session, dashboard)
        self.dashboard = dashboard
        self.analytics = analytics

    def overview(self, context: AnalysisContext) -> DashboardOverview:
        counts: DashboardCounts = self.read(self.dashboard.get_counts)
        metrics = self.analytics.get_metrics(context)
        quality = AnalyticsService.quality_summary_from_metrics(metrics)
        plays = [metric.raw.play_count for metric in metrics if metric.raw.play_count is not None]
        engagement = [
            metric.engagement.engagement_rate
            for metric in metrics
            if metric.engagement.engagement_rate is not None
        ]
        return DashboardOverview(
            analysis_as_of=context.analysis_as_of,
            drama_count=counts.drama_count,
            actor_count=counts.actor_count,
            director_count=counts.director_count,
            company_count=counts.company_count,
            platform_count=counts.platform_count,
            tag_count=counts.tag_count,
            total_play_count=sum(plays),
            average_engagement_rate=(sum(engagement) / len(engagement) if engagement else None),
            quality_issue_count=int(quality["quality_issue_count"]),
        )

    def heat_ranking(
        self, context: AnalysisContext, limit: int
    ) -> list[DashboardRanking]:
        metrics, heat_scores, _ = self.analytics.get_rankings(context)
        ordered = sorted(
            (metric for metric in metrics if metric.object_key in heat_scores),
            key=lambda metric: heat_scores[metric.object_key].rank,
        )[:limit]
        return [
            self._ranking(metric, heat=heat_scores[metric.object_key])
            for metric in ordered
        ]

    def growth_ranking(
        self, context: AnalysisContext, limit: int
    ) -> list[DashboardRanking]:
        metrics = [metric for metric in self.analytics.get_metrics(context) if metric.growth_7d is not None]
        ordered = sorted(
            metrics,
            key=lambda metric: (-metric.growth_7d, metric.drama_code),
        )[:limit]
        return [self._ranking(metric) for metric in ordered]

    def potential_ranking(
        self, context: AnalysisContext, limit: int
    ) -> list[DashboardRanking]:
        metrics, _, potential_scores = self.analytics.get_rankings(context)
        ordered = sorted(
            (metric for metric in metrics if metric.object_key in potential_scores),
            key=lambda metric: potential_scores[metric.object_key].rank,
        )[:limit]
        return [
            self._ranking(metric, potential=potential_scores[metric.object_key])
            for metric in ordered
        ]

    def trend(self, context: AnalysisContext) -> list[dict[str, object]]:
        return self.analytics.get_trend(context)

    def quality(self, context: AnalysisContext) -> dict[str, object]:
        result = dict(self.analytics.get_quality_summary(context))
        result["analysis_as_of"] = context.analysis_as_of
        return result

    def tag_distribution(self, limit: int) -> list[DashboardTagDistribution]:
        return [
            DashboardTagDistribution(
                tag_name=item.tag_name,
                drama_count=item.drama_count,
                percentage=(
                    round(item.drama_count * 100 / item.total_drama_count, 2)
                    if item.total_drama_count
                    else 0.0
                ),
            )
            for item in self.read(self.dashboard.get_tag_distribution, limit)
        ]

    @staticmethod
    def _ranking(
        metric: object,
        *,
        heat: HeatScore | None = None,
        potential: PotentialScore | None = None,
    ) -> DashboardRanking:
        return DashboardRanking(
            drama_id=metric.drama_id,
            drama_name=metric.drama_name,
            platform_count=metric.included_platform_count,
            heat_score=heat.score if heat else None,
            growth_rate=metric.growth_7d,
            current_play_count=metric.raw.play_count,
            potential_score=potential.score if potential else None,
            growth_7d=metric.growth_7d,
        )
