"""Tag master-data CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from auth.dependencies import require_admin, require_user
from routers.dependencies import MasterDataServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.master_data import (
    EntityStatus,
    TagCreate,
    TagListResponse,
    TagResponse,
    TagUpdate,
)

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_user)],
)


@router.get("", response_model=ResponseModel[PageResponse[TagListResponse]])
def list_tags(
    service: MasterDataServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[EntityStatus | None, Query(alias="status")] = None,
    name_contains: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ResponseModel[PageResponse[TagListResponse]]:
    result = service.list_tags(
        page=page,
        page_size=page_size,
        status=status_filter,
        name_contains=name_contains,
    )
    return page_response(result, TagListResponse)


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
    dependencies=[Depends(require_admin)],
)
def create_tag(
    payload: TagCreate,
    service: MasterDataServiceDependency,
) -> ResponseModel[TagResponse]:
    return item_response(
        service.create_tag(payload.model_dump(exclude_unset=True)),
        TagResponse,
    )


@router.put(
    "/{tag_id}",
    response_model=ResponseModel[TagResponse],
    dependencies=[Depends(require_admin)],
)
def update_tag(
    payload: TagUpdate,
    service: MasterDataServiceDependency,
    tag_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[TagResponse]:
    return item_response(
        service.update_tag(tag_id, payload.model_dump(exclude_unset=True)),
        TagResponse,
    )


@router.delete(
    "/{tag_id}",
    response_model=ResponseModel[TagResponse],
    dependencies=[Depends(require_admin)],
)
def delete_tag(
    service: MasterDataServiceDependency,
    tag_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[TagResponse]:
    return item_response(service.deactivate_tag(tag_id), TagResponse)
