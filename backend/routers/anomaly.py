"""Authenticated Phase 4 anomaly-detection endpoints."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from auth.dependencies import AdministratorDependency, AuthenticatedUserDependency
from routers.dependencies import AnomalyServiceDependency
from routers.errors import ERROR_RESPONSES
from schemas.anomaly import (
    AnomalyCalculateRequest,
    AnomalyDetectionResponse,
    AnomalyResponse,
    AnomalySeverity,
    AnomalyStatisticsResponse,
    AnomalyStatus,
    AnomalyStatusUpdateRequest,
    AnomalyType,
    MetricType,
)
from schemas.common import PageResponse, ResponseModel
from services.exceptions import NotFoundException

router = APIRouter(
    prefix="/anomalies",
    tags=["anomalies"],
    responses=ERROR_RESPONSES,
)


@router.post(
    "/detect",
    response_model=ResponseModel[AnomalyDetectionResponse],
)
def detect_anomalies(
    payload: AnomalyCalculateRequest,
    administrator: AdministratorDependency,
    service: AnomalyServiceDependency,
) -> ResponseModel[AnomalyDetectionResponse]:
    result = service.detect_anomalies(
        payload.analysis_as_of,
        operator_user_id=administrator.user_id,
    )
    return ResponseModel(data=AnomalyDetectionResponse.model_validate(result))


@router.get(
    "/statistics",
    response_model=ResponseModel[AnomalyStatisticsResponse],
)
def get_statistics(
    current_user: AuthenticatedUserDependency,
    service: AnomalyServiceDependency,
) -> ResponseModel[AnomalyStatisticsResponse]:
    del current_user
    statistics = service.get_statistics()
    return ResponseModel(data=AnomalyStatisticsResponse(
        total_count=statistics.total_count,
        severity_distribution=statistics.severity_distribution,
        status_distribution=statistics.status_distribution,
        type_distribution=statistics.metric_distribution,
    ))


@router.get(
    "",
    response_model=ResponseModel[PageResponse[AnomalyResponse]],
)
def get_anomalies(
    current_user: AuthenticatedUserDependency,
    service: AnomalyServiceDependency,
    analysis_as_of: Annotated[datetime | None, Query()] = None,
    metric_type: Annotated[MetricType | None, Query()] = None,
    anomaly_type: Annotated[AnomalyType | None, Query()] = None,
    severity: Annotated[AnomalySeverity | None, Query()] = None,
    status: Annotated[AnomalyStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResponseModel[PageResponse[AnomalyResponse]]:
    del current_user
    result = service.get_anomalies(
        analysis_as_of=analysis_as_of,
        metric_type=metric_type,
        anomaly_type=anomaly_type,
        severity=severity,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ResponseModel(data=PageResponse(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[_anomaly_response(entity) for entity in result.items],
    ))


@router.patch(
    "/{record_id}/status",
    response_model=ResponseModel[AnomalyResponse],
)
def update_status(
    payload: AnomalyStatusUpdateRequest,
    administrator: AdministratorDependency,
    service: AnomalyServiceDependency,
    record_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[AnomalyResponse]:
    entity = service.update_status(
        record_id,
        payload.status,
        operator_user_id=administrator.user_id,
    )
    return ResponseModel(data=_anomaly_response(entity))


@router.get(
    "/{drama_id}",
    response_model=ResponseModel[list[AnomalyResponse]],
)
def get_drama_anomalies(
    current_user: AuthenticatedUserDependency,
    service: AnomalyServiceDependency,
    drama_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[list[AnomalyResponse]]:
    del current_user
    entities = service.get_drama_anomalies(drama_id)
    if not entities:
        raise NotFoundException(
            "Drama anomalies were not found",
            details={"drama_id": drama_id},
        )
    return ResponseModel(data=[_anomaly_response(entity) for entity in entities])


def _anomaly_response(entity: Any) -> AnomalyResponse:
    """Flatten the eagerly loaded Drama identity for HTTP only."""

    return AnomalyResponse(
        record_id=entity.anomaly_id,
        drama_id=entity.drama_id,
        drama_code=entity.drama.drama_code,
        drama_name=entity.drama.drama_name,
        metric_type=entity.metric_type,
        anomaly_type=entity.anomaly_type,
        severity=entity.severity,
        status=entity.status,
        analysis_as_of=entity.analysis_as_of,
        algorithm_version=entity.algorithm_version,
        evidence_summary=entity.evidence_summary,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


__all__ = ("router",)
