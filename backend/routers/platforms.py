"""Platform master-data CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from routers.dependencies import PlatformServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.platform import (
    PlatformCreate,
    PlatformResponse,
    PlatformStatus,
    PlatformUpdate,
)

router = APIRouter(prefix="/platforms", tags=["platforms"], responses=ERROR_RESPONSES)


@router.get("", response_model=ResponseModel[PageResponse[PlatformResponse]])
def list_platforms(
    service: PlatformServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[PlatformStatus | None, Query(alias="status")] = None,
    name_contains: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ResponseModel[PageResponse[PlatformResponse]]:
    result = service.list_platforms(
        page=page,
        page_size=page_size,
        status=status_filter,
        name_contains=name_contains,
    )
    return page_response(result, PlatformResponse)


@router.get("/{platform_id}", response_model=ResponseModel[PlatformResponse])
def get_platform(
    service: PlatformServiceDependency,
    platform_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[PlatformResponse]:
    return item_response(service.get_platform(platform_id), PlatformResponse)


@router.post(
    "",
    response_model=ResponseModel[PlatformResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_platform(
    payload: PlatformCreate,
    service: PlatformServiceDependency,
) -> ResponseModel[PlatformResponse]:
    return item_response(
        service.create_platform(payload.model_dump(exclude_unset=True)),
        PlatformResponse,
    )


@router.put("/{platform_id}", response_model=ResponseModel[PlatformResponse])
def update_platform(
    payload: PlatformUpdate,
    service: PlatformServiceDependency,
    platform_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[PlatformResponse]:
    return item_response(
        service.update_platform(
            platform_id,
            payload.model_dump(exclude_unset=True),
        ),
        PlatformResponse,
    )


@router.delete("/{platform_id}", response_model=ResponseModel[PlatformResponse])
def delete_platform(
    service: PlatformServiceDependency,
    platform_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[PlatformResponse]:
    return item_response(service.deactivate_platform(platform_id), PlatformResponse)
