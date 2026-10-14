"""Legacy Shanghai-wall-clock compatibility for Data Quality evidence."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from sqlalchemy.orm import Session

from repositories.data_quality_evidence_repository import (
    LEGACY_SHANGHAI_WALL_CLOCK,
    UTC_NAIVE,
    DataQualityEvidenceRepository,
    LegacyRevisionClassificationError,
    LegacyRevisionTimePolicy,
    _normalize_revision_changed_at,
    _utc_naive_to_local_wall_clock,
    BUSINESS_TIME_ZONE,
)


AS_OF = datetime(2026, 9, 9, 15, 59, 59, 999999)


def _policy(**overrides: object) -> LegacyRevisionTimePolicy:
    values: dict[str, object] = {
        "database_name": "isolated",
        "max_revision_id": 2,
        "expected_revision_count": 2,
        "expected_min_changed_at": datetime(2026, 9, 9, 8),
        "expected_max_changed_at": datetime(2026, 9, 9, 20),
    }
    values.update(overrides)
    return LegacyRevisionTimePolicy(**values)  # type: ignore[arg-type]


def _row(
    revision_id: int | None,
    *,
    snapshot_id: int = 10,
    version_no: int = 1,
    previous_revision_id: int | None = None,
    action: str = "INITIAL",
    changed_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        snapshot_id=snapshot_id,
        drama_platform_id=20,
        snapshot_time=datetime(2026, 9, 8, 4),
        snapshot_revision_id=revision_id,
        version_no=version_no,
        previous_revision_id=previous_revision_id,
        revision_action=action,
        play_count=None if action == "VOID" else 100,
        like_count=10,
        comment_count=5,
        favorite_count=3,
        share_count=2,
        changed_at=changed_at,
    )


def _repository_with_rows(
    rows: list[SimpleNamespace],
    *,
    policy: LegacyRevisionTimePolicy | None = None,
) -> DataQualityEvidenceRepository:
    session = create_autospec(Session, instance=True)
    session.execute.return_value.all.return_value = rows
    return DataQualityEvidenceRepository(session, legacy_time_policy=policy)


def test_legacy_wall_clock_is_normalized_with_microseconds_preserved() -> None:
    raw = datetime(2026, 9, 9, 19, 41, 11, 712205)

    normalized, semantics = _normalize_revision_changed_at(
        revision_id=2,
        changed_at=raw,
        policy=_policy(),
    )

    assert normalized == datetime(2026, 9, 9, 11, 41, 11, 712205)
    assert semantics == LEGACY_SHANGHAI_WALL_CLOCK


def test_new_revision_remains_utc_even_on_an_old_snapshot() -> None:
    changed_at = datetime(2026, 9, 9, 13)

    normalized, semantics = _normalize_revision_changed_at(
        revision_id=3,
        changed_at=changed_at,
        policy=_policy(),
    )

    assert normalized == changed_at
    assert semantics == UTC_NAIVE


def test_legacy_sql_prefilter_cutoff_uses_shanghai_wall_clock() -> None:
    assert _utc_naive_to_local_wall_clock(
        AS_OF,
        BUSINESS_TIME_ZONE,
    ) == datetime(2026, 9, 9, 23, 59, 59, 999999)


def test_mixed_legacy_and_utc_chain_selects_latest_normalized_revision() -> None:
    repository = _repository_with_rows(
        [
            _row(1, changed_at=datetime(2026, 9, 9, 20)),
            _row(
                3,
                version_no=2,
                previous_revision_id=1,
                action="CORRECTION",
                changed_at=datetime(2026, 9, 9, 13),
            ),
        ],
        policy=_policy(),
    )

    slots = repository._list_visible_slots(  # noqa: SLF001
        drama_platform_ids=(20,),
        analysis_as_of=AS_OF,
    )

    assert [item.snapshot_revision_id for item in slots[0].visible_revisions] == [
        1,
        3,
    ]
    assert slots[0].selected_revision.snapshot_revision_id == 3


def test_latest_visible_void_is_selected_without_revision_fallback() -> None:
    repository = _repository_with_rows(
        [
            _row(1, changed_at=datetime(2026, 9, 9, 20)),
            _row(
                3,
                version_no=2,
                previous_revision_id=1,
                action="VOID",
                changed_at=datetime(2026, 9, 9, 13),
            ),
        ],
        policy=_policy(),
    )

    slot = repository._list_visible_slots(  # noqa: SLF001
        drama_platform_ids=(20,),
        analysis_as_of=AS_OF,
    )[0]

    assert slot.selected_revision.snapshot_revision_id == 3
    assert slot.selected_revision.revision_action == "VOID"


def test_same_normalized_time_uses_revision_id_as_tie_breaker() -> None:
    repository = _repository_with_rows(
        [
            _row(1, changed_at=datetime(2026, 9, 9, 20)),
            _row(
                3,
                version_no=2,
                previous_revision_id=1,
                action="CORRECTION",
                changed_at=datetime(2026, 9, 9, 12),
            ),
        ],
        policy=_policy(),
    )

    slot = repository._list_visible_slots(  # noqa: SLF001
        drama_platform_ids=(20,),
        analysis_as_of=AS_OF,
    )[0]

    assert slot.visible_revisions[0].changed_at == slot.visible_revisions[1].changed_at
    assert slot.selected_revision.snapshot_revision_id == 3


def test_revision_after_as_of_is_excluded_after_normalization() -> None:
    repository = _repository_with_rows(
        [_row(1, changed_at=datetime(2026, 9, 10))],
        policy=_policy(),
    )

    slot = repository._list_visible_slots(  # noqa: SLF001
        drama_platform_ids=(20,),
        analysis_as_of=AS_OF,
    )[0]

    assert slot.visible_revisions == ()
    assert slot.selected_revision is None


def test_analysis_as_of_equal_to_normalized_changed_at_is_visible() -> None:
    repository = _repository_with_rows(
        [_row(1, changed_at=datetime(2026, 9, 9, 23, 59, 59, 999999))],
        policy=_policy(),
    )

    slot = repository._list_visible_slots(  # noqa: SLF001
        drama_platform_ids=(20,),
        analysis_as_of=AS_OF,
    )[0]

    assert slot.selected_revision.snapshot_revision_id == 1


def test_snapshot_without_revision_remains_explicitly_unavailable() -> None:
    repository = _repository_with_rows([_row(None)])

    slot = repository._list_visible_slots(  # noqa: SLF001
        drama_platform_ids=(20,),
        analysis_as_of=AS_OF,
    )[0]

    assert slot.visible_revisions == ()
    assert slot.selected_revision is None


def test_policy_accepts_audited_id_gaps_when_fingerprint_count_matches() -> None:
    session = create_autospec(Session, instance=True)
    session.scalar.return_value = "isolated"
    session.execute.return_value.one.return_value = (
        2,
        datetime(2026, 9, 9, 8),
        datetime(2026, 9, 9, 20),
        3,
    )
    repository = DataQualityEvidenceRepository(
        session,
        legacy_time_policy=_policy(max_revision_id=3),
    )

    repository._validate_legacy_time_policy()  # noqa: SLF001


@pytest.mark.parametrize(
    ("database_name", "fingerprint"),
    [
        ("unexpected_clone", (2, datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 20), 2)),
        ("isolated", (1, datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 20), 2)),
    ],
)
def test_cross_environment_or_fingerprint_mismatch_fails_closed(
    database_name: str,
    fingerprint: tuple[object, ...],
) -> None:
    session = create_autospec(Session, instance=True)
    session.scalar.return_value = database_name
    session.execute.return_value.one.return_value = fingerprint
    repository = DataQualityEvidenceRepository(
        session,
        legacy_time_policy=_policy(),
    )

    with pytest.raises(LegacyRevisionClassificationError):
        repository._validate_legacy_time_policy()  # noqa: SLF001


def test_no_eligible_feed_avoids_revision_query() -> None:
    session = create_autospec(Session, instance=True)
    session.execute.return_value.all.return_value = []
    repository = DataQualityEvidenceRepository(session)

    bundle = repository.load_bundle(
        score_date=date(2026, 9, 9),
        analysis_as_of=AS_OF,
    )

    assert bundle.eligible_feeds == ()
    assert bundle.window_slots == ()
    assert session.execute.call_count == 1
