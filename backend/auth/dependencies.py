"""Current-user resolution and role-based FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from auth.exceptions import AuthenticationException, AuthorizationException
from auth.security import bearer_scheme
from config.settings import Settings, get_settings
from database.session import get_db_session
from models.user import User
from repositories.user_repository import UserRepository
from services.auth_service import AuthService

DatabaseSession = Annotated[Session, Depends(get_db_session)]
ApplicationSettings = Annotated[Settings, Depends(get_settings)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


def get_auth_service(
    session: DatabaseSession,
    settings: ApplicationSettings,
) -> AuthService:
    return AuthService(session, UserRepository(session), settings)


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


def get_current_user(
    credentials: BearerCredentials,
    service: AuthServiceDependency,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationException()
    return service.resolve_current_user(credentials.credentials)


CurrentUserDependency = Annotated[User, Depends(get_current_user)]


def require_user(current_user: CurrentUserDependency) -> User:
    if current_user.role_code not in {"ADMINISTRATOR", "USER"}:
        raise AuthorizationException()
    return current_user


def require_admin(current_user: CurrentUserDependency) -> User:
    if current_user.role_code != "ADMINISTRATOR":
        raise AuthorizationException()
    return current_user


AuthenticatedUserDependency = Annotated[User, Depends(require_user)]
AdministratorDependency = Annotated[User, Depends(require_admin)]
