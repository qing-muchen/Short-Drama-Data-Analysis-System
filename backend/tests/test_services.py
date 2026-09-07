"""Service import, dependency, exception, and transaction-boundary tests."""

from pathlib import Path
from unittest.mock import create_autospec

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import services
from repositories.user_repository import UserRepository
from services.base import BaseService, RepositorySessionMismatchError
from services.exceptions import (
    BusinessException,
    NotFoundException,
    PersistenceException,
    ValidationException,
)
from services.user_service import UserService


def make_session() -> Session:
    """Return a Session-shaped mock without opening a database connection."""

    return create_autospec(Session, instance=True)


def test_service_package_exports_structural_baseline() -> None:
    assert set(services.__all__) == {
        "AnalyticsService",
        "BaseService",
        "BusinessException",
        "ConflictException",
        "DramaService",
        "ImportService",
        "MasterDataService",
        "NotFoundException",
        "PersistenceException",
        "PlatformService",
        "QualityService",
        "RepositorySessionMismatchError",
        "SnapshotService",
        "UserService",
        "ValidationException",
    }


def test_service_accepts_injected_repository_with_shared_session() -> None:
    session = make_session()
    users = UserRepository(session)

    service = UserService(session, users)

    assert service.users is users
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_service_rejects_repository_from_another_session() -> None:
    service_session = make_session()
    repository_session = make_session()

    with pytest.raises(RepositorySessionMismatchError):
        UserService(service_session, UserRepository(repository_session))


def test_transaction_commits_only_after_success() -> None:
    session = make_session()
    service = BaseService(session)

    with service.transaction():
        pass

    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.execute.assert_not_called()


def test_transaction_rolls_back_and_preserves_business_exception() -> None:
    session = make_session()
    service = BaseService(session)
    expected = ValidationException("invalid transition")

    with pytest.raises(ValidationException) as raised:
        with service.transaction():
            raise expected

    assert raised.value is expected
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_database_exception_is_wrapped_before_leaving_service() -> None:
    session = make_session()
    service = BaseService(session)

    with pytest.raises(PersistenceException) as raised:
        with service.transaction():
            raise SQLAlchemyError("internal database detail")

    assert raised.value.code == "PERSISTENCE_ERROR"
    assert "internal database detail" not in raised.value.message
    session.rollback.assert_called_once_with()


def test_business_exception_contract_is_http_independent() -> None:
    error = NotFoundException(
        "Drama was not found",
        details={"resource": "drama"},
    )

    assert isinstance(error, BusinessException)
    assert error.code == "NOT_FOUND"
    assert error.message == "Drama was not found"
    assert error.details == {"resource": "drama"}


def test_service_sources_do_not_access_orm_or_execute_queries() -> None:
    service_path = Path(__file__).parents[1] / "services"
    source = "\n".join(
        file.read_text(encoding="utf-8") for file in service_path.glob("*.py")
    )

    assert "from models" not in source
    assert "import models" not in source
    assert ".execute(" not in source
    assert "APIRouter" not in source
    assert "FastAPI" not in source
