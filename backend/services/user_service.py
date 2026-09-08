"""Read-only user Service used by the pre-authentication API baseline."""

from typing import Any

from sqlalchemy.orm import Session

from repositories.user_repository import UserRepository
from services.base import BaseService
from services.exceptions import NotFoundException


class UserService(BaseService):
    """Expose user queries while authentication and account writes stay deferred."""

    def __init__(self, session: Session, users: UserRepository) -> None:
        super().__init__(session, users)
        self.users = users

    def list_users(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> Any:
        return self.read(
            self.users.list_page,
            page=page,
            page_size=page_size,
            status=status,
        )

    def get_user(self, user_id: int) -> Any:
        user = self.read(self.users.get_by_id, user_id)
        if user is None:
            raise NotFoundException("User was not found", details={"user_id": user_id})
        return user
