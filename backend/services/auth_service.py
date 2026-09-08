"""Authentication Service coordinating credentials, JWT, and current users."""

from typing import Any

from sqlalchemy.orm import Session

from auth.exceptions import AuthenticationException
from auth.jwt import create_access_token, decode_access_token
from auth.password import verify_password
from config.settings import Settings
from repositories.user_repository import UserRepository
from services.base import BaseService


class AuthService(BaseService):
    """Authenticate active users and resolve tokens through the Repository layer."""

    def __init__(
        self,
        session: Session,
        users: UserRepository,
        settings: Settings,
    ) -> None:
        super().__init__(session, users)
        self.users = users
        self.settings = settings

    def login(self, username: str, password: str) -> tuple[str, int]:
        user = self.read(self.users.get_by_username, username)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationException()
        if user.status != "ACTIVE":
            raise AuthenticationException()

        expires_minutes = self.settings.token_expire_minutes
        token = create_access_token(
            user_id=user.user_id,
            username=user.username,
            role=user.role_code,
            secret_key=self.settings.secret_key.get_secret_value(),
            expires_minutes=expires_minutes,
        )
        return token, expires_minutes * 60

    def resolve_current_user(self, token: str) -> Any:
        claims = decode_access_token(
            token,
            secret_key=self.settings.secret_key.get_secret_value(),
        )
        user = self.read(self.users.get_by_id, claims.user_id)
        if user is None or user.status != "ACTIVE":
            raise AuthenticationException()
        if user.username != claims.username:
            raise AuthenticationException()
        return user
