"""Platform CRUD orchestration for the basic API baseline."""

from typing import Any, Mapping

from sqlalchemy.orm import Session

from repositories.platform_repository import PlatformRepository
from services.base import BaseService
from services.exceptions import ConflictException, NotFoundException, ValidationException


class PlatformService(BaseService):
    """Coordinate platform persistence and logical deactivation."""

    def __init__(self, session: Session, platforms: PlatformRepository) -> None:
        super().__init__(session, platforms)
        self.platforms = platforms

    def list_platforms(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
    ) -> Any:
        return self.read(
            self.platforms.list_page,
            page=page,
            page_size=page_size,
            status=status,
            name_contains=name_contains,
        )

    def get_platform(self, platform_id: int) -> Any:
        platform = self.read(self.platforms.get_by_id, platform_id)
        if platform is None:
            raise NotFoundException(
                "Platform was not found",
                details={"platform_id": platform_id},
            )
        return platform

    def create_platform(self, values: Mapping[str, Any]) -> Any:
        self._ensure_unique_name(str(values["platform_name"]))
        with self.transaction():
            return self.platforms.create(values)

    def update_platform(self, platform_id: int, values: Mapping[str, Any]) -> Any:
        self._reject_null(values, "platform_name", "status")
        platform = self.get_platform(platform_id)
        platform_name = values.get("platform_name")
        if platform_name is not None:
            self._ensure_unique_name(str(platform_name), current=platform)
        with self.transaction():
            return self.platforms.update(platform_id, values)

    def deactivate_platform(self, platform_id: int) -> Any:
        return self.update_platform(platform_id, {"status": "INACTIVE"})

    def _ensure_unique_name(self, name: str, *, current: Any = None) -> None:
        existing = self.read(self.platforms.get_by_platform_name, name)
        current_id = getattr(current, "platform_id", None)
        if existing is not None and (
            current is None or getattr(existing, "platform_id", None) != current_id
        ):
            raise ConflictException("Platform name already exists")

    @staticmethod
    def _reject_null(values: Mapping[str, Any], *required: str) -> None:
        invalid = [field for field in required if field in values and values[field] is None]
        if invalid:
            raise ValidationException(
                "Required platform fields cannot be null",
                details={"fields": invalid},
            )
