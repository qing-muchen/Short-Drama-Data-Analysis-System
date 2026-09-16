"""Pure Data Quality Score V1.0 calculations without persistence side effects."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Iterable, Literal, TypeAlias

Numeric: TypeAlias = int | float | Decimal
QualityDimension: TypeAlias = Literal[
    "COMPLETENESS",
    "ACCURACY",
    "CONSISTENCY",
    "TIMELINESS",
]
RuleStatus: TypeAlias = Literal["PASS", "FAIL"]
QualityGrade: TypeAlias = Literal["S", "A", "B", "C"]

QUALITY_SCORE_VERSION = "Quality Score V1.0"
SCORE_QUANTUM = Decimal("0.01")
ZERO = Decimal("0")
ONE = Decimal("1")
ONE_HUNDRED = Decimal("100")

QUALITY_DIMENSION_WEIGHTS: dict[QualityDimension, Decimal] = {
    "COMPLETENESS": Decimal("0.30"),
    "ACCURACY": Decimal("0.30"),
    "CONSISTENCY": Decimal("0.25"),
    "TIMELINESS": Decimal("0.15"),
}


class DataQualityCalculationError(ValueError):
    """Expose stable domain error codes without database or HTTP dependencies."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class QualityRuleResult:
    """One binary rule outcome and its relative weight within a dimension."""

    dimension: str
    status: str
    weight: Numeric | None


@dataclass(frozen=True, slots=True)
class DataQualityScoreResult:
    """Rounded four-dimension quality score with traceable version identity."""

    completeness_score: Decimal
    accuracy_score: Decimal
    consistency_score: Decimal
    timeliness_score: Decimal
    total_score: Decimal
    quality_grade: QualityGrade
    rule_set_version: str
    algorithm_version: str = QUALITY_SCORE_VERSION


@dataclass(frozen=True, slots=True)
class _ValidatedRuleResult:
    dimension: QualityDimension
    status: RuleStatus
    weight: Decimal


def _as_decimal(value: Numeric, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise DataQualityCalculationError(
            "INVALID_NUMERIC_VALUE",
            f"{field_name} must be a finite number",
        )
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise DataQualityCalculationError(
            "INVALID_NUMERIC_VALUE",
            f"{field_name} must be a finite number",
        ) from error
    if not number.is_finite():
        raise DataQualityCalculationError(
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


def calculate_rule_pass_rate(*, pass_count: int, total_count: int) -> Decimal:
    """Return ``pass_count / total_count * 100`` with deterministic rounding."""

    if (
        isinstance(pass_count, bool)
        or isinstance(total_count, bool)
        or not isinstance(pass_count, int)
        or not isinstance(total_count, int)
    ):
        raise DataQualityCalculationError(
            "INVALID_RULE_COUNTS",
            "pass_count and total_count must be integers",
        )
    if total_count <= 0:
        raise DataQualityCalculationError(
            "INVALID_RULE_COUNTS",
            "total_count must be greater than zero",
        )
    if pass_count < 0 or pass_count > total_count:
        raise DataQualityCalculationError(
            "RULE_SCORE_OUT_OF_RANGE",
            "pass_count must produce a rule score between 0 and 100",
        )
    with localcontext() as context:
        context.prec = 50
        return round_half_up(
            Decimal(pass_count) / Decimal(total_count) * ONE_HUNDRED
        )


def _validate_rule_result(result: QualityRuleResult) -> _ValidatedRuleResult:
    if result.dimension not in QUALITY_DIMENSION_WEIGHTS:
        raise DataQualityCalculationError(
            "UNKNOWN_DIMENSION",
            f"unsupported quality dimension: {result.dimension}",
        )
    if result.status not in {"PASS", "FAIL"}:
        raise DataQualityCalculationError(
            "INVALID_RULE_STATUS",
            f"unsupported rule status: {result.status}",
        )
    if result.weight is None:
        raise DataQualityCalculationError(
            "MISSING_RULE_WEIGHT",
            "rule weight is required",
        )
    weight = _as_decimal(result.weight, field_name="weight")
    if weight < ZERO or weight > ONE:
        raise DataQualityCalculationError(
            "INVALID_RULE_WEIGHT",
            "rule weight must be between 0 and 1",
        )
    return _ValidatedRuleResult(
        dimension=result.dimension,
        status=result.status,
        weight=weight,
    )


def _calculate_validated_dimension_score(
    results: tuple[_ValidatedRuleResult, ...],
) -> Decimal:
    if not results:
        raise DataQualityCalculationError(
            "EMPTY_RULE_RESULTS",
            "at least one rule result is required",
        )

    ordered = sorted(results, key=lambda item: (item.weight, item.status))
    with localcontext() as context:
        context.prec = 50
        total_weight = sum((item.weight for item in ordered), start=ZERO)
        if total_weight == ZERO:
            raise DataQualityCalculationError(
                "ZERO_WEIGHT_SUM",
                "the dimension rule weight sum must be greater than zero",
            )
        if any(item.weight == ZERO for item in ordered):
            raise DataQualityCalculationError(
                "INVALID_RULE_WEIGHT",
                "individual rule weight must be greater than zero",
            )
        passed_weight = sum(
            (item.weight for item in ordered if item.status == "PASS"),
            start=ZERO,
        )
        score = passed_weight / total_weight * ONE_HUNDRED
    if not ZERO <= score <= ONE_HUNDRED:
        raise DataQualityCalculationError(
            "DIMENSION_SCORE_OUT_OF_RANGE",
            "dimension score must be between 0 and 100",
        )
    return round_half_up(score)


def calculate_dimension_score(
    rule_results: Iterable[QualityRuleResult],
    *,
    dimension: str,
) -> Decimal:
    """Calculate one dimension from PASS/FAIL rule weights."""

    if dimension not in QUALITY_DIMENSION_WEIGHTS:
        raise DataQualityCalculationError(
            "UNKNOWN_DIMENSION",
            f"unsupported quality dimension: {dimension}",
        )
    validated = tuple(_validate_rule_result(result) for result in rule_results)
    mismatched = tuple(
        result for result in validated if result.dimension != dimension
    )
    if mismatched:
        raise DataQualityCalculationError(
            "MIXED_DIMENSION_RESULTS",
            "all rule results must belong to the requested dimension",
        )
    return _calculate_validated_dimension_score(validated)


def determine_quality_grade(total_score: Numeric) -> QualityGrade:
    """Classify a rounded 0..100 quality score into S/A/B/C."""

    rounded = round_half_up(total_score)
    if not ZERO <= rounded <= ONE_HUNDRED:
        raise DataQualityCalculationError(
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


def calculate_data_quality_score(
    rule_results: Iterable[QualityRuleResult],
    *,
    rule_set_version: str,
) -> DataQualityScoreResult:
    """Calculate the four dimensions, weighted total, grade, and versions."""

    if not isinstance(rule_set_version, str) or not rule_set_version.strip():
        raise DataQualityCalculationError(
            "INVALID_RULE_SET_VERSION",
            "rule_set_version must be a non-blank string",
        )

    materialized = tuple(rule_results)
    if not materialized:
        raise DataQualityCalculationError(
            "EMPTY_RULE_RESULTS",
            "at least one rule result is required",
        )

    grouped: dict[QualityDimension, list[_ValidatedRuleResult]] = defaultdict(list)
    for result in materialized:
        validated = _validate_rule_result(result)
        grouped[validated.dimension].append(validated)

    missing_dimensions = tuple(
        dimension
        for dimension in QUALITY_DIMENSION_WEIGHTS
        if not grouped[dimension]
    )
    if missing_dimensions:
        raise DataQualityCalculationError(
            "INSUFFICIENT_QUALITY_DATA",
            "every quality dimension requires at least one rule result: "
            + ", ".join(missing_dimensions),
        )

    dimension_scores = {
        dimension: _calculate_validated_dimension_score(tuple(grouped[dimension]))
        for dimension in QUALITY_DIMENSION_WEIGHTS
    }
    with localcontext() as context:
        context.prec = 50
        raw_total = sum(
            (
                dimension_scores[dimension] * weight
                for dimension, weight in QUALITY_DIMENSION_WEIGHTS.items()
            ),
            start=ZERO,
        )
    total_score = round_half_up(raw_total)

    return DataQualityScoreResult(
        completeness_score=dimension_scores["COMPLETENESS"],
        accuracy_score=dimension_scores["ACCURACY"],
        consistency_score=dimension_scores["CONSISTENCY"],
        timeliness_score=dimension_scores["TIMELINESS"],
        total_score=total_score,
        quality_grade=determine_quality_grade(total_score),
        rule_set_version=rule_set_version.strip(),
    )


__all__ = (
    "QUALITY_DIMENSION_WEIGHTS",
    "QUALITY_SCORE_VERSION",
    "DataQualityCalculationError",
    "DataQualityScoreResult",
    "QualityRuleResult",
    "calculate_data_quality_score",
    "calculate_dimension_score",
    "calculate_rule_pass_rate",
    "determine_quality_grade",
    "round_half_up",
)
