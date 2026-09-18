"""Pure Moving Average V1.0 prediction calculations.

This module deliberately accepts prepared daily cumulative observations only. It
does not know about snapshots, revisions, platform aggregation, persistence, or
transactions; those concerns belong to the Repository and Service layers.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Sequence, TypeAlias

Numeric: TypeAlias = int | float | Decimal

PREDICTION_ALGORITHM_VERSION = "Moving Average V1.0"
PREDICTION_METRIC = "PLAY_COUNT"
REQUIRED_CUMULATIVE_POINTS = 8
REQUIRED_DAILY_INCREMENTS = 7
PREDICTION_QUANTUM = Decimal("0.01")
ZERO = Decimal("0")


class PredictionCalculationError(ValueError):
    """Stable domain error raised by the database-independent calculator."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CumulativePlayCountPoint:
    """One chronological daily cumulative play-count observation."""

    observation_date: date
    play_count: Numeric


@dataclass(frozen=True, slots=True)
class PredictionCalculationResult:
    """Moving Average V1.0 output before persistence."""

    prediction_date: date
    target_date: date
    predicted_value: Decimal
    predicted_increment: Decimal
    algorithm_version: str = PREDICTION_ALGORITHM_VERSION
    target_metric: str = PREDICTION_METRIC


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise PredictionCalculationError(
        "INVALID_OBSERVATION_DATE",
        "observation_date must be a date or datetime",
    )


def _as_decimal(value: Numeric) -> Decimal:
    if isinstance(value, bool):
        raise PredictionCalculationError(
            "INVALID_PLAY_COUNT",
            "play_count must be a finite non-negative number",
        )
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise PredictionCalculationError(
            "INVALID_PLAY_COUNT",
            "play_count must be a finite non-negative number",
        ) from error
    if not decimal_value.is_finite():
        raise PredictionCalculationError(
            "NON_FINITE_PLAY_COUNT",
            "play_count must be finite",
        )
    if decimal_value < ZERO:
        raise PredictionCalculationError(
            "INVALID_PLAY_COUNT",
            "play_count cannot be negative",
        )
    return decimal_value


def _coerce_point(
    point: CumulativePlayCountPoint | tuple[date | datetime, Numeric],
) -> CumulativePlayCountPoint:
    if isinstance(point, CumulativePlayCountPoint):
        raw_date, raw_count = point.observation_date, point.play_count
    elif isinstance(point, tuple) and len(point) == 2:
        raw_date, raw_count = point
    else:
        raise PredictionCalculationError(
            "INVALID_INPUT_POINT",
            "each input point must contain observation_date and play_count",
        )
    return CumulativePlayCountPoint(_as_date(raw_date), _as_decimal(raw_count))


def _round(value: Decimal) -> Decimal:
    return value.quantize(PREDICTION_QUANTUM, rounding=ROUND_HALF_UP)


def _prepare_points(
    points: Iterable[CumulativePlayCountPoint | tuple[date | datetime, Numeric]],
) -> list[CumulativePlayCountPoint]:
    prepared = [_coerce_point(point) for point in points]
    if not prepared:
        raise PredictionCalculationError(
            "EMPTY_INPUT",
            "at least one cumulative play-count point is required",
        )
    if len(prepared) < REQUIRED_CUMULATIVE_POINTS:
        raise PredictionCalculationError(
            "INSUFFICIENT_HISTORY",
            "at least eight cumulative daily points are required",
        )

    selected = prepared[-REQUIRED_CUMULATIVE_POINTS:]
    dates = [point.observation_date for point in selected]
    if any(current <= previous for previous, current in zip(dates, dates[1:])):
        raise PredictionCalculationError(
            "INVALID_DATE_SEQUENCE",
            "cumulative points must be in strictly increasing date order",
        )
    expected_dates = [
        dates[0] + timedelta(days=offset)
        for offset in range(REQUIRED_CUMULATIVE_POINTS)
    ]
    if dates != expected_dates:
        raise PredictionCalculationError(
            "INSUFFICIENT_DAILY_POINTS",
            "eight consecutive daily points are required",
        )
    if any(
        current.play_count < previous.play_count
        for previous, current in zip(selected, selected[1:])
    ):
        raise PredictionCalculationError(
            "INVALID_CUMULATIVE_SEQUENCE",
            "cumulative play_count cannot decrease",
        )
    return selected


def calculate_prediction(
    points: Sequence[
        CumulativePlayCountPoint | tuple[date | datetime, Numeric]
    ],
) -> PredictionCalculationResult:
    """Calculate the next-day cumulative play count using Moving Average V1.0.

    V1 converts eight consecutive cumulative daily points into seven daily
    increments, averages those increments, and adds the predicted increment to
    the latest cumulative value. The addition is required by cumulative metric
    semantics; subtracting a positive increment would predict a decline.
    """

    selected = _prepare_points(points)
    increments = [
        current.play_count - previous.play_count
        for previous, current in zip(selected, selected[1:])
    ]
    predicted_increment = _round(
        sum(increments, start=ZERO) / Decimal(REQUIRED_DAILY_INCREMENTS)
    )
    predicted_value = _round(selected[-1].play_count + predicted_increment)
    return PredictionCalculationResult(
        prediction_date=selected[-1].observation_date,
        target_date=selected[-1].observation_date + timedelta(days=1),
        predicted_value=predicted_value,
        predicted_increment=predicted_increment,
    )


def calculate_moving_average_prediction(
    points: Sequence[
        CumulativePlayCountPoint | tuple[date | datetime, Numeric]
    ],
) -> PredictionCalculationResult:
    """Descriptive alias for the frozen Moving Average V1.0 calculator."""

    return calculate_prediction(points)


__all__ = (
    "CumulativePlayCountPoint",
    "PREDICTION_ALGORITHM_VERSION",
    "PREDICTION_METRIC",
    "PredictionCalculationError",
    "PredictionCalculationResult",
    "calculate_moving_average_prediction",
    "calculate_prediction",
)
