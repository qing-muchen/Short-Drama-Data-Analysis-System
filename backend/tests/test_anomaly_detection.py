"""Pure Calculator tests for Phase 4 Rule-based Detection V1.0."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from analytics.anomaly_detection import (
    ANOMALY_ALGORITHM_VERSION,
    DATA_SPIKE_ANOMALY,
    ENGAGEMENT_RATE_ANOMALY,
    MINIMUM_PLAY_COUNT_THRESHOLD,
    PLAY_COUNT_DROP_ANOMALY,
    PLAY_COUNT_GROWTH_ANOMALY,
    AnomalyCalculationError,
    calculate_engagement_rate,
    calculate_z_score,
    detect_data_spike_anomaly,
    detect_engagement_rate_anomaly,
    detect_play_count_drop_anomaly,
    detect_play_count_growth_anomaly,
    determine_anomaly_severity,
)


ANALYSIS_AS_OF = datetime(2026, 9, 19, 15, 59, 59, tzinfo=timezone.utc)


def test_z_score_uses_history_mean_and_population_standard_deviation() -> None:
    result = calculate_z_score([1, 2, 3, 4], 5)

    assert result is not None
    assert result.baseline_mean == Decimal("2.5000")
    assert result.baseline_std == Decimal("1.118034")
    assert result.deviation == Decimal("2.5000")
    assert result.z_score == Decimal("2.236068")


def test_severity_boundaries_and_zero_variance_fallback() -> None:
    assert determine_anomaly_severity(Decimal("1.9999")) is None
    assert determine_anomaly_severity(Decimal("2")) == "C"
    assert determine_anomaly_severity(Decimal("2.9999")) == "C"
    assert determine_anomaly_severity(Decimal("3")) == "B"
    assert determine_anomaly_severity(Decimal("4")) == "A"
    assert determine_anomaly_severity(None) == "C"


def test_growth_anomaly_uses_positive_direction_and_evidence() -> None:
    result = detect_play_count_growth_anomaly(
        drama_id=11,
        historical_growth=[10, 11, 9, 10, 10, 10, 10],
        current_growth=13,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "ANOMALY"
    assert result.finding is not None
    assert result.finding.anomaly_type == PLAY_COUNT_GROWTH_ANOMALY
    assert result.finding.metric_type == "PLAY_COUNT"
    assert result.finding.severity == "A"
    assert result.finding.baseline_value == Decimal("10.0000")
    assert result.finding.actual_value == Decimal("13.0000")
    assert result.finding.deviation_value == Decimal("3.0000")
    assert "current_value=13.000000" in result.finding.evidence_summary
    assert "baseline_mean=10.0000" in result.finding.evidence_summary
    assert "z_score=" in result.finding.evidence_summary
    assert result.finding.algorithm_version == ANOMALY_ALGORITHM_VERSION


def test_growth_below_baseline_is_not_growth_anomaly() -> None:
    result = detect_play_count_growth_anomaly(
        drama_id=11,
        historical_growth=[10, 11, 9, 10, 10, 10, 10],
        current_growth=8,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "NORMAL"
    assert result.finding is None


def test_drop_anomaly_requires_negative_deviation() -> None:
    result = detect_play_count_drop_anomaly(
        drama_id=11,
        historical_growth=[10, 11, 9, 10, 10, 10, 10],
        current_growth=8,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "ANOMALY"
    assert result.finding is not None
    assert result.finding.anomaly_type == PLAY_COUNT_DROP_ANOMALY
    assert result.finding.severity == "B"
    assert result.finding.deviation_value == Decimal("-2.0000")


def test_zero_standard_deviation_uses_absolute_fallback() -> None:
    result = detect_play_count_growth_anomaly(
        drama_id=11,
        historical_growth=[10, 10, 10, 10, 10, 10, 10],
        current_growth=11,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "ANOMALY"
    assert result.finding is not None
    assert result.finding.severity == "C"
    assert "threshold_mode=ABSOLUTE_DEVIATION_FALLBACK" in (
        result.finding.evidence_summary
    )


def test_zero_standard_deviation_with_no_deviation_is_normal() -> None:
    result = detect_play_count_drop_anomaly(
        drama_id=11,
        historical_growth=[10, 10, 10, 10, 10, 10, 10],
        current_growth=10,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "NORMAL"


def test_insufficient_history_does_not_generate_finding() -> None:
    result = detect_play_count_growth_anomaly(
        drama_id=11,
        historical_growth=[10],
        current_growth=20,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "INSUFFICIENT_HISTORY"
    assert result.reason == "INSUFFICIENT_HISTORY"
    assert result.finding is None


def test_engagement_rate_formula_and_minimum_play_count_gate() -> None:
    assert calculate_engagement_rate(
        play_count=1000,
        like_count=100,
        comment_count=20,
        favorite_count=30,
        share_count=10,
    ) == Decimal("0.16")

    result = detect_engagement_rate_anomaly(
        drama_id=11,
        historical_rates=[Decimal("0.10")] * 7,
        current_rate=Decimal("0.20"),
        play_count=99,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "NOT_APPLICABLE"
    assert result.reason == "BELOW_MINIMUM_PLAY_COUNT"
    assert MINIMUM_PLAY_COUNT_THRESHOLD == Decimal("100")


def test_engagement_rate_anomaly_uses_zero_variance_fallback() -> None:
    result = detect_engagement_rate_anomaly(
        drama_id=11,
        historical_rates=[Decimal("0.10")] * 7,
        current_rate=Decimal("0.20"),
        play_count=100,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "ANOMALY"
    assert result.finding is not None
    assert result.finding.metric_type == "ENGAGEMENT_RATE"
    assert result.finding.anomaly_type == ENGAGEMENT_RATE_ANOMALY
    assert result.finding.severity == "C"
    assert "minimum_play_count_threshold=100" in result.finding.evidence_summary


def test_data_spike_only_detects_positive_deviation() -> None:
    result = detect_data_spike_anomaly(
        drama_id=11,
        metric_type="PLAY_COUNT",
        historical_values=[10, 11, 9, 10, 10, 10, 10],
        current_value=13,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "ANOMALY"
    assert result.finding is not None
    assert result.finding.anomaly_type == DATA_SPIKE_ANOMALY
    assert result.finding.severity == "A"

    non_spike = detect_data_spike_anomaly(
        drama_id=11,
        metric_type="PLAY_COUNT",
        historical_values=[10, 11, 9, 10, 10, 10, 10],
        current_value=8,
        analysis_as_of=ANALYSIS_AS_OF,
    )
    assert non_spike.status == "NORMAL"


@pytest.mark.parametrize(
    ("history", "current"),
    [([], 10), ([10], 20)],
)
def test_empty_or_single_history_returns_insufficient_history(
    history: list[int], current: int
) -> None:
    result = detect_data_spike_anomaly(
        drama_id=11,
        metric_type="PLAY_COUNT",
        historical_values=history,
        current_value=current,
        analysis_as_of=ANALYSIS_AS_OF,
    )

    assert result.status == "INSUFFICIENT_HISTORY"


def test_invalid_numeric_values_are_rejected() -> None:
    with pytest.raises(AnomalyCalculationError) as negative:
        detect_play_count_growth_anomaly(
            drama_id=11,
            historical_growth=[10, -1],
            current_growth=20,
            analysis_as_of=ANALYSIS_AS_OF,
        )
    assert negative.value.code == "NEGATIVE_METRIC_VALUE"

    with pytest.raises(AnomalyCalculationError) as non_finite:
        detect_play_count_growth_anomaly(
            drama_id=11,
            historical_growth=[10, float("nan")],
            current_growth=20,
            analysis_as_of=ANALYSIS_AS_OF,
        )
    assert non_finite.value.code == "NON_FINITE_VALUE"


def test_invalid_context_and_zero_play_count_are_rejected() -> None:
    with pytest.raises(AnomalyCalculationError) as context_error:
        detect_play_count_growth_anomaly(
            drama_id=0,
            historical_growth=[10, 10],
            current_growth=20,
            analysis_as_of=ANALYSIS_AS_OF,
        )
    assert context_error.value.code == "INVALID_DRAMA_ID"

    with pytest.raises(AnomalyCalculationError) as zero_error:
        calculate_engagement_rate(
            play_count=0,
            like_count=1,
            comment_count=0,
            favorite_count=0,
            share_count=0,
        )
    assert zero_error.value.code == "ZERO_PLAY_COUNT"


def test_algorithm_output_is_deterministic() -> None:
    arguments = {
        "drama_id": 11,
        "historical_growth": ["10", "11", "9", "10", "10", "10", "10"],
        "current_growth": "13",
        "analysis_as_of": ANALYSIS_AS_OF,
    }

    first = detect_play_count_growth_anomaly(**arguments)
    second = detect_play_count_growth_anomaly(**arguments)

    assert first == second
