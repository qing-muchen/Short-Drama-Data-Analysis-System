"""Authenticated Dashboard endpoints over AnalyticsService results."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from auth.dependencies import require_user
from dashboard.constants import DEFAULT_RANKING_LIMIT, MAX_RANKING_LIMIT
from dashboard.schemas import (
    DashboardOverviewResponse,
    QualitySummaryResponse,
    RankingResponse,
    TagDistributionResponse,
    TrendResponse,
)
from routers.dependencies import DashboardServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response
from schemas.analytics import AnalysisContextRequest
from schemas.common import ResponseModel

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_user)],
)


def _context(
    *,
    analysis_as_of: datetime | None,
    time_window: Literal["24H", "7D", "30D"],
    platform_scope: list[int] | None,
    tag_scope: list[int] | None,
):
    return AnalysisContextRequest(
        analysis_as_of=analysis_as_of or datetime.now(UTC),
        time_window=time_window,
        granularity="DRAMA_OVERALL",
        platform_scope=platform_scope or [],
        tag_scope=tag_scope or [],
    ).to_domain()


@router.get("/overview", response_model=ResponseModel[DashboardOverviewResponse])
def overview(
    service: DashboardServiceDependency,
    analysis_as_of: Annotated[datetime | None, Query()] = None,
    time_window: Annotated[Literal["24H", "7D", "30D"], Query()] = "30D",
    platform_scope: Annotated[list[int] | None, Query()] = None,
    tag_scope: Annotated[list[int] | None, Query()] = None,
) -> ResponseModel[DashboardOverviewResponse]:
    context = _context(
        analysis_as_of=analysis_as_of,
        time_window=time_window,
        platform_scope=platform_scope,
        tag_scope=tag_scope,
    )
    return item_response(service.overview(context), DashboardOverviewResponse)


@router.get("/rankings/heat", response_model=ResponseModel[list[RankingResponse]])
def heat_ranking(
    service: DashboardServiceDependency,
    limit: Annotated[int, Query(ge=1, le=MAX_RANKING_LIMIT)] = DEFAULT_RANKING_LIMIT,
    analysis_as_of: Annotated[datetime | None, Query()] = None,
    time_window: Annotated[Literal["24H", "7D", "30D"], Query()] = "30D",
    platform_scope: Annotated[list[int] | None, Query()] = None,
    tag_scope: Annotated[list[int] | None, Query()] = None,
) -> ResponseModel[list[RankingResponse]]:
    context = _context(
        analysis_as_of=analysis_as_of,
        time_window=time_window,
        platform_scope=platform_scope,
        tag_scope=tag_scope,
    )
    return ResponseModel(
        data=[RankingResponse.model_validate(item) for item in service.heat_ranking(context, limit)]
    )


@router.get("/rankings/growth", response_model=ResponseModel[list[RankingResponse]])
def growth_ranking(
    service: DashboardServiceDependency,
    limit: Annotated[int, Query(ge=1, le=MAX_RANKING_LIMIT)] = DEFAULT_RANKING_LIMIT,
    analysis_as_of: Annotated[datetime | None, Query()] = None,
    time_window: Annotated[Literal["24H", "7D", "30D"], Query()] = "7D",
    platform_scope: Annotated[list[int] | None, Query()] = None,
    tag_scope: Annotated[list[int] | None, Query()] = None,
) -> ResponseModel[list[RankingResponse]]:
    context = _context(
        analysis_as_of=analysis_as_of,
        time_window=time_window,
        platform_scope=platform_scope,
        tag_scope=tag_scope,
    )
    return ResponseModel(
        data=[RankingResponse.model_validate(item) for item in service.growth_ranking(context, limit)]
    )


@router.get("/rankings/potential", response_model=ResponseModel[list[RankingResponse]])
def potential_ranking(
    service: DashboardServiceDependency,
    limit: Annotated[int, Query(ge=1, le=MAX_RANKING_LIMIT)] = DEFAULT_RANKING_LIMIT,
    analysis_as_of: Annotated[datetime | None, Query()] = None,
    time_window: Annotated[Literal["24H", "7D", "30D"], Query()] = "7D",
    platform_scope: Annotated[list[int] | None, Query()] = None,
    tag_scope: Annotated[list[int] | None, Query()] = None,
) -> ResponseModel[list[RankingResponse]]:
    context = _context(
        analysis_as_of=analysis_as_of,
        time_window=time_window,
        platform_scope=platform_scope,
        tag_scope=tag_scope,
    )
    return ResponseModel(
        data=[RankingResponse.model_validate(item) for item in service.potential_ranking(context, limit)]
    )


@router.get("/trend", response_model=ResponseModel[list[TrendResponse]])
def trend(
    service: DashboardServiceDependency,
    analysis_as_of: Annotated[datetime | None, Query()] = None,
    time_window: Annotated[Literal["24H", "7D", "30D"], Query()] = "30D",
    platform_scope: Annotated[list[int] | None, Query()] = None,
    tag_scope: Annotated[list[int] | None, Query()] = None,
) -> ResponseModel[list[TrendResponse]]:
    context = _context(
        analysis_as_of=analysis_as_of,
        time_window=time_window,
        platform_scope=platform_scope,
        tag_scope=tag_scope,
    )
    return ResponseModel(
        data=[TrendResponse.model_validate(item) for item in service.trend(context)]
    )


@router.get("/quality", response_model=ResponseModel[QualitySummaryResponse])
def quality(
    service: DashboardServiceDependency,
    analysis_as_of: Annotated[datetime | None, Query()] = None,
    time_window: Annotated[Literal["24H", "7D", "30D"], Query()] = "30D",
    platform_scope: Annotated[list[int] | None, Query()] = None,
    tag_scope: Annotated[list[int] | None, Query()] = None,
) -> ResponseModel[QualitySummaryResponse]:
    context = _context(
        analysis_as_of=analysis_as_of,
        time_window=time_window,
        platform_scope=platform_scope,
        tag_scope=tag_scope,
    )
    return item_response(service.quality(context), QualitySummaryResponse)


@router.get("/tags", response_model=ResponseModel[list[TagDistributionResponse]])
def tag_distribution(
    service: DashboardServiceDependency,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> ResponseModel[list[TagDistributionResponse]]:
    return ResponseModel(
        data=[
            TagDistributionResponse.model_validate(item)
            for item in service.tag_distribution(limit)
        ]
    )
