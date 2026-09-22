"""Tests for deterministic Phase 6 explanation handlers."""

from datetime import datetime, timezone

from services.explanation import ExplanationContext, ExplanationType
from services.explanation.handlers import (
    AnomalyExplanationGenerator,
    MetricExplanationGenerator,
    TrendExplanationGenerator,
)


AS_OF = datetime(2026, 9, 22, tzinfo=timezone.utc)


def context(explanation_type: ExplanationType, payload: dict) -> ExplanationContext:
    module = {
        ExplanationType.METRIC: "SCORE",
        ExplanationType.TREND: "PREDICTION",
        ExplanationType.ANOMALY: "ANOMALY",
    }[explanation_type]
    return ExplanationContext(
        entity_type=module,
        entity_id=payload.get("score_id", payload.get("prediction_id", payload.get("anomaly_id", 1))),
        module_type=module,
        analysis_as_of=AS_OF,
        algorithm_version="Rule-based Detection V1.0",
        rule_set_version="N/A",
        payload=payload,
    )


def test_metric_handler_generates_fixed_detail_and_lineage() -> None:
    payload = {
        "score_id": 12,
        "dimension_scores": {"HEAT": "positive", "GROWTH": "weak"},
        "contribution_info": {"positive": "热度", "weak": "增长"},
        "score_value": 90,  # input may contain it; handler must not persist it.
    }
    result = MetricExplanationGenerator().generate(
        context(ExplanationType.METRIC, payload)
    )

    assert result.summary == "综合评分主要由热度贡献，增长相对较弱。"
    assert set(result.detail) == {"reason", "inputs", "rules", "versions", "evidence"}
    assert "score_value" not in result.detail
    assert result.lineage_sources[0].source_type == "METRIC"
    assert result.lineage_sources[0].source_id == 12


def test_trend_handler_does_not_persist_prediction_value() -> None:
    result = TrendExplanationGenerator().generate(
        context(
            ExplanationType.TREND,
            {
                "prediction_id": 20,
                "prediction_input_id": 21,
                "trend_direction": "UP",
                "window_length": 7,
                "prediction_value": 3850,
            },
        )
    )

    assert result.summary == "预测结果基于连续历史窗口和移动平均趋势。"
    assert result.detail["trend_direction"] == "UP"
    assert result.detail["window_length"] == 7
    assert "prediction_value" not in str(result.detail)
    assert result.lineage_sources[0].source_id == 21


def test_anomaly_handler_uses_fixed_type_template_and_preserves_evidence() -> None:
    result = AnomalyExplanationGenerator().generate(
        context(
            ExplanationType.ANOMALY,
            {
                "anomaly_id": 30,
                "anomaly_type": "DATA_SPIKE_ANOMALY",
                "severity": "A",
                "metric_type": "PLAY_COUNT",
                "evidence_summary": "当前值显著高于历史基线。",
                "threshold_summary": "abs(z-score) >= 2",
                "z_score": 4.2,
            },
        )
    )

    assert result.summary == "指标出现短时间突变。"
    assert result.detail["evidence"] == ["当前值显著高于历史基线。"]
    assert "z_score" not in str(result.detail)
    assert result.lineage_sources[0].source_type == "ANOMALY_EVIDENCE"


def test_same_input_produces_identical_output() -> None:
    payload = {
        "anomaly_id": 30,
        "anomaly_type": "PLAY_COUNT_DROP_ANOMALY",
        "severity": "C",
        "metric_type": "PLAY_COUNT",
        "evidence_summary": "下降偏离基线。",
        "threshold_summary": "abs(z-score) >= 2",
    }
    first = AnomalyExplanationGenerator().generate(
        context(ExplanationType.ANOMALY, payload)
    )
    second = AnomalyExplanationGenerator().generate(
        context(ExplanationType.ANOMALY, payload)
    )

    assert first == second


def test_handlers_do_not_require_database_objects() -> None:
    metric = MetricExplanationGenerator()
    trend = TrendExplanationGenerator()
    anomaly = AnomalyExplanationGenerator()

    assert metric.explanation_type is ExplanationType.METRIC
    assert trend.explanation_type is ExplanationType.TREND
    assert anomaly.explanation_type is ExplanationType.ANOMALY
