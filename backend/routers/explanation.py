"""Authenticated read-only Explanation and Lineage endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query

from auth.dependencies import AuthenticatedUserDependency
from routers.dependencies import AnalysisExplanationQueryServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import page_response
from schemas.common import PageResponse, ResponseModel
from schemas.explanation import (
    ExplanationEntityType,
    ExplanationModuleType,
    ExplanationResponse,
    LineageRelationshipType,
    LineageResponse,
    LineageSourceType,
    LineageTargetType,
)

router = APIRouter(
    prefix="/explanations",
    tags=["explanations"],
    responses=ERROR_RESPONSES,
)

lineage_router = APIRouter(
    prefix="/lineage",
    tags=["lineage"],
    responses=ERROR_RESPONSES,
)


@router.get(
    "/{entity_type}/{entity_id}",
    response_model=ResponseModel[PageResponse[ExplanationResponse]],
)
def get_explanations(
    _current_user: AuthenticatedUserDependency,
    service: AnalysisExplanationQueryServiceDependency,
    entity_type: Annotated[ExplanationEntityType, Path()],
    entity_id: Annotated[int, Path(ge=1)],
    module_type: Annotated[ExplanationModuleType | None, Query()] = None,
    analysis_as_of: Annotated[datetime | None, Query()] = None,
    algorithm_version: Annotated[str | None, Query(min_length=1)] = None,
    rule_set_version: Annotated[str | None, Query(min_length=1)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResponseModel[PageResponse[ExplanationResponse]]:
    result = service.get_explanations(
        entity_type=entity_type,
        entity_id=entity_id,
        module_type=module_type,
        analysis_as_of=analysis_as_of,
        algorithm_version=algorithm_version,
        rule_set_version=rule_set_version,
        page=page,
        page_size=page_size,
    )
    return page_response(result, ExplanationResponse)


@lineage_router.get(
    "/{target_type}/{target_id}",
    response_model=ResponseModel[PageResponse[LineageResponse]],
)
def get_lineage(
    _current_user: AuthenticatedUserDependency,
    service: AnalysisExplanationQueryServiceDependency,
    target_type: Annotated[LineageTargetType, Path()],
    target_id: Annotated[int, Path(ge=1)],
    source_type: Annotated[LineageSourceType | None, Query()] = None,
    relationship_type: Annotated[LineageRelationshipType | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResponseModel[PageResponse[LineageResponse]]:
    result = service.get_lineage(
        target_type=target_type,
        target_id=target_id,
        source_type=source_type,
        relationship_type=relationship_type,
        page=page,
        page_size=page_size,
    )
    return page_response(result, LineageResponse)


__all__ = ("lineage_router", "router")
