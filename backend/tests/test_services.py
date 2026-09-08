"""Service import, dependency, exception, and transaction-boundary tests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import services
from repositories.drama_repository import DramaRepository
from repositories.platform_repository import PlatformRepository
from repositories.user_repository import UserRepository
from services.base import BaseService, RepositorySessionMismatchError
from services.drama_service import DramaService
from services.exceptions import (
    BusinessException,
    NotFoundException,
    PersistenceException,
    ValidationException,
)
from services.platform_service import PlatformService
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


def test_read_database_exception_is_wrapped_and_rolled_back() -> None:
    session = make_session()
    service = BaseService(session)
    operation = MagicMock(side_effect=SQLAlchemyError("private read detail"))

    with pytest.raises(PersistenceException) as raised:
        service.read(operation)

    assert "private read detail" not in raised.value.message
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


def test_drama_service_generates_code_and_commits_create() -> None:
    session = make_session()
    repository = DramaRepository(session)
    entity = SimpleNamespace(drama_id=1, drama_code="generated")
    repository.get_by_drama_code = MagicMock(return_value=None)
    repository.create = MagicMock(return_value=entity)
    service = DramaService(session, repository)

    result = service.create_drama({"drama_name": "Sample Drama"})

    values = repository.create.call_args.args[0]
    assert result is entity
    assert values["drama_name"] == "Sample Drama"
    assert values["drama_code"].startswith("DRM")
    assert len(values["drama_code"]) == 32
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_drama_delete_semantics_deactivate_instead_of_physical_delete() -> None:
    session = make_session()
    repository = DramaRepository(session)
    entity = SimpleNamespace(drama_id=1, status="ACTIVE")
    inactive = SimpleNamespace(drama_id=1, status="INACTIVE")
    repository.get_by_id = MagicMock(return_value=entity)
    repository.update = MagicMock(return_value=inactive)
    repository.delete = MagicMock()
    service = DramaService(session, repository)

    result = service.deactivate_drama(1)

    assert result is inactive
    repository.update.assert_called_once_with(1, {"status": "INACTIVE"})
    repository.delete.assert_not_called()
    session.commit.assert_called_once_with()


def test_platform_service_rejects_duplicate_name_without_writing() -> None:
    session = make_session()
    repository = PlatformRepository(session)
    repository.get_by_platform_name = MagicMock(return_value=SimpleNamespace())
    repository.create = MagicMock()
    service = PlatformService(session, repository)

    with pytest.raises(BusinessException) as raised:
        service.create_platform({"platform_name": "Existing"})

    assert raised.value.code == "BUSINESS_CONFLICT"
    repository.create.assert_not_called()
    session.commit.assert_not_called()


def test_drama_service_rejects_explicit_null_required_fields() -> None:
    session = make_session()
    repository = DramaRepository(session)
    repository.get_by_id = MagicMock()
    repository.update = MagicMock()
    service = DramaService(session, repository)

    with pytest.raises(ValidationException) as raised:
        service.update_drama(1, {"status": None})

    assert raised.value.details == {"fields": ["status"]}
    repository.get_by_id.assert_not_called()
    repository.update.assert_not_called()
    session.commit.assert_not_called()
