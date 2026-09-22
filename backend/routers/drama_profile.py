"""Read-only Drama 360° profile endpoint."""

from typing import Annotated

from fastapi import APIRouter, Path

from auth.dependencies import AuthenticatedUserDependency
from routers.dependencies import DramaProfileServiceDependency
from routers.errors import ERROR_RESPONSES
from schemas.common import ResponseModel
from schemas.drama_profile import DramaProfileResponseSchema

router = APIRouter(
    prefix="/dramas",
    tags=["drama-profile"],
    responses=ERROR_RESPONSES,
)


@router.get(
    "/{drama_id}/profile",
    response_model=ResponseModel[DramaProfileResponseSchema],
)
def get_drama_profile(
    _current_user: AuthenticatedUserDependency,
    service: DramaProfileServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DramaProfileResponseSchema]:
    profile = service.get_profile(drama_id)
    return ResponseModel(
        data=DramaProfileResponseSchema.model_validate(profile, from_attributes=True)
    )


__all__ = ["router"]
