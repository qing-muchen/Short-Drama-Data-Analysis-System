"""Common Pydantic v2 DTO primitives independent of HTTP and ORM."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class SchemaModel(BaseModel):
    """Strict DTO base supporting conversion from SQLAlchemy attributes."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class PageResponse(SchemaModel, Generic[DataT]):
    """Protocol-neutral paginated result."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    items: list[DataT]


class ResponseModel(SchemaModel, Generic[DataT]):
    """Generic successful response envelope for future Router use."""

    data: DataT
    message: str = Field(default="success", min_length=1, max_length=200)


class ErrorResponse(SchemaModel):
    """Safe error payload without traceback or persistence details."""

    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1000)
    details: dict[str, Any] | None = None
