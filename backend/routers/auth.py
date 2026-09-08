"""Login and current-user endpoints; registration is intentionally absent."""

from fastapi import APIRouter

from auth.dependencies import AuthServiceDependency, CurrentUserDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response
from schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse
from schemas.common import ResponseModel

router = APIRouter(prefix="/auth", tags=["authentication"], responses=ERROR_RESPONSES)


@router.post("/login", response_model=ResponseModel[TokenResponse])
def login(
    payload: LoginRequest,
    service: AuthServiceDependency,
) -> ResponseModel[TokenResponse]:
    access_token, expires_in_seconds = service.login(
        payload.username,
        payload.password.get_secret_value(),
    )
    return ResponseModel[TokenResponse](
        data=TokenResponse(
            access_token=access_token,
            expires_in_seconds=expires_in_seconds,
        )
    )


@router.get("/me", response_model=ResponseModel[CurrentUserResponse])
def current_user(user: CurrentUserDependency) -> ResponseModel[CurrentUserResponse]:
    return item_response(user, CurrentUserResponse)
