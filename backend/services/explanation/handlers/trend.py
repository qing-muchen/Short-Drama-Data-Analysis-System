"""Deterministic explanation handler for prediction trend results."""

from __future__ import annotations

from typing import Any

from ..contracts import (
    ExplanationContext,
    ExplanationGenerator,
    ExplanationType,
    GeneratedExplanation,
    LineageSource,
)


class TrendExplanationGenerator(ExplanationGenerator):
    """Explain a supplied prediction trend without running its model."""

    explanation_type = ExplanationType.TREND

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        prediction_id = _positive_id(context.payload.get("prediction_id"), "prediction_id")
        direction = _required_text(context.payload.get("trend_direction"), "trend_direction")
        window_length = context.payload.get("window_length")
        if not isinstance(window_length, int) or isinstance(window_length, bool) or window_length <= 0:
            raise ValueError("payload.window_length must be a positive integer")

        summary = "预测结果基于连续历史窗口和移动平均趋势。"
        detail = {
            "reason": summary,
            "inputs": [
                {"name": "trend_direction", "value": direction},
                {"name": "window_length", "value": window_length},
            ],
            "rules": ["使用调用方已确定的预测趋势", "不重新执行移动平均模型"],
            "versions": {
                "algorithm_version": context.algorithm_version,
                "rule_set_version": context.rule_set_version,
            },
            "evidence": [],
            "trend_direction": direction,
            "window_length": window_length,
            "model_description": "连续历史窗口的移动平均趋势模型",
        }
        source_id = context.payload.get("prediction_input_id", prediction_id)
        source_id = _positive_id(source_id, "prediction_input_id")
        return GeneratedExplanation(
            summary=summary,
            detail=detail,
            lineage_sources=(
                LineageSource("PREDICTION_INPUT", source_id, "USES_WINDOW"),
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


__all__ = ["TrendExplanationGenerator"]
