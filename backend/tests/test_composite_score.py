"""Unit tests for the database-independent Composite Score V1.0 core."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from analytics.composite_score import (
    COMPOSITE_SCORE_VERSION,
    LIFECYCLE_STAGE_SCORE_NAME,
    CompositeScoreValidationError,
    calculate_composite_score,
    calculate_engagement_rate,
    calculate_growth_score,
    calculate_lifecycle_stage_score,
    calculate_min_max_score,
    determine_score_level,
    round_half_up,
)


def test_normal_composite_score_calculation() -> None:
    result = calculate_composite_score(
        heat_score=100,
        growth_score=80,
        engagement_score=60,
        lifecycle_score=40,
    )

    assert result.total_score == Decimal("80.00")
    assert result.level == "A"
    assert result.algorithm_version == COMPOSITE_SCORE_VERSION
    assert LIFECYCLE_STAGE_SCORE_NAME == "Lifecycle Stage Score"


@pytest.mark.parametrize(
    ("component", "expected"),
    [
        ("heat_score", Decimal("40.00")),
        ("growth_score", Decimal("30.00")),
        ("engagement_score", Decimal("20.00")),
        ("lifecycle_score", Decimal("10.00")),
    ],
)
def test_each_weight_contributes_exactly(
    component: str,
    expected: Decimal,
) -> None:
    values = {
        "heat_score": 0,
        "growth_score": 0,
        "engagement_score": 0,
        "lifecycle_score": 0,
    }
    values[component] = 100

    result = calculate_composite_score(**values)

    assert result.total_score == expected


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        ("100.00", "S"),
        ("90.00", "S"),
        ("89.99", "A"),
        ("75.00", "A"),
        ("74.99", "B"),
        ("60.00", "B"),
        ("59.99", "C"),
        ("0.00", "C"),
    ],
)
def test_score_level_boundaries(score: str, expected_level: str) -> None:
    assert determine_score_level(Decimal(score)) == expected_level


@pytest.mark.parametrize(
    ("days_online", "expected"),
    [
        (0, "100.00"),
        (7, "100.00"),
        (8, "80.00"),
        (30, "80.00"),
        (31, "60.00"),
        (90, "60.00"),
        (91, "40.00"),
        (180, "40.00"),
        (181, "20.00"),
        (10_000, "20.00"),
    ],
)
def test_lifecycle_stage_boundaries(days_online: int, expected: str) -> None:
    release_day = date(2026, 1, 1)
    score_day = date.fromordinal(release_day.toordinal() + days_online)

    assert calculate_lifecycle_stage_score(release_day, score_day) == Decimal(
        expected
    )


def test_lifecycle_accepts_datetime_values() -> None:
    assert calculate_lifecycle_stage_score(
        datetime(2026, 1, 1, 23, 59),
        datetime(2026, 1, 9, 0, 1),
    ) == Decimal("80.00")


def test_round_half_up_keeps_two_decimal_places() -> None:
    assert round_half_up(Decimal("2.345")) == Decimal("2.35")
    assert round_half_up(Decimal("2.344")) == Decimal("2.34")
    assert round_half_up(Decimal("-2.345")) == Decimal("-2.35")

    boundary = calculate_composite_score(
        heat_score=Decimal("74.995"),
        growth_score=Decimal("74.995"),
        engagement_score=Decimal("74.995"),
        lifecycle_score=Decimal("74.995"),
    )
    assert boundary.total_score == Decimal("75.00")
    assert boundary.level == "A"


def test_equal_min_max_uses_frozen_zero_range_rule() -> None:
    assert calculate_min_max_score(500, 500, 500) == Decimal("0.00")


def test_missing_release_date_and_future_release_are_rejected() -> None:
    with pytest.raises(CompositeScoreValidationError) as missing:
        calculate_lifecycle_stage_score(None, date(2026, 1, 1))
    assert missing.value.code == "MISSING_RELEASE_DATE"

    with pytest.raises(CompositeScoreValidationError) as future:
        calculate_lifecycle_stage_score(date(2026, 1, 2), date(2026, 1, 1))
    assert future.value.code == "FUTURE_RELEASE_DATE"


def test_zero_play_count_is_rejected() -> None:
    with pytest.raises(CompositeScoreValidationError) as error:
        calculate_engagement_rate(
            play_count=0,
            like_count=1,
            comment_count=1,
            favorite_count=1,
            share_count=1,
        )
    assert error.value.code == "ZERO_PLAY_COUNT"


def test_missing_growth_history_is_rejected() -> None:
    with pytest.raises(CompositeScoreValidationError) as error:
        calculate_growth_score(None, Decimal("-1"), Decimal("2"))
    assert error.value.code == "INSUFFICIENT_GROWTH_HISTORY"


def test_extreme_values_remain_deterministic() -> None:
    magnitude = 10**24
    assert calculate_min_max_score(magnitude, -magnitude, magnitude) == Decimal(
        "100.00"
    )
    assert calculate_growth_score(
        Decimal("-0.5"),
        Decimal("-1"),
        Decimal("1"),
    ) == Decimal("25.00")
    assert calculate_engagement_rate(
        play_count=1,
        like_count=magnitude,
        comment_count=magnitude,
        favorite_count=magnitude,
        share_count=magnitude,
    ) == Decimal(4 * magnitude)


@pytest.mark.parametrize("invalid_score", [-1, 100.01, Decimal("NaN")])
def test_invalid_component_extremes_are_rejected(
    invalid_score: int | float | Decimal,
) -> None:
    with pytest.raises(CompositeScoreValidationError):
        calculate_composite_score(
            heat_score=invalid_score,
            growth_score=50,
            engagement_score=50,
            lifecycle_score=50,
        )
