"""Director persistence queries."""

from sqlalchemy import select

from models.master_data import Director
from repositories.base import BaseRepository, Page


class DirectorRepository(BaseRepository[Director]):
    """Database access for director master records."""

    model = Director

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
    ) -> Page[Director]:
        statement = select(Director)
        if status is not None:
            statement = statement.where(Director.status == status)
        if name_contains:
            statement = statement.where(
                Director.director_name.contains(name_contains, autoescape=True)
            )
        statement = statement.order_by(Director.director_id.asc())
        return self.paginate(statement, page=page, page_size=page_size)
