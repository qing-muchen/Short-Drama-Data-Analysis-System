"""Drama CRUD endpoints using the Service boundary."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from auth.dependencies import require_admin, require_user
from routers.dependencies import DramaServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.drama import (
    DramaCreateRequest,
    DramaDetailResponse,
    DramaStatus,
    DramaUpdateRequest,
)

router = APIRouter(
    prefix="/dramas",
    tags=["dramas"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_user)],
)


@router.get("", response_model=ResponseModel[PageResponse[DramaDetailResponse]])
def list_dramas(
    service: DramaServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    drama_status: Annotated[DramaStatus | None, Query(alias="status")] = None,
    name_contains: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    tag_ids: Annotated[
        str | None,
        Query(pattern=r"^\d+(,\d+)*$", max_length=500),
    ] = None,
) -> ResponseModel[PageResponse[DramaDetailResponse]]:
    result = service.list_dramas(
        page=page,
        page_size=page_size,
        status=drama_status,
        name_contains=name_contains,
        tag_ids=tuple(int(value) for value in tag_ids.split(",")) if tag_ids else (),
    )
    return page_response(result, DramaDetailResponse)


@router.get("/{drama_id}", response_model=ResponseModel[DramaDetailResponse])
def get_drama(
    service: DramaServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DramaDetailResponse]:
    return item_response(service.get_drama(drama_id), DramaDetailResponse)


@router.post(
    "",
    response_model=ResponseModel[DramaDetailResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_drama(
    payload: DramaCreateRequest,
    service: DramaServiceDependency,
) -> ResponseModel[DramaDetailResponse]:
    entity = service.create_drama(payload.model_dump(exclude_unset=True))
    return item_response(entity, DramaDetailResponse)


@router.put(
    "/{drama_id}",
    response_model=ResponseModel[DramaDetailResponse],
    dependencies=[Depends(require_admin)],
)
def update_drama(
    payload: DramaUpdateRequest,
    service: DramaServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DramaDetailResponse]:
    entity = service.update_drama(
        drama_id,
        payload.model_dump(exclude_unset=True),
    )
    return item_response(entity, DramaDetailResponse)


@router.delete(
    "/{drama_id}",
    response_model=ResponseModel[DramaDetailResponse],
    dependencies=[Depends(require_admin)],
)
def delete_drama(
    service: DramaServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DramaDetailResponse]:
    return item_response(service.deactivate_drama(drama_id), DramaDetailResponse)
