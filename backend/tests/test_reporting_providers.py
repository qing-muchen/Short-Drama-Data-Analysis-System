"""Mapping and architecture tests for the six report providers."""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from repositories.reporting_repository import (
    AnomalyRecordsProjection,
    DataQualityResultsProjection,
    DramaCatalogProjection,
    OperationActionsProjection,
    PredictionResultsProjection,
    ScoreResultsProjection,
)
from services.reporting.contracts import ReportRequest, ReportRow, ReportType
from services.reporting.providers import (
    ReportProviderRegistry,
    create_default_provider_registry,
)
from services.reporting.registry import create_default_registry


AS_OF = datetime(2026, 9, 23, 8, tzinfo=UTC)
DB_TIME = datetime(2026, 9, 20, 8)


class StubRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, int | None]] = []
        self.projections = {
            ReportType.DRAMA_CATALOG: DramaCatalogProjection(
                1, "D-001", "Drama", "COMPLETED", None, None, None, None, None
            ),
            ReportType.SCORE_RESULTS: ScoreResultsProjection(
                2,
                1,
                date(2026, 9, 20),
                "ALL",
                0,
                DB_TIME,
                Decimal("70"),
                Decimal("71"),
                Decimal("72"),
                Decimal("73"),
                Decimal("72"),
                "A",
                "score-v1",
            ),
            ReportType.DATA_QUALITY_RESULTS: DataQualityResultsProjection(
                3,
                date(2026, 9, 20),
                "ALL",
                0,
                DB_TIME,
                Decimal("90"),
                Decimal("91"),
                Decimal("92"),
                Decimal("93"),
                Decimal("91.5"),
                "A",
                20,
                0,
                "quality-v1",
                "rules-v1",
                "a" * 64,
            ),
            ReportType.PREDICTION_RESULTS: PredictionResultsProjection(
                4,
                1,
                "PLAY_COUNT",
                date(2026, 9, 20),
                date(2026, 9, 21),
                Decimal("100"),
                "prediction-v1",
                DB_TIME,
            ),
            ReportType.ANOMALY_RECORDS: AnomalyRecordsProjection(
                5,
                1,
                "PLAY_COUNT",
                "DATA_SPIKE_ANOMALY",
                "A",
                "OPEN",
                DB_TIME,
                DB_TIME,
                "anomaly-v1",
                None,
                Decimal("100"),
                None,
                "Evidence",
            ),
            ReportType.OPERATION_ACTIONS: OperationActionsProjection(
                6,
                None,
                "Review",
                None,
                "MEDIUM",
                "OPEN",
                None,
                9,
                None,
                DB_TIME,
                DB_TIME,
                0,
                1,
            ),
        }

    def _count(self, name: str, request: ReportRequest) -> int:
        self.calls.append((name, None, None))
        return 1

    def _list(
        self, name: str, report_type: ReportType, *, offset: int, limit: int
    ) -> tuple[object, ...]:
        self.calls.append((name, offset, limit))
        return (self.projections[report_type],)

    def count_drama_catalog(self, request: ReportRequest) -> int:
        return self._count("count_drama_catalog", request)

    def list_drama_catalog(self, request: ReportRequest, *, offset: int, limit: int):
        return self._list("list_drama_catalog", ReportType.DRAMA_CATALOG, offset=offset, limit=limit)

    def count_score_results(self, request: ReportRequest) -> int:
        return self._count("count_score_results", request)

    def list_score_results(self, request: ReportRequest, *, offset: int, limit: int):
        return self._list("list_score_results", ReportType.SCORE_RESULTS, offset=offset, limit=limit)

    def count_data_quality_results(self, request: ReportRequest) -> int:
        return self._count("count_data_quality_results", request)

    def list_data_quality_results(self, request: ReportRequest, *, offset: int, limit: int):
        return self._list("list_data_quality_results", ReportType.DATA_QUALITY_RESULTS, offset=offset, limit=limit)

    def count_prediction_results(self, request: ReportRequest) -> int:
        return self._count("count_prediction_results", request)

    def list_prediction_results(self, request: ReportRequest, *, offset: int, limit: int):
        return self._list("list_prediction_results", ReportType.PREDICTION_RESULTS, offset=offset, limit=limit)

    def count_anomaly_records(self, request: ReportRequest) -> int:
        return self._count("count_anomaly_records", request)

    def list_anomaly_records(self, request: ReportRequest, *, offset: int, limit: int):
        return self._list("list_anomaly_records", ReportType.ANOMALY_RECORDS, offset=offset, limit=limit)

    def count_operation_actions(self, request: ReportRequest) -> int:
        return self._count("count_operation_actions", request)

    def list_operation_actions(self, request: ReportRequest, *, offset: int, limit: int):
        return self._list("list_operation_actions", ReportType.OPERATION_ACTIONS, offset=offset, limit=limit)


def request(report_type: ReportType) -> ReportRequest:
    return ReportRequest(report_type, (), AS_OF)


@pytest.mark.parametrize("report_type", tuple(ReportType))
def test_each_provider_maps_projection_to_registry_ordered_report_row(
    report_type: ReportType,
) -> None:
    repository = StubRepository()
    schema_registry = create_default_registry()
    provider_registry = create_default_provider_registry(
        repository,  # type: ignore[arg-type]
        schema_registry,
    )
    provider = provider_registry.get_provider(report_type)

    assert provider.count(request(report_type)) == 1
    rows = provider.list_rows(request(report_type), offset=2, limit=3)

    assert len(rows) == 1
    assert isinstance(rows[0], ReportRow)
    assert tuple(rows[0]) == tuple(
        column.name for column in schema_registry.get_schema(report_type).columns
    )
    assert repository.calls[-1][1:] == (2, 3)


def test_provider_preserves_null_and_zero_and_normalizes_database_datetime() -> None:
    repository = StubRepository()
    provider = create_default_provider_registry(
        repository,  # type: ignore[arg-type]
        create_default_registry(),
    ).get_provider(ReportType.OPERATION_ACTIONS)
    row = provider.list_rows(request(ReportType.OPERATION_ACTIONS))[0]

    assert row["drama_id"] is None
    assert row["description"] is None
    assert row["source_count"] == 0
    assert row["created_at"] == DB_TIME.replace(tzinfo=UTC)


def test_provider_rejects_a_request_for_another_report_type() -> None:
    provider = create_default_provider_registry(
        StubRepository(),  # type: ignore[arg-type]
        create_default_registry(),
    ).get_provider(ReportType.SCORE_RESULTS)
    with pytest.raises(ValueError, match="cannot serve"):
        provider.list_rows(request(ReportType.PREDICTION_RESULTS))


def test_provider_registry_is_explicit_immutable_and_rejects_duplicates() -> None:
    registry = create_default_provider_registry(
        StubRepository(),  # type: ignore[arg-type]
        create_default_registry(),
    )
    assert registry.list_report_types() == tuple(ReportType)
    first = registry.get_provider(ReportType.DRAMA_CATALOG)
    with pytest.raises(ValueError, match="duplicate"):
        ReportProviderRegistry((first, first))
    with pytest.raises(KeyError):
        registry.get_provider("UNKNOWN")  # type: ignore[arg-type]


def test_provider_module_has_no_orm_api_serializer_or_business_service_dependency() -> None:
    path = (
        Path(__file__).parents[1]
        / "services"
        / "reporting"
        / "providers"
        / "report_providers.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_import_roots = {"fastapi", "models", "sqlalchemy"}
    forbidden_module_parts = {"routers", "serializers", "service"}
    forbidden_calls = {"commit", "rollback", "flush", "query", "execute"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(
                alias.name.split(".")[0] in forbidden_import_roots
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = set(node.module.split("."))
            assert node.module.split(".")[0] not in forbidden_import_roots
            assert not parts.intersection(forbidden_module_parts)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls
