"""Drama lifecycle operations for the basic CRUD API baseline."""

from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy.orm import Session

from repositories.drama_repository import DramaRepository
from services.base import BaseService
from services.exceptions import NotFoundException, ValidationException


class DramaService(BaseService):
    """Coordinate drama persistence and logical deactivation."""

    def __init__(self, session: Session, dramas: DramaRepository) -> None:
        super().__init__(session, dramas)
        self.dramas = dramas

    def list_dramas(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
    ) -> Any:
        return self.read(
            self.dramas.list_page,
            page=page,
            page_size=page_size,
            status=status,
            name_contains=name_contains,
        )

    def get_drama(self, drama_id: int) -> Any:
        drama = self.read(self.dramas.get_by_id, drama_id)
        if drama is None:
            raise NotFoundException(
                "Drama was not found",
                details={"drama_id": drama_id},
            )
        return drama

    def create_drama(self, values: Mapping[str, Any]) -> Any:
        create_values = dict(values)
        create_values["drama_code"] = self._new_drama_code()
        with self.transaction():
            return self.dramas.create(create_values)

    def update_drama(self, drama_id: int, values: Mapping[str, Any]) -> Any:
        self._reject_null(values, "drama_name", "status")
        self.get_drama(drama_id)
        with self.transaction():
            drama = self.dramas.update(drama_id, values)
        return drama

    def deactivate_drama(self, drama_id: int) -> Any:
        return self.update_drama(drama_id, {"status": "INACTIVE"})

    def _new_drama_code(self) -> str:
        while True:
            candidate = f"DRM{uuid4().hex[:29].upper()}"
            if self.read(self.dramas.get_by_drama_code, candidate) is None:
                return candidate

    @staticmethod
    def _reject_null(values: Mapping[str, Any], *required: str) -> None:
        invalid = [field for field in required if field in values and values[field] is None]
        if invalid:
            raise ValidationException(
                "Required drama fields cannot be null",
                details={"fields": invalid},
            )
