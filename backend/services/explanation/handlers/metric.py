"""Deterministic explanation handler for composite score results."""

from __future__ import annotations

from typing import Any, Mapping

from ..contracts import (
    ExplanationContext,
    ExplanationGenerator,
    ExplanationType,
    GeneratedExplanation,
    LineageSource,
)


class MetricExplanationGenerator(ExplanationGenerator):
    """Explain supplied score contributors without recalculating a score."""

    explanation_type = ExplanationType.METRIC

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        payload = context.payload
        score_id = _positive_id(payload, "score_id")
        positive = _dimension_name(payload, "positive_dimension", "positive")
        weak = _dimension_name(payload, "weak_dimension", "weak")
        summary = f"综合评分主要由{positive}贡献，{weak}相对较弱。"

        detail = {
            "reason": summary,
            "inputs": [
                {"name": "positive_dimension", "value": positive},
                {"name": "weak_dimension", "value": weak},
            ],
            "rules": [
                "使用调用方已确定的维度贡献信息",
                "不重新计算综合评分或等级",
            ],
            "versions": {
                "algorithm_version": context.algorithm_version,
                "rule_set_version": context.rule_set_version,
            },
            "evidence": _evidence_names(payload),
        }
        return GeneratedExplanation(
            summary=summary,
            detail=detail,
            lineage_sources=(LineageSource("METRIC", score_id, "DERIVED_FROM"),),
        )


def _positive_id(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"payload.{key} must be a positive integer")
    return value


def _dimension_name(payload: Mapping[str, Any], direct_key: str, info_key: str) -> str:
    direct = payload.get(direct_key)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    info = payload.get("contribution_info")
    if isinstance(info, Mapping):
        value = info.get(info_key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "指标维度"


def _evidence_names(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    dimensions = payload.get("dimension_scores")
    if not isinstance(dimensions, Mapping):
        return []
    return [
        {"dimension": str(name)}
        for name in sorted(dimensions, key=str)
    ]


__all__ = ["MetricExplanationGenerator"]
