"""Authenticated Phase 2 data-quality calculation and query endpoints."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

from auth.dependencies import AdministratorDependency, AuthenticatedUserDependency
from routers.dependencies import DataQualityServiceDependency
from routers.errors import ERROR_RESPONSES
from schemas.common import ResponseModel
from schemas.data_quality import (
    DataQualityCalculateRequest,
    DataQualityCalculationResponse,
    DataQualityHistoryItemResponse,
    DataQualityHistoryResponse,
    DataQualityRuleListResponse,
    DataQualityRuleResponse,
    DataQualityRuleResultResponse,
    DataQualityScoreResponse,
    QualityAlgorithmVersion,
)
from services.exceptions import NotFoundException

router = APIRouter(
    prefix="/data-quality",
    tags=["data-quality"],
    responses=ERROR_RESPONSES,
)


@router.post(
    "/calculate",
    response_model=ResponseModel[DataQualityCalculationResponse],
)
def calculate_quality_score(
    payload: DataQualityCalculateRequest,
    administrator: AdministratorDependency,
    service: DataQualityServiceDependency,
) -> ResponseModel[DataQualityCalculationResponse]:
    result = service.calculate_quality_score(
        payload.score_date,
        administrator_id=administrator.user_id,
        algorithm_version=payload.algorithm_version,
    )
    return ResponseModel(
        data=DataQualityCalculationResponse.model_validate(result)
    )


@router.get(
    "/score",
    response_model=ResponseModel[DataQualityScoreResponse],
)
def get_current_quality_score(
    current_user: AuthenticatedUserDependency,
    service: DataQualityServiceDependency,
    algorithm_version: Annotated[
        QualityAlgorithmVersion, Query()
    ] = "Quality Score V2.0",
) -> ResponseModel[DataQualityScoreResponse]:
    del current_user
    entity = service.get_current_quality_score(
        algorithm_version=algorithm_version,
    )
    if entity is None:
        raise NotFoundException("Data quality score was not found")
    return ResponseModel(data=_score_response(entity))


@router.get(
    "/history",
    response_model=ResponseModel[DataQualityHistoryResponse],
)
def get_quality_history(
    current_user: AuthenticatedUserDependency,
    service: DataQualityServiceDependency,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=365)] = 90,
    algorithm_version: Annotated[
        QualityAlgorithmVersion, Query()
    ] = "Quality Score V2.0",
) -> ResponseModel[DataQualityHistoryResponse]:
    del current_user
    entities = service.get_quality_history(
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        algorithm_version=algorithm_version,
    )
    items = [
        DataQualityHistoryItemResponse(**_history_values(entity))
        for entity in entities
    ]
    return ResponseModel(
        data=DataQualityHistoryResponse(total=len(items), items=items)
    )


@router.get(
    "/rules",
    response_model=ResponseModel[DataQualityRuleListResponse],
)
def get_current_quality_rules(
    current_user: AuthenticatedUserDependency,
    service: DataQualityServiceDependency,
    algorithm_version: Annotated[
        QualityAlgorithmVersion, Query()
    ] = "Quality Score V2.0",
) -> ResponseModel[DataQualityRuleListResponse]:
    del current_user
    del algorithm_version
    current = service.get_current_quality_rules()
    items = [
        DataQualityRuleResponse.model_validate(rule)
        for rule in current.rules
    ]
    return ResponseModel(
        data=DataQualityRuleListResponse(
            rule_set_version=current.rule_set_version,
            rule_set_hash=current.rule_set_hash,
            total=len(items),
            items=items,
        )
    )


def _score_response(entity: Any) -> DataQualityScoreResponse:
    values = _history_values(entity)
    values.update(
        {
            "source_watermark": entity.source_watermark,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
            "rule_results": [
                DataQualityRuleResultResponse(
                    quality_rule_result_id=result.quality_rule_result_id,
                    quality_rule_id=result.quality_rule_id,
                    rule_code=result.rule.rule_code,
                    rule_version=result.rule.rule_version,
                    rule_name=result.rule.rule_name,
                    dimension=result.rule.dimension,
                    result_status=result.result_status,
                    applicable_count=result.applicable_count,
                    passed_count=result.passed_count,
                    failed_count=result.failed_count,
                    rule_score=result.rule_score,
                    not_applicable_reason=result.not_applicable_reason,
                    evidence_summary=result.evidence_summary,
                    created_at=result.created_at,
                )
                for result in entity.rule_results
            ],
        }
    )
    return DataQualityScoreResponse(**values)


def _history_values(entity: Any) -> dict[str, Any]:
    """Convert a Service result to the public transport representation."""

    return {
        "quality_score_id": entity.quality_score_id,
        "score_date": entity.score_date,
        "analysis_as_of": entity.analysis_as_of,
        "completeness_score": entity.completeness_score,
        "accuracy_score": entity.accuracy_score,
        "consistency_score": entity.consistency_score,
        "timeliness_score": entity.timeliness_score,
        "total_score": entity.total_score,
        "quality_grade": entity.quality_grade,
        "algorithm_version": entity.algorithm_version,
        "rule_set_version": entity.rule_set_version,
        "rule_set_hash": entity.rule_set_hash,
        "score_scope_type": entity.score_scope_type,
        "score_scope_id": entity.score_scope_id,
        "evaluated_entity_count": entity.evaluated_entity_count,
        "open_issue_count": entity.open_issue_count,
    }


__all__ = ("router",)
