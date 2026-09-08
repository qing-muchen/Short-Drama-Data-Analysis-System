"""Deterministic analytics calculations for the frozen V1 baseline."""

from analytics.context import AnalysisContext, ModelVersions
from analytics.growth import GrowthResult, calculate_overall_growth, calculate_platform_growth
from analytics.heat import HeatCandidate, HeatScore, calculate_heat_scores
from analytics.insight import Insight, generate_group_insight, generate_insights
from analytics.metrics import EngagementMetrics, MetricResult, RawMetrics, SnapshotPoint
from analytics.potential import PotentialCandidate, PotentialScore, calculate_potential_scores

__all__ = [
    "AnalysisContext",
    "EngagementMetrics",
    "GrowthResult",
    "HeatCandidate",
    "HeatScore",
    "Insight",
    "MetricResult",
    "ModelVersions",
    "PotentialCandidate",
    "PotentialScore",
    "RawMetrics",
    "SnapshotPoint",
    "calculate_heat_scores",
    "calculate_overall_growth",
    "calculate_platform_growth",
    "calculate_potential_scores",
    "generate_insights",
    "generate_group_insight",
]
