"""Unit tests for Phase 7 read-only profile providers."""

from dataclasses import dataclass
from datetime import datetime, timezone

from services.drama_profile.contracts import AvailabilityReason
from services.drama_profile.providers import (
    ActionProfileProvider,
    AnomalyProfileProvider,
    ExplanationProfileProvider,
    PredictionProfileProvider,
    QualityProfileProvider,
    ScoreProfileProvider,
)


NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)


@dataclass
class Obj:
    pass


def obj(**values):
    result = Obj()
    for key, value in values.items():
        setattr(result, key, value)
    return result


class ScoreRepo:
    def __init__(self, result): self.result = result
    def get_latest_by_drama(self, **kwargs): self.kwargs = kwargs; return self.result


def test_score_provider_maps_result_and_missing_state():
    provider = ScoreProfileProvider(ScoreRepo(obj(level="A", heat_score=80, growth_score=70, engagement_score=60, lifecycle_score=90, analysis_as_of=NOW, algorithm_version="Composite Score V1.0")))
    result = provider.get_profile_summary(3)
    assert result.available.available is True
    assert result.score_level == "A"
    assert result.dimensions["heat_score"] == 80.0
    assert ScoreProfileProvider(ScoreRepo(None)).get_profile_summary(3).available.reason is AvailabilityReason.NOT_CALCULATED


class QualityRepo:
    def __init__(self, result): self.result = result
    def get_current_score(self, **kwargs): return self.result


def test_quality_provider_maps_global_result():
    result = QualityProfileProvider(QualityRepo(obj(quality_grade="B", open_issue_count=2, analysis_as_of=NOW, rule_set_version="R1"))).get_profile_summary(9)
    assert result.quality_level == "B"
    assert result.quality_status == "OPEN_ISSUES"
    assert result.rule_set_version == "R1"
    assert QualityProfileProvider(QualityRepo(None)).get_profile_summary(9).available.reason is AvailabilityReason.NOT_CALCULATED


class PredictionRepo:
    def __init__(self, result, status=None): self.result, self.status = result, status
    def get_latest_prediction(self, **kwargs): return self.result
    def get_prediction_status(self, **kwargs): return self.status


def test_prediction_provider_distinguishes_history_shortage():
    available = PredictionProfileProvider(PredictionRepo(obj(analysis_as_of=NOW, algorithm_version="Moving Average V1.0"))).get_profile_summary(1)
    insufficient = PredictionProfileProvider(PredictionRepo(None, "INSUFFICIENT_HISTORY")).get_profile_summary(1)
    missing = PredictionProfileProvider(PredictionRepo(None)).get_profile_summary(1)
    assert available.available.available is True
    assert insufficient.available.reason is AvailabilityReason.INSUFFICIENT_HISTORY
    assert missing.available.reason is AvailabilityReason.NOT_CALCULATED


class AnomalyRepo:
    def __init__(self, records, detected=True): self.records, self.detected = records, detected
    def get_by_drama(self, **kwargs): return self.records
    def has_detection_for_drama(self, **kwargs): return self.detected


def test_anomaly_provider_handles_active_and_missing_records():
    records = [obj(anomaly_id=1, anomaly_type="DATA_SPIKE_ANOMALY", severity="A", status="OPEN", analysis_as_of=NOW)]
    result = AnomalyProfileProvider(AnomalyRepo(records)).get_profile_summary(1)
    assert result.active_count == 1
    assert result.highest_severity == "A"
    assert AnomalyProfileProvider(AnomalyRepo([])).get_profile_summary(1).available.reason is AvailabilityReason.NO_ANOMALY
    assert AnomalyProfileProvider(AnomalyRepo([], detected=False)).get_profile_summary(1).available.reason is AvailabilityReason.NOT_DETECTED


class ActionRepo:
    def __init__(self, items): self.items = items
    def list_actions(self, **kwargs): return obj(items=self.items)


def test_action_provider_treats_empty_actions_as_available():
    result = ActionProfileProvider(ActionRepo([obj(action_id=1, title="处理", status="OPEN", priority="HIGH", updated_at=NOW)])).get_profile_summary(1)
    empty = ActionProfileProvider(ActionRepo([])).get_profile_summary(1)
    assert result.open_count == 1
    assert empty.available.available is True
    assert empty.recent_actions == ()


class ExplanationRepo:
    def __init__(self, result): self.result = result
    def get_latest_explanation(self, **kwargs): return self.result


class LineageRepo:
    def get_lineage_by_target(self, **kwargs): return [object()]


def test_explanation_provider_maps_snapshot_and_lineage():
    result = ExplanationProfileProvider(ExplanationRepo(obj(explanation_id=8, summary="原因", analysis_as_of=NOW, algorithm_version="V1")), LineageRepo()).get_profile_summary(1)
    missing = ExplanationProfileProvider(ExplanationRepo(None)).get_profile_summary(1)
    assert result.available.available is True
    assert result.lineage_available is True
    assert missing.available.reason is AvailabilityReason.NOT_AVAILABLE


def test_providers_do_not_require_services_or_calculators():
    source = open("backend/services/drama_profile/providers.py", encoding="utf-8").read()
    assert "Service" not in source
    assert "Calculator" not in source
    assert "commit(" not in source
    assert "rollback(" not in source
