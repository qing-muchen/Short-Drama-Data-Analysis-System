"""Read-only user endpoints; authentication and account writes are deferred."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from routers.dependencies import UserServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.user import UserResponse, UserStatus

router = APIRouter(prefix="/users", tags=["users"], responses=ERROR_RESPONSES)


@router.get("", response_model=ResponseModel[PageResponse[UserResponse]])
def list_users(
    service: UserServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: UserStatus | None = None,
) -> ResponseModel[PageResponse[UserResponse]]:
    result = service.list_users(page=page, page_size=page_size, status=status)
    return page_response(result, UserResponse)


@router.get("/{user_id}", response_model=ResponseModel[UserResponse])
def get_user(
    service: UserServiceDependency,
    user_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[UserResponse]:
    return item_response(service.get_user(user_id), UserResponse)
