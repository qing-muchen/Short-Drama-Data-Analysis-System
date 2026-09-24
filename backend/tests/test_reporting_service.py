"""Service orchestration tests for Phase 10 reporting."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from services.reporting.contracts import (
    ExportFormat,
    ReportAvailabilityReason,
    ReportAvailabilityStatus,
    ReportColumnType,
    ReportRequest,
    ReportRow,
    ReportType,
)
from services.reporting.policies import (
    ExportDecisionStatus,
    ExportLimitPolicy,
    ReportFilterPolicy,
)
from services.reporting.providers import ReportProviderRegistry
from services.reporting.registry import create_default_registry
from services.reporting.service import ReportAvailabilityError, ReportingService


AS_OF = datetime(2026, 9, 23, 8, 30, tzinfo=UTC)


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.value


class StubProvider:
    def __init__(self, report_type: ReportType, row: ReportRow) -> None:
        self.report_type = report_type
        self.row = row
        self.total_rows = 1
        self.count_error: Exception | None = None
        self.rows_error: Exception | None = None
        self.requests: list[ReportRequest] = []
        self.windows: list[tuple[int, int]] = []

    def count(self, request: ReportRequest) -> int:
        self.requests.append(request)
        if self.count_error is not None:
            raise self.count_error
        return self.total_rows

    def list_rows(
        self,
        request: ReportRequest,
        *,
        offset: int = 0,
        limit: int = 1000,
    ) -> tuple[ReportRow, ...]:
        self.requests.append(request)
        self.windows.append((offset, limit))
        if self.rows_error is not None:
            raise self.rows_error
        if self.total_rows == 0 or offset >= self.total_rows:
            return ()
        return (self.row,)


def _value_for(column_type: ReportColumnType, *, nullable: bool) -> object:
    if nullable:
        return None
    return {
        ReportColumnType.STRING: "value",
        ReportColumnType.INTEGER: 1,
        ReportColumnType.DECIMAL: Decimal("1.25"),
        ReportColumnType.BOOLEAN: True,
        ReportColumnType.DATE: AS_OF.date(),
        ReportColumnType.DATETIME: AS_OF,
    }[column_type]


def _row(report_type: ReportType) -> ReportRow:
    schema = create_default_registry().get_schema(report_type)
    return ReportRow(
        tuple(
            (
                column.name,
                _value_for(column.data_type, nullable=column.nullable),
            )
            for column in schema.columns
        )
    )


def _service(
    *,
    clock: FixedClock | None = None,
) -> tuple[ReportingService, dict[ReportType, StubProvider], FixedClock]:
    schema_registry = create_default_registry()
    providers = {
        report_type: StubProvider(report_type, _row(report_type))
        for report_type in ReportType
    }
    provider_registry = ReportProviderRegistry(
        tuple(providers.values())  # type: ignore[arg-type]
    )
    fixed_clock = clock or FixedClock(AS_OF)
    return (
        ReportingService(
            schema_registry=schema_registry,
            provider_registry=provider_registry,
            filter_policy=ReportFilterPolicy(schema_registry),
            export_limit_policy=ExportLimitPolicy(),
            clock=fixed_clock,
        ),
        providers,
        fixed_clock,
    )


def test_catalog_returns_all_explicit_registry_schemas_in_stable_order() -> None:
    service, _, clock = _service()

    catalog = service.get_catalog()

    assert tuple(schema.report_type for schema in catalog) == tuple(ReportType)
    assert all(schema.schema_version for schema in catalog)
    assert clock.calls == 0


@pytest.mark.parametrize("report_type", tuple(ReportType))
def test_preview_orchestrates_each_registered_provider(
    report_type: ReportType,
) -> None:
    service, providers, clock = _service()

    response = service.preview_report(report_type=report_type)

    schema = create_default_registry().get_schema(report_type)
    assert response.metadata.report_type is report_type
    assert response.metadata.schema_version == schema.schema_version
    assert response.columns is schema.columns
    assert response.rows == (providers[report_type].row,)
    assert response.availability.status is ReportAvailabilityStatus.AVAILABLE
    assert providers[report_type].windows == [(0, 20)]
    assert clock.calls == 1


def test_preview_freezes_clock_once_and_reuses_one_snapshot_for_provider() -> None:
    service, providers, clock = _service()

    response = service.preview_report(
        report_type=ReportType.SCORE_RESULTS,
        filters={"drama_id": 7},
        offset=2,
        limit=5,
    )

    provider = providers[ReportType.SCORE_RESULTS]
    assert clock.calls == 1
    assert provider.requests[0] is provider.requests[1]
    assert provider.requests[0].analysis_as_of == AS_OF
    assert provider.requests[0].filter_mapping() == {"drama_id": 7}
    assert response.metadata.snapshot.analysis_as_of == AS_OF
    assert response.metadata.snapshot.requested_at == AS_OF
    assert provider.windows == [(2, 5)]


def test_explicit_snapshot_is_normalized_without_reading_clock() -> None:
    service, providers, clock = _service()
    explicit = datetime(2026, 9, 23, 16, 30, tzinfo=timezone_plus_eight())

    response = service.preview_report(
        report_type=ReportType.PREDICTION_RESULTS,
        analysis_as_of=explicit,
    )

    request = providers[ReportType.PREDICTION_RESULTS].requests[0]
    assert clock.calls == 0
    assert request.analysis_as_of == AS_OF
    assert response.metadata.snapshot.analysis_as_of == AS_OF


def timezone_plus_eight():
    return timezone(timedelta(hours=8))


def test_preview_empty_is_explicit_and_does_not_create_zero_row() -> None:
    service, providers, _ = _service()
    providers[ReportType.DRAMA_CATALOG].total_rows = 0

    response = service.preview_report(report_type=ReportType.DRAMA_CATALOG)

    assert response.rows == ()
    assert response.availability.status is ReportAvailabilityStatus.EMPTY
    assert response.availability.reasons == (
        ReportAvailabilityReason.NO_MATCHING_DATA,
    )


def test_provider_failure_is_isolated_as_structured_not_available() -> None:
    service, providers, _ = _service()
    providers[ReportType.ANOMALY_RECORDS].count_error = RuntimeError("source down")

    failed = service.preview_report(report_type=ReportType.ANOMALY_RECORDS)
    healthy = service.preview_report(report_type=ReportType.SCORE_RESULTS)

    assert failed.rows == ()
    assert failed.availability.status is ReportAvailabilityStatus.NOT_AVAILABLE
    assert failed.availability.reasons == (
        ReportAvailabilityReason.MISSING_SOURCE,
    )
    assert healthy.availability.status is ReportAvailabilityStatus.AVAILABLE


def test_provider_row_failure_is_isolated_after_successful_count() -> None:
    service, providers, _ = _service()
    providers[ReportType.OPERATION_ACTIONS].rows_error = RuntimeError("read failed")

    response = service.preview_report(report_type=ReportType.OPERATION_ACTIONS)

    assert response.metadata.total_rows == 0
    assert response.availability.status is ReportAvailabilityStatus.NOT_AVAILABLE


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (
            ReportAvailabilityStatus.PARTIAL,
            ReportAvailabilityReason.SOURCE_VERSION_MISMATCH,
        ),
        (
            ReportAvailabilityStatus.INSUFFICIENT,
            ReportAvailabilityReason.INSUFFICIENT_DATA,
        ),
    ],
)
def test_structured_provider_availability_is_preserved(
    status: ReportAvailabilityStatus,
    reason: ReportAvailabilityReason,
) -> None:
    from services.reporting.contracts import ReportAvailability

    service, providers, _ = _service()
    providers[ReportType.SCORE_RESULTS].count_error = ReportAvailabilityError(
        ReportAvailability(status, (reason,), "Source reported availability.")
    )

    response = service.preview_report(report_type=ReportType.SCORE_RESULTS)

    assert response.availability.status is status
    assert response.availability.reasons == (reason,)


def test_prepare_export_selects_descriptor_and_returns_rows_when_allowed() -> None:
    service, providers, clock = _service()

    preparation = service.prepare_export(
        report_type=ReportType.DATA_QUALITY_RESULTS,
        export_format=ExportFormat.XLSX,
        filters={"rule_set_version": "rules-v1"},
    )

    assert preparation.descriptor.format is ExportFormat.XLSX
    assert preparation.descriptor.extension == ".xlsx"
    assert preparation.schema.report_type is ReportType.DATA_QUALITY_RESULTS
    assert preparation.decision is not None
    assert preparation.decision.status is ExportDecisionStatus.ALLOW
    assert preparation.report.rows == (
        providers[ReportType.DATA_QUALITY_RESULTS].row,
    )
    assert providers[ReportType.DATA_QUALITY_RESULTS].windows == [(0, 1)]
    assert clock.calls == 1


def test_prepare_export_preserves_confirmation_decision_without_rows() -> None:
    service, _, _ = _service()

    preparation = service.prepare_export(
        report_type=ReportType.DRAMA_CATALOG,
        export_format=ExportFormat.CSV,
    )

    assert preparation.decision is not None
    assert (
        preparation.decision.status
        is ExportDecisionStatus.REQUIRE_CONFIRMATION
    )
    assert preparation.report.metadata.total_rows == 1
    assert preparation.report.rows == ()
    assert preparation.report.availability.status is ReportAvailabilityStatus.AVAILABLE


def test_prepare_export_maps_hard_limit_to_not_available() -> None:
    service, providers, _ = _service()
    providers[ReportType.SCORE_RESULTS].total_rows = 10_001

    preparation = service.prepare_export(
        report_type=ReportType.SCORE_RESULTS,
        export_format=ExportFormat.CSV,
        filters={"drama_id": 1},
    )

    assert preparation.report.rows == ()
    assert preparation.report.availability.status is ReportAvailabilityStatus.NOT_AVAILABLE
    assert preparation.report.availability.reasons == (
        ReportAvailabilityReason.LIMIT_EXCEEDED,
    )


def test_prepare_export_provider_failure_is_structured() -> None:
    service, providers, _ = _service()
    providers[ReportType.PREDICTION_RESULTS].count_error = RuntimeError("offline")

    preparation = service.prepare_export(
        report_type=ReportType.PREDICTION_RESULTS,
        export_format=ExportFormat.CSV,
        filters={"drama_id": 1},
    )

    assert preparation.decision is None
    assert preparation.report.availability.status is ReportAvailabilityStatus.NOT_AVAILABLE


@pytest.mark.parametrize(
    ("offset", "limit"),
    [(-1, 20), (0, 0), (0, 101), (True, 20), (0, True)],
)
def test_preview_rejects_invalid_window(offset: int, limit: int) -> None:
    service, _, clock = _service()
    with pytest.raises(ValueError):
        service.preview_report(
            report_type=ReportType.DRAMA_CATALOG,
            offset=offset,
            limit=limit,
        )
    assert clock.calls == 0


def test_service_has_no_forbidden_architecture_dependencies_or_writes() -> None:
    path = Path(__file__).parents[1] / "services" / "reporting" / "service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_import_roots = {"fastapi", "models", "repositories", "sqlalchemy"}
    forbidden_module_parts = {"routers", "serializers"}
    forbidden_calls = {"commit", "rollback", "flush", "query", "execute"}
    forbidden_business_services = {
        "score_service",
        "prediction_service",
        "anomaly_service",
        "operation_action_service",
        "drama_profile",
        "data_governance",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_import_roots
                assert not set(alias.name.split(".")).intersection(
                    forbidden_business_services
                )
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = set(node.module.split("."))
            assert node.module.split(".")[0] not in forbidden_import_roots
            assert not parts.intersection(forbidden_module_parts)
            assert not parts.intersection(forbidden_business_services)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls
