"""Read-only HTTP endpoints for Phase 9 data governance."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from auth.dependencies import AuthenticatedUserDependency
from routers.dependencies import DataGovernanceServiceDependency
from routers.errors import ERROR_RESPONSES
from schemas.common import ResponseModel
from schemas.data_governance import (
    CompletenessSchema,
    ConsistencySchema,
    DataGovernanceResponseSchema,
    FreshnessSchema,
    completeness_schema,
    consistency_schema,
    data_governance_response_schema,
    freshness_schema,
)


router = APIRouter(
    prefix="/data-quality",
    tags=["data-governance"],
    responses=ERROR_RESPONSES,
)

AnalysisAsOf = Annotated[
    AwareDatetime | None,
    Query(description="Timezone-aware analysis cutoff; normalized to UTC"),
]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get(
    "/overview",
    response_model=ResponseModel[DataGovernanceResponseSchema],
)
def get_data_governance_overview(
    _current_user: AuthenticatedUserDependency,
    service: DataGovernanceServiceDependency,
    analysis_as_of: AnalysisAsOf = None,
) -> ResponseModel[DataGovernanceResponseSchema]:
    result = service.get_overview(analysis_as_of=analysis_as_of)
    return ResponseModel(data=data_governance_response_schema(result))


@router.get(
    "/freshness",
    response_model=ResponseModel[FreshnessSchema],
)
def get_data_freshness(
    _current_user: AuthenticatedUserDependency,
    service: DataGovernanceServiceDependency,
    analysis_as_of: AnalysisAsOf = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ResponseModel[FreshnessSchema]:
    result = service.get_freshness(analysis_as_of=analysis_as_of)
    return ResponseModel(
        data=freshness_schema(result, page=page, page_size=page_size)
    )


@router.get(
    "/completeness",
    response_model=ResponseModel[CompletenessSchema],
)
def get_data_completeness(
    _current_user: AuthenticatedUserDependency,
    service: DataGovernanceServiceDependency,
    analysis_as_of: AnalysisAsOf = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ResponseModel[CompletenessSchema]:
    result = service.get_completeness(analysis_as_of=analysis_as_of)
    return ResponseModel(
        data=completeness_schema(result, page=page, page_size=page_size)
    )


@router.get(
    "/consistency",
    response_model=ResponseModel[ConsistencySchema],
)
def get_data_consistency(
    _current_user: AuthenticatedUserDependency,
    service: DataGovernanceServiceDependency,
    analysis_as_of: AnalysisAsOf = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ResponseModel[ConsistencySchema]:
    result = service.get_consistency(analysis_as_of=analysis_as_of)
    return ResponseModel(
        data=consistency_schema(result, page=page, page_size=page_size)
    )


__all__ = ["router"]
