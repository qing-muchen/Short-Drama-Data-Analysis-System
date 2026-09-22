"""Unit tests for the extracted explanation validation rules."""

from datetime import datetime, timezone

import pytest

from services.exceptions import ValidationException
from services.explanation import (
    ExplanationContext,
    ExplanationType,
    ExplanationValidator,
    GeneratedExplanation,
    LineageSource,
)


AS_OF = datetime(2026, 9, 22, tzinfo=timezone.utc)


def context(module_type: str) -> ExplanationContext:
    return ExplanationContext(
        entity_type="SCORE",
        entity_id=1,
        module_type=module_type,
        analysis_as_of=AS_OF,
        algorithm_version="Composite Score V1.0",
        rule_set_version="N/A",
    )


def valid() -> GeneratedExplanation:
    return GeneratedExplanation(
        summary="解释摘要",
        detail={
            "reason": "reason",
            "inputs": [],
            "rules": [],
            "versions": {},
            "evidence": [],
        },
        lineage_sources=(LineageSource("METRIC", 1, "DERIVED_FROM"),),
    )


def test_valid_detail_and_lineage_pass() -> None:
    ExplanationValidator().validate_generated_explanation(valid())


def test_non_dict_detail_is_rejected() -> None:
    value = object.__new__(GeneratedExplanation)
    object.__setattr__(value, "summary", "摘要")
    object.__setattr__(value, "detail", [])
    object.__setattr__(value, "lineage_sources", ())

    with pytest.raises(ValidationException, match="detail must be a dict"):
        ExplanationValidator().validate_generated_explanation(value)


@pytest.mark.parametrize("forbidden", [
    "score_value",
    "prediction_value",
    "full_result",
    "complete_snapshot",
])
def test_forbidden_detail_fields_are_rejected(forbidden: str) -> None:
    value = valid()
    detail = dict(value.detail)
    detail[forbidden] = "not allowed"
    invalid = object.__new__(GeneratedExplanation)
    object.__setattr__(invalid, "summary", value.summary)
    object.__setattr__(invalid, "detail", detail)
    object.__setattr__(invalid, "lineage_sources", value.lineage_sources)

    with pytest.raises(ValidationException, match="forbidden"):
        ExplanationValidator().validate_generated_explanation(invalid)


def test_context_mapping_is_checked() -> None:
    validator = ExplanationValidator()
    validator.validate_context_mapping(context("SCORE"), "SCORE", "SCORE")

    with pytest.raises(ValidationException, match="mapping"):
        validator.validate_context_mapping(context("SCORE"), "PREDICTION", "PREDICTION")


def test_invalid_lineage_is_rejected() -> None:
    invalid = object.__new__(GeneratedExplanation)
    object.__setattr__(invalid, "summary", "摘要")
    object.__setattr__(
        invalid,
        "detail",
        {"reason": "r", "inputs": [], "rules": [], "versions": {}, "evidence": []},
    )
    object.__setattr__(invalid, "lineage_sources", ("not-a-lineage-source",))

    with pytest.raises(ValidationException, match="lineage"):
        ExplanationValidator().validate_generated_explanation(invalid)


def test_all_internal_types_have_expected_mapping() -> None:
    validator = ExplanationValidator()
    for explanation_type, entity_type in (
        (ExplanationType.METRIC, "SCORE"),
        (ExplanationType.TREND, "PREDICTION"),
        (ExplanationType.ANOMALY, "ANOMALY"),
    ):
        validator.validate_context_mapping(
            context(entity_type), entity_type, entity_type
        )
