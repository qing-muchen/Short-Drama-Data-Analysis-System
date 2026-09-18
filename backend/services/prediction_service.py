"""Prediction business orchestration and transaction boundary."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from typing import Any, Callable, Protocol

from sqlalchemy.orm import Session

from analytics.context import normalize_utc
from analytics.prediction import (
    PREDICTION_ALGORITHM_VERSION,
    PREDICTION_METRIC,
    CumulativePlayCountPoint,
    PredictionCalculationError,
    PredictionCalculationResult,
    calculate_prediction,
)
from repositories.import_repository import OperationLogRepository
from repositories.prediction_repository import PredictionRepository
from services.base import BaseService


NO_HISTORY = "NO_HISTORY"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
DATE_GAP = "DATE_GAP"
INVALID_REVISION = "INVALID_REVISION"
INVALID_METRIC = "INVALID_METRIC"


@dataclass(frozen=True, slots=True)
class PredictionContext:
    """Immutable identity shared by history reads, calculation, and audit."""

    drama_id: int
    analysis_as_of: datetime
    metric_type: str = PREDICTION_METRIC
    algorithm_version: str = PREDICTION_ALGORITHM_VERSION


@dataclass(frozen=True, slots=True)
class PredictionObservation:
    """Prepared revision fact supplied by the history provider.

    The provider may return more than one revision for an observation day. The
    Service selects the latest revision whose ``changed_at`` is not after the
    context cutoff, then aggregates comparable active platforms.
    """

    observation_date: date
    platform_id: int
    play_count: int | None
    changed_at: datetime
    revision_id: int = 0
    revision_action: str = "INITIAL"
    platform_active: bool = True


class PredictionHistoryProvider(Protocol):
    """Read-only contract for as-of prediction input preparation."""

    def get_prediction_history(
        self,
        *,
        drama_id: int,
        analysis_as_of: datetime,
    ) -> Sequence[PredictionObservation | CumulativePlayCountPoint]: ...


PredictionCalculator = Callable[
    [Sequence[CumulativePlayCountPoint]], PredictionCalculationResult
]


@dataclass(frozen=True, slots=True)
class PredictionServiceResult:
    """Outcome of one atomic prediction attempt and its audit counters."""

    context: PredictionContext
    prediction: Any | None
    predicted_count: int
    skipped_count: int
    skipped_reason: str | None = None

    @property
    def calculated_count(self) -> int:
        """Compatibility alias for services that call successful rows calculated."""

        return self.predicted_count


class PredictionService(BaseService):
    """Prepare historical input, call Calculator, persist, and audit atomically."""

    def __init__(
        self,
        session: Session,
        history: PredictionHistoryProvider,
        predictions: PredictionRepository,
        operation_logs: OperationLogRepository,
        *,
        calculator: PredictionCalculator = calculate_prediction,
    ) -> None:
        # The history provider is intentionally not treated as a Repository: it
        # is an injected read contract and may be AnalyticsService-backed.
        super().__init__(session, predictions, operation_logs)
        self.history = history
        self.predictions = predictions
        self.operation_logs = operation_logs
        self.calculator = calculator

    def calculate_prediction(
        self,
        drama_id: int,
        *,
        analysis_as_of: datetime,
        administrator_id: int,
        request_id: str | None = None,
    ) -> PredictionServiceResult:
        """Calculate one drama prediction and audit it in one transaction."""

        context = PredictionContext(
            drama_id=drama_id,
            analysis_as_of=normalize_utc(analysis_as_of),
        )

        with self.transaction():
            raw_history = self.history.get_prediction_history(
                drama_id=context.drama_id,
                analysis_as_of=context.analysis_as_of,
            )
            points, skip_reason = self._build_daily_points(
                raw_history,
                context=context,
            )
            if skip_reason is not None:
                self._audit(
                    context=context,
                    administrator_id=administrator_id,
                    request_id=request_id,
                    predicted_count=0,
                    skipped_count=1,
                    skipped_reason=skip_reason,
                )
                return PredictionServiceResult(
                    context=context,
                    prediction=None,
                    predicted_count=0,
                    skipped_count=1,
                    skipped_reason=skip_reason,
                )

            try:
                calculated = self.calculator(points)
            except PredictionCalculationError as error:
                mapped_reason = self._map_calculator_error(error.code)
                if mapped_reason is None:
                    raise
                self._audit(
                    context=context,
                    administrator_id=administrator_id,
                    request_id=request_id,
                    predicted_count=0,
                    skipped_count=1,
                    skipped_reason=mapped_reason,
                )
                return PredictionServiceResult(
                    context=context,
                    prediction=None,
                    predicted_count=0,
                    skipped_count=1,
                    skipped_reason=mapped_reason,
                )

            prediction = self.predictions.replace_prediction(
                {
                    "drama_id": context.drama_id,
                    "metric_type": context.metric_type,
                    "prediction_date": calculated.prediction_date,
                    "target_date": calculated.target_date,
                    "predicted_value": calculated.predicted_value,
                    "algorithm_version": context.algorithm_version,
                    "analysis_as_of": context.analysis_as_of,
                }
            )
            self._audit(
                context=context,
                administrator_id=administrator_id,
                request_id=request_id,
                predicted_count=1,
                skipped_count=0,
                skipped_reason=None,
            )
            return PredictionServiceResult(
                context=context,
                prediction=prediction,
                predicted_count=1,
                skipped_count=0,
            )

    def get_latest_prediction(self, drama_id: int) -> Any | None:
        """Delegate latest-result lookup without recalculating."""

        return self.read(
            self.predictions.get_latest_prediction,
            drama_id=drama_id,
            metric_type=PREDICTION_METRIC,
            algorithm_version=PREDICTION_ALGORITHM_VERSION,
        )

    def get_prediction_history(self, drama_id: int, *, limit: int = 90) -> list[Any]:
        """Delegate chronological prediction history lookup."""

        return self.read(
            self.predictions.get_predictions_by_drama,
            drama_id=drama_id,
            metric_type=PREDICTION_METRIC,
            algorithm_version=PREDICTION_ALGORITHM_VERSION,
            limit=limit,
        )

    def get_prediction_range(
        self,
        drama_id: int,
        *,
        start_date: date,
        end_date: date,
    ) -> list[Any]:
        """Delegate target-date range lookup without sorting or recalculation."""

        return self.read(
            self.predictions.get_prediction_range,
            drama_id=drama_id,
            start_date=start_date,
            end_date=end_date,
            metric_type=PREDICTION_METRIC,
            algorithm_version=PREDICTION_ALGORITHM_VERSION,
        )

    def _build_daily_points(
        self,
        observations: Sequence[PredictionObservation | CumulativePlayCountPoint],
        *,
        context: PredictionContext,
    ) -> tuple[list[CumulativePlayCountPoint], str | None]:
        if not observations:
            return [], NO_HISTORY

        if all(isinstance(item, CumulativePlayCountPoint) for item in observations):
            points = list(observations)
            if len(points) < 8:
                return [], INSUFFICIENT_HISTORY
            if any(
                current.observation_date
                <= previous.observation_date
                for previous, current in zip(points, points[1:])
            ):
                return [], DATE_GAP
            if any(
                current.observation_date
                != previous.observation_date + timedelta(days=1)
                for previous, current in zip(points[-8:], points[-7:])
            ):
                return [], DATE_GAP
            return points[-8:], None

        if not all(isinstance(item, PredictionObservation) for item in observations):
            return [], INVALID_REVISION

        eligible: list[PredictionObservation] = []
        saw_future_revision = False
        for item in observations:
            changed_at = normalize_utc(item.changed_at)
            if changed_at > context.analysis_as_of:
                saw_future_revision = True
                continue
            if item.revision_action not in {"INITIAL", "CORRECTION", "VOID"}:
                return [], INVALID_REVISION
            eligible.append(
                PredictionObservation(
                    observation_date=item.observation_date,
                    platform_id=item.platform_id,
                    play_count=item.play_count,
                    changed_at=changed_at,
                    revision_id=item.revision_id,
                    revision_action=item.revision_action,
                    platform_active=item.platform_active,
                )
            )

        if not eligible:
            if saw_future_revision:
                return [], INVALID_REVISION
            return [], NO_HISTORY

        latest_by_platform_day: dict[tuple[int, date], PredictionObservation] = {}
        for item in eligible:
            key = (item.platform_id, item.observation_date)
            previous = latest_by_platform_day.get(key)
            if previous is None or (item.changed_at, item.revision_id) > (
                previous.changed_at,
                previous.revision_id,
            ):
                latest_by_platform_day[key] = item

        by_date: dict[date, dict[int, PredictionObservation]] = {}
        for item in latest_by_platform_day.values():
            # The revision visible at the cutoff owns the slot.  In particular,
            # a visible VOID must not fall back to an older valid revision.
            if item.revision_action == "VOID" or not item.platform_active:
                continue
            if item.play_count is None or item.play_count < 0:
                return [], INVALID_METRIC
            by_date.setdefault(item.observation_date, {})[item.platform_id] = item
        if not by_date:
            return [], INVALID_REVISION
        dates = sorted(by_date)
        if len(dates) < 8:
            return [], INSUFFICIENT_HISTORY

        for start_index in range(len(dates) - 8, -1, -1):
            window_start = dates[start_index]
            window_dates = [
                window_start + timedelta(days=offset)
                for offset in range(8)
            ]
            if any(day not in by_date for day in window_dates):
                continue
            common_platforms = set(by_date[window_dates[0]])
            for day in window_dates[1:]:
                common_platforms.intersection_update(by_date[day])
            if not common_platforms:
                continue
            points = [
                CumulativePlayCountPoint(
                    observation_date=day,
                    play_count=sum(
                        by_date[day][platform_id].play_count or 0
                        for platform_id in common_platforms
                    ),
                )
                for day in window_dates
            ]
            return points, None

        return [], DATE_GAP

    @staticmethod
    def _map_calculator_error(code: str) -> str | None:
        if code in {"EMPTY_INPUT", "INSUFFICIENT_HISTORY"}:
            return INSUFFICIENT_HISTORY
        if code in {"INSUFFICIENT_DAILY_POINTS", "INVALID_DATE_SEQUENCE"}:
            return DATE_GAP
        if code == "INVALID_CUMULATIVE_SEQUENCE":
            return INVALID_REVISION
        if code in {
            "INVALID_PLAY_COUNT",
            "NON_FINITE_PLAY_COUNT",
            "INVALID_INPUT_POINT",
        }:
            return INVALID_METRIC
        return None

    def _audit(
        self,
        *,
        context: PredictionContext,
        administrator_id: int,
        request_id: str | None,
        predicted_count: int,
        skipped_count: int,
        skipped_reason: str | None,
    ) -> None:
        detail = {
            "algorithm_version": context.algorithm_version,
            "metric_type": context.metric_type,
            "drama_id": context.drama_id,
            "analysis_as_of": context.analysis_as_of.isoformat(),
            "predicted_count": predicted_count,
            "skipped_count": skipped_count,
            "skipped_reasons": ({skipped_reason: skipped_count} if skipped_reason else {}),
        }
        values: dict[str, Any] = {
            "actor_user_id": administrator_id,
            "target_drama_id": context.drama_id,
            "operation_type": "PREDICTION_CALCULATE",
            "result_status": "SUCCESS",
            "summary": json.dumps(
                detail,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        }
        if request_id is not None:
            values["request_id"] = request_id
        self.operation_logs.create(values)


__all__ = (
    "DATE_GAP",
    "INSUFFICIENT_HISTORY",
    "INVALID_METRIC",
    "INVALID_REVISION",
    "NO_HISTORY",
    "PredictionContext",
    "PredictionHistoryProvider",
    "PredictionObservation",
    "PredictionService",
    "PredictionServiceResult",
)
