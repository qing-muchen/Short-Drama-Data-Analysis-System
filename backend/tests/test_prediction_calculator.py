"""Pure unit tests for Phase 3 Moving Average V1.0."""

from datetime import date
from decimal import Decimal

import pytest

from analytics.prediction import (
    PREDICTION_ALGORITHM_VERSION,
    PREDICTION_METRIC,
    CumulativePlayCountPoint,
    PredictionCalculationError,
    calculate_prediction,
)


BASE_DATE = date(2026, 1, 1)


def points(values: list[int | Decimal]) -> list[CumulativePlayCountPoint]:
    return [
        CumulativePlayCountPoint(
            observation_date=BASE_DATE.fromordinal(BASE_DATE.toordinal() + index),
            play_count=value,
        )
        for index, value in enumerate(values)
    ]


def test_eight_points_produce_seven_increment_moving_average() -> None:
    result = calculate_prediction(points([100, 110, 130, 160, 200, 250, 310, 380]))

    assert result.predicted_increment == Decimal("40.00")
    assert result.predicted_value == Decimal("420.00")
    assert result.prediction_date == date(2026, 1, 8)
    assert result.target_date == date(2026, 1, 9)
    assert result.target_metric == PREDICTION_METRIC
    assert result.algorithm_version == PREDICTION_ALGORITHM_VERSION


def test_prediction_uses_latest_cumulative_value_plus_increment() -> None:
    result = calculate_prediction(points([100, 200, 300, 400, 500, 600, 700, 800]))

    assert result.predicted_increment == Decimal("100.00")
    assert result.predicted_value == Decimal("900.00")


def test_more_than_eight_points_use_latest_contiguous_window() -> None:
    result = calculate_prediction(
        points([1, 2, 3, 4, 100, 110, 120, 130, 140])
    )

    assert result.predicted_increment == Decimal("19.71")
    assert result.predicted_value == Decimal("159.71")


@pytest.mark.parametrize(
    ("values", "code"),
    [
        ([100] * 7, "INSUFFICIENT_HISTORY"),
        ([], "EMPTY_INPUT"),
    ],
)
def test_empty_and_insufficient_history(values: list[int], code: str) -> None:
    with pytest.raises(PredictionCalculationError) as error:
        calculate_prediction(points(values))
    assert error.value.code == code


def test_date_gap_is_insufficient_daily_points() -> None:
    input_points = [
        CumulativePlayCountPoint(date(2026, 1, 1), 100),
        CumulativePlayCountPoint(date(2026, 1, 2), 110),
        CumulativePlayCountPoint(date(2026, 1, 3), 120),
        CumulativePlayCountPoint(date(2026, 1, 4), 130),
        CumulativePlayCountPoint(date(2026, 1, 6), 140),
        CumulativePlayCountPoint(date(2026, 1, 7), 150),
        CumulativePlayCountPoint(date(2026, 1, 8), 160),
        CumulativePlayCountPoint(date(2026, 1, 9), 170),
    ]

    with pytest.raises(PredictionCalculationError) as error:
        calculate_prediction(input_points)
    assert error.value.code == "INSUFFICIENT_DAILY_POINTS"


def test_input_order_must_be_chronological() -> None:
    input_points = points([100, 110, 120, 130, 140, 150, 160, 170])
    input_points[2], input_points[3] = input_points[3], input_points[2]

    with pytest.raises(PredictionCalculationError) as error:
        calculate_prediction(input_points)
    assert error.value.code == "INVALID_DATE_SEQUENCE"


def test_cumulative_regression_is_rejected() -> None:
    with pytest.raises(PredictionCalculationError) as error:
        calculate_prediction(points([100, 110, 120, 115, 130, 140, 150, 160]))
    assert error.value.code == "INVALID_CUMULATIVE_SEQUENCE"


def test_zero_growth_is_valid() -> None:
    result = calculate_prediction(points([100] * 8))

    assert result.predicted_increment == Decimal("0.00")
    assert result.predicted_value == Decimal("100.00")


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (-1, "INVALID_PLAY_COUNT"),
        (Decimal("NaN"), "NON_FINITE_PLAY_COUNT"),
        (Decimal("Infinity"), "NON_FINITE_PLAY_COUNT"),
    ],
)
def test_invalid_play_counts_are_rejected(value: Decimal | int, code: str) -> None:
    input_points = points([100, 110, 120, 130, 140, 150, 160, 170])
    input_points[3] = CumulativePlayCountPoint(BASE_DATE.fromordinal(BASE_DATE.toordinal() + 3), value)

    with pytest.raises(PredictionCalculationError) as error:
        calculate_prediction(input_points)
    assert error.value.code == code


def test_large_values_use_decimal_without_float_drift() -> None:
    base = Decimal("999999999999999999.99")
    result = calculate_prediction(
        points([base + Decimal(index * 2) for index in range(8)])
    )

    assert result.predicted_increment == Decimal("2.00")
    assert result.predicted_value == Decimal("1000000000000000015.99")


def test_round_half_up_is_stable_for_fractional_increment() -> None:
    result = calculate_prediction(
        points(
            [
                Decimal("0.00"),
                Decimal("0.01"),
                Decimal("0.02"),
                Decimal("0.03"),
                Decimal("0.04"),
                Decimal("0.05"),
                Decimal("0.06"),
                Decimal("0.075"),
            ]
        )
    )

    assert result.predicted_increment == Decimal("0.01")
    assert result.predicted_value == Decimal("0.09")
