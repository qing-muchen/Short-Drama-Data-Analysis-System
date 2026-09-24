"""Public HTTP schemas and DTO mappings for Phase 10 reporting."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from pydantic import Field

from schemas.common import SchemaModel
from services.reporting.contracts import (
    ReportAvailability,
    ReportColumn,
    ReportResponse,
    ReportSchema,
)


class ReportTypeSchema(str, Enum):
    DRAMA_CATALOG = "DRAMA_CATALOG"
    SCORE_RESULTS = "SCORE_RESULTS"
    DATA_QUALITY_RESULTS = "DATA_QUALITY_RESULTS"
    PREDICTION_RESULTS = "PREDICTION_RESULTS"
    ANOMALY_RECORDS = "ANOMALY_RECORDS"
    OPERATION_ACTIONS = "OPERATION_ACTIONS"


class ExportFormatSchema(str, Enum):
    CSV = "CSV"
    XLSX = "XLSX"


class ReportAvailabilityStatusSchema(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class ReportAvailabilityReasonSchema(str, Enum):
    NO_MATCHING_DATA = "NO_MATCHING_DATA"
    MISSING_SOURCE = "MISSING_SOURCE"
    UNSUPPORTED_FILTER = "UNSUPPORTED_FILTER"
    SOURCE_VERSION_MISMATCH = "SOURCE_VERSION_MISMATCH"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    EXPORT_FAILED = "EXPORT_FAILED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ReportColumnSchema(SchemaModel):
    name: str
    display_name: str
    data_type: str
    nullable: bool
    format: str | None = None


class ReportFilterDefinitionSchema(SchemaModel):
    key: str
    value_type: str
    required: bool
    default: str | int | datetime | None = None
    allowed_values: list[str] = Field(default_factory=list)


class ReportCatalogSchema(SchemaModel):
    report_type: ReportTypeSchema
    title: str
    description: str
    schema_version: str
    columns: list[ReportColumnSchema]
    filters: list[ReportFilterDefinitionSchema]
    supported_formats: list[ExportFormatSchema]
    snapshot_semantics: str


class ReportAvailabilitySchema(SchemaModel):
    status: ReportAvailabilityStatusSchema
    reasons: list[ReportAvailabilityReasonSchema] = Field(default_factory=list)
    message: str | None = None


class AnalysisSnapshotSchema(SchemaModel):
    requested_at: datetime
    analysis_as_of: datetime
    timezone: str
    semantics: str


class ReportMetadataSchema(SchemaModel):
    report_type: ReportTypeSchema
    title: str
    description: str
    schema_version: str
    snapshot: AnalysisSnapshotSchema
    total_rows: int = Field(ge=0)
    source_versions: list[str] = Field(default_factory=list)


class ReportPreviewSchema(SchemaModel):
    metadata: ReportMetadataSchema
    columns: list[ReportColumnSchema]
    rows: list[dict[str, Any]]
    availability: ReportAvailabilitySchema


class ReportExportResponse(SchemaModel):
    """Documentation model for a successful binary export response."""

    media_type: str
    filename: str
    headers: dict[str, str]


def report_column_schema(value: ReportColumn) -> ReportColumnSchema:
    return ReportColumnSchema(
        name=value.name,
        display_name=value.display_name,
        data_type=value.data_type.value,
        nullable=value.nullable,
        format=value.format,
    )


def report_catalog_schema(value: ReportSchema) -> ReportCatalogSchema:
    return ReportCatalogSchema(
        report_type=value.report_type.value,
        title=value.name,
        description=value.description,
        schema_version=value.schema_version,
        columns=[report_column_schema(column) for column in value.columns],
        filters=[
            ReportFilterDefinitionSchema(
                key=item.key,
                value_type=item.value_type,
                required=item.required,
                default=item.default,
                allowed_values=list(item.allowed_values),
            )
            for item in value.filters
        ],
        supported_formats=[item.value for item in value.supported_formats],
        snapshot_semantics=value.snapshot_semantics.value,
    )


def report_availability_schema(
    value: ReportAvailability,
) -> ReportAvailabilitySchema:
    return ReportAvailabilitySchema(
        status=value.status.value,
        reasons=[reason.value for reason in value.reasons],
        message=value.message,
    )


def report_preview_schema(value: ReportResponse) -> ReportPreviewSchema:
    snapshot = value.metadata.snapshot
    return ReportPreviewSchema(
        metadata=ReportMetadataSchema(
            report_type=value.metadata.report_type.value,
            title=value.metadata.title,
            description=value.metadata.description,
            schema_version=value.metadata.schema_version,
            snapshot=AnalysisSnapshotSchema(
                requested_at=snapshot.requested_at,
                analysis_as_of=snapshot.analysis_as_of,
                timezone=snapshot.timezone,
                semantics=snapshot.semantics.value,
            ),
            total_rows=value.metadata.total_rows,
            source_versions=list(value.metadata.source_versions),
        ),
        columns=[report_column_schema(column) for column in value.columns],
        rows=[dict(row.items()) for row in value.rows],
        availability=report_availability_schema(value.availability),
    )


def parse_report_filters(value: str | None) -> Mapping[str, Any] | None:
    """Parse one JSON object query value without applying report rules."""

    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("filters must be a valid JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError("filters must be a JSON object")
    if any(not isinstance(key, str) or not key.strip() for key in parsed):
        raise ValueError("filter keys must be non-blank strings")
    return parsed


__all__ = (
    "AnalysisSnapshotSchema",
    "ExportFormatSchema",
    "ReportAvailabilityReasonSchema",
    "ReportAvailabilitySchema",
    "ReportAvailabilityStatusSchema",
    "ReportCatalogSchema",
    "ReportColumnSchema",
    "ReportExportResponse",
    "ReportFilterDefinitionSchema",
    "ReportMetadataSchema",
    "ReportPreviewSchema",
    "ReportTypeSchema",
    "parse_report_filters",
    "report_catalog_schema",
    "report_preview_schema",
)
