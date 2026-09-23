"""Projection-to-ReportRow providers for six explicit V1 reports."""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from typing import Mapping

from repositories.reporting_repository import ReportingRepository
from services.reporting.contracts import ReportRequest, ReportRow, ReportType
from services.reporting.registry import ReportSchemaRegistry


class ReportProvider:
    """Map one repository projection type to one registered report schema."""

    report_type: ReportType
    count_method_name: str
    list_method_name: str

    def __init__(
        self,
        repository: ReportingRepository,
        schema_registry: ReportSchemaRegistry,
    ) -> None:
        self._repository = repository
        self._schema = schema_registry.get_schema(self.report_type)

    def count(self, request: ReportRequest) -> int:
        self._validate_request(request)
        method = getattr(self._repository, self.count_method_name)
        return int(method(request))

    def list_rows(
        self,
        request: ReportRequest,
        *,
        offset: int = 0,
        limit: int = 1000,
    ) -> tuple[ReportRow, ...]:
        self._validate_request(request)
        method = getattr(self._repository, self.list_method_name)
        projections = method(request, offset=offset, limit=limit)
        column_names = tuple(column.name for column in self._schema.columns)
        return tuple(
            ReportRow(
                tuple(
                    (name, self._normalize_value(getattr(projection, name)))
                    for name in column_names
                )
            )
            for projection in projections
        )

    def _validate_request(self, request: ReportRequest) -> None:
        if not isinstance(request, ReportRequest):
            raise TypeError("request must be a ReportRequest")
        if request.report_type is not self.report_type:
            raise ValueError(
                f"provider {self.report_type.value} cannot serve "
                f"{request.report_type.value}"
            )

    @staticmethod
    def _normalize_value(value: object) -> object:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        return value


class DramaCatalogReportProvider(ReportProvider):
    report_type = ReportType.DRAMA_CATALOG
    count_method_name = "count_drama_catalog"
    list_method_name = "list_drama_catalog"


class ScoreResultsReportProvider(ReportProvider):
    report_type = ReportType.SCORE_RESULTS
    count_method_name = "count_score_results"
    list_method_name = "list_score_results"


class DataQualityResultsReportProvider(ReportProvider):
    report_type = ReportType.DATA_QUALITY_RESULTS
    count_method_name = "count_data_quality_results"
    list_method_name = "list_data_quality_results"


class PredictionResultsReportProvider(ReportProvider):
    report_type = ReportType.PREDICTION_RESULTS
    count_method_name = "count_prediction_results"
    list_method_name = "list_prediction_results"


class AnomalyRecordsReportProvider(ReportProvider):
    report_type = ReportType.ANOMALY_RECORDS
    count_method_name = "count_anomaly_records"
    list_method_name = "list_anomaly_records"


class OperationActionsReportProvider(ReportProvider):
    report_type = ReportType.OPERATION_ACTIONS
    count_method_name = "count_operation_actions"
    list_method_name = "list_operation_actions"


class ReportProviderRegistry:
    """Immutable explicit provider lookup without discovery."""

    __slots__ = ("_providers",)

    def __init__(self, providers: tuple[ReportProvider, ...]) -> None:
        if not providers:
            raise ValueError("at least one report provider is required")
        mapping: dict[ReportType, ReportProvider] = {}
        for provider in providers:
            if provider.report_type in mapping:
                raise ValueError(
                    f"duplicate report provider: {provider.report_type.value}"
                )
            mapping[provider.report_type] = provider
        self._providers: Mapping[ReportType, ReportProvider] = MappingProxyType(
            mapping
        )

    def get_provider(self, report_type: ReportType) -> ReportProvider:
        if not isinstance(report_type, ReportType):
            raise KeyError(str(report_type))
        try:
            return self._providers[report_type]
        except KeyError as exc:
            raise KeyError(report_type.value) from exc

    def list_report_types(self) -> tuple[ReportType, ...]:
        return tuple(self._providers)


def create_default_provider_registry(
    repository: ReportingRepository,
    schema_registry: ReportSchemaRegistry,
) -> ReportProviderRegistry:
    """Compose all six providers explicitly for later Service injection."""

    return ReportProviderRegistry(
        (
            DramaCatalogReportProvider(repository, schema_registry),
            ScoreResultsReportProvider(repository, schema_registry),
            DataQualityResultsReportProvider(repository, schema_registry),
            PredictionResultsReportProvider(repository, schema_registry),
            AnomalyRecordsReportProvider(repository, schema_registry),
            OperationActionsReportProvider(repository, schema_registry),
        )
    )


__all__ = (
    "AnomalyRecordsReportProvider",
    "DataQualityResultsReportProvider",
    "DramaCatalogReportProvider",
    "OperationActionsReportProvider",
    "PredictionResultsReportProvider",
    "ReportProvider",
    "ReportProviderRegistry",
    "ScoreResultsReportProvider",
    "create_default_provider_registry",
)
