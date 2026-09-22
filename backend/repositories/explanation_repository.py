"""Persistence access for V013 explanation and lineage records."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from models.explanation import AnalysisExplanation, AnalysisLineageRecord
from repositories.base import BaseRepository


class AnalysisExplanationRepository(BaseRepository[AnalysisExplanation]):
    """Store and query explanation snapshots without business decisions."""

    model = AnalysisExplanation

    def get_by_identity(
        self,
        *,
        module_type: str,
        entity_type: str,
        entity_id: int,
        analysis_as_of: datetime,
        algorithm_version: str,
        rule_set_version: str,
    ) -> AnalysisExplanation | None:
        """Return the exact versioned identity, or ``None``."""

        statement = select(AnalysisExplanation).where(
            AnalysisExplanation.module_type == module_type,
            AnalysisExplanation.entity_type == entity_type,
            AnalysisExplanation.entity_id == entity_id,
            AnalysisExplanation.analysis_as_of == analysis_as_of,
            AnalysisExplanation.algorithm_version == algorithm_version,
            AnalysisExplanation.rule_set_version == rule_set_version,
        )
        return self.session.scalar(statement)

    def create_explanation(
        self,
        explanation: AnalysisExplanation,
    ) -> AnalysisExplanation:
        """Add one ORM explanation and flush without committing."""

        self.session.add(explanation)
        self.session.flush()
        return explanation

    def get_by_entity(
        self,
        *,
        entity_type: str,
        entity_id: int,
    ) -> list[AnalysisExplanation]:
        """Return all explanation snapshots for an entity, newest first."""

        statement = (
            select(AnalysisExplanation)
            .where(
                AnalysisExplanation.entity_type == entity_type,
                AnalysisExplanation.entity_id == entity_id,
            )
            .order_by(
                AnalysisExplanation.analysis_as_of.desc(),
                AnalysisExplanation.explanation_id.desc(),
            )
        )
        return list(self.session.scalars(statement).all())


class AnalysisLineageRepository(BaseRepository[AnalysisLineageRecord]):
    """Store and query weakly linked explanation lineage records."""

    model = AnalysisLineageRecord

    def create_many(
        self,
        lineage_records: Sequence[AnalysisLineageRecord],
    ) -> list[AnalysisLineageRecord]:
        """Add and flush lineage records without enforcing business rules."""

        records = list(lineage_records)
        self.session.add_all(records)
        self.session.flush()
        return records

    def get_by_target(
        self,
        *,
        target_type: str,
        target_id: int,
    ) -> list[AnalysisLineageRecord]:
        """Return lineage for one target in stable creation order."""

        statement = (
            select(AnalysisLineageRecord)
            .where(
                AnalysisLineageRecord.target_type == target_type,
                AnalysisLineageRecord.target_id == target_id,
            )
            .order_by(
                AnalysisLineageRecord.created_at.asc(),
                AnalysisLineageRecord.lineage_id.asc(),
            )
        )
        return list(self.session.scalars(statement).all())


__all__ = ["AnalysisExplanationRepository", "AnalysisLineageRepository"]
