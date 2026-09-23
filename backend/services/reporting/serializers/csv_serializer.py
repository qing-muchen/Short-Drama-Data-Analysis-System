"""Safe UTF-8 CSV serialization for schema-defined report rows."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from decimal import Decimal
from io import TextIOWrapper
from typing import Iterable

from services.reporting.policies.export_limit_policy import (
    SPOOL_MEMORY_THRESHOLD_BYTES,
)

from . import (
    ReportColumnLike,
    ReportRowLike,
    ReportSchemaLike,
    SerializedReport,
    create_spooled_stream,
)


CSV_MIME_TYPE = "text/csv; charset=utf-8"
FORMULA_PREFIXES = frozenset({"=", "+", "-", "*", "@"})
SUPPORTED_COLUMN_TYPES = frozenset(
    {"STRING", "INTEGER", "DECIMAL", "BOOLEAN", "DATE", "DATETIME"}
)


def _column_type_name(column: ReportColumnLike) -> str:
    raw_value = getattr(column.column_type, "value", column.column_type)
    if not isinstance(raw_value, str):
        raise ValueError(f"column type must be a string enum: {column.key}")
    name = raw_value.upper()
    if name not in SUPPORTED_COLUMN_TYPES:
        raise ValueError(f"unsupported column type for {column.key}: {raw_value}")
    return name


def _protect_text(value: str) -> str:
    if not value:
        raise ValueError("meaningful empty strings are not supported in V1 reports")
    stripped = value.lstrip()
    if stripped and stripped[0] in FORMULA_PREFIXES:
        return "'" + value
    return value


def _serialize_value(column: ReportColumnLike, value: object) -> object:
    if value is None:
        if not column.nullable:
            raise ValueError(f"non-nullable column is missing: {column.key}")
        return ""

    column_type = _column_type_name(column)
    if column_type == "STRING":
        if not isinstance(value, str):
            raise TypeError(f"column {column.key} must contain strings")
        return _protect_text(value)
    if column_type == "INTEGER":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"column {column.key} must contain integers")
        return value
    if column_type == "DECIMAL":
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            raise TypeError(f"column {column.key} must contain decimals")
        return str(value)
    if column_type == "BOOLEAN":
        if not isinstance(value, bool):
            raise TypeError(f"column {column.key} must contain booleans")
        return "true" if value else "false"
    if column_type == "DATE":
        if isinstance(value, datetime) or not isinstance(value, date):
            raise TypeError(f"column {column.key} must contain dates")
        return value.isoformat()
    if column_type == "DATETIME":
        if not isinstance(value, datetime):
            raise TypeError(f"column {column.key} must contain datetimes")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"column {column.key} datetime must be timezone-aware")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    raise AssertionError(f"unhandled column type: {column_type}")


def _validate_schema(schema: ReportSchemaLike) -> tuple[ReportColumnLike, ...]:
    columns = tuple(schema.columns)
    if not columns:
        raise ValueError("report schema must contain at least one column")
    keys = tuple(column.key for column in columns)
    if any(not key or not key.strip() for key in keys):
        raise ValueError("column keys must not be blank")
    if len(keys) != len(set(keys)):
        raise ValueError("column keys must be unique")
    for column in columns:
        if not column.title or not column.title.strip():
            raise ValueError(f"column title must not be blank: {column.key}")
        _column_type_name(column)
    return columns


def _ordered_row(
    row: ReportRowLike,
    columns: tuple[ReportColumnLike, ...],
) -> list[object]:
    expected = {column.key for column in columns}
    actual = set(row)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"row/schema mismatch; missing={missing}, extra={extra}")
    return [_serialize_value(column, row[column.key]) for column in columns]


class CsvReportSerializer:
    """Serialize an iterable without retaining report rows in memory."""

    def __init__(self, spool_threshold_bytes: int = SPOOL_MEMORY_THRESHOLD_BYTES):
        if spool_threshold_bytes <= 0:
            raise ValueError("spool_threshold_bytes must be positive")
        self._spool_threshold_bytes = spool_threshold_bytes

    def serialize(
        self,
        rows: Iterable[ReportRowLike],
        schema: ReportSchemaLike,
    ) -> SerializedReport:
        columns = _validate_schema(schema)
        stream = create_spooled_stream(self._spool_threshold_bytes)
        text_stream = TextIOWrapper(
            stream,
            encoding="utf-8-sig",
            newline="",
            write_through=True,
        )
        try:
            writer = csv.writer(text_stream, lineterminator="\r\n")
            writer.writerow([column.title for column in columns])
            for row in rows:
                writer.writerow(_ordered_row(row, columns))
            text_stream.detach()
            byte_length = stream.tell()
            stream.seek(0)
            return SerializedReport(
                stream=stream,
                mime_type=CSV_MIME_TYPE,
                file_extension=".csv",
                byte_length=byte_length,
            )
        except Exception:
            try:
                text_stream.detach()
            except (ValueError, OSError):
                pass
            stream.close()
            raise


__all__ = ("CSV_MIME_TYPE", "CsvReportSerializer")
