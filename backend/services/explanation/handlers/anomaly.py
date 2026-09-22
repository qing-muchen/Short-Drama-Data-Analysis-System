"""Deterministic explanation handler for anomaly findings."""

from __future__ import annotations

from typing import Any

from ..contracts import (
    ExplanationContext,
    ExplanationGenerator,
    ExplanationType,
    GeneratedExplanation,
    LineageSource,
)


_ANOMALY_SUMMARIES = {
    "PLAY_COUNT_GROWTH_ANOMALY": "播放量增长偏离历史正常范围。",
    "PLAY_COUNT_DROP_ANOMALY": "播放量下降偏离历史正常范围。",
    "ENGAGEMENT_RATE_ANOMALY": "互动率偏离历史正常范围。",
    "DATA_SPIKE_ANOMALY": "指标出现短时间突变。",
}


class AnomalyExplanationGenerator(ExplanationGenerator):
    """Explain an existing anomaly finding without recalculating its severity."""

    explanation_type = ExplanationType.ANOMALY

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        payload = context.payload
        anomaly_id = _positive_id(payload.get("anomaly_id"), "anomaly_id")
        anomaly_type = _required_text(payload.get("anomaly_type"), "anomaly_type")
        severity = _required_text(payload.get("severity"), "severity")
        metric_type = _required_text(payload.get("metric_type"), "metric_type")
        summary = _ANOMALY_SUMMARIES.get(
            anomaly_type,
            "指标行为偏离历史正常范围。",
        )
        threshold = _required_text(
            payload.get("threshold_summary"), "threshold_summary"
        )
        evidence = _required_text(
            payload.get("evidence_summary"), "evidence_summary"
        )
        detail = {
            "reason": summary,
            "inputs": [{"metric_type": metric_type}],
            "rules": [
                {"anomaly_type": anomaly_type, "severity": severity},
                {"threshold": threshold},
            ],
            "versions": {
                "algorithm_version": context.algorithm_version,
                "rule_set_version": context.rule_set_version,
            },
            "evidence": [evidence],
        }
        return GeneratedExplanation(
            summary=summary,
            detail=detail,
            lineage_sources=(
                LineageSource("ANOMALY_EVIDENCE", anomaly_id, "DERIVED_FROM"),
            ),
        )


def _positive_id(value: Any, key: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"payload.{key} must be a positive integer")
    return value


def _required_text(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"payload.{key} must not be blank")
    return value.strip()


__all__ = ["AnomalyExplanationGenerator"]
