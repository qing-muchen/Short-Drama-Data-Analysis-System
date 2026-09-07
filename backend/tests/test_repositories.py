"""Repository import, statement, pagination, and transaction-boundary tests."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Delete, Update

import repositories
from models.drama import Drama
from models.user import User
from repositories.drama_repository import DramaRepository
from repositories.snapshot_repository import SnapshotRepository
from repositories.user_repository import UserRepository


def make_session() -> Session:
    """Return a Session-shaped mock without any database connection."""

    return create_autospec(Session, instance=True)


def test_repository_package_exports_expected_types() -> None:
    assert set(repositories.__all__) == {
        "ActorRepository",
        "BaseRepository",
        "CompanyRepository",
        "DirectorRepository",
        "DramaRepository",
        "Page",
        "PlatformRepository",
        "SnapshotRepository",
        "TagRepository",
        "UserRepository",
    }


def test_session_is_injected_and_username_query_uses_select() -> None:
    session = make_session()
    expected = User(username="reader", password_hash="hash")
    session.scalar.return_value = expected
    repository = UserRepository(session)

    result = repository.get_by_username("reader")

    assert repository.session is session
    assert result is expected
    statement = session.scalar.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "FROM users" in compiled
    assert "users.username = %s" in compiled
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_base_create_update_delete_never_owns_transaction() -> None:
    session = make_session()
    repository = UserRepository(session)

    created = repository.create({"username": "new_user", "password_hash": "hash"})
    assert created.username == "new_user"
    session.add.assert_called_once_with(created)
    session.flush.assert_called_once_with()

    existing = User(user_id=1, username="existing", password_hash="hash")
    session.scalar.return_value = existing
    assert repository.update(1, {"display_name": "Updated"}) is existing
    assert isinstance(session.execute.call_args.args[0], Update)

    session.execute.reset_mock()
    assert repository.delete(1) is True
    assert isinstance(session.execute.call_args.args[0], Delete)

    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.close.assert_not_called()


def test_drama_page_contains_total_and_items() -> None:
    session = make_session()
    drama = Drama(drama_code="DRM001", drama_name="Sample")
    session.scalar.return_value = 1
    session.scalars.return_value.all.return_value = [drama]

    page = DramaRepository(session).list_page(
        page=2,
        page_size=20,
        status="COMPLETED",
        name_contains="Sample",
    )

    assert page.page == 2
    assert page.page_size == 20
    assert page.total == 1
    assert page.items == [drama]
    statement = session.scalars.call_args.args[0]
    assert statement._offset_clause.value == 20
    assert statement._limit_clause.value == 20


def test_snapshot_time_range_builds_database_filters() -> None:
    session = make_session()
    session.scalar.return_value = 0
    session.scalars.return_value.all.return_value = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, tzinfo=timezone.utc)

    result = SnapshotRepository(session).list_by_drama_platform(
        drama_platform_id=7,
        start_time=start,
        end_time=end,
        page=1,
        page_size=50,
    )

    assert result.total == 0
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "drama_metric_snapshots.drama_platform_id = %s" in compiled
    assert "drama_metric_snapshots.snapshot_time >= %s" in compiled
    assert "drama_metric_snapshots.snapshot_time <= %s" in compiled


def test_pagination_and_column_guards() -> None:
    session = make_session()
    repository = DramaRepository(session)

    with pytest.raises(ValueError, match="page"):
        repository.list_page(page=0, page_size=20)
    with pytest.raises(ValueError, match="page_size"):
        repository.list_page(page=1, page_size=0)
    with pytest.raises(ValueError, match="Unknown mapped columns"):
        repository.create({"unknown": "value"})
    with pytest.raises(ValueError, match="Primary key"):
        repository.update(1, {"drama_id": 2})


def test_repository_sources_do_not_manage_transactions() -> None:
    repository_path = Path(__file__).parents[1] / "repositories"
    source = "\n".join(
        file.read_text(encoding="utf-8")
        for file in repository_path.glob("*.py")
    )
    assert ".commit(" not in source
    assert ".rollback(" not in source
    assert "sessionmaker(" not in source
