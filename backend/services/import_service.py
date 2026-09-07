"""Import Service structural entry point; no import workflow is implemented."""

from sqlalchemy.orm import Session

from services.base import BaseService


class ImportService(BaseService):
    """Future entry point for staged import validation and transactions."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
