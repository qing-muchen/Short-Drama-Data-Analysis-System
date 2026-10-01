"""Read-only master-data counts used by the Dashboard composition layer."""

from dataclasses import dataclass

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from models.drama import Drama
from models.master_data import Actor, Company, Director, Platform, Tag
from models.relations import DramaTag
from repositories.base import BaseRepository


@dataclass(frozen=True, slots=True)
class DashboardCounts:
    drama_count: int
    actor_count: int
    director_count: int
    company_count: int
    platform_count: int
    tag_count: int


@dataclass(frozen=True, slots=True)
class DashboardTagCount:
    tag_name: str
    drama_count: int
    total_drama_count: int


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

    def get_tag_distribution(self, limit: int) -> list[DashboardTagCount]:
        """Return tag usage and the all-drama denominator in one SQL query."""

        all_dramas = (
            select(func.count(Drama.drama_id).label("total_drama_count"))
            .subquery()
        )
        drama_count = func.count(func.distinct(DramaTag.drama_id)).label(
            "drama_count"
        )
        statement = (
            select(Tag.tag_name, drama_count, all_dramas.c.total_drama_count)
            .select_from(Tag)
            .join(DramaTag, DramaTag.tag_id == Tag.tag_id)
            .join(all_dramas, true())
            .where(
                Tag.status == "ACTIVE",
                DramaTag.relation_status == "ACTIVE",
            )
            .group_by(
                Tag.tag_id,
                Tag.tag_name,
                all_dramas.c.total_drama_count,
            )
            .order_by(drama_count.desc(), Tag.tag_name.asc())
            .limit(limit)
        )
        return [
            DashboardTagCount(str(name), int(count), int(total))
            for name, count, total in self.session.execute(statement).all()
        ]
