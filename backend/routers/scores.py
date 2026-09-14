"""Authenticated Composite Score V1.0 calculation and query endpoints."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from auth.dependencies import AdministratorDependency, AuthenticatedUserDependency
from routers.dependencies import ScoreServiceDependency
from routers.errors import ERROR_RESPONSES
from schemas.common import PageResponse, ResponseModel
from schemas.score import (
    DramaScoreResponse,
    ScoreCalculateRequest,
    ScoreCalculationResponse,
    ScoreLevel,
    ScoreLevelCountResponse,
    ScoreLevelDistributionResponse,
    ScoreRankingItemResponse,
)
from services.exceptions import NotFoundException
from services.score_service import (
    COMPOSITE_SCORE_VERSION,
    SCORE_SCOPE_ID,
    SCORE_SCOPE_TYPE,
)

router = APIRouter(
    prefix="/scores",
    tags=["scores"],
    responses=ERROR_RESPONSES,
)
SCORE_LEVEL_ORDER: tuple[ScoreLevel, ...] = ("S", "A", "B", "C")


@router.post(
    "/calculate",
    response_model=ResponseModel[ScoreCalculationResponse],
)
def calculate_scores(
    payload: ScoreCalculateRequest,
    administrator: AdministratorDependency,
    service: ScoreServiceDependency,
) -> ResponseModel[ScoreCalculationResponse]:
    result = service.calculate_scores(
        payload.score_date,
        administrator_id=administrator.user_id,
    )
    return ResponseModel(data=ScoreCalculationResponse.model_validate(result))


@router.get(
    "/ranking",
    response_model=ResponseModel[PageResponse[ScoreRankingItemResponse]],
)
def get_ranking(
    current_user: AuthenticatedUserDependency,
    service: ScoreServiceDependency,
    score_date: Annotated[date, Query()],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    level: Annotated[ScoreLevel | None, Query()] = None,
) -> ResponseModel[PageResponse[ScoreRankingItemResponse]]:
    del current_user
    result = service.get_ranking(
        score_date,
        page=page,
        page_size=page_size,
        level=level,
    )
    start_rank = (result.page - 1) * result.page_size
    payload = PageResponse[ScoreRankingItemResponse](
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[
            ScoreRankingItemResponse(
                rank=start_rank + offset,
                **_score_values(entity),
            )
            for offset, entity in enumerate(result.items, start=1)
        ],
    )
    return ResponseModel(data=payload)


@router.get(
    "/level-distribution",
    response_model=ResponseModel[ScoreLevelDistributionResponse],
)
def get_level_distribution(
    current_user: AuthenticatedUserDependency,
    service: ScoreServiceDependency,
    score_date: Annotated[date, Query()],
) -> ResponseModel[ScoreLevelDistributionResponse]:
    del current_user
    distribution = service.get_level_distribution(score_date)
    items = [
        ScoreLevelCountResponse(level=level, count=distribution[level])
        for level in SCORE_LEVEL_ORDER
    ]
    return ResponseModel(
        data=ScoreLevelDistributionResponse(
            score_date=score_date,
            algorithm_version=COMPOSITE_SCORE_VERSION,
            score_scope_type=SCORE_SCOPE_TYPE,
            score_scope_id=SCORE_SCOPE_ID,
            total=sum(item.count for item in items),
            items=items,
        )
    )


@router.get(
    "/{drama_id}",
    response_model=ResponseModel[DramaScoreResponse],
)
def get_drama_score(
    current_user: AuthenticatedUserDependency,
    service: ScoreServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[DramaScoreResponse]:
    del current_user
    entity = service.get_drama_score(drama_id)
    if entity is None:
        raise NotFoundException(
            "Drama score was not found",
            details={"drama_id": drama_id},
        )
    return ResponseModel(data=DramaScoreResponse(**_score_values(entity)))


def _score_values(entity: Any) -> dict[str, Any]:
    """Flatten the eagerly loaded drama identity for the HTTP response only."""

    return {
        "score_id": entity.score_id,
        "drama_id": entity.drama_id,
        "drama_code": entity.drama.drama_code,
        "drama_name": entity.drama.drama_name,
        "score_date": entity.score_date,
        "score_scope_type": entity.score_scope_type,
        "score_scope_id": entity.score_scope_id,
        "analysis_as_of": entity.analysis_as_of,
        "heat_score": entity.heat_score,
        "growth_score": entity.growth_score,
        "engagement_score": entity.engagement_score,
        "lifecycle_score": entity.lifecycle_score,
        "total_score": entity.total_score,
        "level": entity.level,
        "algorithm_version": entity.algorithm_version,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }
