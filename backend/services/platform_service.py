"""Platform Service dependency boundary; business flows are not implemented."""

from sqlalchemy.orm import Session

from repositories.platform_repository import PlatformRepository
from services.base import BaseService


class PlatformService(BaseService):
    """Future entry point for platform and release business rules."""

    def __init__(self, session: Session, platforms: PlatformRepository) -> None:
        super().__init__(session, platforms)
        self.platforms = platforms
