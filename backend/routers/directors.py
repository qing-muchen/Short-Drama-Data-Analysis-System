"""Director master-data CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from auth.dependencies import require_admin, require_user
from routers.dependencies import MasterDataServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.master_data import (
    DirectorCreate,
    DirectorResponse,
    DirectorUpdate,
    EntityStatus,
)

router = APIRouter(
    prefix="/directors",
    tags=["directors"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_user)],
)


@router.get("", response_model=ResponseModel[PageResponse[DirectorResponse]])
def list_directors(
    service: MasterDataServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[EntityStatus | None, Query(alias="status")] = None,
    name_contains: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ResponseModel[PageResponse[DirectorResponse]]:
    result = service.list_directors(
        page=page,
        page_size=page_size,
        status=status_filter,
        name_contains=name_contains,
    )
    return page_response(result, DirectorResponse)


@router.get("/{director_id}", response_model=ResponseModel[DirectorResponse])
def get_director(
    service: MasterDataServiceDependency,
    director_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DirectorResponse]:
    return item_response(service.get_director(director_id), DirectorResponse)


@router.post(
    "",
    response_model=ResponseModel[DirectorResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_director(
    payload: DirectorCreate,
    service: MasterDataServiceDependency,
) -> ResponseModel[DirectorResponse]:
    return item_response(
        service.create_director(payload.model_dump(exclude_unset=True)),
        DirectorResponse,
    )


@router.put(
    "/{director_id}",
    response_model=ResponseModel[DirectorResponse],
    dependencies=[Depends(require_admin)],
)
def update_director(
    payload: DirectorUpdate,
    service: MasterDataServiceDependency,
    director_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DirectorResponse]:
    return item_response(
        service.update_director(
            director_id,
            payload.model_dump(exclude_unset=True),
        ),
        DirectorResponse,
    )


@router.delete(
    "/{director_id}",
    response_model=ResponseModel[DirectorResponse],
    dependencies=[Depends(require_admin)],
)
def delete_director(
    service: MasterDataServiceDependency,
    director_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DirectorResponse]:
    return item_response(service.deactivate_director(director_id), DirectorResponse)
