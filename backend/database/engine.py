"""Lazy SQLAlchemy engine construction."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from config.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    """Build the shared engine without opening a connection eagerly."""

    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
