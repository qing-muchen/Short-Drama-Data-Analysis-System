"""Tag persistence queries."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, select

from models.master_data import Tag
from models.relations import DramaTag
from repositories.base import BaseRepository, Page


@dataclass(frozen=True, slots=True)
class TagWithDramaCount:
    tag_id: int
    tag_name: str
    status: str
    created_at: datetime
    updated_at: datetime
    drama_count: int


class TagRepository(BaseRepository[Tag]):
    """Database access for tag master records."""

    model = Tag

    def get_by_tag_name(self, tag_name: str) -> Tag | None:
        statement = select(Tag).where(Tag.tag_name == tag_name)
        return self.session.scalar(statement)

    def get_active_ids(self, tag_ids: Sequence[int]) -> set[int]:
        if not tag_ids:
            return set()
        statement = select(Tag.tag_id).where(
            Tag.tag_id.in_(tag_ids),
            Tag.status == "ACTIVE",
        )
        return set(self.session.scalars(statement).all())

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
    ) -> Page:
        drama_count = func.count(func.distinct(DramaTag.drama_id)).label("drama_count")
        statement = (
            select(Tag, drama_count)
            .outerjoin(
                DramaTag,
                and_(
                    DramaTag.tag_id == Tag.tag_id,
                    DramaTag.relation_status == "ACTIVE",
                ),
            )
            .group_by(
                Tag.tag_id,
                Tag.tag_name,
                Tag.status,
                Tag.created_at,
                Tag.updated_at,
            )
        )
        if status is not None:
            statement = statement.where(Tag.status == status)
        if name_contains:
            statement = statement.where(Tag.tag_name.contains(name_contains, autoescape=True))
        statement = statement.order_by(Tag.tag_id.asc())
        total_statement = select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
        total = int(self.session.scalar(total_statement) or 0)
        rows = self.session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        ).all()
        return Page(
            page=page,
            page_size=page_size,
            total=total,
            items=[
                TagWithDramaCount(
                    tag_id=tag.tag_id,
                    tag_name=tag.tag_name,
                    status=tag.status,
                    created_at=tag.created_at,
                    updated_at=tag.updated_at,
                    drama_count=int(count),
                )
                for tag, count in rows
            ],
        )
