"""Authenticated Prediction V1.0 endpoints."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from auth.dependencies import AdministratorDependency, AuthenticatedUserDependency
from routers.dependencies import PredictionServiceDependency
from routers.errors import ERROR_RESPONSES
from schemas.common import ResponseModel
from schemas.prediction import (
    PredictionCalculateRequest,
    PredictionHistoryResponse,
    PredictionResponse,
)
from services.exceptions import NotFoundException, ValidationException

router = APIRouter(
    prefix="/predictions",
    tags=["predictions"],
    responses=ERROR_RESPONSES,
)


@router.post(
    "/calculate",
    response_model=ResponseModel[PredictionResponse],
)
def calculate_prediction(
    payload: PredictionCalculateRequest,
    administrator: AdministratorDependency,
    service: PredictionServiceDependency,
) -> ResponseModel[PredictionResponse]:
    """Calculate one drama's next-day cumulative play-count prediction."""

    result = service.calculate_prediction(
        payload.drama_id,
        analysis_as_of=payload.analysis_as_of or datetime.now(UTC),
        administrator_id=administrator.user_id,
    )
    if result.prediction is None:
        raise ValidationException(
            "Prediction was not generated",
            details={"reason": result.skipped_reason or "UNKNOWN"},
        )
    return ResponseModel(data=_prediction_response(result.prediction))


@router.get(
    "/{drama_id}/history",
    response_model=ResponseModel[PredictionHistoryResponse],
)
def get_prediction_history(
    current_user: AuthenticatedUserDependency,
    service: PredictionServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResponseModel[PredictionHistoryResponse]:
    del current_user
    entities = service.get_prediction_history(drama_id, limit=limit)
    return ResponseModel(
        data=PredictionHistoryResponse(
            drama_id=drama_id,
            metric_type="PLAY_COUNT",
            algorithm_version="Moving Average V1.0",
            items=[_prediction_response(entity) for entity in entities],
        )
    )


@router.get(
    "/{drama_id}",
    response_model=ResponseModel[PredictionResponse],
)
def get_latest_prediction(
    current_user: AuthenticatedUserDependency,
    service: PredictionServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[PredictionResponse]:
    del current_user
    entity = service.get_latest_prediction(drama_id)
    if entity is None:
        raise NotFoundException(
            "Prediction was not found",
            details={"drama_id": drama_id},
        )
    return ResponseModel(data=_prediction_response(entity))


def _prediction_response(entity: Any) -> PredictionResponse:
    """Convert a Service result to the public DTO without ORM imports."""

    return PredictionResponse(
        prediction_id=entity.prediction_id,
        drama_id=entity.drama_id,
        metric_type=entity.metric_type,
        algorithm_version=entity.algorithm_version,
        analysis_as_of=entity.analysis_as_of,
        target_date=entity.target_date,
        predicted_value=float(entity.predicted_value),
        created_at=entity.created_at,
    )


__all__ = ("router",)
