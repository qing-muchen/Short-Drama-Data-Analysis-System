"""Opt-in MySQL integration test; refuses every non-isolated database name."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import os

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from analytics.data_quality import QUALITY_SCORE_VERSION, QUALITY_SCORE_V2_VERSION
from analytics.data_quality_rules import production_evaluator_registry
from models.data_quality import DataQualityRuleResult, DataQualityScore
from models.drama import Drama
from models.master_data import Platform
from models.relations import DramaPlatform
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision
from models.user import User
from repositories.data_quality_evidence_repository import DataQualityEvidenceRepository
from repositories.data_quality_repository import (
    DataQualityRuleRepository,
    DataQualityRuleResultRepository,
    DataQualityScoreRepository,
)
from repositories.import_repository import OperationLogRepository
from services.data_quality_rule_seed import seed_data_quality_rules
from services.data_quality_service import DataQualityService
from services.exceptions import PersistenceException

DATABASE_URL = os.getenv("DQ_ISOLATED_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DQ_ISOLATED_DATABASE_URL is required for opt-in MySQL integration",
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


class _FailingOperationLogRepository(OperationLogRepository):
    def create(self, values):  # type: ignore[no-untyped-def]
        raise SQLAlchemyError("forced audit failure")


def test_full_data_quality_workflow_on_isolated_mysql() -> None:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory() as session:
        administrator_id = _insert_evidence(session)
        first_seed = seed_data_quality_rules(
            session,
            valid_from=datetime(2026, 10, 1),
            apply=True,
            actor_user_id=administrator_id,
        )
        second_seed = seed_data_quality_rules(
            session,
            valid_from=datetime(2026, 10, 1),
            apply=True,
            actor_user_id=administrator_id,
        )
        assert (first_seed.inserted_count, second_seed.inserted_count) == (4, 0)
        assert second_seed.unchanged_count == 4

        evidence_repository = DataQualityEvidenceRepository(session)
        evidence = evidence_repository.load_bundle(
            score_date=date(2026, 10, 10),
            analysis_as_of=datetime(2026, 10, 10, 15, 59, 59, 999999),
        )
        assert len(evidence.eligible_feeds) == 1
        assert len(evidence.window_slots) == 7
        latest = evidence.latest_valid_slot_by_feed[
            evidence.eligible_feeds[0].drama_platform_id
        ]
        assert latest.snapshot_time == datetime(2026, 10, 9, 4)
        assert evidence.source_watermark["replay_capability"] == "LIMITED_CURRENT_MASTER"

        service = _service(session)
        v2 = service.calculate_quality_score(
            date(2026, 10, 10),
            administrator_id=administrator_id,
            now=datetime(2026, 10, 10, 15, 59, 59, 999999, tzinfo=UTC),
            algorithm_version=QUALITY_SCORE_V2_VERSION,
        )
        v1 = service.calculate_quality_score(
            date(2026, 10, 10),
            administrator_id=administrator_id,
            now=datetime(2026, 10, 10, 15, 59, 59, 999999, tzinfo=UTC),
            algorithm_version=QUALITY_SCORE_VERSION,
        )
        repeated_v2 = service.calculate_quality_score(
            date(2026, 10, 10),
            administrator_id=administrator_id,
            now=datetime(2026, 10, 10, 15, 59, 59, 999999, tzinfo=UTC),
            algorithm_version=QUALITY_SCORE_V2_VERSION,
        )

        assert v2.total_score == 97
        assert v1.total_score == 100
        assert repeated_v2.quality_score_id == v2.quality_score_id
        assert service.get_current_quality_score(
            algorithm_version=QUALITY_SCORE_V2_VERSION
        ).quality_score_id == v2.quality_score_id
        assert service.get_current_quality_score(
            algorithm_version=QUALITY_SCORE_VERSION
        ).quality_score_id == v1.quality_score_id
        assert len(
            service.get_quality_history(
                algorithm_version=QUALITY_SCORE_V2_VERSION
            )
        ) == 1
        assert session.scalar(select(func.count()).select_from(DataQualityScore)) == 2
        assert session.scalar(
            select(func.count()).select_from(DataQualityRuleResult)
        ) == 8

        failing = _service(
            session,
            operation_logs=_FailingOperationLogRepository(session),
        )
        with pytest.raises(PersistenceException):
            failing.calculate_quality_score(
                date(2026, 10, 11),
                administrator_id=administrator_id,
                now=datetime(2026, 10, 11, 15, 59, 59, tzinfo=UTC),
                algorithm_version=QUALITY_SCORE_V2_VERSION,
            )
        assert session.scalar(select(func.count()).select_from(DataQualityScore)) == 2


def _service(
    session: Session,
    *,
    operation_logs: OperationLogRepository | None = None,
) -> DataQualityService:
    return DataQualityService(
        session,
        DataQualityRuleRepository(session),
        DataQualityRuleResultRepository(session),
        DataQualityScoreRepository(session),
        operation_logs or OperationLogRepository(session),
        production_evaluator_registry(),
        evidence=DataQualityEvidenceRepository(session),
    )


def _insert_evidence(session: Session) -> int:
    administrator = User(
        username="dq-integration-admin",
        password_hash="not-a-real-credential",
        display_name="DQ integration",
        role_code="ADMINISTRATOR",
        status="ACTIVE",
    )
    drama = Drama(
        drama_code="DQ-INTEGRATION-1",
        drama_name="DQ integration drama",
        status="SERIALIZING",
    )
    platform = Platform(platform_name="DQ integration platform", status="ACTIVE")
    session.add_all([administrator, drama, platform])
    session.flush()
    feed = DramaPlatform(
        drama_id=drama.drama_id,
        platform_id=platform.platform_id,
        platform_drama_code="DQ-1",
        online_at=datetime(2026, 10, 1),
        status="ONLINE",
    )
    session.add(feed)

    excluded_drama = Drama(
        drama_code="DQ-INTEGRATION-EXCLUDED",
        drama_name="Excluded draft",
        status="DRAFT",
    )
    excluded_platform = Platform(
        platform_name="DQ integration inactive platform",
        status="INACTIVE",
    )
    session.add_all([excluded_drama, excluded_platform])
    session.flush()
    session.add(
        DramaPlatform(
            drama_id=excluded_drama.drama_id,
            platform_id=excluded_platform.platform_id,
            platform_drama_code="DQ-X",
            online_at=datetime(2026, 10, 1),
            status="ONLINE",
        )
    )
    session.flush()

    for offset in range(7):
        snapshot_time = datetime(2026, 10, 3 + offset, 4)
        slot = DramaMetricSnapshot(
            drama_platform_id=feed.drama_platform_id,
            snapshot_time=snapshot_time,
        )
        session.add(slot)
        session.flush()
        revision = DramaMetricSnapshotRevision(
            snapshot_id=slot.snapshot_id,
            version_no=1,
            previous_revision_id=None,
            revision_action="INITIAL",
            play_count=100 + offset,
            like_count=10,
            comment_count=5,
            favorite_count=3,
            share_count=2,
            changed_by_user_id=administrator.user_id,
            changed_at=snapshot_time + timedelta(hours=1),
        )
        session.add(revision)
        session.flush()
        slot.current_revision_id = revision.snapshot_revision_id
        if offset == 0:
            future_correction = DramaMetricSnapshotRevision(
                snapshot_id=slot.snapshot_id,
                version_no=2,
                previous_revision_id=revision.snapshot_revision_id,
                revision_action="CORRECTION",
                play_count=999,
                like_count=10,
                comment_count=5,
                favorite_count=3,
                share_count=2,
                change_reason="Visible after test as-of",
                changed_by_user_id=administrator.user_id,
                changed_at=datetime(2026, 10, 12),
            )
            session.add(future_correction)
            session.flush()
            slot.current_revision_id = future_correction.snapshot_revision_id

    void_slot = DramaMetricSnapshot(
        drama_platform_id=feed.drama_platform_id,
        snapshot_time=datetime(2026, 10, 10, 4),
    )
    session.add(void_slot)
    session.flush()
    initial = DramaMetricSnapshotRevision(
        snapshot_id=void_slot.snapshot_id,
        version_no=1,
        previous_revision_id=None,
        revision_action="INITIAL",
        play_count=200,
        changed_by_user_id=administrator.user_id,
        changed_at=datetime(2026, 10, 10, 5),
    )
    session.add(initial)
    session.flush()
    voided = DramaMetricSnapshotRevision(
        snapshot_id=void_slot.snapshot_id,
        version_no=2,
        previous_revision_id=initial.snapshot_revision_id,
        revision_action="VOID",
        play_count=None,
        change_reason="Integration VOID",
        changed_by_user_id=administrator.user_id,
        changed_at=datetime(2026, 10, 10, 6),
    )
    session.add(voided)
    session.flush()
    void_slot.current_revision_id = voided.snapshot_revision_id
    session.commit()
    return administrator.user_id
