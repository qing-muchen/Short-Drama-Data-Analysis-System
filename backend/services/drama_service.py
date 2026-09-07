"""Drama Service dependency boundary; business flows are not implemented."""

from sqlalchemy.orm import Session

from repositories.drama_repository import DramaRepository
from services.base import BaseService


class DramaService(BaseService):
    """Future entry point for the drama lifecycle and its orchestration."""

    def __init__(self, session: Session, dramas: DramaRepository) -> None:
        super().__init__(session, dramas)
        self.dramas = dramas
