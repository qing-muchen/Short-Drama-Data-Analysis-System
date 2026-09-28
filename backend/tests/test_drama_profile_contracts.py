"""Tests for the pure Phase 7 Drama Profile contracts."""

import ast
from datetime import datetime, timezone
import inspect

import pytest

from services.drama_profile.contracts import (
    ActionProfileSummary,
    AnomalyProfileSummary,
    AvailabilityReason,
    DramaProfileBasic,
    DramaProfileResponse,
    ExplanationProfileSummary,
    ModuleAvailability,
    PredictionProfileSummary,
    QualityProfileSummary,
    ScoreProfileSummary,
)


def test_availability_reasons_are_closed_enum() -> None:
    assert {reason.value for reason in AvailabilityReason} == {
        "NOT_CALCULATED",
        "INSUFFICIENT_HISTORY",
        "NO_ANOMALY",
        "NOT_DETECTED",
        "NOT_AVAILABLE",
    }
    with pytest.raises(ValueError):
        AvailabilityReason("UNKNOWN")


def test_availability_protocol_requires_consistent_reason() -> None:
    assert ModuleAvailability(available=True).reason is None
    assert ModuleAvailability(
        available=False,
        reason=AvailabilityReason.INSUFFICIENT_HISTORY,
    ).available is False
    with pytest.raises(ValueError):
        ModuleAvailability(available=False)
    with pytest.raises(ValueError):
        ModuleAvailability(available=True, reason=AvailabilityReason.NO_ANOMALY)


def test_basic_drama_and_summary_defaults() -> None:
    basic = DramaProfileBasic(drama_id=7, title="示例短剧")
    score = ScoreProfileSummary(available=ModuleAvailability(available=True))
    prediction = PredictionProfileSummary(
        available=ModuleAvailability(
            available=False,
            reason=AvailabilityReason.NOT_CALCULATED,
        )
    )

    assert basic.platform is None
    assert basic.tags == ()
    assert score.dimensions == {}
    assert prediction.algorithm_version is None


def test_profile_response_supports_complete_and_partial_profiles() -> None:
    unavailable = ModuleAvailability(
        available=False,
        reason=AvailabilityReason.NOT_AVAILABLE,
    )
    basic = DramaProfileBasic(drama_id=1, title="全景短剧", tags=("都市",))
    complete = DramaProfileResponse(
        drama=basic,
        availability={"score": ModuleAvailability(available=True)},
        performance=ScoreProfileSummary(
            available=ModuleAvailability(available=True),
            score_level="A",
            dimensions={"heat": 80.0},
            analysis_as_of=datetime.now(timezone.utc),
            algorithm_version="Composite Score V1.0",
        ),
        quality=QualityProfileSummary(available=ModuleAvailability(available=True)),
        trend=PredictionProfileSummary(available=unavailable),
        risk=AnomalyProfileSummary(available=unavailable),
        operations=ActionProfileSummary(available=unavailable),
        explanations=ExplanationProfileSummary(available=unavailable),
    )
    partial = DramaProfileResponse(drama=basic, availability={"score": unavailable})

    assert complete.performance is not None
    assert complete.trend is not None
    assert partial.quality is None
    assert partial.availability["score"].reason is AvailabilityReason.NOT_AVAILABLE


def test_contract_module_has_no_persistence_dependencies() -> None:
    module = __import__("services.drama_profile.contracts", fromlist=["contracts"])
    tree = ast.parse(inspect.getsource(module))
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    referenced_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }

    assert imported_roots.isdisjoint(
        {"sqlalchemy", "database", "models", "repositories"}
    )
    assert referenced_names.isdisjoint({"Session", "query", "select", "Repository"})


def test_invalid_dto_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        DramaProfileBasic(drama_id=0, title="短剧")
    with pytest.raises(ValueError):
        AnomalyProfileSummary(
            available=ModuleAvailability(available=True),
            active_count=-1,
        )
    with pytest.raises(ValueError):
        ActionProfileSummary(
            available=ModuleAvailability(available=True),
            open_count=-1,
        )
