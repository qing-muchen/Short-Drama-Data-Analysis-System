"""Read-only query repositories for persisted explanation snapshots."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from models.explanation import AnalysisExplanation, AnalysisLineageRecord
from repositories.base import BaseRepository, Page


class AnalysisExplanationQueryRepository(BaseRepository[AnalysisExplanation]):
    """Query explanation history without generating or changing explanations."""

    model = AnalysisExplanation

    def get_explanations_by_entity(
        self,
        *,
        entity_type: str,
        entity_id: int,
        module_type: str | None = None,
        analysis_as_of: datetime | None = None,
        algorithm_version: str | None = None,
        rule_set_version: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[AnalysisExplanation]:
        """Return stable, paginated explanation history for one entity."""

        filters = [
            AnalysisExplanation.entity_type == entity_type,
            AnalysisExplanation.entity_id == entity_id,
        ]
        if module_type is not None:
            filters.append(AnalysisExplanation.module_type == module_type)
        if analysis_as_of is not None:
            filters.append(AnalysisExplanation.analysis_as_of <= analysis_as_of)
        if algorithm_version is not None:
            filters.append(AnalysisExplanation.algorithm_version == algorithm_version)
        if rule_set_version is not None:
            filters.append(AnalysisExplanation.rule_set_version == rule_set_version)

        statement = (
            select(AnalysisExplanation)
            .where(*filters)
            .order_by(
                AnalysisExplanation.analysis_as_of.desc(),
                AnalysisExplanation.explanation_id.desc(),
            )
        )
        return self.paginate(statement, page=page, page_size=page_size)

    def get_latest_explanation(
        self,
        *,
        entity_type: str,
        entity_id: int,
        module_type: str,
    ) -> AnalysisExplanation | None:
        """Return the newest explanation snapshot for one module/entity."""

        statement = (
            select(AnalysisExplanation)
            .where(
                AnalysisExplanation.entity_type == entity_type,
                AnalysisExplanation.entity_id == entity_id,
                AnalysisExplanation.module_type == module_type,
            )
            .order_by(
                AnalysisExplanation.analysis_as_of.desc(),
                AnalysisExplanation.explanation_id.desc(),
            )
            .limit(1)
        )
        return self.session.scalar(statement)


class AnalysisLineageQueryRepository(BaseRepository[AnalysisLineageRecord]):
    """Query weakly linked lineage records without resolving business objects."""

    model = AnalysisLineageRecord

    def get_lineage_by_target(
        self,
        *,
        target_type: str,
        target_id: int,
        source_type: str | None = None,
        relationship_type: str | None = None,
    ) -> list[AnalysisLineageRecord]:
        """Return target lineage in deterministic creation order."""

        filters = [
            AnalysisLineageRecord.target_type == target_type,
            AnalysisLineageRecord.target_id == target_id,
        ]
        if source_type is not None:
            filters.append(AnalysisLineageRecord.source_type == source_type)
        if relationship_type is not None:
            filters.append(
                AnalysisLineageRecord.relationship_type == relationship_type
            )

        statement = (
            select(AnalysisLineageRecord)
            .where(*filters)
            .order_by(
                AnalysisLineageRecord.created_at.asc(),
                AnalysisLineageRecord.lineage_id.asc(),
            )
        )
        return list(self.session.scalars(statement).all())


__all__ = [
    "AnalysisExplanationQueryRepository",
    "AnalysisLineageQueryRepository",
]
