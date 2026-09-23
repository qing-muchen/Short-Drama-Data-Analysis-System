"""Immutable explicit report schema registry."""

from __future__ import annotations

from types import MappingProxyType
from typing import Iterable, Mapping

from services.reporting.contracts import (
    FilterDefinition,
    ReportSchema,
    ReportType,
)

from .schemas import DEFAULT_REPORT_SCHEMAS


class UnknownReportTypeError(KeyError):
    """Raised when a report type has no explicitly registered schema."""


class ReportSchemaRegistry:
    """Read-only mapping constructed only from explicitly supplied schemas."""

    __slots__ = ("_schemas", "_ordered_schemas")

    def __init__(self, schemas: Iterable[ReportSchema]) -> None:
        ordered = tuple(schemas)
        if not ordered:
            raise ValueError("at least one report schema must be registered")
        mapping: dict[ReportType, ReportSchema] = {}
        for schema in ordered:
            if not isinstance(schema, ReportSchema):
                raise TypeError("registry accepts only ReportSchema values")
            if schema.report_type in mapping:
                raise ValueError(
                    f"duplicate report schema: {schema.report_type.value}"
                )
            mapping[schema.report_type] = schema
        self._ordered_schemas = ordered
        self._schemas: Mapping[ReportType, ReportSchema] = MappingProxyType(mapping)

    def get_schema(self, report_type: ReportType) -> ReportSchema:
        if not isinstance(report_type, ReportType):
            raise UnknownReportTypeError(str(report_type))
        try:
            return self._schemas[report_type]
        except KeyError as exc:
            raise UnknownReportTypeError(report_type.value) from exc

    def get_filter_definitions(
        self, report_type: object
    ) -> tuple[FilterDefinition, ...]:
        if not isinstance(report_type, ReportType):
            raise UnknownReportTypeError(str(report_type))
        return self.get_schema(report_type).filters

    def list_schemas(self) -> tuple[ReportSchema, ...]:
        return self._ordered_schemas

    def __len__(self) -> int:
        return len(self._ordered_schemas)


def create_default_registry() -> ReportSchemaRegistry:
    """Build the frozen V1 catalog without global mutable registry state."""

    return ReportSchemaRegistry(DEFAULT_REPORT_SCHEMAS)


__all__ = (
    "ReportSchemaRegistry",
    "UnknownReportTypeError",
    "create_default_registry",
)
