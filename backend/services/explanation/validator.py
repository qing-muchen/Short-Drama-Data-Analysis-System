"""Validation rules shared by the explanation generation Service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.exceptions import ValidationException

from .contracts import ExplanationContext, ExplanationType, GeneratedExplanation, LineageSource


_ENTITY_MODULE_MAPPING: dict[str, tuple[str, str]] = {
    "METRIC": ("SCORE", "SCORE"),
    "SCORE": ("SCORE", "SCORE"),
    "TREND": ("PREDICTION", "PREDICTION"),
    "PREDICTION": ("PREDICTION", "PREDICTION"),
    "ANOMALY": ("ANOMALY", "ANOMALY"),
}
_BASE_DETAIL_FIELDS = {"reason", "inputs", "rules", "versions", "evidence"}
# Trend has three documented, controlled extensions in addition to the common
# explanation envelope. Arbitrary keys remain invalid.
_ALLOWED_DETAIL_FIELDS = _BASE_DETAIL_FIELDS | {
    "trend_direction",
    "window_length",
    "model_description",
}
_FORBIDDEN_DETAIL_KEYS = {
    "score_value",
    "prediction_value",
    "full_result",
    "complete_snapshot",
}


class ExplanationValidator:
    """Validate explanation output without accessing persistence."""

    def validate_generated_explanation(
        self,
        generated_explanation: GeneratedExplanation,
    ) -> None:
        """Validate the controlled detail envelope and lineage fields."""

        detail = getattr(generated_explanation, "detail", None)
        if not isinstance(detail, dict):
            raise ValidationException("Explanation detail must be a dict")
        missing = _BASE_DETAIL_FIELDS - set(detail)
        if missing:
            raise ValidationException(
                "Explanation detail is missing required fields",
                details={"fields": sorted(missing)},
            )
        if _contains_forbidden_key(detail):
            raise ValidationException(
                "Explanation detail contains forbidden business result fields"
            )
        unexpected = set(detail) - _ALLOWED_DETAIL_FIELDS
        if unexpected:
            raise ValidationException(
                "Explanation detail contains unsupported fields",
                details={"fields": sorted(unexpected)},
            )
        lineage_sources = getattr(generated_explanation, "lineage_sources", None)
        if not isinstance(lineage_sources, tuple):
            raise ValidationException("lineage_sources must be a tuple")
        for source in lineage_sources:
            self._validate_lineage_source(source)

    def validate_context_mapping(
        self,
        context: ExplanationContext,
        entity_type: str,
        module_type: str,
    ) -> None:
        """Ensure the Service's database mapping matches the context module."""

        context_key = context.module_type.upper()
        expected = _ENTITY_MODULE_MAPPING.get(context_key)
        if expected is None:
            raise ValidationException(
                "Unsupported explanation context module",
                details={"module_type": context.module_type},
            )
        if (entity_type, module_type) != expected:
            raise ValidationException(
                "Explanation entity/module mapping is invalid",
                details={
                    "expected": {"entity_type": expected[0], "module_type": expected[1]},
                    "actual": {"entity_type": entity_type, "module_type": module_type},
                },
            )

    @staticmethod
    def _validate_lineage_source(source: Any) -> None:
        if not isinstance(source, LineageSource):
            raise ValidationException("Invalid lineage source")
        if (
            not isinstance(source.source_type, str)
            or not source.source_type.strip()
            or not isinstance(source.source_id, int)
            or isinstance(source.source_id, bool)
            or source.source_id <= 0
            or not isinstance(source.relationship_type, str)
            or not source.relationship_type.strip()
        ):
            raise ValidationException("Invalid lineage source fields")


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) in _FORBIDDEN_DETAIL_KEYS
            or _contains_forbidden_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(item) for item in value)
    return False


__all__ = ["ExplanationValidator"]
