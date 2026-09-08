"""Authenticated deterministic analytics endpoints."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query

from auth.dependencies import require_user
from routers.dependencies import AnalyticsServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response
from schemas.analytics import AnalysisContextRequest, AnalyticsSummaryResponse
from schemas.common import ResponseModel

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_user)],
)


@router.get(
    "/dramas/{drama_id}/summary",
    response_model=ResponseModel[AnalyticsSummaryResponse],
)
def get_drama_analytics_summary(
    service: AnalyticsServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
    analysis_as_of: Annotated[datetime | None, Query()] = None,
    time_window: Annotated[Literal["24H", "7D", "30D"], Query()] = "7D",
    granularity: Annotated[
        Literal["DRAMA_PLATFORM", "DRAMA_OVERALL"], Query()
    ] = "DRAMA_OVERALL",
    platform_scope: Annotated[list[int] | None, Query()] = None,
    tag_scope: Annotated[list[int] | None, Query()] = None,
) -> ResponseModel[AnalyticsSummaryResponse]:
    request_context = AnalysisContextRequest(
        analysis_as_of=analysis_as_of or datetime.now(UTC),
        time_window=time_window,
        granularity=granularity,
        platform_scope=platform_scope or [],
        tag_scope=tag_scope or [],
    )
    summary = service.get_drama_summary(drama_id, request_context.to_domain())
    return item_response(summary, AnalyticsSummaryResponse)

