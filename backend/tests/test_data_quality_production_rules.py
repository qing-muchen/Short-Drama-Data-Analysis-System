"""Approved production evaluator behavior over immutable evidence DTOs."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType, SimpleNamespace

from analytics.data_quality_rules import (
    evaluate_cumulative_nonnegative,
    evaluate_play_count_coverage,
    evaluate_revision_chain,
    evaluate_snapshot_freshness,
)
from repositories.data_quality_evidence_repository import (
    EligibleFeedEvidence,
    QualityEvidenceBundle,
    SnapshotRevisionEvidence,
    SnapshotSlotEvidence,
)
from services.data_quality_service import QualityEvaluationContext

SCORE_DATE = date(2026, 10, 10)
AS_OF = datetime(2026, 10, 10, 0, 0)
WINDOW_START = datetime(2026, 10, 2, 16, 0)
WINDOW_END = datetime(2026, 10, 9, 16, 0)


def _revision(
    revision_id: int,
    *,
    snapshot_id: int,
    version: int = 1,
    previous: int | None = None,
    action: str = "INITIAL",
    play_count: int | None = 10,
    changed_at: datetime | None = None,
) -> SnapshotRevisionEvidence:
    return SnapshotRevisionEvidence(
        snapshot_revision_id=revision_id,
        snapshot_id=snapshot_id,
        version_no=version,
        previous_revision_id=previous,
        revision_action=action,
        play_count=play_count,
        like_count=1,
        comment_count=1,
        favorite_count=1,
        share_count=1,
        changed_at=changed_at or datetime(2026, 10, 3),
    )


def _slot(
    snapshot_id: int,
    day_offset: int,
    revisions: tuple[SnapshotRevisionEvidence, ...],
) -> SnapshotSlotEvidence:
    return SnapshotSlotEvidence(
        snapshot_id=snapshot_id,
        drama_platform_id=1,
        snapshot_time=WINDOW_START + timedelta(days=day_offset, hours=1),
        visible_revisions=revisions,
        selected_revision=max(
            revisions,
            key=lambda item: (item.changed_at, item.snapshot_revision_id),
            default=None,
        ),
    )


def _bundle(
    slots: tuple[SnapshotSlotEvidence, ...],
    *,
    feeds: tuple[EligibleFeedEvidence, ...] = (EligibleFeedEvidence(1, 1, 1),),
    latest: SnapshotSlotEvidence | None = None,
) -> QualityEvidenceBundle:
    return QualityEvidenceBundle(
        score_date=SCORE_DATE,
        analysis_as_of=AS_OF,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        eligible_feeds=feeds,
        window_slots=slots,
        latest_valid_slot_by_feed=MappingProxyType(
            {1: latest} if latest is not None else {}
        ),
        source_watermark=MappingProxyType(
            {"replay_capability": "LIMITED_CURRENT_MASTER"}
        ),
    )


def _rule(threshold: int) -> SimpleNamespace:
    return SimpleNamespace(configuration={"pass_threshold": threshold})


def test_c4_uses_seven_complete_shanghai_days() -> None:
    slots = tuple(
        _slot(day + 1, day, (_revision(day + 1, snapshot_id=day + 1),))
        for day in range(7)
    )
    result = evaluate_play_count_coverage(
        _rule(100),
        QualityEvaluationContext(SCORE_DATE, AS_OF),
        _bundle(slots),
    )
    assert result.status == "PASS"
    assert (result.applicable_count, result.passed_count) == (7, 7)
    assert result.rule_score == Decimal("100.00")


def test_void_latest_revision_does_not_fallback_for_coverage_or_freshness() -> None:
    initial = _revision(1, snapshot_id=1, changed_at=datetime(2026, 10, 3))
    void = _revision(
        2,
        snapshot_id=1,
        version=2,
        previous=1,
        action="VOID",
        play_count=None,
        changed_at=datetime(2026, 10, 4),
    )
    slot = _slot(1, 0, (initial, void))
    bundle = _bundle((slot,))

    coverage = evaluate_play_count_coverage(
        _rule(100), QualityEvaluationContext(SCORE_DATE, AS_OF), bundle
    )
    freshness = evaluate_snapshot_freshness(
        _rule(80), QualityEvaluationContext(SCORE_DATE, AS_OF), bundle
    )

    assert coverage.passed_count == 0
    assert freshness.rule_score == Decimal("0.00")


def test_a1_missing_optional_values_are_excluded_and_negative_values_fail() -> None:
    revision = _revision(1, snapshot_id=1, play_count=-1)
    slot = _slot(1, 0, (revision,))
    result = evaluate_cumulative_nonnegative(
        _rule(100),
        QualityEvaluationContext(SCORE_DATE, AS_OF),
        _bundle((slot,)),
    )
    assert result.status == "FAIL"
    assert result.applicable_count == 5
    assert result.failed_count == 1


def test_k2_includes_void_and_rejects_incomplete_visible_chain() -> None:
    first = _revision(1, snapshot_id=1)
    void = _revision(
        3,
        snapshot_id=1,
        version=3,
        previous=2,
        action="VOID",
        play_count=None,
    )
    result = evaluate_revision_chain(
        _rule(100),
        QualityEvaluationContext(SCORE_DATE, AS_OF),
        _bundle((_slot(1, 0, (first, void)),)),
    )
    assert result.status == "FAIL"
    assert result.failed_count == 1


def test_k2_accepts_complete_initial_correction_void_chain() -> None:
    first = _revision(1, snapshot_id=1)
    correction = _revision(
        2,
        snapshot_id=1,
        version=2,
        previous=1,
        action="CORRECTION",
    )
    void = _revision(
        3,
        snapshot_id=1,
        version=3,
        previous=2,
        action="VOID",
        play_count=None,
    )
    result = evaluate_revision_chain(
        _rule(100),
        QualityEvaluationContext(SCORE_DATE, AS_OF),
        _bundle((_slot(1, 0, (first, correction, void)),)),
    )
    assert result.status == "PASS"
    assert result.passed_count == 1


def test_no_eligible_feed_is_not_scored_by_individual_rules() -> None:
    bundle = _bundle((), feeds=())
    context = QualityEvaluationContext(SCORE_DATE, AS_OF)
    assert evaluate_play_count_coverage(_rule(100), context, bundle).status == "NOT_APPLICABLE"
    assert evaluate_snapshot_freshness(_rule(80), context, bundle).status == "NOT_APPLICABLE"
