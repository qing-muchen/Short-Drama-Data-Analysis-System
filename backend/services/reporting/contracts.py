"""Pure immutable contracts for the Phase 10 reporting read model."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TypeAlias


ReportScalar: TypeAlias = str | int | Decimal | bool | date | datetime | None
FilterScalar: TypeAlias = str | int | datetime | None


class ReportType(str, Enum):
    DRAMA_CATALOG = "DRAMA_CATALOG"
    SCORE_RESULTS = "SCORE_RESULTS"
    DATA_QUALITY_RESULTS = "DATA_QUALITY_RESULTS"
    PREDICTION_RESULTS = "PREDICTION_RESULTS"
    ANOMALY_RECORDS = "ANOMALY_RECORDS"
    OPERATION_ACTIONS = "OPERATION_ACTIONS"


class ExportFormat(str, Enum):
    CSV = "CSV"
    XLSX = "XLSX"


class ReportAvailabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class ReportAvailabilityReason(str, Enum):
    NO_MATCHING_DATA = "NO_MATCHING_DATA"
    MISSING_SOURCE = "MISSING_SOURCE"
    UNSUPPORTED_FILTER = "UNSUPPORTED_FILTER"
    SOURCE_VERSION_MISMATCH = "SOURCE_VERSION_MISMATCH"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    EXPORT_FAILED = "EXPORT_FAILED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class SnapshotSemantics(str, Enum):
    AS_OF_RECONSTRUCTED = "AS_OF_RECONSTRUCTED"
    CURRENT_STATE_AT_REQUEST = "CURRENT_STATE_AT_REQUEST"


class ReportColumnType(str, Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"


class FilterValueType(str, Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    DATETIME = "DATETIME"
    ENUM = "ENUM"


def _require_nonblank(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{field_name} must be a {enum_type.__name__}")


@dataclass(frozen=True, slots=True)
class ReportAvailability:
    status: ReportAvailabilityStatus
    reasons: tuple[ReportAvailabilityReason, ...] = ()
    message: str | None = None

    def __post_init__(self) -> None:
        _require_enum(self.status, ReportAvailabilityStatus, "status")
        if not isinstance(self.reasons, tuple):
            raise ValueError("reasons must be an immutable tuple")
        if any(
            not isinstance(reason, ReportAvailabilityReason)
            for reason in self.reasons
        ):
            raise ValueError("reasons must contain ReportAvailabilityReason values")
        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError("availability reasons must be unique")
        reason_order = {
            reason: index for index, reason in enumerate(ReportAvailabilityReason)
        }
        if self.reasons != tuple(
            sorted(self.reasons, key=reason_order.__getitem__)
        ):
            raise ValueError("availability reasons must follow enum order")
        if self.status is ReportAvailabilityStatus.AVAILABLE and self.reasons:
            raise ValueError("AVAILABLE must not contain reasons")
        if self.status is not ReportAvailabilityStatus.AVAILABLE and not self.reasons:
            raise ValueError("non-AVAILABLE status requires at least one reason")
        if self.message is not None:
            _require_nonblank(self.message, "message")


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    requested_at: datetime
    analysis_as_of: datetime
    timezone: str = "UTC"
    semantics: SnapshotSemantics = SnapshotSemantics.CURRENT_STATE_AT_REQUEST

    def __post_init__(self) -> None:
        _require_aware(self.requested_at, "requested_at")
        _require_aware(self.analysis_as_of, "analysis_as_of")
        _require_nonblank(self.timezone, "timezone")
        if self.timezone != "UTC":
            raise ValueError("timezone must be UTC in Phase 10 V1")
        _require_enum(self.semantics, SnapshotSemantics, "semantics")
        if self.analysis_as_of > self.requested_at:
            raise ValueError("analysis_as_of must not be after requested_at")


@dataclass(frozen=True, slots=True)
class ReportFilter:
    key: str
    value: FilterScalar

    def __post_init__(self) -> None:
        _require_nonblank(self.key, "key")
        if self.value is None:
            raise ValueError("filter value must not be None")
        if isinstance(self.value, bool) or not isinstance(
            self.value, (str, int, datetime)
        ):
            raise ValueError("filter value must be a string, integer, or datetime")
        if isinstance(self.value, str):
            _require_nonblank(self.value, "filter value")
        if isinstance(self.value, datetime):
            _require_aware(self.value, "filter datetime")


@dataclass(frozen=True, slots=True)
class ReportRequest:
    report_type: ReportType
    filters: tuple[ReportFilter, ...]
    analysis_as_of: datetime
    export_format: ExportFormat | None = None

    def __post_init__(self) -> None:
        _require_enum(self.report_type, ReportType, "report_type")
        if not isinstance(self.filters, tuple):
            raise ValueError("filters must be an immutable tuple")
        keys = tuple(item.key for item in self.filters)
        if len(keys) != len(set(keys)):
            raise ValueError("report filter keys must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("report filters must be sorted by key")
        _require_aware(self.analysis_as_of, "analysis_as_of")
        if self.export_format is not None:
            _require_enum(self.export_format, ExportFormat, "export_format")

    def filter_mapping(self) -> Mapping[str, FilterScalar]:
        return {item.key: item.value for item in self.filters}


@dataclass(frozen=True, slots=True)
class ReportColumn:
    name: str
    display_name: str
    data_type: ReportColumnType
    nullable: bool
    format: str | None = None

    def __post_init__(self) -> None:
        _require_nonblank(self.name, "name")
        _require_nonblank(self.display_name, "display_name")
        _require_enum(self.data_type, ReportColumnType, "data_type")
        if not isinstance(self.nullable, bool):
            raise ValueError("nullable must be a boolean")
        if self.format is not None:
            _require_nonblank(self.format, "format")

    @property
    def key(self) -> str:
        """Compatibility key consumed by Phase 10.2 serializers."""

        return self.name

    @property
    def title(self) -> str:
        """Compatibility title consumed by Phase 10.2 serializers."""

        return self.display_name

    @property
    def column_type(self) -> ReportColumnType:
        """Compatibility type consumed by Phase 10.2 serializers."""

        return self.data_type


@dataclass(frozen=True, slots=True)
class ReportRow(Mapping[str, ReportScalar]):
    values: tuple[tuple[str, ReportScalar], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.values, tuple):
            raise ValueError("row values must be an immutable tuple")
        keys = tuple(key for key, _ in self.values)
        if any(not isinstance(key, str) or not key.strip() for key in keys):
            raise ValueError("row keys must not be blank")
        if len(keys) != len(set(keys)):
            raise ValueError("row keys must be unique")
        for key, value in self.values:
            if isinstance(value, float) or not isinstance(
                value,
                (str, int, Decimal, bool, date, datetime, type(None)),
            ):
                raise ValueError(f"unsupported row value for {key}")
            if isinstance(value, datetime):
                _require_aware(value, f"row datetime {key}")

    def __getitem__(self, key: str) -> ReportScalar:
        for item_key, value in self.values:
            if item_key == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self.values)

    def __len__(self) -> int:
        return len(self.values)


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    report_type: ReportType
    title: str
    description: str
    schema_version: str
    snapshot: AnalysisSnapshot
    total_rows: int
    source_versions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(self.report_type, ReportType, "report_type")
        _require_nonblank(self.title, "title")
        _require_nonblank(self.description, "description")
        _require_nonblank(self.schema_version, "schema_version")
        if (
            isinstance(self.total_rows, bool)
            or not isinstance(self.total_rows, int)
            or self.total_rows < 0
        ):
            raise ValueError("total_rows must be a non-negative integer")
        if any(not version.strip() for version in self.source_versions):
            raise ValueError("source_versions must not contain blank values")


@dataclass(frozen=True, slots=True)
class ReportResponse:
    metadata: ReportMetadata
    columns: tuple[ReportColumn, ...]
    rows: tuple[ReportRow, ...]
    availability: ReportAvailability

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("report response must contain columns")
        column_names = tuple(column.name for column in self.columns)
        if len(column_names) != len(set(column_names)):
            raise ValueError("report response column names must be unique")
        for row in self.rows:
            if tuple(row) != column_names:
                raise ValueError("report row keys must match column order")
        if self.metadata.total_rows < len(self.rows):
            raise ValueError("metadata total_rows must cover returned rows")


@dataclass(frozen=True, slots=True)
class ExportDescriptor:
    format: ExportFormat
    mime_type: str
    extension: str
    filename_template: str

    def __post_init__(self) -> None:
        _require_enum(self.format, ExportFormat, "format")
        _require_nonblank(self.mime_type, "mime_type")
        if not self.extension.startswith(".") or any(
            separator in self.extension for separator in ("/", "\\")
        ):
            raise ValueError("extension must be a safe dotted suffix")
        _require_nonblank(self.filename_template, "filename_template")
        if any(
            separator in self.filename_template for separator in ("/", "\\")
        ):
            raise ValueError("filename_template must not contain path separators")
        if not self.filename_template.endswith(self.extension):
            raise ValueError("filename_template must end with extension")


@dataclass(frozen=True, slots=True)
class FilterDefinition:
    key: str
    value_type: str
    required: bool = False
    default: FilterScalar = None
    allowed_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonblank(self.key, "key")
        if self.value_type not in {item.value for item in FilterValueType}:
            raise ValueError("value_type must be a supported FilterValueType")
        if not isinstance(self.required, bool):
            raise ValueError("required must be a boolean")
        if self.value_type == FilterValueType.ENUM.value:
            if not self.allowed_values:
                raise ValueError("enum filter must declare allowed_values")
            if len(self.allowed_values) != len(set(self.allowed_values)):
                raise ValueError("allowed_values must be unique")
        elif self.allowed_values:
            raise ValueError("allowed_values are only valid for ENUM filters")


@dataclass(frozen=True, slots=True)
class ReportSchema:
    report_type: ReportType
    name: str
    description: str
    schema_version: str
    columns: tuple[ReportColumn, ...]
    filters: tuple[FilterDefinition, ...]
    supported_formats: tuple[ExportFormat, ...]
    snapshot_semantics: SnapshotSemantics
    sheet_name: str
    export_descriptors: tuple[ExportDescriptor, ...]

    def __post_init__(self) -> None:
        _require_enum(self.report_type, ReportType, "report_type")
        _require_nonblank(self.name, "name")
        _require_nonblank(self.description, "description")
        _require_nonblank(self.schema_version, "schema_version")
        _require_nonblank(self.sheet_name, "sheet_name")
        if len(self.sheet_name) > 31 or any(
            char in self.sheet_name for char in "[]:*?/\\"
        ):
            raise ValueError("sheet_name must be a safe XLSX sheet name")
        if not self.columns:
            raise ValueError("report schema must contain columns")
        column_names = tuple(column.name for column in self.columns)
        if len(column_names) != len(set(column_names)):
            raise ValueError("report schema column names must be unique")
        filter_keys = tuple(item.key for item in self.filters)
        if len(filter_keys) != len(set(filter_keys)):
            raise ValueError("report schema filter keys must be unique")
        if filter_keys != tuple(sorted(filter_keys)):
            raise ValueError("report schema filters must be sorted by key")
        if not self.supported_formats:
            raise ValueError("report schema must support at least one format")
        if len(self.supported_formats) != len(set(self.supported_formats)):
            raise ValueError("supported_formats must be unique")
        if any(
            not isinstance(item, ExportFormat) for item in self.supported_formats
        ):
            raise ValueError("supported_formats must contain ExportFormat values")
        _require_enum(
            self.snapshot_semantics, SnapshotSemantics, "snapshot_semantics"
        )
        descriptor_formats = tuple(item.format for item in self.export_descriptors)
        if descriptor_formats != self.supported_formats:
            raise ValueError(
                "export descriptors must match supported_formats in order"
            )

    @property
    def identifier(self) -> str:
        return self.report_type.value


AVAILABLE_REPORT = ReportAvailability(ReportAvailabilityStatus.AVAILABLE)


__all__ = (
    "AVAILABLE_REPORT",
    "AnalysisSnapshot",
    "ExportDescriptor",
    "ExportFormat",
    "FilterDefinition",
    "FilterValueType",
    "ReportAvailability",
    "ReportAvailabilityReason",
    "ReportAvailabilityStatus",
    "ReportColumn",
    "ReportColumnType",
    "ReportFilter",
    "ReportMetadata",
    "ReportRequest",
    "ReportResponse",
    "ReportRow",
    "ReportSchema",
    "ReportType",
    "SnapshotSemantics",
)
