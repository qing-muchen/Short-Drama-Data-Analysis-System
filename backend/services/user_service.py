"""User Service dependency boundary; business flows are not implemented."""

from sqlalchemy.orm import Session

from repositories.user_repository import UserRepository
from services.base import BaseService


class UserService(BaseService):
    """Future entry point for user lifecycle and account business rules."""

    def __init__(self, session: Session, users: UserRepository) -> None:
        super().__init__(session, users)
        self.users = users
