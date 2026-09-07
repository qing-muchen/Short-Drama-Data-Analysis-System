"""Platform persistence queries."""

from sqlalchemy import select

from models.master_data import Platform
from repositories.base import BaseRepository, Page


class PlatformRepository(BaseRepository[Platform]):
    """Database access for platform master records."""

    model = Platform

    def get_by_platform_name(self, platform_name: str) -> Platform | None:
        statement = select(Platform).where(Platform.platform_name == platform_name)
        return self.session.scalar(statement)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
    ) -> Page[Platform]:
        statement = select(Platform)
        if status is not None:
            statement = statement.where(Platform.status == status)
        if name_contains:
            statement = statement.where(
                Platform.platform_name.contains(name_contains, autoescape=True)
            )
        statement = statement.order_by(Platform.platform_id.asc())
        return self.paginate(statement, page=page, page_size=page_size)
