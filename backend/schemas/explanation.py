"""Public read-only DTOs for Phase 6 explanation and lineage queries."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from schemas.common import SchemaModel

ExplanationEntityType = Literal["SCORE", "QUALITY", "PREDICTION", "ANOMALY", "ACTION"]
ExplanationModuleType = Literal[
    "SCORE", "QUALITY", "PREDICTION", "ANOMALY", "OPERATION_ACTION"
]
LineageTargetType = Literal[
    "EXPLANATION", "SCORE", "QUALITY", "PREDICTION", "ANOMALY", "ACTION"
]
LineageSourceType = Literal[
    "METRIC", "SNAPSHOT", "RULE", "PREDICTION_INPUT", "ANOMALY_EVIDENCE"
]
LineageRelationshipType = Literal[
    "DERIVED_FROM", "USES_METRIC", "USES_RULE", "USES_WINDOW"
]


class ExplanationResponse(SchemaModel):
    explanation_id: int = Field(ge=1)
    entity_type: ExplanationEntityType
    entity_id: int = Field(ge=1)
    module_type: ExplanationModuleType
    summary: str = Field(min_length=1)
    detail: dict[str, Any]
    algorithm_version: str = Field(min_length=1)
    rule_set_version: str = Field(min_length=1)
    analysis_as_of: datetime
    created_at: datetime


class LineageResponse(SchemaModel):
    lineage_id: int = Field(ge=1)
    target_type: LineageTargetType
    target_id: int = Field(ge=1)
    source_type: LineageSourceType
    source_id: int = Field(ge=1)
    relationship_type: LineageRelationshipType
    analysis_as_of: datetime
    created_at: datetime


__all__ = [
    "ExplanationEntityType",
    "ExplanationModuleType",
    "ExplanationResponse",
    "LineageRelationshipType",
    "LineageResponse",
    "LineageSourceType",
    "LineageTargetType",
]
