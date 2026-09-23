"""Unit and architecture tests for pure Phase 10 reporting contracts."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from services.reporting.contracts import (
    AVAILABLE_REPORT,
    AnalysisSnapshot,
    ExportDescriptor,
    ExportFormat,
    ReportAvailability,
    ReportAvailabilityReason,
    ReportAvailabilityStatus,
    ReportColumn,
    ReportColumnType,
    ReportFilter,
    ReportMetadata,
    ReportRequest,
    ReportResponse,
    ReportRow,
    ReportType,
    SnapshotSemantics,
)


AS_OF = datetime(2026, 9, 23, 8, tzinfo=UTC)
REQUESTED_AT = AS_OF + timedelta(seconds=1)


def test_closed_enums_contain_frozen_v1_values() -> None:
    assert tuple(item.value for item in ReportType) == (
        "DRAMA_CATALOG",
        "SCORE_RESULTS",
        "DATA_QUALITY_RESULTS",
        "PREDICTION_RESULTS",
        "ANOMALY_RECORDS",
        "OPERATION_ACTIONS",
    )
    assert {item.value for item in ExportFormat} == {"CSV", "XLSX"}
    assert {item.value for item in ReportAvailabilityStatus} >= {
        "AVAILABLE",
        "PARTIAL",
        "INSUFFICIENT",
        "NOT_AVAILABLE",
    }
    with pytest.raises(ValueError):
        ReportType("UNKNOWN")


def test_availability_never_uses_none_as_business_state() -> None:
    assert AVAILABLE_REPORT.status is ReportAvailabilityStatus.AVAILABLE
    assert AVAILABLE_REPORT.reasons == ()
    insufficient = ReportAvailability(
        ReportAvailabilityStatus.INSUFFICIENT,
        (ReportAvailabilityReason.INSUFFICIENT_DATA,),
        "History is insufficient.",
    )
    assert insufficient.reasons == (ReportAvailabilityReason.INSUFFICIENT_DATA,)
    with pytest.raises(ValueError):
        ReportAvailability(ReportAvailabilityStatus.NOT_AVAILABLE)
    with pytest.raises(ValueError):
        ReportAvailability(
            ReportAvailabilityStatus.AVAILABLE,
            (ReportAvailabilityReason.MISSING_SOURCE,),
        )


def test_snapshot_requires_explicit_aware_times_and_order() -> None:
    snapshot = AnalysisSnapshot(
        requested_at=REQUESTED_AT,
        analysis_as_of=AS_OF,
        semantics=SnapshotSemantics.AS_OF_RECONSTRUCTED,
    )
    assert snapshot.timezone == "UTC"
    with pytest.raises(ValueError, match="must be UTC"):
        AnalysisSnapshot(REQUESTED_AT, AS_OF, timezone="Asia/Shanghai")
    with pytest.raises(ValueError, match="timezone-aware"):
        AnalysisSnapshot(datetime(2026, 9, 23), AS_OF)
    with pytest.raises(ValueError, match="must not be after"):
        AnalysisSnapshot(AS_OF, REQUESTED_AT)


def test_request_is_immutable_and_contains_only_structured_filters() -> None:
    request = ReportRequest(
        ReportType.SCORE_RESULTS,
        (
            ReportFilter("algorithm_version", "score-v1"),
            ReportFilter("drama_id", 7),
        ),
        AS_OF,
        ExportFormat.CSV,
    )
    assert request.filter_mapping() == {
        "algorithm_version": "score-v1",
        "drama_id": 7,
    }
    with pytest.raises(FrozenInstanceError):
        request.report_type = ReportType.DRAMA_CATALOG  # type: ignore[misc]
    with pytest.raises(ValueError, match="sorted"):
        ReportRequest(
            ReportType.SCORE_RESULTS,
            (ReportFilter("z", 1), ReportFilter("a", 2)),
            AS_OF,
        )
    with pytest.raises(ValueError):
        ReportFilter("query", object())  # type: ignore[arg-type]


def test_column_exposes_serializer_compatibility_properties() -> None:
    column = ReportColumn(
        "analysis_as_of",
        "Analysis As Of",
        ReportColumnType.DATETIME,
        False,
        "ISO_8601_UTC",
    )
    assert column.key == column.name
    assert column.title == column.display_name
    assert column.column_type is column.data_type
    with pytest.raises(FrozenInstanceError):
        column.nullable = True  # type: ignore[misc]


def test_report_row_is_an_immutable_mapping_with_supported_scalars() -> None:
    row = ReportRow(
        (
            ("name", "Drama"),
            ("count", 0),
            ("ratio", Decimal("1.25")),
            ("day", date(2026, 9, 23)),
            ("analysis_as_of", AS_OF),
            ("optional", None),
        )
    )
    assert row["count"] == 0
    assert tuple(row) == (
        "name",
        "count",
        "ratio",
        "day",
        "analysis_as_of",
        "optional",
    )
    with pytest.raises(ValueError, match="unsupported"):
        ReportRow((("float", 1.5),))
    with pytest.raises(ValueError, match="timezone-aware"):
        ReportRow((("time", datetime(2026, 9, 23)),))


def test_response_metadata_rows_and_availability_construct_together() -> None:
    columns = (
        ReportColumn("drama_id", "Drama ID", ReportColumnType.INTEGER, False),
        ReportColumn("name", "Name", ReportColumnType.STRING, False),
    )
    metadata = ReportMetadata(
        ReportType.DRAMA_CATALOG,
        "Drama Catalog",
        "Authorized current drama catalog.",
        "DRAMA_CATALOG Schema V1.0",
        AnalysisSnapshot(REQUESTED_AT, AS_OF),
        1,
    )
    response = ReportResponse(
        metadata,
        columns,
        (ReportRow((("drama_id", 1), ("name", "Drama"))),),
        AVAILABLE_REPORT,
    )
    assert response.metadata.total_rows == 1
    with pytest.raises(ValueError, match="column order"):
        ReportResponse(
            metadata,
            columns,
            (ReportRow((("name", "Drama"), ("drama_id", 1))),),
            AVAILABLE_REPORT,
        )


def test_export_descriptor_is_transport_metadata_without_a_path() -> None:
    descriptor = ExportDescriptor(
        ExportFormat.CSV,
        "text/csv; charset=utf-8",
        ".csv",
        "score_results_{analysis_as_of}_{schema_version}.csv",
    )
    assert descriptor.extension == ".csv"
    assert not hasattr(descriptor, "path")
    with pytest.raises(ValueError, match="path separators"):
        ExportDescriptor(
            ExportFormat.CSV,
            "text/csv",
            ".csv",
            "reports/file.csv",
        )


def test_contracts_have_no_data_or_application_layer_dependencies() -> None:
    path = Path(__file__).parents[1] / "services" / "reporting" / "contracts.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "database",
        "fastapi",
        "models",
        "repositories",
        "sqlalchemy",
    }
    forbidden_calls = {"commit", "rollback", "flush", "query", "execute"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(
                alias.name.split(".")[0] in forbidden_roots for alias in node.names
            )
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden_roots
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls
