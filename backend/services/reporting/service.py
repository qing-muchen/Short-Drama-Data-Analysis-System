"""Read-only orchestration for the Phase 10 reporting center."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol

from services.reporting.contracts import (
    AnalysisSnapshot,
    ExportDescriptor,
    ExportFormat,
    ReportAvailability,
    ReportAvailabilityReason,
    ReportAvailabilityStatus,
    ReportFilter,
    ReportMetadata,
    ReportRequest,
    ReportResponse,
    ReportRow,
    ReportSchema,
    ReportType,
)
from services.reporting.policies import (
    ExportDecision,
    ExportDecisionStatus,
    ExportLimitPolicy,
    ReportFilterPolicy,
)
from services.reporting.providers import ReportProviderRegistry
from services.reporting.registry import ReportSchemaRegistry


logger = logging.getLogger(__name__)


class Clock(Protocol):
    """Injectable request clock read once at a public Service boundary."""

    def now(self) -> datetime: ...


class SystemClock:
    """UTC production clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class ReportAvailabilityError(RuntimeError):
    """Structured provider failure whose availability must be preserved."""

    def __init__(self, availability: ReportAvailability) -> None:
        if availability.status in {
            ReportAvailabilityStatus.AVAILABLE,
            ReportAvailabilityStatus.EMPTY,
        }:
            raise ValueError(
                "provider availability errors require a failure status"
            )
        super().__init__(availability.message or availability.status.value)
        self.availability = availability


@dataclass(frozen=True, slots=True)
class ReportExportPreparation:
    """Serializer-independent export input and policy decision."""

    report: ReportResponse
    schema: ReportSchema
    descriptor: ExportDescriptor
    decision: ExportDecision | None


class ReportingService:
    """Validate and orchestrate report catalog, preview, and export inputs."""

    def __init__(
        self,
        *,
        schema_registry: ReportSchemaRegistry,
        provider_registry: ReportProviderRegistry,
        filter_policy: ReportFilterPolicy,
        export_limit_policy: ExportLimitPolicy,
        clock: Clock,
    ) -> None:
        self._schema_registry = schema_registry
        self._provider_registry = provider_registry
        self._filter_policy = filter_policy
        self._export_limit_policy = export_limit_policy
        self._clock = clock

    def get_catalog(self) -> tuple[ReportSchema, ...]:
        """Return the explicitly registered immutable report catalog."""

        return self._schema_registry.list_schemas()

    def preview_report(
        self,
        *,
        report_type: ReportType,
        filters: Mapping[str, Any] | None = None,
        analysis_as_of: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> ReportResponse:
        """Build a bounded report preview without generating a file."""

        self._validate_preview_window(offset, limit)
        schema, request, snapshot, _ = self._prepare_request(
            report_type=report_type,
            filters=filters,
            analysis_as_of=analysis_as_of,
            export_format=None,
        )
        return self._build_response(
            schema=schema,
            request=request,
            snapshot=snapshot,
            offset=offset,
            limit=limit,
        )

    def prepare_export(
        self,
        *,
        report_type: ReportType,
        export_format: ExportFormat,
        filters: Mapping[str, Any] | None = None,
        analysis_as_of: datetime | None = None,
        confirmed_row_count: int | None = None,
    ) -> ReportExportPreparation:
        """Prepare schema-bound rows and descriptor; never serialize a file."""

        schema, request, snapshot, has_effective_filters = self._prepare_request(
            report_type=report_type,
            filters=filters,
            analysis_as_of=analysis_as_of,
            export_format=export_format,
        )
        descriptor = self._select_descriptor(schema, export_format)
        provider = self._provider_registry.get_provider(report_type)

        try:
            total_rows = provider.count(request)
        except Exception as exc:
            logger.exception(
                "report provider count failed during export preparation",
                extra={"report_type": report_type.value},
            )
            return ReportExportPreparation(
                report=self._provider_failure_response(schema, snapshot, exc),
                schema=schema,
                descriptor=descriptor,
                decision=None,
            )

        decision = self._export_limit_policy.evaluate_rows(
            total_rows=total_rows,
            export_format=export_format,
            has_effective_filters=has_effective_filters,
            confirmed_row_count=confirmed_row_count,
        )
        if decision.status is not ExportDecisionStatus.ALLOW:
            availability = self._availability_for_export_decision(decision)
            return ReportExportPreparation(
                report=self._response(
                    schema=schema,
                    snapshot=snapshot,
                    total_rows=total_rows,
                    rows=(),
                    availability=availability,
                ),
                schema=schema,
                descriptor=descriptor,
                decision=decision,
            )

        try:
            rows = provider.list_rows(request, offset=0, limit=total_rows)
        except Exception as exc:
            logger.exception(
                "report provider rows failed during export preparation",
                extra={"report_type": report_type.value},
            )
            return ReportExportPreparation(
                report=self._provider_failure_response(schema, snapshot, exc),
                schema=schema,
                descriptor=descriptor,
                decision=decision,
            )

        return ReportExportPreparation(
            report=self._response(
                schema=schema,
                snapshot=snapshot,
                total_rows=total_rows,
                rows=rows,
                availability=self._availability_for_rows(total_rows),
            ),
            schema=schema,
            descriptor=descriptor,
            decision=decision,
        )

    def _prepare_request(
        self,
        *,
        report_type: ReportType,
        filters: Mapping[str, Any] | None,
        analysis_as_of: datetime | None,
        export_format: ExportFormat | None,
    ) -> tuple[ReportSchema, ReportRequest, AnalysisSnapshot, bool]:
        if not isinstance(report_type, ReportType):
            raise ValueError("report_type must be a ReportType")
        if export_format is not None and not isinstance(export_format, ExportFormat):
            raise ValueError("export_format must be an ExportFormat")

        schema = self._schema_registry.get_schema(report_type)
        validated = self._filter_policy.validate(report_type, filters)
        resolved_as_of = self._resolve_analysis_as_of(analysis_as_of)
        snapshot = AnalysisSnapshot(
            requested_at=resolved_as_of,
            analysis_as_of=resolved_as_of,
            timezone="UTC",
            semantics=schema.snapshot_semantics,
        )
        request = ReportRequest(
            report_type=report_type,
            filters=tuple(
                ReportFilter(key, value)
                for key, value in validated.items
                if value is not None
            ),
            analysis_as_of=resolved_as_of,
            export_format=export_format,
        )
        return schema, request, snapshot, validated.has_effective_filters

    def _build_response(
        self,
        *,
        schema: ReportSchema,
        request: ReportRequest,
        snapshot: AnalysisSnapshot,
        offset: int,
        limit: int,
    ) -> ReportResponse:
        provider = self._provider_registry.get_provider(request.report_type)
        try:
            total_rows = provider.count(request)
            rows = provider.list_rows(request, offset=offset, limit=limit)
        except Exception as exc:
            logger.exception(
                "report provider failed during preview",
                extra={"report_type": request.report_type.value},
            )
            return self._provider_failure_response(schema, snapshot, exc)

        return self._response(
            schema=schema,
            snapshot=snapshot,
            total_rows=total_rows,
            rows=rows,
            availability=self._availability_for_rows(total_rows),
        )

    @staticmethod
    def _response(
        *,
        schema: ReportSchema,
        snapshot: AnalysisSnapshot,
        total_rows: int,
        rows: tuple[ReportRow, ...],
        availability: ReportAvailability,
    ) -> ReportResponse:
        return ReportResponse(
            metadata=ReportMetadata(
                report_type=schema.report_type,
                title=schema.name,
                description=schema.description,
                schema_version=schema.schema_version,
                snapshot=snapshot,
                total_rows=total_rows,
            ),
            columns=schema.columns,
            rows=rows,
            availability=availability,
        )

    @classmethod
    def _unavailable_response(
        cls,
        schema: ReportSchema,
        snapshot: AnalysisSnapshot,
    ) -> ReportResponse:
        return cls._response(
            schema=schema,
            snapshot=snapshot,
            total_rows=0,
            rows=(),
            availability=ReportAvailability(
                ReportAvailabilityStatus.NOT_AVAILABLE,
                (ReportAvailabilityReason.MISSING_SOURCE,),
                "Report source is temporarily unavailable.",
            ),
        )

    @classmethod
    def _provider_failure_response(
        cls,
        schema: ReportSchema,
        snapshot: AnalysisSnapshot,
        error: Exception,
    ) -> ReportResponse:
        if isinstance(error, ReportAvailabilityError):
            return cls._response(
                schema=schema,
                snapshot=snapshot,
                total_rows=0,
                rows=(),
                availability=error.availability,
            )
        return cls._unavailable_response(schema, snapshot)

    @staticmethod
    def _availability_for_rows(total_rows: int) -> ReportAvailability:
        if total_rows == 0:
            return ReportAvailability(
                ReportAvailabilityStatus.EMPTY,
                (ReportAvailabilityReason.NO_MATCHING_DATA,),
                "No rows match the report request.",
            )
        return ReportAvailability(ReportAvailabilityStatus.AVAILABLE)

    @staticmethod
    def _availability_for_export_decision(
        decision: ExportDecision,
    ) -> ReportAvailability:
        if decision.code == "EMPTY_REPORT":
            return ReportingService._availability_for_rows(0)
        if decision.status is ExportDecisionStatus.REQUIRE_CONFIRMATION:
            return ReportAvailability(ReportAvailabilityStatus.AVAILABLE)
        return ReportAvailability(
            ReportAvailabilityStatus.NOT_AVAILABLE,
            (ReportAvailabilityReason.LIMIT_EXCEEDED,),
            "Export exceeds the configured limit.",
        )

    @staticmethod
    def _select_descriptor(
        schema: ReportSchema,
        export_format: ExportFormat,
    ) -> ExportDescriptor:
        for descriptor in schema.export_descriptors:
            if descriptor.format is export_format:
                return descriptor
        raise ValueError(
            f"format {export_format.value} is not supported for "
            f"{schema.report_type.value}"
        )

    def _resolve_analysis_as_of(self, value: datetime | None) -> datetime:
        candidate = self._clock.now() if value is None else value
        if not isinstance(candidate, datetime):
            raise TypeError("analysis_as_of must be a datetime")
        if candidate.tzinfo is None or candidate.utcoffset() is None:
            raise ValueError("analysis_as_of must be timezone-aware")
        return candidate.astimezone(UTC)

    @staticmethod
    def _validate_preview_window(offset: int, limit: int) -> None:
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > 100
        ):
            raise ValueError("limit must be between 1 and 100")


__all__ = (
    "Clock",
    "ReportAvailabilityError",
    "ReportExportPreparation",
    "ReportingService",
    "SystemClock",
)
