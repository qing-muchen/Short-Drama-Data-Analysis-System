"""Pure rule-based anomaly detection calculations for Phase 4 V1.0.

The calculator accepts already-prepared metric histories only. It deliberately
does not know about snapshots, revisions, platform aggregation, ORM objects,
sessions, transactions, or persistence. Those responsibilities belong to the
Service and Repository layers.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Literal, Sequence, TypeAlias

Numeric: TypeAlias = int | float | Decimal
Severity: TypeAlias = Literal["A", "B", "C"]
MetricType: TypeAlias = Literal["PLAY_COUNT", "ENGAGEMENT_RATE"]
AnomalyType: TypeAlias = Literal[
    "PLAY_COUNT_GROWTH_ANOMALY",
    "PLAY_COUNT_DROP_ANOMALY",
    "ENGAGEMENT_RATE_ANOMALY",
    "DATA_SPIKE_ANOMALY",
]
DetectionStatus: TypeAlias = Literal[
    "ANOMALY",
    "NORMAL",
    "NOT_APPLICABLE",
    "INSUFFICIENT_HISTORY",
]

ANOMALY_ALGORITHM_VERSION = "Rule-based Detection V1.0"
PLAY_COUNT_METRIC = "PLAY_COUNT"
ENGAGEMENT_RATE_METRIC = "ENGAGEMENT_RATE"
PLAY_COUNT_GROWTH_ANOMALY = "PLAY_COUNT_GROWTH_ANOMALY"
PLAY_COUNT_DROP_ANOMALY = "PLAY_COUNT_DROP_ANOMALY"
ENGAGEMENT_RATE_ANOMALY = "ENGAGEMENT_RATE_ANOMALY"
DATA_SPIKE_ANOMALY = "DATA_SPIKE_ANOMALY"

MINIMUM_HISTORY_POINTS = 2
RECOMMENDED_BASELINE_WINDOW = 7
MINIMUM_PLAY_COUNT_THRESHOLD = Decimal("100")
MINIMUM_ENGAGEMENT_DEVIATION = Decimal("0.010000")
Z_SCORE_THRESHOLD = Decimal("2")
Z_SCORE_MEDIUM_THRESHOLD = Decimal("3")
Z_SCORE_HIGH_THRESHOLD = Decimal("4")
VALUE_QUANTUM = Decimal("0.0001")
EVIDENCE_QUANTUM = Decimal("0.000001")
ZERO = Decimal("0")

ALLOWED_METRICS = {PLAY_COUNT_METRIC, ENGAGEMENT_RATE_METRIC}
ALLOWED_ANOMALIES = {
    PLAY_COUNT_GROWTH_ANOMALY,
    PLAY_COUNT_DROP_ANOMALY,
    ENGAGEMENT_RATE_ANOMALY,
    DATA_SPIKE_ANOMALY,
}


class AnomalyCalculationError(ValueError):
    """Stable domain error raised without database or HTTP dependencies."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class AnomalyFinding:
    """One explainable anomaly finding before persistence."""

    drama_id: int
    metric_type: MetricType
    anomaly_type: AnomalyType
    severity: Severity
    analysis_as_of: datetime
    baseline_value: Decimal | None
    actual_value: Decimal | None
    deviation_value: Decimal | None
    evidence_summary: str
    algorithm_version: str = ANOMALY_ALGORITHM_VERSION


@dataclass(frozen=True, slots=True)
class AnomalyDetectionResult:
    """Calculator result, including normal and non-applicable outcomes."""

    status: DetectionStatus
    finding: AnomalyFinding | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ZScoreResult:
    """Mean, standard deviation and deviation values for one current point."""

    baseline_mean: Decimal
    baseline_std: Decimal
    deviation: Decimal
    z_score: Decimal | None


def _as_decimal(value: Numeric, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise AnomalyCalculationError(
            "INVALID_METRIC_VALUE",
            f"{field_name} must be a finite numeric value",
        )
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise AnomalyCalculationError(
            "INVALID_METRIC_VALUE",
            f"{field_name} must be a finite numeric value",
        ) from error
    if not decimal_value.is_finite():
        raise AnomalyCalculationError(
            "NON_FINITE_VALUE",
            f"{field_name} must be finite",
        )
    return decimal_value


def _as_non_negative(value: Numeric, *, field_name: str) -> Decimal:
    decimal_value = _as_decimal(value, field_name=field_name)
    if decimal_value < ZERO:
        raise AnomalyCalculationError(
            "NEGATIVE_METRIC_VALUE",
            f"{field_name} cannot be negative",
        )
    return decimal_value


def _round_value(value: Decimal) -> Decimal:
    return value.quantize(VALUE_QUANTUM, rounding=ROUND_HALF_UP)


def _round_evidence(value: Decimal) -> Decimal:
    return value.quantize(EVIDENCE_QUANTUM, rounding=ROUND_HALF_UP)


def _validate_context(drama_id: int, analysis_as_of: datetime) -> None:
    if isinstance(drama_id, bool) or not isinstance(drama_id, int) or drama_id <= 0:
        raise AnomalyCalculationError(
            "INVALID_DRAMA_ID",
            "drama_id must be a positive integer",
        )
    if not isinstance(analysis_as_of, datetime):
        raise AnomalyCalculationError(
            "INVALID_ANALYSIS_AS_OF",
            "analysis_as_of must be a datetime",
        )


def _prepare_history(history: Sequence[Numeric]) -> list[Decimal]:
    if history is None:
        raise AnomalyCalculationError(
            "EMPTY_HISTORY",
            "history is required",
        )
    prepared = [
        _as_non_negative(value, field_name=f"history[{index}]")
        for index, value in enumerate(history)
    ]
    if len(prepared) < MINIMUM_HISTORY_POINTS:
        return prepared
    return prepared[-RECOMMENDED_BASELINE_WINDOW:]


def calculate_z_score(
    history: Sequence[Numeric],
    current_value: Numeric,
) -> ZScoreResult | None:
    """Calculate a population-standard-deviation Z-score.

    A result of ``None`` means the history has fewer than two valid points.
    When the standard deviation is zero, ``z_score`` is ``None`` so callers
    must use the absolute-deviation fallback instead of dividing by zero.
    """

    prepared = _prepare_history(history)
    if len(prepared) < MINIMUM_HISTORY_POINTS:
        return None
    current = _as_non_negative(current_value, field_name="current_value")
    with localcontext() as context:
        context.prec = 40
        mean = sum(prepared, start=ZERO) / Decimal(len(prepared))
        variance = sum(
            ((value - mean) ** 2 for value in prepared),
            start=ZERO,
        ) / Decimal(len(prepared))
        standard_deviation = variance.sqrt()
        deviation = current - mean
        z_score = (
            None
            if standard_deviation == ZERO
            else deviation / standard_deviation
        )
    return ZScoreResult(
        baseline_mean=_round_value(mean),
        baseline_std=_round_evidence(standard_deviation),
        deviation=_round_value(deviation),
        z_score=None if z_score is None else _round_evidence(z_score),
    )


def determine_anomaly_severity(
    absolute_z_score: Numeric | None,
) -> Severity | None:
    """Map an absolute Z-score to the database A/B/C severity code.

    Values below 2.0 are not anomalies and return ``None``. ``None`` as an
    input represents the standard-deviation-zero fallback and maps to ``C``.
    """

    if absolute_z_score is None:
        return "C"
    score = _as_decimal(absolute_z_score, field_name="absolute_z_score")
    if score < ZERO:
        raise AnomalyCalculationError(
            "INVALID_Z_SCORE",
            "absolute_z_score cannot be negative",
        )
    if score >= Z_SCORE_HIGH_THRESHOLD:
        return "A"
    if score >= Z_SCORE_MEDIUM_THRESHOLD:
        return "B"
    if score >= Z_SCORE_THRESHOLD:
        return "C"
    return None


def calculate_engagement_rate(
    *,
    play_count: Numeric,
    like_count: Numeric,
    comment_count: Numeric,
    favorite_count: Numeric,
    share_count: Numeric,
) -> Decimal:
    """Calculate interactions divided by play_count without persistence."""

    play = _as_non_negative(play_count, field_name="play_count")
    interactions = sum(
        (
            _as_non_negative(like_count, field_name="like_count"),
            _as_non_negative(comment_count, field_name="comment_count"),
            _as_non_negative(favorite_count, field_name="favorite_count"),
            _as_non_negative(share_count, field_name="share_count"),
        ),
        start=ZERO,
    )
    if play == ZERO:
        raise AnomalyCalculationError(
            "ZERO_PLAY_COUNT",
            "play_count must be greater than zero for engagement rate",
        )
    return interactions / play


def _insufficient_history() -> AnomalyDetectionResult:
    return AnomalyDetectionResult(
        status="INSUFFICIENT_HISTORY",
        reason="INSUFFICIENT_HISTORY",
    )


def _normal() -> AnomalyDetectionResult:
    return AnomalyDetectionResult(status="NORMAL")


def _not_applicable(reason: str) -> AnomalyDetectionResult:
    return AnomalyDetectionResult(status="NOT_APPLICABLE", reason=reason)


def _build_evidence(
    *,
    current: Decimal,
    statistics: ZScoreResult,
    threshold_mode: str = "Z_SCORE",
    minimum_absolute_deviation: Decimal | None = None,
    extra: str | None = None,
) -> str:
    z_score = "NULL" if statistics.z_score is None else str(statistics.z_score)
    evidence = (
        f"current_value={_round_evidence(current)}; "
        f"baseline_mean={statistics.baseline_mean}; "
        f"baseline_std={statistics.baseline_std}; "
        f"deviation={statistics.deviation}; "
        f"z_score={z_score}; "
        f"threshold_mode={threshold_mode}"
    )
    if minimum_absolute_deviation is not None:
        evidence += (
            f"; minimum_absolute_deviation="
            f"{_round_evidence(minimum_absolute_deviation)}"
        )
    if extra:
        evidence += f"; {extra}"
    return evidence


def _finding(
    *,
    drama_id: int,
    metric_type: MetricType,
    anomaly_type: AnomalyType,
    severity: Severity,
    analysis_as_of: datetime,
    statistics: ZScoreResult,
    current: Decimal,
    evidence: str,
) -> AnomalyDetectionResult:
    return AnomalyDetectionResult(
        status="ANOMALY",
        finding=AnomalyFinding(
            drama_id=drama_id,
            metric_type=metric_type,
            anomaly_type=anomaly_type,
            severity=severity,
            analysis_as_of=analysis_as_of,
            baseline_value=statistics.baseline_mean,
            actual_value=_round_value(current),
            deviation_value=statistics.deviation,
            evidence_summary=evidence,
        ),
    )


def _detect_directional(
    *,
    drama_id: int,
    history: Sequence[Numeric],
    current_value: Numeric,
    analysis_as_of: datetime,
    anomaly_type: Literal[
        "PLAY_COUNT_GROWTH_ANOMALY", "PLAY_COUNT_DROP_ANOMALY"
    ],
) -> AnomalyDetectionResult:
    _validate_context(drama_id, analysis_as_of)
    statistics = calculate_z_score(history, current_value)
    if statistics is None:
        return _insufficient_history()
    current = _as_non_negative(current_value, field_name="current_value")
    deviation = statistics.deviation

    if anomaly_type == PLAY_COUNT_GROWTH_ANOMALY and deviation <= ZERO:
        return _normal()
    if anomaly_type == PLAY_COUNT_DROP_ANOMALY and deviation >= ZERO:
        return _normal()

    if statistics.z_score is None:
        if deviation == ZERO:
            return _normal()
        severity: Severity = "C"
        evidence = _build_evidence(
            current=current,
            statistics=statistics,
            threshold_mode="ABSOLUTE_DEVIATION_FALLBACK",
        )
    else:
        severity = determine_anomaly_severity(abs(statistics.z_score))
        if severity is None:
            return _normal()
        evidence = _build_evidence(current=current, statistics=statistics)

    return _finding(
        drama_id=drama_id,
        metric_type=PLAY_COUNT_METRIC,
        anomaly_type=anomaly_type,
        severity=severity,
        analysis_as_of=analysis_as_of,
        statistics=statistics,
        current=current,
        evidence=evidence,
    )


def detect_play_count_growth_anomaly(
    *,
    drama_id: int,
    historical_growth: Sequence[Numeric],
    current_growth: Numeric,
    analysis_as_of: datetime,
) -> AnomalyDetectionResult:
    """Detect growth above the historical daily-growth baseline."""

    return _detect_directional(
        drama_id=drama_id,
        history=historical_growth,
        current_value=current_growth,
        analysis_as_of=analysis_as_of,
        anomaly_type=PLAY_COUNT_GROWTH_ANOMALY,
    )


def detect_play_count_drop_anomaly(
    *,
    drama_id: int,
    historical_growth: Sequence[Numeric],
    current_growth: Numeric,
    analysis_as_of: datetime,
) -> AnomalyDetectionResult:
    """Detect daily growth significantly below the historical baseline."""

    return _detect_directional(
        drama_id=drama_id,
        history=historical_growth,
        current_value=current_growth,
        analysis_as_of=analysis_as_of,
        anomaly_type=PLAY_COUNT_DROP_ANOMALY,
    )


def detect_engagement_rate_anomaly(
    *,
    drama_id: int,
    historical_rates: Sequence[Numeric],
    current_rate: Numeric,
    play_count: Numeric,
    analysis_as_of: datetime,
) -> AnomalyDetectionResult:
    """Detect an engagement-rate deviation after the minimum-play gate."""

    _validate_context(drama_id, analysis_as_of)
    current_play_count = _as_non_negative(play_count, field_name="play_count")
    if current_play_count == ZERO:
        return _not_applicable("ZERO_PLAY_COUNT")
    if current_play_count < MINIMUM_PLAY_COUNT_THRESHOLD:
        return _not_applicable("BELOW_MINIMUM_PLAY_COUNT")

    statistics = calculate_z_score(historical_rates, current_rate)
    if statistics is None:
        return _insufficient_history()
    current = _as_non_negative(current_rate, field_name="current_rate")
    if abs(statistics.deviation) < MINIMUM_ENGAGEMENT_DEVIATION:
        return _normal()

    if statistics.z_score is None:
        severity: Severity = "C"
        evidence = _build_evidence(
            current=current,
            statistics=statistics,
            threshold_mode="ABSOLUTE_DEVIATION_FALLBACK",
            minimum_absolute_deviation=MINIMUM_ENGAGEMENT_DEVIATION,
            extra=(
                f"minimum_play_count_threshold="
                f"{MINIMUM_PLAY_COUNT_THRESHOLD}"
            ),
        )
    else:
        severity = determine_anomaly_severity(abs(statistics.z_score))
        if severity is None:
            return _normal()
        evidence = _build_evidence(
            current=current,
            statistics=statistics,
            minimum_absolute_deviation=MINIMUM_ENGAGEMENT_DEVIATION,
            extra=(
                f"minimum_play_count_threshold="
                f"{MINIMUM_PLAY_COUNT_THRESHOLD}"
            ),
        )

    return _finding(
        drama_id=drama_id,
        metric_type=ENGAGEMENT_RATE_METRIC,
        anomaly_type=ENGAGEMENT_RATE_ANOMALY,
        severity=severity,
        analysis_as_of=analysis_as_of,
        statistics=statistics,
        current=current,
        evidence=evidence,
    )


def detect_data_spike_anomaly(
    *,
    drama_id: int,
    metric_type: MetricType,
    historical_values: Sequence[Numeric],
    current_value: Numeric,
    analysis_as_of: datetime,
    play_count: Numeric | None = None,
) -> AnomalyDetectionResult:
    """Detect a positive one-day spike for a supported metric."""

    _validate_context(drama_id, analysis_as_of)
    if metric_type not in ALLOWED_METRICS:
        raise AnomalyCalculationError(
            "INVALID_METRIC_TYPE",
            f"unsupported metric_type: {metric_type}",
        )
    if metric_type == ENGAGEMENT_RATE_METRIC:
        if play_count is None:
            raise AnomalyCalculationError(
                "MISSING_PLAY_COUNT",
                "play_count is required for engagement-rate spike detection",
            )
        current_play_count = _as_non_negative(
            play_count,
            field_name="play_count",
        )
        if current_play_count == ZERO:
            return _not_applicable("ZERO_PLAY_COUNT")
        if current_play_count < MINIMUM_PLAY_COUNT_THRESHOLD:
            return _not_applicable("BELOW_MINIMUM_PLAY_COUNT")

    statistics = calculate_z_score(historical_values, current_value)
    if statistics is None:
        return _insufficient_history()
    current = _as_non_negative(current_value, field_name="current_value")
    if statistics.deviation <= ZERO:
        return _normal()

    if statistics.z_score is None:
        severity: Severity = "C"
        evidence = _build_evidence(
            current=current,
            statistics=statistics,
            threshold_mode="ABSOLUTE_DEVIATION_FALLBACK",
        )
    else:
        severity = determine_anomaly_severity(abs(statistics.z_score))
        if severity is None:
            return _normal()
        evidence = _build_evidence(current=current, statistics=statistics)

    return _finding(
        drama_id=drama_id,
        metric_type=metric_type,
        anomaly_type=DATA_SPIKE_ANOMALY,
        severity=severity,
        analysis_as_of=analysis_as_of,
        statistics=statistics,
        current=current,
        evidence=evidence,
    )


# Short aliases keep call sites readable while the explicit names remain part
# of the public API used by later Service tests.
detect_play_count_growth = detect_play_count_growth_anomaly
detect_play_count_drop = detect_play_count_drop_anomaly
detect_engagement_rate = detect_engagement_rate_anomaly
detect_data_spike = detect_data_spike_anomaly


__all__ = (
    "ALLOWED_ANOMALIES",
    "ALLOWED_METRICS",
    "ANOMALY_ALGORITHM_VERSION",
    "AnomalyCalculationError",
    "AnomalyDetectionResult",
    "AnomalyFinding",
    "DATA_SPIKE_ANOMALY",
    "ENGAGEMENT_RATE_ANOMALY",
    "ENGAGEMENT_RATE_METRIC",
    "MINIMUM_ENGAGEMENT_DEVIATION",
    "MINIMUM_HISTORY_POINTS",
    "MINIMUM_PLAY_COUNT_THRESHOLD",
    "PLAY_COUNT_DROP_ANOMALY",
    "PLAY_COUNT_GROWTH_ANOMALY",
    "PLAY_COUNT_METRIC",
    "RECOMMENDED_BASELINE_WINDOW",
    "ZScoreResult",
    "calculate_engagement_rate",
    "calculate_z_score",
    "detect_data_spike",
    "detect_data_spike_anomaly",
    "detect_engagement_rate",
    "detect_engagement_rate_anomaly",
    "detect_play_count_drop",
    "detect_play_count_drop_anomaly",
    "detect_play_count_growth",
    "detect_play_count_growth_anomaly",
    "determine_anomaly_severity",
)
