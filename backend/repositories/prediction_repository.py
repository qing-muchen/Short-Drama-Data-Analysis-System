"""Persistence operations for drama-level prediction results."""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from sqlalchemy import delete, select

from models.prediction import PredictionResult
from repositories.base import BaseRepository


PredictionPayload = PredictionResult | Mapping[str, Any]


class PredictionRepository(BaseRepository[PredictionResult]):
    """Store and query prediction results without calculating or committing."""

    model = PredictionResult

    def save_prediction(self, prediction: PredictionPayload) -> PredictionResult:
        """Add and flush one prediction; the caller owns the transaction."""

        entity = self._as_entity(prediction)
        self.session.add(entity)
        self.session.flush()
        return entity

    def replace_prediction(self, prediction: PredictionPayload) -> PredictionResult:
        """Replace one target-date result for a drama and algorithm identity."""

        entity = self._as_entity(prediction)
        self.session.execute(
            delete(PredictionResult)
            .where(
                PredictionResult.drama_id == entity.drama_id,
                PredictionResult.metric_type == entity.metric_type,
                PredictionResult.algorithm_version == entity.algorithm_version,
                PredictionResult.target_date == entity.target_date,
            )
            .execution_options(synchronize_session="fetch")
        )
        self.session.add(entity)
        self.session.flush()
        return entity

    def get_latest_prediction(
        self,
        *,
        drama_id: int,
        metric_type: str,
        algorithm_version: str,
    ) -> PredictionResult | None:
        """Return the most recently analysed prediction for one drama."""

        statement = (
            select(PredictionResult)
            .where(
                PredictionResult.drama_id == drama_id,
                PredictionResult.metric_type == metric_type,
                PredictionResult.algorithm_version == algorithm_version,
            )
            .order_by(
                PredictionResult.analysis_as_of.desc(),
                PredictionResult.created_at.desc(),
                PredictionResult.prediction_id.desc(),
            )
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_predictions_by_drama(
        self,
        *,
        drama_id: int,
        metric_type: str,
        algorithm_version: str,
        limit: int,
    ) -> list[PredictionResult]:
        """Return a bounded chronological prediction history for one drama."""

        self._validate_window(offset=0, limit=limit)
        statement = (
            select(PredictionResult)
            .where(
                PredictionResult.drama_id == drama_id,
                PredictionResult.metric_type == metric_type,
                PredictionResult.algorithm_version == algorithm_version,
            )
            .order_by(
                PredictionResult.target_date.asc(),
                PredictionResult.prediction_id.asc(),
            )
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

    def get_prediction_range(
        self,
        *,
        drama_id: int,
        start_date: date,
        end_date: date,
        metric_type: str | None = None,
        algorithm_version: str | None = None,
    ) -> list[PredictionResult]:
        """Return predictions whose target dates fall in an inclusive range."""

        if start_date > end_date:
            raise ValueError("start_date must not be later than end_date")
        filters = [
            PredictionResult.drama_id == drama_id,
            PredictionResult.target_date >= start_date,
            PredictionResult.target_date <= end_date,
        ]
        if metric_type is not None:
            filters.append(PredictionResult.metric_type == metric_type)
        if algorithm_version is not None:
            filters.append(PredictionResult.algorithm_version == algorithm_version)
        statement = (
            select(PredictionResult)
            .where(*filters)
            .order_by(
                PredictionResult.target_date.asc(),
                PredictionResult.prediction_id.asc(),
            )
        )
        return list(self.session.scalars(statement).all())

    def delete_prediction_scope(
        self,
        *,
        drama_id: int,
        metric_type: str,
        algorithm_version: str,
    ) -> int:
        """Delete one drama/metric/algorithm result scope without committing."""

        result = self.session.execute(
            delete(PredictionResult)
            .where(
                PredictionResult.drama_id == drama_id,
                PredictionResult.metric_type == metric_type,
                PredictionResult.algorithm_version == algorithm_version,
            )
            .execution_options(synchronize_session="fetch")
        )
        self.session.flush()
        return int(result.rowcount or 0)

    def _as_entity(self, prediction: PredictionPayload) -> PredictionResult:
        if isinstance(prediction, PredictionResult):
            return prediction
        self._validate_columns(prediction, allow_primary_key=False)
        return PredictionResult(**dict(prediction))


__all__ = ("PredictionRepository",)
