"""Session factory and request-scoped session dependency."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from database.engine import get_engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the shared SQLAlchemy 2.x session factory."""

    return sessionmaker(
        bind=get_engine(),
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db_session() -> Generator[Session, None, None]:
    """Yield a session and always close it after request processing."""

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
