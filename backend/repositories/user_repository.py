"""User persistence queries."""

from sqlalchemy import select

from models.user import User
from repositories.base import BaseRepository, Page


class UserRepository(BaseRepository[User]):
    """Database access for users only."""

    model = User

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self.session.scalar(statement)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> Page[User]:
        statement = select(User)
        if status is not None:
            statement = statement.where(User.status == status)
        statement = statement.order_by(User.user_id.asc())
        return self.paginate(statement, page=page, page_size=page_size)
