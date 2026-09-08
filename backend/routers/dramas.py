"""Drama CRUD endpoints using the Service boundary."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from auth.dependencies import require_admin, require_user
from routers.dependencies import DramaServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.drama import DramaCreate, DramaResponse, DramaStatus, DramaUpdate

router = APIRouter(
    prefix="/dramas",
    tags=["dramas"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_user)],
)


@router.get("", response_model=ResponseModel[PageResponse[DramaResponse]])
def list_dramas(
    service: DramaServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    drama_status: Annotated[DramaStatus | None, Query(alias="status")] = None,
    name_contains: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> ResponseModel[PageResponse[DramaResponse]]:
    result = service.list_dramas(
        page=page,
        page_size=page_size,
        status=drama_status,
        name_contains=name_contains,
    )
    return page_response(result, DramaResponse)


@router.get("/{drama_id}", response_model=ResponseModel[DramaResponse])
def get_drama(
    service: DramaServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DramaResponse]:
    return item_response(service.get_drama(drama_id), DramaResponse)


@router.post(
    "",
    response_model=ResponseModel[DramaResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_drama(
    payload: DramaCreate,
    service: DramaServiceDependency,
) -> ResponseModel[DramaResponse]:
    entity = service.create_drama(payload.model_dump(exclude_unset=True))
    return item_response(entity, DramaResponse)


@router.put(
    "/{drama_id}",
    response_model=ResponseModel[DramaResponse],
    dependencies=[Depends(require_admin)],
)
def update_drama(
    payload: DramaUpdate,
    service: DramaServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DramaResponse]:
    entity = service.update_drama(
        drama_id,
        payload.model_dump(exclude_unset=True),
    )
    return item_response(entity, DramaResponse)


@router.delete(
    "/{drama_id}",
    response_model=ResponseModel[DramaResponse],
    dependencies=[Depends(require_admin)],
)
def delete_drama(
    service: DramaServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DramaResponse]:
    return item_response(service.deactivate_drama(drama_id), DramaResponse)
