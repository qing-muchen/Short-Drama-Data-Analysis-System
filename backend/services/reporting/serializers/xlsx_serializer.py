"""Safe write-only XLSX serialization for schema-defined report rows."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Iterable

from openpyxl import Workbook

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
from .csv_serializer import FORMULA_PREFIXES, _column_type_name, _validate_schema


XLSX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
FIXED_WORKBOOK_TIMESTAMP = datetime(1980, 1, 1)
INVALID_SHEET_NAME_CHARS = frozenset("[]:*?/\\")


def _validate_sheet_name(sheet_name: str) -> str:
    if not isinstance(sheet_name, str) or not sheet_name.strip():
        raise ValueError("schema sheet_name must not be blank")
    if len(sheet_name) > 31 or any(char in sheet_name for char in INVALID_SHEET_NAME_CHARS):
        raise ValueError("schema sheet_name is not a safe XLSX sheet name")
    return sheet_name


def _protect_xlsx_text(value: str) -> str:
    if not value:
        raise ValueError("meaningful empty strings are not supported in V1 reports")
    stripped = value.lstrip()
    if stripped and stripped[0] in FORMULA_PREFIXES:
        return "'" + value
    return value


def _xlsx_value(column: ReportColumnLike, value: object) -> object:
    if value is None:
        if not column.nullable:
            raise ValueError(f"non-nullable column is missing: {column.key}")
        return None

    column_type = _column_type_name(column)
    if column_type == "STRING":
        if not isinstance(value, str):
            raise TypeError(f"column {column.key} must contain strings")
        return _protect_xlsx_text(value)
    if column_type == "INTEGER":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"column {column.key} must contain integers")
        return value
    if column_type == "DECIMAL":
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            raise TypeError(f"column {column.key} must contain decimals")
        return value
    if column_type == "BOOLEAN":
        if not isinstance(value, bool):
            raise TypeError(f"column {column.key} must contain booleans")
        return value
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


class XlsxReportSerializer:
    """Generate a write-only workbook into a request-scoped spool."""

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
        sheet_name = _validate_sheet_name(schema.sheet_name)
        stream = create_spooled_stream(self._spool_threshold_bytes)
        workbook = Workbook(write_only=True)
        workbook.properties.created = FIXED_WORKBOOK_TIMESTAMP
        workbook.properties.modified = FIXED_WORKBOOK_TIMESTAMP
        worksheet = None
        try:
            worksheet = workbook.create_sheet(title=sheet_name)
            worksheet.append([column.title for column in columns])
            expected = {column.key for column in columns}
            for row in rows:
                actual = set(row)
                if actual != expected:
                    missing = sorted(expected - actual)
                    extra = sorted(actual - expected)
                    raise ValueError(
                        f"row/schema mismatch; missing={missing}, extra={extra}"
                    )
                worksheet.append(
                    [_xlsx_value(column, row[column.key]) for column in columns]
                )
            workbook.save(stream)
            byte_length = stream.tell()
            stream.seek(0)
            return SerializedReport(
                stream=stream,
                mime_type=XLSX_MIME_TYPE,
                file_extension=".xlsx",
                byte_length=byte_length,
            )
        except Exception:
            if worksheet is not None:
                try:
                    worksheet.close()
                except Exception:
                    pass
            workbook.close()
            stream.close()
            raise
        finally:
            workbook.close()


__all__ = ("XLSX_MIME_TYPE", "XlsxReportSerializer")
