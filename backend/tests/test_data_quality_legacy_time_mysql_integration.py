"""Opt-in mixed legacy/UTC Revision integration test on guarded MySQL."""

from datetime import date, datetime
import os

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.engine import create_engine, make_url
from sqlalchemy.orm import sessionmaker

from database.engine import _set_mysql_session_utc
from models.drama import Drama
from models.master_data import Platform
from models.relations import DramaPlatform
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision
from models.user import User
from repositories.data_quality_evidence_repository import (
    LEGACY_SHANGHAI_WALL_CLOCK,
    UTC_NAIVE,
    DataQualityEvidenceRepository,
    LegacyRevisionClassificationError,
    LegacyRevisionTimePolicy,
)

DATABASE_URL = os.getenv("DQ_LEGACY_ISOLATED_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DQ_LEGACY_ISOLATED_DATABASE_URL is required for opt-in MySQL integration",
)


def _database_url() -> str:
    assert DATABASE_URL is not None
    database = make_url(DATABASE_URL).database or ""
    assert database.startswith("short_drama_s5_2_b2_part1_")
    assert database not in {
        "short_drama_analysis",
        "short_drama_acceptance_v1",
        "short_drama_analysis_test",
    }
    return DATABASE_URL


def test_mixed_legacy_and_utc_revision_chain_on_isolated_mysql() -> None:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    event.listen(engine, "connect", _set_mysql_session_utc)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory() as session:
        assert session.scalar(
            select(func.count()).select_from(DramaMetricSnapshotRevision)
        ) == 0
        administrator = User(
            username="legacy-time-admin",
            password_hash="not-a-real-credential",
            display_name="Legacy time integration",
            role_code="ADMINISTRATOR",
            status="ACTIVE",
        )
        drama = Drama(
            drama_code="LEGACY-TIME-1",
            drama_name="Legacy time integration drama",
            status="SERIALIZING",
        )
        platform = Platform(
            platform_name="Legacy time integration platform",
            status="ACTIVE",
        )
        session.add_all([administrator, drama, platform])
        session.flush()
        feed = DramaPlatform(
            drama_id=drama.drama_id,
            platform_id=platform.platform_id,
            platform_drama_code="LEGACY-TIME-1",
            online_at=datetime(2026, 9, 1),
            status="ONLINE",
        )
        session.add(feed)
        session.flush()

        slots: list[DramaMetricSnapshot] = []
        legacy_raw_times = (
            datetime(2026, 9, 9, 20),
            datetime(2026, 9, 9, 20, 30),
            datetime(2026, 9, 9, 23, 59, 59, 999999),
            datetime(2026, 9, 10),
        )
        legacy_revisions: list[DramaMetricSnapshotRevision] = []
        for index, raw_changed_at in enumerate(legacy_raw_times, start=1):
            slot = DramaMetricSnapshot(
                drama_platform_id=feed.drama_platform_id,
                snapshot_time=datetime(2026, 9, index + 1, 4),
            )
            session.add(slot)
            session.flush()
            revision = DramaMetricSnapshotRevision(
                snapshot_id=slot.snapshot_id,
                version_no=1,
                previous_revision_id=None,
                revision_action="INITIAL",
                play_count=100 * index,
                like_count=10,
                comment_count=5,
                favorite_count=3,
                share_count=2,
                changed_by_user_id=administrator.user_id,
                changed_at=raw_changed_at,
            )
            session.add(revision)
            session.flush()
            slot.current_revision_id = revision.snapshot_revision_id
            slots.append(slot)
            legacy_revisions.append(revision)
        session.flush()

        cutover_id = legacy_revisions[-1].snapshot_revision_id
        correction = DramaMetricSnapshotRevision(
            snapshot_id=slots[0].snapshot_id,
            version_no=2,
            previous_revision_id=legacy_revisions[0].snapshot_revision_id,
            revision_action="CORRECTION",
            play_count=150,
            like_count=10,
            comment_count=5,
            favorite_count=3,
            share_count=2,
            change_reason="UTC correction",
            changed_by_user_id=administrator.user_id,
            changed_at=datetime(2026, 9, 9, 13),
        )
        voided = DramaMetricSnapshotRevision(
            snapshot_id=slots[1].snapshot_id,
            version_no=2,
            previous_revision_id=legacy_revisions[1].snapshot_revision_id,
            revision_action="VOID",
            play_count=None,
            change_reason="UTC void",
            changed_by_user_id=administrator.user_id,
            changed_at=datetime(2026, 9, 9, 13, 30),
        )
        session.add_all([correction, voided])
        session.flush()
        slots[0].current_revision_id = correction.snapshot_revision_id
        slots[1].current_revision_id = voided.snapshot_revision_id
        session.flush()

        policy = LegacyRevisionTimePolicy(
            database_name=make_url(_database_url()).database or "",
            max_revision_id=cutover_id,
            expected_revision_count=4,
            expected_min_changed_at=legacy_raw_times[0],
            expected_max_changed_at=legacy_raw_times[-1],
        )
        repository = DataQualityEvidenceRepository(
            session,
            legacy_time_policy=policy,
        )
        bundle = repository.load_bundle(
            score_date=date(2026, 9, 9),
            analysis_as_of=datetime(2026, 9, 9, 15, 59, 59, 999999),
        )

        by_snapshot = {slot.snapshot_id: slot for slot in bundle.window_slots}
        corrected = by_snapshot[slots[0].snapshot_id]
        assert corrected.selected_revision.snapshot_revision_id == (
            correction.snapshot_revision_id
        )
        assert [item.time_semantics for item in corrected.visible_revisions] == [
            LEGACY_SHANGHAI_WALL_CLOCK,
            UTC_NAIVE,
        ]
        void_slot = by_snapshot[slots[1].snapshot_id]
        assert void_slot.selected_revision.snapshot_revision_id == (
            voided.snapshot_revision_id
        )
        assert void_slot.selected_revision.revision_action == "VOID"
        assert by_snapshot[slots[2].snapshot_id].selected_revision is not None
        assert by_snapshot[slots[3].snapshot_id].selected_revision is None
        assert bundle.source_watermark["revision_time_semantics"] == (
            "MIXED_LEGACY_SHANGHAI_AND_UTC"
        )

        mismatched = DataQualityEvidenceRepository(
            session,
            legacy_time_policy=LegacyRevisionTimePolicy(
                database_name="wrong_database",
                max_revision_id=cutover_id,
                expected_revision_count=4,
                expected_min_changed_at=legacy_raw_times[0],
                expected_max_changed_at=legacy_raw_times[-1],
            ),
        )
        with pytest.raises(LegacyRevisionClassificationError):
            mismatched.load_bundle(
                score_date=date(2026, 9, 9),
                analysis_as_of=datetime(2026, 9, 9, 15, 59, 59, 999999),
            )
        session.rollback()

    engine.dispose()
