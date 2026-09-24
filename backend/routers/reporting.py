"""Read-only HTTP endpoints for Phase 10 reporting and export."""

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import AwareDatetime
from starlette.background import BackgroundTask

from auth.dependencies import AuthenticatedUserDependency
from routers.dependencies import ReportingServiceDependency
from routers.errors import ERROR_RESPONSES
from schemas.common import ResponseModel
from schemas.reporting import (
    ExportFormatSchema,
    ReportCatalogSchema,
    ReportPreviewSchema,
    ReportTypeSchema,
    parse_report_filters,
    report_catalog_schema,
    report_preview_schema,
)
from services.exceptions import ValidationException


router = APIRouter(
    prefix="/reports",
    tags=["reporting"],
    responses=ERROR_RESPONSES,
)

ReportTypeQuery = Annotated[ReportTypeSchema, Query(description="Report type")]
FiltersQuery = Annotated[
    str | None,
    Query(
        description=(
            "JSON object containing only filters declared by the report catalog"
        )
    ),
]
AnalysisAsOfQuery = Annotated[
    AwareDatetime | None,
    Query(description="Timezone-aware analysis cutoff; normalized to UTC"),
]
PageSizeQuery = Annotated[int, Query(ge=1, le=100)]
ExportFormatQuery = Annotated[
    ExportFormatSchema,
    Query(description="CSV or XLSX"),
]
ConfirmationQuery = Annotated[
    int | None,
    Query(
        ge=0,
        description="Exact row count returned by an earlier confirmation response",
    ),
]


def _filters(value: str | None):
    try:
        return parse_report_filters(value)
    except ValueError as exc:
        raise ValidationException(
            str(exc),
            code="INVALID_REPORT_FILTERS",
        ) from exc


@router.get(
    "/catalog",
    response_model=ResponseModel[list[ReportCatalogSchema]],
)
def get_report_catalog(
    _current_user: AuthenticatedUserDependency,
    service: ReportingServiceDependency,
) -> ResponseModel[list[ReportCatalogSchema]]:
    return ResponseModel(
        data=[report_catalog_schema(item) for item in service.get_catalog()]
    )


@router.get(
    "/preview",
    response_model=ResponseModel[ReportPreviewSchema],
)
def preview_report(
    report_type: ReportTypeQuery,
    _current_user: AuthenticatedUserDependency,
    service: ReportingServiceDependency,
    filters: FiltersQuery = None,
    analysis_as_of: AnalysisAsOfQuery = None,
    page_size: PageSizeQuery = 20,
) -> ResponseModel[ReportPreviewSchema]:
    result = service.preview_report(
        report_type=report_type,
        filters=_filters(filters),
        analysis_as_of=analysis_as_of,
        page_size=page_size,
    )
    return ResponseModel(data=report_preview_schema(result))


@router.get(
    "/export",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "CSV or XLSX report stream",
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
            },
        }
    },
)
def export_report(
    report_type: ReportTypeQuery,
    export_format: ExportFormatQuery,
    _current_user: AuthenticatedUserDependency,
    service: ReportingServiceDependency,
    filters: FiltersQuery = None,
    analysis_as_of: AnalysisAsOfQuery = None,
    confirmation: ConfirmationQuery = None,
) -> StreamingResponse:
    result = service.export_report(
        report_type=report_type,
        filters=_filters(filters),
        analysis_as_of=analysis_as_of,
        export_format=export_format,
        confirmation=confirmation,
    )
    return StreamingResponse(
        result.iter_bytes(),
        media_type=result.media_type,
        headers=result.headers,
        background=BackgroundTask(result.close),
    )


__all__ = ["router"]
