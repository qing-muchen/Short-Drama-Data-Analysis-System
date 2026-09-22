"""Tests for the read-only DramaProfileService aggregation boundary."""

from datetime import datetime, timezone

import pytest

from services.drama_profile.contracts import (
    ActionProfileSummary,
    AnomalyProfileSummary,
    AvailabilityReason,
    ExplanationProfileSummary,
    ModuleAvailability,
    PredictionProfileSummary,
    QualityProfileSummary,
    ScoreProfileSummary,
)
from services.drama_profile.service import DramaProfileService


NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)


class Provider:
    def __init__(self, value=None, error=None): self.value, self.error, self.calls = value, error, []
    def get_profile_summary(self, drama_id):
        self.calls.append(drama_id)
        if self.error: raise self.error
        return self.value


def make_service(*, failing=None):
    available = ModuleAvailability(available=True)
    providers = {
        "score": Provider(ScoreProfileSummary(available=available, score_level="A", analysis_as_of=NOW)),
        "quality": Provider(QualityProfileSummary(available=available, quality_level="B", analysis_as_of=NOW)),
        "prediction": Provider(PredictionProfileSummary(available=available, prediction_status="CALCULATED", analysis_as_of=NOW)),
        "anomaly": Provider(AnomalyProfileSummary(available=available, active_count=1, analysis_as_of=NOW)),
        "action": Provider(ActionProfileSummary(available=available, open_count=2)),
        "explanation": Provider(ExplanationProfileSummary(available=available, lineage_available=True)),
    }
    if failing:
        providers[failing] = Provider(error=RuntimeError("provider failure"))
    return DramaProfileService(*providers.values()), providers


def test_complete_profile_aggregates_all_six_providers():
    service, providers = make_service()
    profile = service.get_profile(7)
    assert profile.drama.drama_id == 7
    assert profile.performance.score_level == "A"
    assert profile.quality.quality_level == "B"
    assert profile.trend.prediction_status == "CALCULATED"
    assert profile.risk.active_count == 1
    assert profile.operations.open_count == 2
    assert profile.explanations.lineage_available is True
    assert all(provider.calls == [7] for provider in providers.values())


def test_partial_module_state_is_preserved():
    service, providers = make_service()
    unavailable = ModuleAvailability(available=False, reason=AvailabilityReason.INSUFFICIENT_HISTORY)
    providers["prediction"].value = PredictionProfileSummary(available=unavailable)
    profile = service.get_profile(7)
    assert profile.trend.available.reason is AvailabilityReason.INSUFFICIENT_HISTORY
    assert profile.performance.available.available is True


def test_provider_exception_isolated_to_one_module():
    service, _ = make_service(failing="anomaly")
    profile = service.get_profile(7)
    assert profile.risk.available.available is False
    assert profile.risk.available.reason is AvailabilityReason.NOT_AVAILABLE
    assert profile.performance.available.available is True


def test_invalid_drama_id_rejected():
    service, _ = make_service()
    with pytest.raises(ValueError):
        service.get_profile(0)


def test_basic_provider_is_injected_without_orm_access():
    class BasicProvider:
        def get_profile_basic(self, drama_id):
            return {"drama_id": drama_id, "title": "注入短剧", "platform": "平台", "tags": ["都市"]}

    service, _ = make_service()
    service.basic_provider = BasicProvider()
    profile = service.get_profile(7)
    assert profile.drama.title == "注入短剧"
    assert profile.drama.tags == ("都市",)


def test_service_source_has_no_business_service_or_transaction_calls():
    source = open("backend/services/drama_profile/service.py", encoding="utf-8").read()
    for forbidden in ("ScoreService", "PredictionService", "AnomalyService", "OperationActionService", "commit(", "rollback(", "flush(", "sqlalchemy", "Session"):
        assert forbidden not in source
