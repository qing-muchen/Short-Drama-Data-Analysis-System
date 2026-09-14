"""Pure Composite Score V1.0 calculations with deterministic decimal rounding."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Literal, TypeAlias

Numeric: TypeAlias = int | float | Decimal
DateValue: TypeAlias = date | datetime
ScoreLevel: TypeAlias = Literal["S", "A", "B", "C"]

COMPOSITE_SCORE_VERSION = "Composite Score V1.0"
LIFECYCLE_STAGE_SCORE_NAME = "Lifecycle Stage Score"
SCORE_QUANTUM = Decimal("0.01")
ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")

COMPOSITE_WEIGHTS = {
    "heat": Decimal("0.40"),
    "growth": Decimal("0.30"),
    "engagement": Decimal("0.20"),
    "lifecycle": Decimal("0.10"),
}


class CompositeScoreValidationError(ValueError):
    """Report a stable domain error code without depending on HTTP or persistence."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CompositeScoreResult:
    """Rounded Composite Score V1.0 result and its deterministic level."""

    total_score: Decimal
    level: ScoreLevel
    algorithm_version: str = COMPOSITE_SCORE_VERSION


def _as_decimal(value: Numeric, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise CompositeScoreValidationError(
            "INVALID_NUMERIC_VALUE",
            f"{field_name} must be a finite number",
        )
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise CompositeScoreValidationError(
            "INVALID_NUMERIC_VALUE",
            f"{field_name} must be a finite number",
        ) from error
    if not number.is_finite():
        raise CompositeScoreValidationError(
            "INVALID_NUMERIC_VALUE",
            f"{field_name} must be a finite number",
        )
    return number


def round_half_up(value: Numeric) -> Decimal:
    """Round a finite decimal value to two places using ROUND_HALF_UP."""

    return _as_decimal(value, field_name="score").quantize(
        SCORE_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def calculate_min_max_score(
    value: Numeric,
    minimum: Numeric,
    maximum: Numeric,
) -> Decimal:
    """Map one cohort value to 0..100 using the frozen zero-range rule."""

    decimal_value = _as_decimal(value, field_name="value")
    decimal_minimum = _as_decimal(minimum, field_name="minimum")
    decimal_maximum = _as_decimal(maximum, field_name="maximum")
    if decimal_minimum > decimal_maximum:
        raise CompositeScoreValidationError(
            "INVALID_NORMALIZATION_RANGE",
            "minimum must be less than or equal to maximum",
        )
    if not decimal_minimum <= decimal_value <= decimal_maximum:
        raise CompositeScoreValidationError(
            "NORMALIZATION_VALUE_OUT_OF_RANGE",
            "value must be within the normalization range",
        )
    if decimal_minimum == decimal_maximum:
        return round_half_up(ZERO)
    normalized = (
        (decimal_value - decimal_minimum)
        / (decimal_maximum - decimal_minimum)
        * ONE_HUNDRED
    )
    return round_half_up(normalized)


def calculate_growth_score(
    growth_rate: Numeric | None,
    minimum: Numeric,
    maximum: Numeric,
) -> Decimal:
    """Normalize a Growth value or reject a candidate without history."""

    if growth_rate is None:
        raise CompositeScoreValidationError(
            "INSUFFICIENT_GROWTH_HISTORY",
            "Growth history is required for Composite Score V1.0",
        )
    return calculate_min_max_score(growth_rate, minimum, maximum)


def calculate_engagement_rate(
    *,
    play_count: Numeric,
    like_count: Numeric,
    comment_count: Numeric,
    favorite_count: Numeric,
    share_count: Numeric,
) -> Decimal:
    """Calculate total interactions divided by plays without database access."""

    play = _as_decimal(play_count, field_name="play_count")
    interactions = {
        "like_count": _as_decimal(like_count, field_name="like_count"),
        "comment_count": _as_decimal(comment_count, field_name="comment_count"),
        "favorite_count": _as_decimal(favorite_count, field_name="favorite_count"),
        "share_count": _as_decimal(share_count, field_name="share_count"),
    }
    if play < ZERO or any(value < ZERO for value in interactions.values()):
        raise CompositeScoreValidationError(
            "NEGATIVE_METRIC_VALUE",
            "engagement source metrics cannot be negative",
        )
    if play == ZERO:
        raise CompositeScoreValidationError(
            "ZERO_PLAY_COUNT",
            "play_count must be greater than zero",
        )
    return sum(interactions.values(), start=ZERO) / play


def _to_date(value: DateValue, *, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise CompositeScoreValidationError(
        "INVALID_DATE_VALUE",
        f"{field_name} must be a date or datetime",
    )


def calculate_lifecycle_stage_score(
    release_date: DateValue | None,
    score_date: DateValue,
) -> Decimal:
    """Apply the deterministic Lifecycle Stage Score rules for V1.0."""

    if release_date is None:
        raise CompositeScoreValidationError(
            "MISSING_RELEASE_DATE",
            "release date is required for Lifecycle Stage Score",
        )
    release_day = _to_date(release_date, field_name="release_date")
    scoring_day = _to_date(score_date, field_name="score_date")
    days_online = (scoring_day - release_day).days
    if days_online < 0:
        raise CompositeScoreValidationError(
            "FUTURE_RELEASE_DATE",
            "release date cannot be later than score date",
        )
    if days_online <= 7:
        return Decimal("100.00")
    if days_online <= 30:
        return Decimal("80.00")
    if days_online <= 90:
        return Decimal("60.00")
    if days_online <= 180:
        return Decimal("40.00")
    return Decimal("20.00")


def _validated_component(value: Numeric, *, field_name: str) -> Decimal:
    score = _as_decimal(value, field_name=field_name)
    if not ZERO <= score <= ONE_HUNDRED:
        raise CompositeScoreValidationError(
            "SCORE_COMPONENT_OUT_OF_RANGE",
            f"{field_name} must be between 0 and 100",
        )
    return score


def determine_score_level(total_score: Numeric) -> ScoreLevel:
    """Classify the rounded total into the S/A/B/C score bands."""

    rounded = round_half_up(total_score)
    if not ZERO <= rounded <= ONE_HUNDRED:
        raise CompositeScoreValidationError(
            "TOTAL_SCORE_OUT_OF_RANGE",
            "total_score must be between 0 and 100",
        )
    if rounded >= Decimal("90"):
        return "S"
    if rounded >= Decimal("75"):
        return "A"
    if rounded >= Decimal("60"):
        return "B"
    return "C"


def calculate_composite_score(
    *,
    heat_score: Numeric,
    growth_score: Numeric,
    engagement_score: Numeric,
    lifecycle_score: Numeric,
) -> CompositeScoreResult:
    """Calculate and round Composite Score V1.0, then assign its level."""

    components = {
        "heat": _validated_component(heat_score, field_name="heat_score"),
        "growth": _validated_component(growth_score, field_name="growth_score"),
        "engagement": _validated_component(
            engagement_score,
            field_name="engagement_score",
        ),
        "lifecycle": _validated_component(
            lifecycle_score,
            field_name="lifecycle_score",
        ),
    }
    raw_total = sum(
        (
            components[name] * weight
            for name, weight in COMPOSITE_WEIGHTS.items()
        ),
        start=ZERO,
    )
    total = round_half_up(raw_total)
    return CompositeScoreResult(
        total_score=total,
        level=determine_score_level(total),
    )
