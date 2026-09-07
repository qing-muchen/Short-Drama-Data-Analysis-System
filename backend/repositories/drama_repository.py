"""Drama persistence queries."""

from sqlalchemy import select

from models.drama import Drama
from repositories.base import BaseRepository, Page


class DramaRepository(BaseRepository[Drama]):
    """Database access for drama master records."""

    model = Drama

    def get_by_drama_code(self, drama_code: str) -> Drama | None:
        statement = select(Drama).where(Drama.drama_code == drama_code)
        return self.session.scalar(statement)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
    ) -> Page[Drama]:
        statement = select(Drama)
        if status is not None:
            statement = statement.where(Drama.status == status)
        if name_contains:
            statement = statement.where(
                Drama.drama_name.contains(name_contains, autoescape=True)
            )
        statement = statement.order_by(Drama.drama_id.asc())
        return self.paginate(statement, page=page, page_size=page_size)
