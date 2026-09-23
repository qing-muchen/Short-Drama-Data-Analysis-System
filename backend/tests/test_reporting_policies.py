"""Unit and architecture tests for deterministic reporting policies."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from services.reporting.policies import (
    CSV_MAX_ROWS,
    DIRECT_EXPORT_MAX_ROWS,
    MAX_FILE_SIZE_BYTES,
    XLSX_MAX_ROWS,
    ExportDecisionStatus,
    ExportLimitPolicy,
    FilterValidationError,
    ReportFilterPolicy,
)


@dataclass(frozen=True)
class FilterDefinition:
    key: str
    value_type: str
    required: bool = False
    default: object | None = None
    allowed_values: tuple[str, ...] = ()


class StubRegistry:
    def get_filter_definitions(self, report_type: object) -> tuple[FilterDefinition, ...]:
        assert report_type == "SCORE_RESULTS"
        return (
            FilterDefinition("drama_id", "INTEGER"),
            FilterDefinition("end_time", "DATETIME"),
            FilterDefinition("start_time", "DATETIME"),
            FilterDefinition(
                "status",
                "ENUM",
                default="ACTIVE",
                allowed_values=("ACTIVE", "INACTIVE"),
            ),
        )


def test_filter_policy_normalizes_allowlisted_values() -> None:
    result = ReportFilterPolicy(StubRegistry()).validate(
        "SCORE_RESULTS",
        {
            "drama_id": 7,
            "start_time": "2026-09-01T08:00:00+08:00",
            "end_time": datetime(2026, 9, 2, tzinfo=UTC),
        },
    )

    values = result.as_mapping()
    assert values["drama_id"] == 7
    assert values["start_time"] == datetime(2026, 9, 1, tzinfo=UTC)
    assert values["status"] == "ACTIVE"
    assert result.has_effective_filters is True
    assert result.explicit_keys == ("drama_id", "end_time", "start_time")


def test_filter_defaults_do_not_count_as_explicit_filters() -> None:
    result = ReportFilterPolicy(StubRegistry()).validate("SCORE_RESULTS", {})
    assert result.as_mapping()["status"] == "ACTIVE"
    assert result.has_effective_filters is False


@pytest.mark.parametrize(
    ("filters", "code"),
    [
        ({"unknown": 1}, "UNSUPPORTED_REPORT_FILTER"),
        ({"drama_id": 0}, "INVALID_FILTER_VALUE"),
        ({"status": "MISSING"}, "INVALID_FILTER_VALUE"),
        ({"start_time": "2026-09-01T00:00:00"}, "INVALID_FILTER_VALUE"),
        (
            {
                "start_time": "2026-09-03T00:00:00Z",
                "end_time": "2026-09-02T00:00:00Z",
            },
            "INVALID_FILTER_RANGE",
        ),
    ],
)
def test_filter_policy_rejects_invalid_input(
    filters: dict[str, object], code: str
) -> None:
    with pytest.raises(FilterValidationError) as exc_info:
        ReportFilterPolicy(StubRegistry()).validate("SCORE_RESULTS", filters)
    assert exc_info.value.code == code
    assert exc_info.value.field is not None


def test_filter_policy_rejects_missing_required_filter() -> None:
    class RequiredRegistry:
        def get_filter_definitions(self, report_type: object) -> tuple[FilterDefinition, ...]:
            return (FilterDefinition("drama_id", "INTEGER", required=True),)

    with pytest.raises(FilterValidationError) as exc_info:
        ReportFilterPolicy(RequiredRegistry()).validate("SCORE_RESULTS", {})
    assert exc_info.value.code == "MISSING_REQUIRED_FILTER"


def test_export_policy_allows_small_filtered_exports() -> None:
    decision = ExportLimitPolicy().evaluate_rows(
        total_rows=DIRECT_EXPORT_MAX_ROWS,
        export_format="CSV",
        has_effective_filters=True,
    )
    assert decision.status is ExportDecisionStatus.ALLOW
    assert decision.allowed is True


def test_export_policy_requires_and_rechecks_confirmation() -> None:
    policy = ExportLimitPolicy()
    first = policy.evaluate_rows(
        total_rows=100,
        export_format="CSV",
        has_effective_filters=False,
    )
    stale = policy.evaluate_rows(
        total_rows=101,
        export_format="CSV",
        has_effective_filters=False,
        confirmed_row_count=100,
    )
    confirmed = policy.evaluate_rows(
        total_rows=101,
        export_format="CSV",
        has_effective_filters=False,
        confirmed_row_count=101,
    )
    assert first.status is ExportDecisionStatus.REQUIRE_CONFIRMATION
    assert stale.status is ExportDecisionStatus.REQUIRE_CONFIRMATION
    assert confirmed.status is ExportDecisionStatus.ALLOW


@pytest.mark.parametrize(
    ("export_format", "row_count"),
    [("CSV", CSV_MAX_ROWS + 1), ("XLSX", XLSX_MAX_ROWS + 1)],
)
def test_export_policy_rejects_hard_row_limits(
    export_format: str, row_count: int
) -> None:
    decision = ExportLimitPolicy().evaluate_rows(
        total_rows=row_count,
        export_format=export_format,
        has_effective_filters=True,
        confirmed_row_count=row_count,
    )
    assert decision.status is ExportDecisionStatus.REJECT
    assert decision.code == "EXPORT_LIMIT_EXCEEDED"


@pytest.mark.parametrize(
    ("export_format", "row_count"),
    [("CSV", CSV_MAX_ROWS), ("XLSX", XLSX_MAX_ROWS)],
)
def test_export_policy_allows_exact_hard_limit_after_confirmation(
    export_format: str, row_count: int
) -> None:
    decision = ExportLimitPolicy().evaluate_rows(
        total_rows=row_count,
        export_format=export_format,
        has_effective_filters=True,
        confirmed_row_count=row_count,
    )
    assert decision.allowed is True


def test_export_policy_rejects_empty_and_oversized_files() -> None:
    policy = ExportLimitPolicy()
    empty = policy.evaluate_rows(
        total_rows=0,
        export_format="CSV",
        has_effective_filters=True,
    )
    oversized = policy.evaluate_file_size(MAX_FILE_SIZE_BYTES + 1)
    exact = policy.evaluate_file_size(MAX_FILE_SIZE_BYTES)
    assert empty.code == "EMPTY_REPORT"
    assert oversized.code == "EXPORT_SIZE_LIMIT_EXCEEDED"
    assert exact.allowed is True
    assert policy.estimate_file_size(row_count=10, average_row_bytes=25) == 250


def test_policy_modules_have_no_forbidden_architecture_dependencies() -> None:
    root = Path(__file__).parents[1] / "services" / "reporting" / "policies"
    forbidden_import_roots = {
        "database",
        "models",
        "repositories",
        "sqlalchemy",
        "services",
    }
    forbidden_calls = {"commit", "rollback", "flush", "query", "execute"}

    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name.split(".")[0] in forbidden_import_roots
                    for alias in node.names
                )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden_import_roots
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
