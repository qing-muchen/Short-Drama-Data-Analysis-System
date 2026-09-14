"""Persistence operations for versioned, scoped composite-score results."""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import joinedload

from models.drama import Drama
from models.score import DramaScore
from repositories.base import BaseRepository, Page


class ScoreRepository(BaseRepository[DramaScore]):
    """Store and query score results without calculating them or owning commits."""

    model = DramaScore

    def replace_scope_scores(
        self,
        *,
        score_date: date,
        algorithm_version: str,
        score_scope_type: str,
        score_scope_id: int,
        scores: Sequence[Mapping[str, Any]],
    ) -> list[DramaScore]:
        """Replace every score in one date, model-version, and scope set."""

        self.session.execute(
            delete(DramaScore)
            .where(
                DramaScore.score_date == score_date,
                DramaScore.algorithm_version == algorithm_version,
                DramaScore.score_scope_type == score_scope_type,
                DramaScore.score_scope_id == score_scope_id,
            )
            .execution_options(synchronize_session="fetch")
        )
        scope_values = {
            "score_date": score_date,
            "algorithm_version": algorithm_version,
            "score_scope_type": score_scope_type,
            "score_scope_id": score_scope_id,
        }
        entities: list[DramaScore] = []
        for values in scores:
            payload = {**dict(values), **scope_values}
            self._validate_columns(payload, allow_primary_key=False)
            entities.append(DramaScore(**payload))
        self.session.add_all(entities)
        self.session.flush()
        return entities

    def paginate_ranking(
        self,
        *,
        score_date: date,
        algorithm_version: str,
        score_scope_type: str,
        score_scope_id: int,
        page: int,
        page_size: int,
        level: str | None = None,
    ) -> Page[DramaScore]:
        """Return one stable, database-sorted score ranking page."""

        statement = (
            select(DramaScore)
            .join(Drama, Drama.drama_id == DramaScore.drama_id)
            .options(joinedload(DramaScore.drama))
            .where(
                DramaScore.score_date == score_date,
                DramaScore.algorithm_version == algorithm_version,
                DramaScore.score_scope_type == score_scope_type,
                DramaScore.score_scope_id == score_scope_id,
            )
        )
        if level is not None:
            statement = statement.where(DramaScore.level == level)
        statement = statement.order_by(
            DramaScore.total_score.desc(),
            DramaScore.heat_score.desc(),
            DramaScore.growth_score.desc(),
            Drama.drama_code.asc(),
        )
        return self.paginate(statement, page=page, page_size=page_size)

    def get_latest_by_drama(
        self,
        *,
        drama_id: int,
        algorithm_version: str,
        score_scope_type: str,
        score_scope_id: int,
    ) -> DramaScore | None:
        """Return a drama's most recent score in one model version and scope."""

        statement = (
            select(DramaScore)
            .options(joinedload(DramaScore.drama))
            .where(
                DramaScore.drama_id == drama_id,
                DramaScore.algorithm_version == algorithm_version,
                DramaScore.score_scope_type == score_scope_type,
                DramaScore.score_scope_id == score_scope_id,
            )
            .order_by(
                DramaScore.score_date.desc(),
                DramaScore.analysis_as_of.desc(),
                DramaScore.score_id.desc(),
            )
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_latest_score_date(
        self,
        *,
        algorithm_version: str,
        score_scope_type: str,
        score_scope_id: int,
    ) -> date | None:
        """Return the latest available score date for one version and scope."""

        statement = select(func.max(DramaScore.score_date)).where(
            DramaScore.algorithm_version == algorithm_version,
            DramaScore.score_scope_type == score_scope_type,
            DramaScore.score_scope_id == score_scope_id,
        )
        return self.session.scalar(statement)

    def get_level_distribution(
        self,
        *,
        score_date: date,
        algorithm_version: str,
        score_scope_type: str,
        score_scope_id: int,
    ) -> dict[str, int]:
        """Count persisted S/A/B/C values without deriving score levels."""

        statement = (
            select(DramaScore.level, func.count(DramaScore.score_id))
            .where(
                DramaScore.score_date == score_date,
                DramaScore.algorithm_version == algorithm_version,
                DramaScore.score_scope_type == score_scope_type,
                DramaScore.score_scope_id == score_scope_id,
            )
            .group_by(DramaScore.level)
        )
        distribution = {level: 0 for level in ("S", "A", "B", "C")}
        for level, count in self.session.execute(statement).all():
            distribution[str(level)] = int(count)
        return distribution
