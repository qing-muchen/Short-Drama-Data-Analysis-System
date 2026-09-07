"""Company persistence queries."""

from sqlalchemy import select

from models.master_data import Company
from repositories.base import BaseRepository, Page


class CompanyRepository(BaseRepository[Company]):
    """Database access for company master records."""

    model = Company

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
    ) -> Page[Company]:
        statement = select(Company)
        if status is not None:
            statement = statement.where(Company.status == status)
        if name_contains:
            statement = statement.where(
                Company.company_name.contains(name_contains, autoescape=True)
            )
        statement = statement.order_by(Company.company_id.asc())
        return self.paginate(statement, page=page, page_size=page_size)
