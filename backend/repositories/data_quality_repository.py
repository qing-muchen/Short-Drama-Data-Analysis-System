"""Persistence repositories for Phase 2 data-quality governance records."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import contains_eager, joinedload

from models.data_quality import (
    DataQualityRule,
    DataQualityRuleResult,
    DataQualityScore,
)
from repositories.base import BaseRepository

QUALITY_GRADES = ("S", "A", "B", "C")


class DataQualityRuleRepository(BaseRepository[DataQualityRule]):
    """Query versioned rule definitions without executing quality rules."""

    model = DataQualityRule

    def list_effective_rules(
        self,
        *,
        as_of: datetime,
        status: str = "ACTIVE",
        dimension: str | None = None,
        rule_version: str | None = None,
    ) -> list[DataQualityRule]:
        """Return effective rules in stable rule-code/version order."""

        statement = select(DataQualityRule).where(
            DataQualityRule.status == status,
            DataQualityRule.valid_from <= as_of,
            or_(
                DataQualityRule.valid_to.is_(None),
                DataQualityRule.valid_to > as_of,
            ),
        )
        if dimension is not None:
            statement = statement.where(DataQualityRule.dimension == dimension)
        if rule_version is not None:
            statement = statement.where(
                DataQualityRule.rule_version == rule_version
            )
        statement = statement.order_by(
            DataQualityRule.rule_code.asc(),
            DataQualityRule.rule_version.asc(),
            DataQualityRule.quality_rule_id.asc(),
        )
        return list(self.session.scalars(statement).all())

    def list_by_rule_set_version(
        self,
        *,
        rule_set_version: str,
        status: str | None = None,
        dimension: str | None = None,
    ) -> list[DataQualityRule]:
        """Return rules historically referenced by a persisted rule-set version."""

        statement = (
            select(DataQualityRule)
            .join(
                DataQualityRuleResult,
                DataQualityRuleResult.quality_rule_id
                == DataQualityRule.quality_rule_id,
            )
            .join(
                DataQualityScore,
                DataQualityScore.quality_score_id
                == DataQualityRuleResult.quality_score_id,
            )
            .where(DataQualityScore.rule_set_version == rule_set_version)
        )
        if status is not None:
            statement = statement.where(DataQualityRule.status == status)
        if dimension is not None:
            statement = statement.where(DataQualityRule.dimension == dimension)
        statement = statement.distinct().order_by(
            DataQualityRule.rule_code.asc(),
            DataQualityRule.rule_version.asc(),
            DataQualityRule.quality_rule_id.asc(),
        )
        return list(self.session.scalars(statement).all())

    def list_rule_versions(
        self,
        *,
        rule_code: str,
        status: str | None = None,
    ) -> list[DataQualityRule]:
        """Return all known versions of one rule code for future version review."""

        statement = select(DataQualityRule).where(
            DataQualityRule.rule_code == rule_code
        )
        if status is not None:
            statement = statement.where(DataQualityRule.status == status)
        statement = statement.order_by(
            DataQualityRule.valid_from.desc(),
            DataQualityRule.rule_version.desc(),
            DataQualityRule.quality_rule_id.desc(),
        )
        return list(self.session.scalars(statement).all())


class DataQualityRuleResultRepository(BaseRepository[DataQualityRuleResult]):
    """Persist rule execution facts and query them with rule metadata."""

    model = DataQualityRuleResult

    def bulk_create(
        self,
        *,
        quality_score_id: int,
        results: Sequence[Mapping[str, Any]],
    ) -> list[DataQualityRuleResult]:
        """Add and flush a complete rule-result collection without committing."""

        entities: list[DataQualityRuleResult] = []
        for values in results:
            payload = {**dict(values), "quality_score_id": quality_score_id}
            self._validate_columns(payload, allow_primary_key=False)
            entities.append(DataQualityRuleResult(**payload))
        self.session.add_all(entities)
        self.session.flush()
        return entities

    def list_by_score_id(
        self,
        *,
        quality_score_id: int,
    ) -> list[DataQualityRuleResult]:
        """Return all results in one query, eager-loading rules to avoid N+1."""

        statement = (
            select(DataQualityRuleResult)
            .join(
                DataQualityRule,
                DataQualityRule.quality_rule_id
                == DataQualityRuleResult.quality_rule_id,
            )
            .options(contains_eager(DataQualityRuleResult.rule))
            .where(DataQualityRuleResult.quality_score_id == quality_score_id)
            .order_by(
                DataQualityRule.rule_code.asc(),
                DataQualityRule.rule_version.asc(),
                DataQualityRuleResult.quality_rule_result_id.asc(),
            )
        )
        return list(self.session.scalars(statement).unique().all())


class DataQualityScoreRepository(BaseRepository[DataQualityScore]):
    """Store scoped quality scores and expose read-only trend aggregates."""

    model = DataQualityScore

    def save_score(self, values: Mapping[str, Any]) -> DataQualityScore:
        """Add and flush one quality score without committing its transaction."""

        return self.create(values)

    def replace_scope_scores(
        self,
        *,
        score_date: date,
        rule_set_version: str,
        score_scope_type: str,
        score_scope_id: int,
        scores: Sequence[Mapping[str, Any]],
    ) -> list[DataQualityScore]:
        """Replace one date, rule-set, and scope collection atomically."""

        self.session.execute(
            delete(DataQualityScore)
            .where(
                DataQualityScore.score_date == score_date,
                DataQualityScore.rule_set_version == rule_set_version,
                DataQualityScore.score_scope_type == score_scope_type,
                DataQualityScore.score_scope_id == score_scope_id,
            )
            .execution_options(synchronize_session="fetch")
        )
        scope_values = {
            "score_date": score_date,
            "rule_set_version": rule_set_version,
            "score_scope_type": score_scope_type,
            "score_scope_id": score_scope_id,
        }
        entities: list[DataQualityScore] = []
        for values in scores:
            payload = {**dict(values), **scope_values}
            self._validate_columns(payload, allow_primary_key=False)
            entities.append(DataQualityScore(**payload))
        self.session.add_all(entities)
        self.session.flush()
        return entities

    def get_latest_score_date(
        self,
        *,
        score_scope_type: str,
        score_scope_id: int,
        algorithm_version: str | None = None,
        rule_set_version: str | None = None,
    ) -> date | None:
        """Return the latest score date matching a scope and optional versions."""

        statement = select(func.max(DataQualityScore.score_date)).where(
            DataQualityScore.score_scope_type == score_scope_type,
            DataQualityScore.score_scope_id == score_scope_id,
        )
        statement = self._apply_version_filters(
            statement,
            algorithm_version=algorithm_version,
            rule_set_version=rule_set_version,
        )
        return self.session.scalar(statement)

    def get_current_score(
        self,
        *,
        score_scope_type: str,
        score_scope_id: int,
        algorithm_version: str | None = None,
        rule_set_version: str | None = None,
    ) -> DataQualityScore | None:
        """Return the latest score with all rule details loaded in one query."""

        statement = (
            select(DataQualityScore)
            .options(
                joinedload(DataQualityScore.rule_results).joinedload(
                    DataQualityRuleResult.rule
                )
            )
            .where(
                DataQualityScore.score_scope_type == score_scope_type,
                DataQualityScore.score_scope_id == score_scope_id,
            )
        )
        statement = self._apply_version_filters(
            statement,
            algorithm_version=algorithm_version,
            rule_set_version=rule_set_version,
        )
        statement = statement.order_by(
            DataQualityScore.score_date.desc(),
            DataQualityScore.analysis_as_of.desc(),
            DataQualityScore.quality_score_id.desc(),
        ).limit(1)
        return self.session.execute(statement).unique().scalar_one_or_none()

    def list_history(
        self,
        *,
        score_scope_type: str,
        score_scope_id: int,
        algorithm_version: str | None = None,
        rule_set_version: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 90,
    ) -> list[DataQualityScore]:
        """Return the most recent bounded trend window in chronological order."""

        self._validate_window(offset=0, limit=limit)
        recent_ids = select(DataQualityScore.quality_score_id).where(
            DataQualityScore.score_scope_type == score_scope_type,
            DataQualityScore.score_scope_id == score_scope_id,
        )
        recent_ids = self._apply_version_filters(
            recent_ids,
            algorithm_version=algorithm_version,
            rule_set_version=rule_set_version,
        )
        if start_date is not None:
            recent_ids = recent_ids.where(DataQualityScore.score_date >= start_date)
        if end_date is not None:
            recent_ids = recent_ids.where(DataQualityScore.score_date <= end_date)
        recent_ids = recent_ids.order_by(
            DataQualityScore.score_date.desc(),
            DataQualityScore.analysis_as_of.desc(),
            DataQualityScore.quality_score_id.desc(),
        ).limit(limit)

        statement = (
            select(DataQualityScore)
            .where(DataQualityScore.quality_score_id.in_(recent_ids))
            .order_by(
                DataQualityScore.score_date.asc(),
                DataQualityScore.analysis_as_of.asc(),
                DataQualityScore.quality_score_id.asc(),
            )
        )
        return list(self.session.scalars(statement).all())

    def get_grade_distribution(
        self,
        *,
        score_date: date,
        score_scope_type: str,
        score_scope_id: int,
        algorithm_version: str | None = None,
        rule_set_version: str | None = None,
    ) -> dict[str, int]:
        """Count persisted S/A/B/C grades without deriving classifications."""

        statement = select(
            DataQualityScore.quality_grade,
            func.count(DataQualityScore.quality_score_id),
        ).where(
            DataQualityScore.score_date == score_date,
            DataQualityScore.score_scope_type == score_scope_type,
            DataQualityScore.score_scope_id == score_scope_id,
        )
        statement = self._apply_version_filters(
            statement,
            algorithm_version=algorithm_version,
            rule_set_version=rule_set_version,
        ).group_by(DataQualityScore.quality_grade)

        distribution = {grade: 0 for grade in QUALITY_GRADES}
        for grade, count in self.session.execute(statement).all():
            distribution[str(grade)] = int(count)
        return distribution

    @staticmethod
    def _apply_version_filters(
        statement: Any,
        *,
        algorithm_version: str | None,
        rule_set_version: str | None,
    ) -> Any:
        if algorithm_version is not None:
            statement = statement.where(
                DataQualityScore.algorithm_version == algorithm_version
            )
        if rule_set_version is not None:
            statement = statement.where(
                DataQualityScore.rule_set_version == rule_set_version
            )
        return statement


__all__ = (
    "DataQualityRuleRepository",
    "DataQualityRuleResultRepository",
    "DataQualityScoreRepository",
)
