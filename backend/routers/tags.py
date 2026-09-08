"""Tag master-data CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from routers.dependencies import MasterDataServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.master_data import EntityStatus, TagCreate, TagResponse, TagUpdate

router = APIRouter(prefix="/tags", tags=["tags"], responses=ERROR_RESPONSES)


@router.get("", response_model=ResponseModel[PageResponse[TagResponse]])
def list_tags(
    service: MasterDataServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[EntityStatus | None, Query(alias="status")] = None,
    name_contains: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ResponseModel[PageResponse[TagResponse]]:
    result = service.list_tags(
        page=page,
        page_size=page_size,
        status=status_filter,
        name_contains=name_contains,
    )
    return page_response(result, TagResponse)


@router.get("/{tag_id}", response_model=ResponseModel[TagResponse])
def get_tag(
    service: MasterDataServiceDependency,
    tag_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[TagResponse]:
    return item_response(service.get_tag(tag_id), TagResponse)


@router.post(
    "",
    response_model=ResponseModel[TagResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_tag(
    payload: TagCreate,
    service: MasterDataServiceDependency,
) -> ResponseModel[TagResponse]:
    return item_response(
        service.create_tag(payload.model_dump(exclude_unset=True)),
        TagResponse,
    )


@router.put("/{tag_id}", response_model=ResponseModel[TagResponse])
def update_tag(
    payload: TagUpdate,
    service: MasterDataServiceDependency,
    tag_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[TagResponse]:
    return item_response(
        service.update_tag(tag_id, payload.model_dump(exclude_unset=True)),
        TagResponse,
    )


@router.delete("/{tag_id}", response_model=ResponseModel[TagResponse])
def delete_tag(
    service: MasterDataServiceDependency,
    tag_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[TagResponse]:
    return item_response(service.deactivate_tag(tag_id), TagResponse)
