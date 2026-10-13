"""Lazy SQLAlchemy engine construction."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine, event

from config.settings import get_settings


def _set_mysql_session_utc(
    dbapi_connection: object,
    _connection_record: object,
) -> None:
    """Keep MySQL server-generated ``DATETIME`` values on the UTC contract."""

    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("SET time_zone = '+00:00'")
    finally:
        cursor.close()


@lru_cache
def get_engine() -> Engine:
    """Build the shared engine without opening a connection eagerly."""

    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    if engine.dialect.name == "mysql":
        event.listen(engine, "connect", _set_mysql_session_utc)
    return engine
