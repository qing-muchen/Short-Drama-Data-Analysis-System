"""Service dependency and transaction boundary primitives."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from repositories.base import BaseRepository
from services.exceptions import PersistenceException


class RepositorySessionMismatchError(RuntimeError):
    """Raised during wiring when a Repository uses another Session."""


class BaseService:
    """Own transaction completion while delegating all data access.

    Session and Repository instances are injected by the composition layer.
    Subclasses must access persisted data only through injected Repositories.
    """

    def __init__(
        self,
        session: Session,
        *repositories: BaseRepository[Any],
    ) -> None:
        self._session = session
        self._assert_shared_session(repositories)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit on success and roll back on any failed Service operation."""

        try:
            yield
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PersistenceException() from error
        except Exception:
            self._session.rollback()
            raise

    def _assert_shared_session(
        self,
        repositories: tuple[BaseRepository[Any], ...],
    ) -> None:
        mismatched = [
            repository.__class__.__name__
            for repository in repositories
            if repository.session is not self._session
        ]
        if mismatched:
            names = ", ".join(mismatched)
            raise RepositorySessionMismatchError(
                f"Repositories must share the Service Session: {names}"
            )
