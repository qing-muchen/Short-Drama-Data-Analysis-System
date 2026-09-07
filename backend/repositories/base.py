"""Generic SQLAlchemy repository primitives without transaction ownership."""

from dataclasses import dataclass
from typing import Any, Generic, Mapping, Sequence, TypeVar

from sqlalchemy import ColumnElement, delete, func, inspect, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


@dataclass(frozen=True, slots=True)
class Page(Generic[ModelT]):
    """Transport-neutral page of ORM results."""

    page: int
    page_size: int
    total: int
    items: list[ModelT]


class BaseRepository(Generic[ModelT]):
    """Provide schema-agnostic persistence operations for one ORM model.

    The caller owns the Session and its transaction. This class deliberately
    never creates, commits, rolls back, or closes a Session.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    @property
    def _primary_key(self) -> Any:
        primary_key = inspect(self.model).primary_key
        if len(primary_key) != 1:
            raise RuntimeError(
                f"{self.model.__name__} must have one primary key column"
            )
        return primary_key[0]

    def get_by_id(self, entity_id: int) -> ModelT | None:
        """Return one entity by its single-column primary key."""

        statement = select(self.model).where(self._primary_key == entity_id)
        return self.session.scalar(statement)

    def list(
        self,
        *,
        filters: Sequence[ColumnElement[bool]] = (),
        order_by: Sequence[ColumnElement[Any]] = (),
        offset: int = 0,
        limit: int = 20,
    ) -> list[ModelT]:
        """Return a bounded list using database-side filtering and ordering."""

        self._validate_window(offset=offset, limit=limit)
        statement = select(self.model).where(*filters)
        if order_by:
            statement = statement.order_by(*order_by)
        else:
            statement = statement.order_by(self._primary_key.asc())
        statement = statement.offset(offset).limit(limit)
        return list(self.session.scalars(statement).all())

    def count(self, *, filters: Sequence[ColumnElement[bool]] = ()) -> int:
        """Count rows matching database-side equality/range expressions."""

        statement = select(func.count()).select_from(self.model).where(*filters)
        return int(self.session.scalar(statement) or 0)

    def create(self, values: Mapping[str, Any]) -> ModelT:
        """Add and flush one instance without committing its transaction."""

        self._validate_columns(values)
        entity = self.model(**dict(values))
        self.session.add(entity)
        self.session.flush()
        return entity

    def update(self, entity_id: int, values: Mapping[str, Any]) -> ModelT | None:
        """Update allowed mapped columns without committing the transaction."""

        self._validate_columns(values, allow_primary_key=False)
        entity = self.get_by_id(entity_id)
        if entity is None or not values:
            return entity

        statement = (
            update(self.model)
            .where(self._primary_key == entity_id)
            .values(**dict(values))
            .execution_options(synchronize_session="fetch")
        )
        self.session.execute(statement)
        return entity

    def delete(self, entity_id: int) -> bool:
        """Delete one row without committing; Service must authorize its use."""

        if self.get_by_id(entity_id) is None:
            return False
        statement = delete(self.model).where(self._primary_key == entity_id)
        self.session.execute(statement)
        return True

    def paginate(
        self,
        statement: Select[tuple[ModelT]],
        *,
        page: int,
        page_size: int,
    ) -> Page[ModelT]:
        """Execute a select and its total count as a transport-neutral page."""

        self._validate_page(page=page, page_size=page_size)
        total_statement = select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
        total = int(self.session.scalar(total_statement) or 0)
        items_statement = statement.offset((page - 1) * page_size).limit(page_size)
        items = list(self.session.scalars(items_statement).all())
        return Page(page=page, page_size=page_size, total=total, items=items)

    def _validate_columns(
        self,
        values: Mapping[str, Any],
        *,
        allow_primary_key: bool = True,
    ) -> None:
        mapper = inspect(self.model)
        mapped_columns = set(mapper.columns.keys())
        unknown = set(values) - mapped_columns
        if unknown:
            raise ValueError(f"Unknown mapped columns: {sorted(unknown)}")

        if not allow_primary_key:
            primary_keys = {column.key for column in mapper.primary_key}
            forbidden = set(values) & primary_keys
            if forbidden:
                raise ValueError(
                    f"Primary key columns cannot be updated: {sorted(forbidden)}"
                )

    @staticmethod
    def _validate_window(*, offset: int, limit: int) -> None:
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1")

    @staticmethod
    def _validate_page(*, page: int, page_size: int) -> None:
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if page_size < 1:
            raise ValueError("page_size must be greater than or equal to 1")
