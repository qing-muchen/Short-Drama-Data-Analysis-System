"""Actor persistence queries."""

from sqlalchemy import select

from models.master_data import Actor
from repositories.base import BaseRepository, Page


class ActorRepository(BaseRepository[Actor]):
    """Database access for actor master records."""

    model = Actor

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
    ) -> Page[Actor]:
        statement = select(Actor)
        if status is not None:
            statement = statement.where(Actor.status == status)
        if name_contains:
            statement = statement.where(
                Actor.actor_name.contains(name_contains, autoescape=True)
            )
        statement = statement.order_by(Actor.actor_id.asc())
        return self.paginate(statement, page=page, page_size=page_size)
