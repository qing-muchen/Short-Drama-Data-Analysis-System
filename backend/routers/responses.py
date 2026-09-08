"""Schema conversion helpers shared by HTTP route modules."""

from typing import Any, TypeVar

from schemas.common import PageResponse, ResponseModel, SchemaModel

SchemaT = TypeVar("SchemaT", bound=SchemaModel)


def item_response(entity: Any, schema_type: type[SchemaT]) -> ResponseModel[SchemaT]:
    return ResponseModel[SchemaT](data=schema_type.model_validate(entity))


def page_response(page: Any, schema_type: type[SchemaT]) -> ResponseModel[Any]:
    payload = PageResponse[SchemaT](
        page=page.page,
        page_size=page.page_size,
        total=page.total,
        items=[schema_type.model_validate(item) for item in page.items],
    )
    return ResponseModel[PageResponse[SchemaT]](data=payload)
