"""Frozen Analytics Design Baseline V1 constants."""

from datetime import timedelta

HEAT_MODEL_VERSION = "Heat Model V1"
POTENTIAL_MODEL_VERSION = "Potential Model V1"
ANOMALY_MODEL_VERSION = "Anomaly Detection Model V1"
INSIGHT_RULE_SET_VERSION = "Insight Rule Set V1"
METRIC_DICTIONARY_VERSION = "Analytics Metric Dictionary V1.0"

HEAT_WEIGHTS = {
    "play_count": 0.40,
    "like_count": 0.20,
    "comment_count": 0.15,
    "favorite_count": 0.15,
    "share_count": 0.10,
}

POTENTIAL_WEIGHTS = {
    "growth_7d": 0.45,
    "quality_engagement": 0.25,
    "favorite_rate": 0.20,
    "share_rate": 0.10,
}

WINDOW_TARGETS = {
    "24H": timedelta(hours=24),
    "7D": timedelta(days=7),
    "30D": timedelta(days=30),
}

WINDOW_TOLERANCES = {
    "24H": timedelta(hours=6),
    "7D": timedelta(hours=24),
    "30D": timedelta(hours=48),
}

FRESHNESS_LIMIT = timedelta(hours=24)
ACTIVE_QUALITY_STATUSES = frozenset({"OPEN", "CONFIRMED"})
CURRENT_DRAMA_STATUSES = frozenset({"SERIALIZING", "COMPLETED"})
CURRENT_RELEASE_STATUS = "ONLINE"
ACTIVE_MASTER_STATUS = "ACTIVE"

GROWTH_RAPID_THRESHOLD = 0.50
GROWTH_CLEAR_THRESHOLD = 0.20
GROWTH_DECLINE_THRESHOLD = -0.10

INSIGHT_PRIORITY = {
    "RISK": 1,
    "DATA_QUALITY": 1,
    "PERFORMANCE": 2,
    "GROWTH": 3,
    "POTENTIAL": 4,
    "TAG": 5,
    "PLATFORM": 5,
}

DETAIL_INSIGHT_LIMIT = 5
GROUP_INSIGHT_MIN_SAMPLE = 5
STRONG_RANKING_MIN_SAMPLE = 10

