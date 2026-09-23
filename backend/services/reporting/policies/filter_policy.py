"""Allowlist-based report filter validation without data access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable


FilterScalar = str | int | datetime | None
SUPPORTED_FILTER_TYPES = frozenset({"STRING", "INTEGER", "DATETIME", "ENUM"})


@runtime_checkable
class FilterDefinitionLike(Protocol):
    """Structural contract supplied by the future schema registry."""

    key: str
    value_type: str
    required: bool
    default: FilterScalar
    allowed_values: tuple[str, ...]


@runtime_checkable
class FilterRegistryLike(Protocol):
    """Minimum registry capability required by the policy."""

    def get_filter_definitions(
        self, report_type: object
    ) -> tuple[FilterDefinitionLike, ...]: ...


class FilterValidationError(ValueError):
    """Structured validation failure safe for later API translation."""

    def __init__(self, *, code: str, field: str | None, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message


@dataclass(frozen=True, slots=True)
class ValidatedFilters:
    """Immutable, deterministic normalized filter collection."""

    items: tuple[tuple[str, FilterScalar], ...]
    explicit_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        keys = tuple(key for key, _ in self.items)
        if len(keys) != len(set(keys)):
            raise ValueError("validated filter keys must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("validated filter keys must be sorted")
        if self.explicit_keys != tuple(sorted(self.explicit_keys)):
            raise ValueError("explicit filter keys must be sorted")
        if not set(self.explicit_keys).issubset(keys):
            raise ValueError("explicit filter keys must exist in items")

    @property
    def has_effective_filters(self) -> bool:
        return bool(self.explicit_keys)

    def as_mapping(self) -> Mapping[str, FilterScalar]:
        return MappingProxyType(dict(self.items))


class ReportFilterPolicy:
    """Validate only fields explicitly declared by a report schema registry."""

    def __init__(self, registry: FilterRegistryLike) -> None:
        if not isinstance(registry, FilterRegistryLike):
            raise TypeError("registry must implement FilterRegistryLike")
        self._registry = registry

    def validate(
        self,
        report_type: object,
        filters: Mapping[str, Any] | None,
    ) -> ValidatedFilters:
        definitions = self._registry.get_filter_definitions(report_type)
        by_key = self._validate_definitions(definitions)
        supplied = dict(filters or {})

        unknown = sorted(set(supplied) - set(by_key))
        if unknown:
            raise FilterValidationError(
                code="UNSUPPORTED_REPORT_FILTER",
                field=unknown[0],
                message=f"unsupported filter: {unknown[0]}",
            )

        normalized: list[tuple[str, FilterScalar]] = []
        for key in sorted(by_key):
            definition = by_key[key]
            value = supplied.get(key, definition.default)
            if value is None:
                if definition.required:
                    raise FilterValidationError(
                        code="MISSING_REQUIRED_FILTER",
                        field=key,
                        message=f"required filter is missing: {key}",
                    )
                continue
            normalized.append((key, self._normalize(definition, value)))

        normalized_values = dict(normalized)
        start = normalized_values.get("start_time")
        end = normalized_values.get("end_time")
        if isinstance(start, datetime) and isinstance(end, datetime) and start > end:
            raise FilterValidationError(
                code="INVALID_FILTER_RANGE",
                field="start_time",
                message="start_time must not be after end_time",
            )

        explicit_keys = tuple(
            sorted(key for key, value in supplied.items() if value is not None)
        )
        return ValidatedFilters(tuple(normalized), explicit_keys)

    @staticmethod
    def _validate_definitions(
        definitions: tuple[FilterDefinitionLike, ...],
    ) -> dict[str, FilterDefinitionLike]:
        result: dict[str, FilterDefinitionLike] = {}
        for definition in definitions:
            if not definition.key or not definition.key.strip():
                raise ValueError("filter definition key must not be blank")
            if definition.key in result:
                raise ValueError(f"duplicate filter definition: {definition.key}")
            if definition.value_type not in SUPPORTED_FILTER_TYPES:
                raise ValueError(
                    f"unsupported filter type for {definition.key}: "
                    f"{definition.value_type}"
                )
            if definition.value_type == "ENUM" and not definition.allowed_values:
                raise ValueError(
                    f"enum filter requires allowed values: {definition.key}"
                )
            result[definition.key] = definition
        return result

    @staticmethod
    def _normalize(
        definition: FilterDefinitionLike,
        value: Any,
    ) -> FilterScalar:
        key = definition.key
        value_type = definition.value_type
        if value_type == "STRING":
            if not isinstance(value, str) or not value.strip():
                raise FilterValidationError(
                    code="INVALID_FILTER_VALUE",
                    field=key,
                    message=f"filter {key} must be a non-blank string",
                )
            return value.strip()

        if value_type == "INTEGER":
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise FilterValidationError(
                    code="INVALID_FILTER_VALUE",
                    field=key,
                    message=f"filter {key} must be a positive integer",
                )
            return value

        if value_type == "DATETIME":
            parsed = ReportFilterPolicy._parse_datetime(value, key)
            return parsed.astimezone(UTC)

        if value_type == "ENUM":
            if not isinstance(value, str) or value not in definition.allowed_values:
                raise FilterValidationError(
                    code="INVALID_FILTER_VALUE",
                    field=key,
                    message=f"filter {key} must be one of the declared values",
                )
            return value

        raise AssertionError(f"unhandled filter type: {value_type}")

    @staticmethod
    def _parse_datetime(value: Any, key: str) -> datetime:
        parsed: datetime
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            candidate = value.strip()
            if candidate.endswith("Z"):
                candidate = candidate[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(candidate)
            except ValueError as exc:
                raise FilterValidationError(
                    code="INVALID_FILTER_VALUE",
                    field=key,
                    message=f"filter {key} must be an ISO 8601 datetime",
                ) from exc
        else:
            raise FilterValidationError(
                code="INVALID_FILTER_VALUE",
                field=key,
                message=f"filter {key} must be an ISO 8601 datetime",
            )

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise FilterValidationError(
                code="INVALID_FILTER_VALUE",
                field=key,
                message=f"filter {key} must be timezone-aware",
            )
        return parsed
