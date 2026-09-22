"""Service tests for the Phase 6 explanation generation workflow."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from models.explanation import AnalysisExplanation
from services.exceptions import ConflictException, ValidationException
from services.explanation import ExplanationHandlerRegistry, ExplanationType
from services.explanation.handlers import (
    AnomalyExplanationGenerator,
    MetricExplanationGenerator,
    TrendExplanationGenerator,
)
from services.explanation.service import (
    AnalysisExplanationService,
    ExplanationGenerationRequest,
)


AS_OF = datetime(2026, 9, 22, tzinfo=timezone.utc)


class FakeExplanationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.existing: AnalysisExplanation | None = None
        self.created: list[AnalysisExplanation] = []

    def get_by_identity(self, **_: object) -> AnalysisExplanation | None:
        return self.existing

    def create_explanation(self, explanation: AnalysisExplanation) -> AnalysisExplanation:
        explanation.explanation_id = len(self.created) + 1
        self.created.append(explanation)
        return explanation


class FakeLineageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.created = []
        self.existing = []
        self.fail = False

    def create_many(self, records):
        if self.fail:
            raise RuntimeError("lineage failure")
        self.created.extend(records)
        return records

    def get_by_target(self, **_: object):
        return self.existing


def make_service(*, registry: ExplanationHandlerRegistry | None = None):
    session = MagicMock(spec=Session)
    explanations = FakeExplanationRepository(session)
    lineage = FakeLineageRepository(session)
    service = AnalysisExplanationService(
        session,
        explanations,
        lineage,
        registry or make_registry(),
    )
    return service, session, explanations, lineage


def make_registry() -> ExplanationHandlerRegistry:
    registry = ExplanationHandlerRegistry()
    registry.register(ExplanationType.METRIC, MetricExplanationGenerator())
    registry.register(ExplanationType.TREND, TrendExplanationGenerator())
    registry.register(ExplanationType.ANOMALY, AnomalyExplanationGenerator())
    return registry


def request(explanation_type: ExplanationType, payload: dict) -> ExplanationGenerationRequest:
    return ExplanationGenerationRequest(
        explanation_type=explanation_type,
        entity_id=payload.get("score_id", payload.get("prediction_id", payload.get("anomaly_id", 1))),
        analysis_as_of=AS_OF,
        algorithm_version="Rule-based Detection V1.0",
        rule_set_version="N/A",
        payload=payload,
    )


def test_metric_trend_and_anomaly_generation_map_database_types() -> None:
    cases = [
        (
            ExplanationType.METRIC,
            {"score_id": 1, "positive_dimension": "热度", "weak_dimension": "增长"},
            "SCORE",
        ),
        (
            ExplanationType.TREND,
            {"prediction_id": 2, "trend_direction": "UP", "window_length": 7},
            "PREDICTION",
        ),
        (
            ExplanationType.ANOMALY,
            {
                "anomaly_id": 3,
                "anomaly_type": "DATA_SPIKE_ANOMALY",
                "severity": "A",
                "metric_type": "PLAY_COUNT",
                "evidence_summary": "偏离基线",
                "threshold_summary": "abs(z-score) >= 2",
            },
            "ANOMALY",
        ),
    ]
    for explanation_type, payload, module_type in cases:
        service, _, explanations, lineage = make_service()
        saved = service.generate_explanation(request(explanation_type, payload))
        assert saved.module_type == module_type
        assert saved.entity_type == module_type
        assert explanations.created
        assert lineage.created[0].target_type == "EXPLANATION"
        assert lineage.created[0].target_id == saved.explanation_id


def test_same_identity_and_content_returns_existing_without_writing() -> None:
    service, session, explanations, lineage = make_service()
    first = service.generate_explanation(
        request(ExplanationType.METRIC, {"score_id": 1, "positive_dimension": "热度", "weak_dimension": "增长"})
    )
    lineage.existing = lineage.created.copy()
    explanations.existing = first

    result = service.generate_explanation(
        request(ExplanationType.METRIC, {"score_id": 1, "positive_dimension": "热度", "weak_dimension": "增长"})
    )

    assert result is first
    assert len(explanations.created) == 1
    session.commit.assert_called_once()


def test_same_identity_with_different_content_raises_conflict() -> None:
    service, _, explanations, lineage = make_service()
    first = service.generate_explanation(
        request(ExplanationType.METRIC, {"score_id": 1, "positive_dimension": "热度", "weak_dimension": "增长"})
    )
    lineage.existing = lineage.created.copy()
    explanations.existing = first

    with pytest.raises(ConflictException):
        service.generate_explanation(
            request(ExplanationType.METRIC, {"score_id": 1, "positive_dimension": "互动", "weak_dimension": "增长"})
        )


def test_generator_exception_does_not_write_or_commit() -> None:
    registry = ExplanationHandlerRegistry()
    generator = MagicMock()
    generator.generate.side_effect = RuntimeError("generator failure")
    registry.register(ExplanationType.METRIC, generator)
    service, session, explanations, lineage = make_service(registry=registry)

    with pytest.raises(RuntimeError):
        service.generate_explanation(request(ExplanationType.METRIC, {"score_id": 1}))

    assert explanations.created == []
    assert lineage.created == []
    session.commit.assert_not_called()


def test_lineage_failure_rolls_back_transaction() -> None:
    service, session, _, lineage = make_service()
    lineage.fail = True

    with pytest.raises(RuntimeError):
        service.generate_explanation(
            request(ExplanationType.METRIC, {"score_id": 1, "positive_dimension": "热度", "weak_dimension": "增长"})
        )

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_unsupported_detail_field_is_rejected_before_persistence() -> None:
    registry = ExplanationHandlerRegistry()
    generator = MagicMock()
    from services.explanation.contracts import GeneratedExplanation

    generator.generate.return_value = GeneratedExplanation(
        summary="ok",
        detail={
            "reason": "ok",
            "inputs": [],
            "rules": [],
            "versions": {},
            "evidence": [],
            "unsupported": True,
        },
    )
    registry.register(ExplanationType.METRIC, generator)
    service, session, _, _ = make_service(registry=registry)
    with pytest.raises(ValidationException):
        service.generate_explanation(request(ExplanationType.METRIC, {"score_id": 1}))
    session.commit.assert_not_called()


def test_service_does_not_import_existing_business_services() -> None:
    import inspect
    import services.explanation.service as explanation_service

    source = inspect.getsource(explanation_service)
    assert "ScoreService" not in source
    assert "PredictionService" not in source
    assert "AnomalyService" not in source
