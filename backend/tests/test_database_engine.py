"""UTC session initialization for pooled MySQL connections."""

import pytest

from database.engine import _set_mysql_session_utc


class _Cursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.closed = False

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def close(self) -> None:
        self.closed = True


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _Cursor:
        return self._cursor


def test_mysql_connection_is_initialized_in_utc() -> None:
    cursor = _Cursor()

    _set_mysql_session_utc(_Connection(cursor), object())

    assert cursor.statements == ["SET time_zone = '+00:00'"]
    assert cursor.closed is True


def test_mysql_connection_cursor_is_closed_when_initialization_fails() -> None:
    class FailingCursor(_Cursor):
        def execute(self, statement: str) -> None:
            super().execute(statement)
            raise RuntimeError("database rejected session setting")

    cursor = FailingCursor()

    with pytest.raises(RuntimeError, match="database rejected session setting"):
        _set_mysql_session_utc(_Connection(cursor), object())

    assert cursor.closed is True
