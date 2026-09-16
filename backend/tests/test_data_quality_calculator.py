"""Unit tests for the database-independent Data Quality Score V1.0 core."""

from decimal import Decimal
from itertools import permutations

import pytest

from analytics.data_quality import (
    QUALITY_DIMENSION_WEIGHTS,
    QUALITY_SCORE_VERSION,
    DataQualityCalculationError,
    QualityRuleResult,
    calculate_data_quality_score,
    calculate_dimension_score,
    calculate_rule_pass_rate,
    determine_quality_grade,
    round_half_up,
)


def _rule(
    dimension: str,
    status: str,
    weight: Decimal | int | float | None = Decimal("1"),
) -> QualityRuleResult:
    return QualityRuleResult(
        dimension=dimension,
        status=status,
        weight=weight,
    )


def _dimension_rules(dimension: str, pass_ratio: str) -> list[QualityRuleResult]:
    passed_weight = Decimal(pass_ratio)
    failed_weight = Decimal("1") - passed_weight
    results = []
    if passed_weight:
        results.append(_rule(dimension, "PASS", passed_weight))
    if failed_weight:
        results.append(_rule(dimension, "FAIL", failed_weight))
    return results


def _four_dimension_rules() -> list[QualityRuleResult]:
    return [
        *_dimension_rules("COMPLETENESS", "1"),
        *_dimension_rules("ACCURACY", "0.8"),
        *_dimension_rules("CONSISTENCY", "0.6"),
        *_dimension_rules("TIMELINESS", "0.4"),
    ]


def test_four_dimension_weighted_score() -> None:
    result = calculate_data_quality_score(
        _four_dimension_rules(),
        rule_set_version="DQ Rules 1.0",
    )

    assert result.completeness_score == Decimal("100.00")
    assert result.accuracy_score == Decimal("80.00")
    assert result.consistency_score == Decimal("60.00")
    assert result.timeliness_score == Decimal("40.00")
    assert result.total_score == Decimal("75.00")
    assert result.quality_grade == "A"
    assert QUALITY_DIMENSION_WEIGHTS == {
        "COMPLETENESS": Decimal("0.30"),
        "ACCURACY": Decimal("0.30"),
        "CONSISTENCY": Decimal("0.25"),
        "TIMELINESS": Decimal("0.15"),
    }


@pytest.mark.parametrize(
    ("passed_dimension", "expected_total"),
    [
        ("COMPLETENESS", "30.00"),
        ("ACCURACY", "30.00"),
        ("CONSISTENCY", "25.00"),
        ("TIMELINESS", "15.00"),
    ],
)
def test_each_dimension_contributes_its_frozen_weight(
    passed_dimension: str,
    expected_total: str,
) -> None:
    results = [
        _rule(
            dimension,
            "PASS" if dimension == passed_dimension else "FAIL",
        )
        for dimension in QUALITY_DIMENSION_WEIGHTS
    ]

    calculated = calculate_data_quality_score(
        results,
        rule_set_version="DQ Rules 1.0",
    )

    assert calculated.total_score == Decimal(expected_total)


def test_single_dimension_uses_relative_rule_weights() -> None:
    score = calculate_dimension_score(
        [
            _rule("COMPLETENESS", "PASS", Decimal("0.75")),
            _rule("COMPLETENESS", "FAIL", Decimal("0.25")),
        ],
        dimension="COMPLETENESS",
    )

    assert score == Decimal("75.00")


def test_pass_and_fail_rules_produce_bounds() -> None:
    assert calculate_dimension_score(
        [_rule("ACCURACY", "PASS")],
        dimension="ACCURACY",
    ) == Decimal("100.00")
    assert calculate_dimension_score(
        [_rule("ACCURACY", "FAIL")],
        dimension="ACCURACY",
    ) == Decimal("0.00")


@pytest.mark.parametrize(
    ("pass_count", "total_count", "expected"),
    [
        (1, 1, "100.00"),
        (0, 7, "0.00"),
        (1, 3, "33.33"),
        (2, 3, "66.67"),
    ],
)
def test_rule_pass_rate(
    pass_count: int,
    total_count: int,
    expected: str,
) -> None:
    assert calculate_rule_pass_rate(
        pass_count=pass_count,
        total_count=total_count,
    ) == Decimal(expected)


@pytest.mark.parametrize(
    ("score", "grade"),
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
def test_quality_grade_boundaries(score: str, grade: str) -> None:
    assert determine_quality_grade(Decimal(score)) == grade


def test_round_half_up_and_decimal_precision() -> None:
    assert round_half_up(Decimal("2.345")) == Decimal("2.35")
    assert round_half_up(Decimal("2.344")) == Decimal("2.34")

    results = []
    for dimension in QUALITY_DIMENSION_WEIGHTS:
        results.extend(_dimension_rules(dimension, "0.74995"))

    calculated = calculate_data_quality_score(
        results,
        rule_set_version="DQ Rules Rounding",
    )

    assert calculated.completeness_score == Decimal("75.00")
    assert calculated.total_score == Decimal("75.00")
    assert calculated.quality_grade == "A"


def test_empty_results_are_rejected() -> None:
    with pytest.raises(DataQualityCalculationError) as complete_error:
        calculate_data_quality_score([], rule_set_version="DQ Rules 1.0")
    assert complete_error.value.code == "EMPTY_RULE_RESULTS"

    with pytest.raises(DataQualityCalculationError) as dimension_error:
        calculate_dimension_score([], dimension="COMPLETENESS")
    assert dimension_error.value.code == "EMPTY_RULE_RESULTS"


def test_missing_and_zero_weights_are_rejected() -> None:
    with pytest.raises(DataQualityCalculationError) as missing:
        calculate_dimension_score(
            [_rule("COMPLETENESS", "PASS", None)],
            dimension="COMPLETENESS",
        )
    assert missing.value.code == "MISSING_RULE_WEIGHT"

    with pytest.raises(DataQualityCalculationError) as zero_sum:
        calculate_dimension_score(
            [
                _rule("COMPLETENESS", "PASS", 0),
                _rule("COMPLETENESS", "FAIL", Decimal("0")),
            ],
            dimension="COMPLETENESS",
        )
    assert zero_sum.value.code == "ZERO_WEIGHT_SUM"


@pytest.mark.parametrize("weight", [-1, Decimal("1.000001"), Decimal("NaN")])
def test_invalid_weights_are_rejected(
    weight: int | Decimal,
) -> None:
    with pytest.raises(DataQualityCalculationError) as error:
        calculate_dimension_score(
            [_rule("CONSISTENCY", "PASS", weight)],
            dimension="CONSISTENCY",
        )
    assert error.value.code in {"INVALID_RULE_WEIGHT", "INVALID_NUMERIC_VALUE"}


def test_zero_weight_cannot_hide_inside_positive_weight_set() -> None:
    with pytest.raises(DataQualityCalculationError) as error:
        calculate_dimension_score(
            [
                _rule("TIMELINESS", "PASS", Decimal("0")),
                _rule("TIMELINESS", "FAIL", Decimal("1")),
            ],
            dimension="TIMELINESS",
        )
    assert error.value.code == "INVALID_RULE_WEIGHT"


def test_unknown_dimension_and_illegal_status_are_rejected() -> None:
    with pytest.raises(DataQualityCalculationError) as dimension:
        calculate_dimension_score(
            [_rule("POPULARITY", "PASS")],
            dimension="POPULARITY",
        )
    assert dimension.value.code == "UNKNOWN_DIMENSION"

    with pytest.raises(DataQualityCalculationError) as status:
        calculate_dimension_score(
            [_rule("ACCURACY", "SKIPPED")],
            dimension="ACCURACY",
        )
    assert status.value.code == "INVALID_RULE_STATUS"


def test_mixed_dimension_input_is_rejected() -> None:
    with pytest.raises(DataQualityCalculationError) as error:
        calculate_dimension_score(
            [
                _rule("ACCURACY", "PASS"),
                _rule("CONSISTENCY", "FAIL"),
            ],
            dimension="ACCURACY",
        )
    assert error.value.code == "MIXED_DIMENSION_RESULTS"


@pytest.mark.parametrize(
    ("pass_count", "total_count", "error_code"),
    [
        (2, 1, "RULE_SCORE_OUT_OF_RANGE"),
        (-1, 1, "RULE_SCORE_OUT_OF_RANGE"),
        (0, 0, "INVALID_RULE_COUNTS"),
        (True, 1, "INVALID_RULE_COUNTS"),
    ],
)
def test_invalid_rule_counts_and_out_of_range_scores(
    pass_count: int,
    total_count: int,
    error_code: str,
) -> None:
    with pytest.raises(DataQualityCalculationError) as error:
        calculate_rule_pass_rate(
            pass_count=pass_count,
            total_count=total_count,
        )
    assert error.value.code == error_code


def test_all_four_dimensions_are_required_for_total_score() -> None:
    with pytest.raises(DataQualityCalculationError) as error:
        calculate_data_quality_score(
            [_rule("COMPLETENESS", "PASS")],
            rule_set_version="DQ Rules 1.0",
        )
    assert error.value.code == "INSUFFICIENT_QUALITY_DATA"


def test_rule_set_version_is_validated_and_transferred() -> None:
    result = calculate_data_quality_score(
        [_rule(dimension, "PASS") for dimension in QUALITY_DIMENSION_WEIGHTS],
        rule_set_version="  DQ Rules 2.0  ",
    )

    assert result.rule_set_version == "DQ Rules 2.0"
    assert result.algorithm_version == QUALITY_SCORE_VERSION

    with pytest.raises(DataQualityCalculationError) as error:
        calculate_data_quality_score(
            [_rule(dimension, "PASS") for dimension in QUALITY_DIMENSION_WEIGHTS],
            rule_set_version="   ",
        )
    assert error.value.code == "INVALID_RULE_SET_VERSION"


def test_result_is_deterministic_for_generators_and_input_order() -> None:
    expected = calculate_data_quality_score(
        _four_dimension_rules(),
        rule_set_version="DQ Rules Deterministic",
    )

    for reordered in permutations(_four_dimension_rules()):
        actual = calculate_data_quality_score(
            (item for item in reordered),
            rule_set_version="DQ Rules Deterministic",
        )
        assert actual == expected
