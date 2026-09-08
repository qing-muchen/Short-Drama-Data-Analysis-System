"""Request-scoped composition root for Service and Repository objects."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from database.session import get_db_session
from repositories.actor_repository import ActorRepository
from repositories.company_repository import CompanyRepository
from repositories.director_repository import DirectorRepository
from repositories.drama_repository import DramaRepository
from repositories.import_repository import (
    ImportDataRepository,
    ImportErrorRepository,
    ImportJobRepository,
    OperationLogRepository,
)
from repositories.platform_repository import PlatformRepository
from repositories.tag_repository import TagRepository
from repositories.user_repository import UserRepository
from services.drama_service import DramaService
from services.import_service import ImportService
from services.master_data_service import MasterDataService
from services.platform_service import PlatformService
from services.user_service import UserService

DatabaseSession = Annotated[Session, Depends(get_db_session)]


def get_user_service(session: DatabaseSession) -> UserService:
    return UserService(session, UserRepository(session))


def get_drama_service(session: DatabaseSession) -> DramaService:
    return DramaService(session, DramaRepository(session))


def get_master_data_service(session: DatabaseSession) -> MasterDataService:
    return MasterDataService(
        session,
        ActorRepository(session),
        DirectorRepository(session),
        CompanyRepository(session),
        TagRepository(session),
    )


def get_platform_service(session: DatabaseSession) -> PlatformService:
    return PlatformService(session, PlatformRepository(session))


def get_import_service(session: DatabaseSession) -> ImportService:
    return ImportService(
        session,
        ImportJobRepository(session),
        ImportErrorRepository(session),
        ImportDataRepository(session),
        OperationLogRepository(session),
    )


UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
DramaServiceDependency = Annotated[DramaService, Depends(get_drama_service)]
MasterDataServiceDependency = Annotated[
    MasterDataService,
    Depends(get_master_data_service),
]
PlatformServiceDependency = Annotated[
    PlatformService,
    Depends(get_platform_service),
]
ImportServiceDependency = Annotated[ImportService, Depends(get_import_service)]
