"""Quality Service structural entry point; no quality flow is implemented."""

from sqlalchemy.orm import Session

from services.base import BaseService


class QualityService(BaseService):
    """Future entry point for quality issue review and lifecycle rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
