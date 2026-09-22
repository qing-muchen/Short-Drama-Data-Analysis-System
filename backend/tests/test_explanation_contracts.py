"""Unit tests for the pure Phase 6 explanation contracts and registry."""

from datetime import datetime, timezone

import pytest

from services.explanation import (
    DuplicateExplanationHandlerError,
    ExplanationContext,
    ExplanationHandlerNotFoundError,
    ExplanationHandlerRegistry,
    ExplanationType,
    GeneratedExplanation,
    LineageSource,
)


def make_context() -> ExplanationContext:
    return ExplanationContext(
        entity_type="SCORE",
        entity_id=10,
        module_type="SCORE",
        analysis_as_of=datetime(2026, 9, 22, tzinfo=timezone.utc),
        algorithm_version="Composite Score V1.0",
        rule_set_version="N/A",
        payload={"contributors": ["HEAT"]},
        lineage_sources=(LineageSource("METRIC", 20, "DERIVED_FROM"),),
    )


def test_explanation_context_creation_and_lineage_fields() -> None:
    context = make_context()

    assert context.entity_id == 10
    assert context.payload["contributors"] == ["HEAT"]
    assert context.lineage_sources[0] == LineageSource("METRIC", 20, "DERIVED_FROM")


def test_generated_explanation_requires_dict_detail() -> None:
    with pytest.raises(TypeError, match="detail must be a dict"):
        GeneratedExplanation(summary="ok", detail=[])


def test_generated_explanation_rejects_forbidden_nested_values() -> None:
    with pytest.raises(ValueError, match="must not contain"):
        GeneratedExplanation(
            summary="ok",
            detail={"evidence": [{"prediction_value": "hidden"}]},
        )


class MockGenerator:
    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        return GeneratedExplanation(
            summary=f"Explanation for {context.entity_id}",
            detail={"reason": "deterministic"},
        )


def test_registry_registers_and_resolves_mock_generator() -> None:
    registry = ExplanationHandlerRegistry()
    generator = MockGenerator()

    registry.register(ExplanationType.METRIC, generator)

    assert len(registry) == 1
    assert registry.get_handler(ExplanationType.METRIC) is generator
    assert isinstance(registry.get_handler(ExplanationType.METRIC).generate(make_context()), GeneratedExplanation)


def test_registry_rejects_duplicate_registration() -> None:
    registry = ExplanationHandlerRegistry()
    generator = MockGenerator()
    registry.register(ExplanationType.TREND, generator)

    with pytest.raises(DuplicateExplanationHandlerError):
        registry.register(ExplanationType.TREND, generator)


def test_registry_rejects_unknown_type_lookup() -> None:
    registry = ExplanationHandlerRegistry()

    with pytest.raises(ExplanationHandlerNotFoundError):
        registry.get_handler(ExplanationType.ANOMALY)


def test_registry_rejects_non_enum_key() -> None:
    registry = ExplanationHandlerRegistry()

    with pytest.raises(TypeError):
        registry.register("METRIC", MockGenerator())  # type: ignore[arg-type]
