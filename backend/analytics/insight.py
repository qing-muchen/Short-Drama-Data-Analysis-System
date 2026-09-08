"""Insight Rule Set V1: deterministic, evidence-backed summaries."""

from dataclasses import dataclass
from math import ceil
from typing import Any, Iterable

from analytics.constants import (
    DETAIL_INSIGHT_LIMIT,
    GROWTH_CLEAR_THRESHOLD,
    GROWTH_DECLINE_THRESHOLD,
    GROWTH_RAPID_THRESHOLD,
    GROUP_INSIGHT_MIN_SAMPLE,
    INSIGHT_PRIORITY,
    INSIGHT_RULE_SET_VERSION,
    STRONG_RANKING_MIN_SAMPLE,
)
from analytics.context import AnalysisContext
from analytics.heat import HeatScore
from analytics.metrics import MetricResult
from analytics.potential import PotentialScore


@dataclass(frozen=True, slots=True)
class Insight:
    insight_type: str
    rule_code: str
    trigger: str
    evidence: dict[str, Any]
    conclusion: str
    priority: int
    rule_set_version: str = INSIGHT_RULE_SET_VERSION


def _top_decile(rank: int, count: int) -> bool:
    return count >= STRONG_RANKING_MIN_SAMPLE and rank <= ceil(count * 0.10)


def _evidence_context(context: AnalysisContext) -> dict[str, Any]:
    return {
        "analysis_as_of": context.analysis_as_of.isoformat(),
        "time_window": context.time_window,
        "granularity": context.granularity,
        "platform_scope": list(context.platform_scope),
        "tag_scope": list(context.tag_scope),
        "model_versions": {
            "heat": context.model_versions.heat,
            "potential": context.model_versions.potential,
            "anomaly": context.model_versions.anomaly,
            "insight": context.model_versions.insight,
            "metrics": context.model_versions.metrics,
        },
    }


def generate_insights(
    *,
    metrics: MetricResult,
    heat: HeatScore | None,
    potential: PotentialScore | None,
    context: AnalysisContext,
    limit: int = DETAIL_INSIGHT_LIMIT,
) -> list[Insight]:
    """Generate detail-page Insights and merge high-Heat/decline conflict."""

    insights: list[Insight] = []
    shared = _evidence_context(context)

    if metrics.excluded_error_count:
        insights.append(
            Insight(
                insight_type="DATA_QUALITY",
                rule_code="DQ_ERROR_EXCLUDED_V1",
                trigger="Active ERROR data was excluded",
                evidence={**shared, "excluded_error_count": metrics.excluded_error_count},
                conclusion="部分异常数据未参与分析。",
                priority=INSIGHT_PRIORITY["DATA_QUALITY"],
            )
        )
    if metrics.warning_count:
        insights.append(
            Insight(
                insight_type="DATA_QUALITY",
                rule_code="DQ_WARNING_INCLUDED_V1",
                trigger="WARNING data participated in the analysis",
                evidence={**shared, "warning_count": metrics.warning_count},
                conclusion="当前分析包含部分质量告警数据。",
                priority=INSIGHT_PRIORITY["DATA_QUALITY"],
            )
        )
    if metrics.freshness == "STALE":
        insights.append(
            Insight(
                insight_type="DATA_QUALITY",
                rule_code="DQ_STALE_V1",
                trigger="Latest included data is older than 24 hours",
                evidence={**shared, "latest_snapshot_time": metrics.snapshot_time.isoformat() if metrics.snapshot_time else None},
                conclusion="部分平台最新数据超过 24 小时未更新。",
                priority=INSIGHT_PRIORITY["DATA_QUALITY"],
            )
        )

    high_heat = heat is not None and (
        _top_decile(heat.rank, heat.candidate_count)
        or (heat.candidate_count < STRONG_RANKING_MIN_SAMPLE and heat.rank <= 3)
    )
    declining = (
        metrics.growth_7d is not None
        and metrics.growth_7d < GROWTH_DECLINE_THRESHOLD
    )
    if high_heat and declining:
        insights.append(
            Insight(
                insight_type="RISK",
                rule_code="PERFORMANCE_HIGH_GROWTH_DECLINE_V1",
                trigger="High Heat ranking with declining Growth7D",
                evidence={
                    **shared,
                    "heat_score": heat.score,
                    "heat_rank": heat.rank,
                    "heat_candidate_count": heat.candidate_count,
                    "growth_7d": metrics.growth_7d,
                    "decline_threshold": GROWTH_DECLINE_THRESHOLD,
                },
                conclusion="当前综合热度较高，但近 7 日播放增长下降，需要关注近期变化。",
                priority=INSIGHT_PRIORITY["RISK"],
            )
        )
    else:
        if high_heat and heat is not None:
            strong = heat.candidate_count >= STRONG_RANKING_MIN_SAMPLE
            insights.append(
                Insight(
                    insight_type="PERFORMANCE",
                    rule_code="PERFORMANCE_TOP_HEAT_V1" if strong else "PERFORMANCE_SMALL_SAMPLE_TOP3_V1",
                    trigger="Heat ranking is within the applicable leading range",
                    evidence={
                        **shared,
                        "heat_score": heat.score,
                        "rank": heat.rank,
                        "candidate_count": heat.candidate_count,
                    },
                    conclusion=(
                        "该短剧在当前分析范围内综合热度较高。"
                        if strong
                        else "该短剧在当前小样本范围内综合热度排名靠前。"
                    ),
                    priority=INSIGHT_PRIORITY["PERFORMANCE"],
                )
            )
        if metrics.growth_7d is None:
            insights.append(
                Insight(
                    insight_type="RISK",
                    rule_code="RISK_INSUFFICIENT_7D_BASELINE_V1",
                    trigger="No qualified 7D baseline",
                    evidence={**shared, "growth_7d": None},
                    conclusion="当前缺少合格的 7 日历史基准，暂不形成增长方向结论。",
                    priority=INSIGHT_PRIORITY["RISK"],
                )
            )
        else:
            value = metrics.growth_7d
            if value > GROWTH_RAPID_THRESHOLD:
                label, conclusion = "RAPID", "该短剧近 7 日播放增长较快。"
            elif value > GROWTH_CLEAR_THRESHOLD:
                label, conclusion = "CLEAR", "该短剧近 7 日播放呈明显增长。"
            elif value >= GROWTH_DECLINE_THRESHOLD:
                label, conclusion = "STABLE", "该短剧近 7 日播放变化相对稳定。"
            else:
                label, conclusion = "DECLINE", "该短剧近 7 日播放下降，需要关注。"
            insights.append(
                Insight(
                    insight_type="GROWTH" if label != "DECLINE" else "RISK",
                    rule_code=f"GROWTH_7D_{label}_V1",
                    trigger="Growth7D matched the frozen interpretation interval",
                    evidence={
                        **shared,
                        "growth_7d": value,
                        "rapid_threshold": GROWTH_RAPID_THRESHOLD,
                        "clear_threshold": GROWTH_CLEAR_THRESHOLD,
                        "decline_threshold": GROWTH_DECLINE_THRESHOLD,
                    },
                    conclusion=conclusion,
                    priority=INSIGHT_PRIORITY["GROWTH" if label != "DECLINE" else "RISK"],
                )
            )

    if potential is not None:
        if _top_decile(potential.rank, potential.candidate_count) and (
            metrics.growth_7d is not None
            and metrics.growth_7d > GROWTH_CLEAR_THRESHOLD
        ):
            conclusion = "该短剧当前数据呈现较高的增长潜力信号。"
            rule_code = "POTENTIAL_HIGH_GROWTH_SIGNAL_V1"
        elif potential.candidate_count < STRONG_RANKING_MIN_SAMPLE and potential.rank <= 3:
            conclusion = "该短剧在当前小样本候选中 Potential 排名靠前。"
            rule_code = "POTENTIAL_SMALL_SAMPLE_TOP3_V1"
        else:
            conclusion = ""
            rule_code = ""
        if conclusion:
            insights.append(
                Insight(
                    insight_type="POTENTIAL",
                    rule_code=rule_code,
                    trigger="Potential ranking met the applicable evidence rule",
                    evidence={
                        **shared,
                        "potential_score": potential.score,
                        "rank": potential.rank,
                        "candidate_count": potential.candidate_count,
                        "growth_7d": metrics.growth_7d,
                        "quality_engagement": metrics.engagement.quality_engagement,
                        "favorite_rate": metrics.engagement.favorite_rate,
                        "share_rate": metrics.engagement.share_rate,
                    },
                    conclusion=conclusion,
                    priority=INSIGHT_PRIORITY["POTENTIAL"],
                )
            )

    if not insights:
        insights.append(
            Insight(
                insight_type="RISK",
                rule_code="EMPTY_NO_MATCH_V1",
                trigger="No object-level Insight rule matched",
                evidence=shared,
                conclusion="当前筛选条件下暂无满足条件的分析对象。",
                priority=INSIGHT_PRIORITY["RISK"],
            )
        )
    return sorted(insights, key=lambda item: (item.priority, item.rule_code))[:limit]


def adaptive_top_n(candidate_count: int) -> int:
    if candidate_count >= 50:
        return 10
    if candidate_count >= 10:
        return 5
    return min(3, candidate_count)


def generate_group_insight(
    *,
    insight_type: str,
    subject_name: str,
    metric_name: str,
    metric_value: float,
    sample_size: int,
    context: AnalysisContext,
) -> Insight:
    """Build a non-causal PLATFORM or TAG comparison Insight."""

    if insight_type not in {"PLATFORM", "TAG"}:
        raise ValueError("group insight type must be PLATFORM or TAG")
    shared = _evidence_context(context)
    if sample_size < GROUP_INSIGHT_MIN_SAMPLE:
        return Insight(
            insight_type="RISK",
            rule_code=f"{insight_type}_INSUFFICIENT_SAMPLE_V1",
            trigger="Group sample is below the frozen minimum",
            evidence={
                **shared,
                "subject_name": subject_name,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "sample_size": sample_size,
                "minimum_sample_size": GROUP_INSIGHT_MIN_SAMPLE,
            },
            conclusion="当前样本较少，仅展示对象级统计，不形成群体趋势结论。",
            priority=INSIGHT_PRIORITY["RISK"],
        )
    noun = "平台" if insight_type == "PLATFORM" else "标签"
    return Insight(
        insight_type=insight_type,
        rule_code=f"{insight_type}_COMPARATIVE_METRIC_V1",
        trigger="Comparable group metric is available with sufficient sample",
        evidence={
            **shared,
            "subject_name": subject_name,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "sample_size": sample_size,
        },
        conclusion=f"{subject_name}{noun}在当前范围内的{metric_name}统计值相对突出。",
        priority=INSIGHT_PRIORITY[insight_type],
    )


def limit_insights(insights: Iterable[Insight], limit: int) -> list[Insight]:
    return sorted(insights, key=lambda item: (item.priority, item.rule_code))[:limit]
