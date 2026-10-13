"""Quality Score V2 rule-score aggregation and V1 isolation tests."""

from decimal import Decimal

import pytest

from analytics.data_quality import (
    QUALITY_SCORE_V2_VERSION,
    DataQualityCalculationError,
    ScoredQualityRuleResult,
    calculate_data_quality_score_v2,
)


def _score(dimension: str, value: str, weight: str = "1") -> ScoredQualityRuleResult:
    return ScoredQualityRuleResult(
        dimension=dimension,
        rule_score=Decimal(value),
        weight=Decimal(weight),
    )


def test_v2_uses_rule_score_instead_of_binary_status() -> None:
    result = calculate_data_quality_score_v2(
        [
            _score("COMPLETENESS", "94", "0.4"),
            _score("COMPLETENESS", "94", "0.6"),
            _score("ACCURACY", "100"),
            _score("CONSISTENCY", "100"),
            _score("TIMELINESS", "100"),
        ],
        rule_set_version="DQ Rules 1.0",
    )

    assert result.completeness_score == Decimal("94.00")
    assert result.total_score == Decimal("98.20")
    assert result.quality_grade == "S"
    assert result.algorithm_version == QUALITY_SCORE_V2_VERSION


def test_v2_normalizes_applied_weights_and_rounds_half_up() -> None:
    result = calculate_data_quality_score_v2(
        [
            _score("COMPLETENESS", "80", "0.25"),
            _score("COMPLETENESS", "100", "0.75"),
            _score("ACCURACY", "100"),
            _score("CONSISTENCY", "100"),
            _score("TIMELINESS", "66.65"),
        ],
        rule_set_version="DQ Rules 1.0",
    )

    assert result.completeness_score == Decimal("95.00")
    assert result.total_score == Decimal("93.50")


@pytest.mark.parametrize(
    ("results", "code"),
    [
        ([_score("COMPLETENESS", "100")], "INSUFFICIENT_QUALITY_DATA"),
        (
            [
                _score("COMPLETENESS", "101"),
                _score("ACCURACY", "100"),
                _score("CONSISTENCY", "100"),
                _score("TIMELINESS", "100"),
            ],
            "RULE_SCORE_OUT_OF_RANGE",
        ),
    ],
)
def test_v2_rejects_incomplete_or_invalid_inputs(
    results: list[ScoredQualityRuleResult],
    code: str,
) -> None:
    with pytest.raises(DataQualityCalculationError) as error:
        calculate_data_quality_score_v2(
            results,
            rule_set_version="DQ Rules 1.0",
        )
    assert error.value.code == code
