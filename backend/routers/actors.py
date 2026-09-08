"""Actor master-data CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from auth.dependencies import require_admin, require_user
from routers.dependencies import MasterDataServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.master_data import ActorCreate, ActorResponse, ActorUpdate, EntityStatus

router = APIRouter(
    prefix="/actors",
    tags=["actors"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_user)],
)


@router.get("", response_model=ResponseModel[PageResponse[ActorResponse]])
def list_actors(
    service: MasterDataServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[EntityStatus | None, Query(alias="status")] = None,
    name_contains: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ResponseModel[PageResponse[ActorResponse]]:
    result = service.list_actors(
        page=page,
        page_size=page_size,
        status=status_filter,
        name_contains=name_contains,
    )
    return page_response(result, ActorResponse)


@router.get("/{actor_id}", response_model=ResponseModel[ActorResponse])
def get_actor(
    service: MasterDataServiceDependency,
    actor_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[ActorResponse]:
    return item_response(service.get_actor(actor_id), ActorResponse)


@router.post(
    "",
    response_model=ResponseModel[ActorResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_actor(
    payload: ActorCreate,
    service: MasterDataServiceDependency,
) -> ResponseModel[ActorResponse]:
    return item_response(
        service.create_actor(payload.model_dump(exclude_unset=True)),
        ActorResponse,
    )


@router.put(
    "/{actor_id}",
    response_model=ResponseModel[ActorResponse],
    dependencies=[Depends(require_admin)],
)
def update_actor(
    payload: ActorUpdate,
    service: MasterDataServiceDependency,
    actor_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[ActorResponse]:
    return item_response(
        service.update_actor(actor_id, payload.model_dump(exclude_unset=True)),
        ActorResponse,
    )


@router.delete(
    "/{actor_id}",
    response_model=ResponseModel[ActorResponse],
    dependencies=[Depends(require_admin)],
)
def delete_actor(
    service: MasterDataServiceDependency,
    actor_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[ActorResponse]:
    return item_response(service.deactivate_actor(actor_id), ActorResponse)
