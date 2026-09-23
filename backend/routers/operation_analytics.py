"""Read-only HTTP endpoints for Phase 8 operation analytics."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query

from auth.dependencies import AuthenticatedUserDependency
from routers.dependencies import OperationAnalyticsServiceDependency
from routers.errors import ERROR_RESPONSES
from schemas.common import ResponseModel
from schemas.operation_analytics import (
    BenchmarkResponseSchema,
    LifecycleResponseSchema,
    OperationEffectivenessPageResponseSchema,
)


router = APIRouter(tags=["operation-analytics"], responses=ERROR_RESPONSES)


@router.get(
    "/operations/effectiveness",
    response_model=ResponseModel[OperationEffectivenessPageResponseSchema],
)
def get_operation_effectiveness(
    _current_user: AuthenticatedUserDependency,
    service: OperationAnalyticsServiceDependency,
    action_id: Annotated[int | None, Query(ge=1)] = None,
    drama_id: Annotated[int | None, Query(ge=1)] = None,
    analysis_as_of: Annotated[
        datetime | None,
        Query(description="Timezone-aware analysis cutoff; normalized to UTC"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResponseModel[OperationEffectivenessPageResponseSchema]:
    result = service.get_operation_effectiveness(
        action_id=action_id,
        drama_id=drama_id,
        analysis_as_of=analysis_as_of,
        page=page,
        page_size=page_size,
    )
    return ResponseModel(
        data=OperationEffectivenessPageResponseSchema.model_validate(
            result,
            from_attributes=True,
        )
    )


# Register this static path before the dynamic drama lifecycle path and before
# the general drama router so "benchmark" is never parsed as a drama ID.
@router.get(
    "/dramas/benchmark",
    response_model=ResponseModel[BenchmarkResponseSchema],
)
def get_benchmark(
    _current_user: AuthenticatedUserDependency,
    service: OperationAnalyticsServiceDependency,
    drama_ids: Annotated[
        list[int],
        Query(min_length=2, max_length=20, description="2-20 unique drama IDs"),
    ],
    platform_id: Annotated[int, Query(ge=1)],
    analysis_as_of: Annotated[
        datetime | None,
        Query(description="Timezone-aware analysis cutoff; normalized to UTC"),
    ] = None,
) -> ResponseModel[BenchmarkResponseSchema]:
    result = service.get_benchmark(
        drama_ids=drama_ids,
        platform_id=platform_id,
        analysis_as_of=analysis_as_of,
    )
    return ResponseModel(
        data=BenchmarkResponseSchema.model_validate(result, from_attributes=True)
    )


@router.get(
    "/dramas/{drama_id}/lifecycle",
    response_model=ResponseModel[LifecycleResponseSchema],
)
def get_lifecycle(
    _current_user: AuthenticatedUserDependency,
    service: OperationAnalyticsServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
    analysis_as_of: Annotated[
        datetime | None,
        Query(description="Timezone-aware analysis cutoff; normalized to UTC"),
    ] = None,
) -> ResponseModel[LifecycleResponseSchema]:
    result = service.get_lifecycle(
        drama_id=drama_id,
        analysis_as_of=analysis_as_of,
    )
    return ResponseModel(
        data=LifecycleResponseSchema.model_validate(result, from_attributes=True)
    )


__all__ = ["router"]
