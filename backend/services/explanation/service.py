"""Application service for deterministic explanation generation and storage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from models.explanation import AnalysisExplanation, AnalysisLineageRecord
from repositories.explanation_repository import (
    AnalysisExplanationRepository,
    AnalysisLineageRepository,
)
from services.base import BaseService
from services.exceptions import ConflictException, ValidationException

from .contracts import (
    ExplanationContext,
    ExplanationType,
    GeneratedExplanation,
    LineageSource,
)
from .registry import ExplanationHandlerRegistry


@dataclass(frozen=True, slots=True)
class ExplanationGenerationRequest:
    """Trusted application input for one explanation snapshot."""

    explanation_type: ExplanationType
    entity_id: int
    analysis_as_of: datetime
    algorithm_version: str
    rule_set_version: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    lineage_sources: tuple[LineageSource, ...] = ()


_ENTITY_MODULE_MAPPING: dict[ExplanationType, tuple[str, str]] = {
    ExplanationType.METRIC: ("SCORE", "SCORE"),
    ExplanationType.TREND: ("PREDICTION", "PREDICTION"),
    ExplanationType.ANOMALY: ("ANOMALY", "ANOMALY"),
}

_BASE_DETAIL_FIELDS = {"reason", "inputs", "rules", "versions", "evidence"}
_HANDLER_DETAIL_FIELDS = _BASE_DETAIL_FIELDS | {
    "trend_direction",
    "window_length",
    "model_description",
}


class AnalysisExplanationService(BaseService):
    """Coordinate handler execution, idempotency, lineage, and one transaction."""

    def __init__(
        self,
        session: Any,
        explanations: AnalysisExplanationRepository,
        lineage: AnalysisLineageRepository,
        registry: ExplanationHandlerRegistry,
    ) -> None:
        super().__init__(session, explanations, lineage)
        self.explanations = explanations
        self.lineage = lineage
        self.registry = registry

    def generate_explanation(
        self,
        request: ExplanationGenerationRequest,
    ) -> AnalysisExplanation:
        """Generate and persist one deterministic explanation snapshot."""

        self._validate_request(request)
        entity_type, module_type = _ENTITY_MODULE_MAPPING[request.explanation_type]
        handler = self.registry.get_handler(request.explanation_type)
        context = ExplanationContext(
            entity_type=entity_type,
            entity_id=request.entity_id,
            module_type=module_type,
            analysis_as_of=request.analysis_as_of,
            algorithm_version=request.algorithm_version,
            rule_set_version=request.rule_set_version,
            payload=request.payload,
            lineage_sources=request.lineage_sources,
        )

        # Generation is deliberately outside the transaction: a pure Handler
        # failure must not create or modify any persistence state.
        generated = handler.generate(context)
        self._validate_generated(generated)

        existing = self.explanations.get_by_identity(
            module_type=module_type,
            entity_type=entity_type,
            entity_id=request.entity_id,
            analysis_as_of=request.analysis_as_of,
            algorithm_version=request.algorithm_version,
            rule_set_version=request.rule_set_version,
        )
        if existing is not None:
            self._ensure_same_snapshot(existing, generated)
            return existing

        with self.transaction():
            explanation = self.explanations.create_explanation(
                AnalysisExplanation(
                    entity_type=entity_type,
                    entity_id=request.entity_id,
                    module_type=module_type,
                    summary=generated.summary,
                    detail=generated.detail,
                    algorithm_version=request.algorithm_version,
                    rule_set_version=request.rule_set_version,
                    analysis_as_of=request.analysis_as_of,
                )
            )
            records = [
                AnalysisLineageRecord(
                    target_type="EXPLANATION",
                    target_id=explanation.explanation_id,
                    source_type=source.source_type,
                    source_id=source.source_id,
                    relationship_type=source.relationship_type,
                    analysis_as_of=request.analysis_as_of,
                )
                for source in generated.lineage_sources
            ]
            self.lineage.create_many(records)
        return explanation

    @staticmethod
    def _validate_request(request: ExplanationGenerationRequest) -> None:
        if not isinstance(request.explanation_type, ExplanationType):
            raise ValidationException("Unsupported explanation type")
        if request.entity_id <= 0:
            raise ValidationException("entity_id must be greater than zero")
        if not isinstance(request.analysis_as_of, datetime):
            raise ValidationException("analysis_as_of must be a datetime")
        if not request.algorithm_version.strip():
            raise ValidationException("algorithm_version must not be blank")
        if not request.rule_set_version.strip():
            raise ValidationException("rule_set_version must not be blank")
        if not isinstance(request.payload, Mapping):
            raise ValidationException("payload must be a mapping")

    @staticmethod
    def _validate_generated(generated: GeneratedExplanation) -> None:
        if not isinstance(generated, GeneratedExplanation):
            raise ValidationException("Handler must return GeneratedExplanation")
        if not isinstance(generated.detail, dict):
            raise ValidationException("Explanation detail must be a dict")
        missing = _BASE_DETAIL_FIELDS - set(generated.detail)
        if missing:
            raise ValidationException(
                "Explanation detail is missing required fields",
                details={"fields": sorted(missing)},
            )
        unexpected = set(generated.detail) - _HANDLER_DETAIL_FIELDS
        if unexpected:
            raise ValidationException(
                "Explanation detail contains unsupported fields",
                details={"fields": sorted(unexpected)},
            )

    def _ensure_same_snapshot(
        self,
        existing: AnalysisExplanation,
        generated: GeneratedExplanation,
    ) -> None:
        if existing.summary != generated.summary or existing.detail != generated.detail:
            raise ConflictException(
                "Explanation identity already exists with different content",
                details={"explanation_id": existing.explanation_id},
            )
        existing_lineage = self.lineage.get_by_target(
            target_type="EXPLANATION",
            target_id=existing.explanation_id,
        )
        expected = _lineage_signature(generated.lineage_sources)
        actual = tuple(
            sorted(
                (
                    record.source_type,
                    int(record.source_id),
                    record.relationship_type,
                )
                for record in existing_lineage
            )
        )
        if actual != expected:
            raise ConflictException(
                "Explanation identity already exists with different lineage",
                details={"explanation_id": existing.explanation_id},
            )


def _lineage_signature(
    sources: tuple[LineageSource, ...],
) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        sorted(
            (source.source_type, source.source_id, source.relationship_type)
            for source in sources
        )
    )


__all__ = [
    "AnalysisExplanationService",
    "ExplanationGenerationRequest",
]
