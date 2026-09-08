"""Read-only master-data counts used by the Dashboard composition layer."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.drama import Drama
from models.master_data import Actor, Company, Director, Platform, Tag
from repositories.base import BaseRepository


@dataclass(frozen=True, slots=True)
class DashboardCounts:
    drama_count: int
    actor_count: int
    director_count: int
    company_count: int
    platform_count: int
    tag_count: int


class DashboardRepository(BaseRepository[Drama]):
    """Expose bounded aggregate counts; metric calculations stay in AnalyticsService."""

    model = Drama

    def get_counts(self) -> DashboardCounts:
        def count(model: type[object]) -> int:
            statement = select(func.count()).select_from(model)
            return int(self.session.scalar(statement) or 0)

        return DashboardCounts(
            drama_count=count(Drama),
            actor_count=count(Actor),
            director_count=count(Director),
            company_count=count(Company),
            platform_count=count(Platform),
            tag_count=count(Tag),
        )

