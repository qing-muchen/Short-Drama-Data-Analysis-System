"""Read-only application service for persisted explanation snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from repositories.base import Page
from repositories.explanation_query_repository import (
    AnalysisExplanationQueryRepository,
    AnalysisLineageQueryRepository,
)
from services.base import BaseService


class AnalysisExplanationQueryService(BaseService):
    """Validate query arguments and delegate reads to Query Repositories."""

    def __init__(
        self,
        session: Any,
        explanations: AnalysisExplanationQueryRepository,
        lineage: AnalysisLineageQueryRepository,
    ) -> None:
        super().__init__(session, explanations, lineage)
        self.explanations = explanations
        self.lineage = lineage

    def get_explanations(
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
    ) -> Page[Any]:
        self._validate_page(page, page_size)
        return self.read(
            self.explanations.get_explanations_by_entity,
            entity_type=entity_type,
            entity_id=entity_id,
            module_type=module_type,
            analysis_as_of=analysis_as_of,
            algorithm_version=algorithm_version,
            rule_set_version=rule_set_version,
            page=page,
            page_size=page_size,
        )

    def get_latest_explanation(
        self,
        *,
        entity_type: str,
        entity_id: int,
        module_type: str,
    ) -> Any | None:
        return self.read(
            self.explanations.get_latest_explanation,
            entity_type=entity_type,
            entity_id=entity_id,
            module_type=module_type,
        )

    def get_lineage(
        self,
        *,
        target_type: str,
        target_id: int,
        source_type: str | None = None,
        relationship_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[Any]:
        """Return a paged read result while preserving Repository ordering."""

        self._validate_page(page, page_size)
        items = self.read(
            self.lineage.get_lineage_by_target,
            target_type=target_type,
            target_id=target_id,
            source_type=source_type,
            relationship_type=relationship_type,
        )
        start = (page - 1) * page_size
        return Page(
            page=page,
            page_size=page_size,
            total=len(items),
            items=items[start : start + page_size],
        )

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")


__all__ = ["AnalysisExplanationQueryService"]
