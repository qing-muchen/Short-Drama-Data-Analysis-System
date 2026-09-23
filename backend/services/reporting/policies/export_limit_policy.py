"""Deterministic row, confirmation, and file-size export limits."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


DIRECT_EXPORT_MAX_ROWS = 1_000
CSV_MAX_ROWS = 10_000
XLSX_MAX_ROWS = 5_000
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
SPOOL_MEMORY_THRESHOLD_BYTES = 5 * 1024 * 1024
EXPORT_POLICY_VERSION = "Export Limit Policy V1.0"


class ExportDecisionStatus(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class ExportDecision:
    status: ExportDecisionStatus
    code: str | None
    total_rows: int
    max_rows: int
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES
    policy_version: str = EXPORT_POLICY_VERSION

    @property
    def allowed(self) -> bool:
        return self.status is ExportDecisionStatus.ALLOW


class ExportLimitPolicy:
    """Apply frozen V1 limits without generating or reading files."""

    def evaluate_rows(
        self,
        *,
        total_rows: int,
        export_format: object,
        has_effective_filters: bool,
        confirmed_row_count: int | None = None,
    ) -> ExportDecision:
        if isinstance(total_rows, bool) or not isinstance(total_rows, int):
            raise TypeError("total_rows must be an integer")
        if total_rows < 0:
            raise ValueError("total_rows must not be negative")
        if confirmed_row_count is not None and (
            isinstance(confirmed_row_count, bool)
            or not isinstance(confirmed_row_count, int)
            or confirmed_row_count < 0
        ):
            raise ValueError("confirmed_row_count must be a non-negative integer")

        format_name = self._format_name(export_format)
        max_rows = CSV_MAX_ROWS if format_name == "CSV" else XLSX_MAX_ROWS

        if total_rows == 0:
            return ExportDecision(
                ExportDecisionStatus.REJECT,
                "EMPTY_REPORT",
                total_rows,
                max_rows,
            )
        if total_rows > max_rows:
            return ExportDecision(
                ExportDecisionStatus.REJECT,
                "EXPORT_LIMIT_EXCEEDED",
                total_rows,
                max_rows,
            )

        needs_confirmation = (
            not has_effective_filters or total_rows > DIRECT_EXPORT_MAX_ROWS
        )
        if needs_confirmation and confirmed_row_count != total_rows:
            return ExportDecision(
                ExportDecisionStatus.REQUIRE_CONFIRMATION,
                "EXPORT_CONFIRMATION_REQUIRED",
                total_rows,
                max_rows,
            )

        return ExportDecision(
            ExportDecisionStatus.ALLOW,
            None,
            total_rows,
            max_rows,
        )

    def evaluate_file_size(self, byte_length: int) -> ExportDecision:
        if isinstance(byte_length, bool) or not isinstance(byte_length, int):
            raise TypeError("byte_length must be an integer")
        if byte_length < 0:
            raise ValueError("byte_length must not be negative")
        if byte_length > MAX_FILE_SIZE_BYTES:
            return ExportDecision(
                ExportDecisionStatus.REJECT,
                "EXPORT_SIZE_LIMIT_EXCEEDED",
                total_rows=0,
                max_rows=0,
            )
        return ExportDecision(
            ExportDecisionStatus.ALLOW,
            None,
            total_rows=0,
            max_rows=0,
        )

    def estimate_file_size(self, *, row_count: int, average_row_bytes: int) -> int:
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (row_count, average_row_bytes)
        ):
            raise ValueError("size estimate inputs must be non-negative integers")
        return row_count * average_row_bytes

    @staticmethod
    def _format_name(export_format: object) -> str:
        raw_value = getattr(export_format, "value", export_format)
        if not isinstance(raw_value, str):
            raise ValueError("export_format must be CSV or XLSX")
        normalized = raw_value.upper()
        if normalized not in {"CSV", "XLSX"}:
            raise ValueError("export_format must be CSV or XLSX")
        return normalized
