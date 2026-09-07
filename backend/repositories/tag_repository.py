"""Tag persistence queries."""

from sqlalchemy import select

from models.master_data import Tag
from repositories.base import BaseRepository, Page


class TagRepository(BaseRepository[Tag]):
    """Database access for tag master records."""

    model = Tag

    def get_by_tag_name(self, tag_name: str) -> Tag | None:
        statement = select(Tag).where(Tag.tag_name == tag_name)
        return self.session.scalar(statement)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
    ) -> Page[Tag]:
        statement = select(Tag)
        if status is not None:
            statement = statement.where(Tag.status == status)
        if name_contains:
            statement = statement.where(Tag.tag_name.contains(name_contains, autoescape=True))
        statement = statement.order_by(Tag.tag_id.asc())
        return self.paginate(statement, page=page, page_size=page_size)
