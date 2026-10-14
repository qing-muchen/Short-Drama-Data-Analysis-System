"""Read-only evidence projections for production data-quality rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from types import MappingProxyType
from typing import Mapping
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from models.drama import Drama
from models.master_data import Platform
from models.relations import DramaPlatform
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision

BUSINESS_TIME_ZONE = ZoneInfo("Asia/Shanghai")
LIMITED_CURRENT_MASTER = "LIMITED_CURRENT_MASTER"
LEGACY_SHANGHAI_WALL_CLOCK = "LEGACY_SHANGHAI_WALL_CLOCK"
UTC_NAIVE = "UTC_NAIVE"


class LegacyRevisionClassificationError(RuntimeError):
    """Reject an unsafe or mismatched legacy timestamp policy."""


@dataclass(frozen=True, slots=True)
class LegacyRevisionTimePolicy:
    """One explicitly audited database-specific legacy revision boundary."""

    database_name: str
    max_revision_id: int
    expected_revision_count: int
    expected_min_changed_at: datetime
    expected_max_changed_at: datetime

    def __post_init__(self) -> None:
        if not self.database_name.strip():
            raise ValueError("legacy revision database name is required")
        if self.max_revision_id < 1 or self.expected_revision_count < 1:
            raise ValueError("legacy revision boundary and count must be positive")
        if (
            self.expected_min_changed_at.tzinfo is not None
            or self.expected_max_changed_at.tzinfo is not None
        ):
            raise ValueError("legacy revision fingerprint timestamps must be naive")
        if self.expected_min_changed_at > self.expected_max_changed_at:
            raise ValueError("legacy revision fingerprint range is invalid")


@dataclass(frozen=True, slots=True)
class EligibleFeedEvidence:
    drama_platform_id: int
    drama_id: int
    platform_id: int


@dataclass(frozen=True, slots=True)
class SnapshotRevisionEvidence:
    snapshot_revision_id: int
    snapshot_id: int
    version_no: int
    previous_revision_id: int | None
    revision_action: str
    play_count: int | None
    like_count: int | None
    comment_count: int | None
    favorite_count: int | None
    share_count: int | None
    changed_at: datetime
    raw_changed_at: datetime | None = None
    time_semantics: str = UTC_NAIVE


@dataclass(frozen=True, slots=True)
class SnapshotSlotEvidence:
    snapshot_id: int
    drama_platform_id: int
    snapshot_time: datetime
    visible_revisions: tuple[SnapshotRevisionEvidence, ...]
    selected_revision: SnapshotRevisionEvidence | None


@dataclass(frozen=True, slots=True)
class QualityEvidenceBundle:
    score_date: date
    analysis_as_of: datetime
    window_start: datetime
    window_end: datetime
    eligible_feeds: tuple[EligibleFeedEvidence, ...]
    window_slots: tuple[SnapshotSlotEvidence, ...]
    latest_valid_slot_by_feed: Mapping[int, SnapshotSlotEvidence]
    source_watermark: Mapping[str, object]
    limitations: tuple[str, ...] = (LIMITED_CURRENT_MASTER,)


class DataQualityEvidenceRepository:
    """Load deterministic evidence without applying rule judgments or committing."""

    def __init__(
        self,
        session: Session,
        *,
        legacy_time_policy: LegacyRevisionTimePolicy | None = None,
    ) -> None:
        self.session = session
        self.legacy_time_policy = legacy_time_policy

    def load_bundle(
        self,
        *,
        score_date: date,
        analysis_as_of: datetime,
    ) -> QualityEvidenceBundle:
        self._validate_legacy_time_policy()
        window_start, window_end = _window_bounds(score_date)
        feeds = self._list_eligible_feeds()
        feed_ids = tuple(feed.drama_platform_id for feed in feeds)
        slots = self._list_visible_slots(
            drama_platform_ids=feed_ids,
            analysis_as_of=analysis_as_of,
        )
        window_slots = tuple(
            slot
            for slot in slots
            if window_start <= slot.snapshot_time < window_end
        )
        latest_valid = _latest_valid_slots(feeds=feeds, slots=slots)
        revisions = tuple(
            revision
            for slot in slots
            for revision in slot.visible_revisions
        )
        watermark: dict[str, object] = {
            "replay_capability": LIMITED_CURRENT_MASTER,
            "eligible_feed_count": len(feeds),
            "window_start": window_start.isoformat(timespec="microseconds"),
            "window_end": window_end.isoformat(timespec="microseconds"),
            "max_snapshot_id": max((slot.snapshot_id for slot in slots), default=None),
            "max_snapshot_revision_id": max(
                (item.snapshot_revision_id for item in revisions),
                default=None,
            ),
            "max_revision_changed_at": (
                max((item.changed_at for item in revisions), default=None)
            ),
            "revision_time_semantics": (
                "MIXED_LEGACY_SHANGHAI_AND_UTC"
                if self.legacy_time_policy is not None
                else UTC_NAIVE
            ),
        }
        if self.legacy_time_policy is not None:
            watermark["legacy_revision_max_id"] = (
                self.legacy_time_policy.max_revision_id
            )
        if isinstance(watermark["max_revision_changed_at"], datetime):
            watermark["max_revision_changed_at"] = watermark[
                "max_revision_changed_at"
            ].isoformat(timespec="microseconds")
        return QualityEvidenceBundle(
            score_date=score_date,
            analysis_as_of=analysis_as_of,
            window_start=window_start,
            window_end=window_end,
            eligible_feeds=feeds,
            window_slots=window_slots,
            latest_valid_slot_by_feed=MappingProxyType(latest_valid),
            source_watermark=MappingProxyType(watermark),
        )

    def _list_eligible_feeds(self) -> tuple[EligibleFeedEvidence, ...]:
        statement = (
            select(
                DramaPlatform.drama_platform_id,
                DramaPlatform.drama_id,
                DramaPlatform.platform_id,
            )
            .select_from(DramaPlatform)
            .join(Drama, Drama.drama_id == DramaPlatform.drama_id)
            .join(Platform, Platform.platform_id == DramaPlatform.platform_id)
            .where(
                Drama.status.in_(("SERIALIZING", "COMPLETED")),
                Platform.status == "ACTIVE",
                DramaPlatform.status == "ONLINE",
            )
            .distinct()
            .order_by(
                DramaPlatform.drama_platform_id.asc(),
                DramaPlatform.drama_id.asc(),
                DramaPlatform.platform_id.asc(),
            )
        )
        return tuple(
            EligibleFeedEvidence(*row)
            for row in self.session.execute(statement).all()
        )

    def _list_visible_slots(
        self,
        *,
        drama_platform_ids: tuple[int, ...],
        analysis_as_of: datetime,
    ) -> tuple[SnapshotSlotEvidence, ...]:
        if not drama_platform_ids:
            return ()
        revision = DramaMetricSnapshotRevision
        visibility = revision.changed_at <= analysis_as_of
        if self.legacy_time_policy is not None:
            legacy_raw_cutoff = _utc_naive_to_local_wall_clock(
                analysis_as_of,
                BUSINESS_TIME_ZONE,
            )
            visibility = or_(
                and_(
                    revision.snapshot_revision_id
                    <= self.legacy_time_policy.max_revision_id,
                    revision.changed_at <= legacy_raw_cutoff,
                ),
                and_(
                    revision.snapshot_revision_id
                    > self.legacy_time_policy.max_revision_id,
                    revision.changed_at <= analysis_as_of,
                ),
            )
        statement = (
            select(
                DramaMetricSnapshot.snapshot_id,
                DramaMetricSnapshot.drama_platform_id,
                DramaMetricSnapshot.snapshot_time,
                revision.snapshot_revision_id,
                revision.version_no,
                revision.previous_revision_id,
                revision.revision_action,
                revision.play_count,
                revision.like_count,
                revision.comment_count,
                revision.favorite_count,
                revision.share_count,
                revision.changed_at,
            )
            .select_from(DramaMetricSnapshot)
            .outerjoin(
                revision,
                and_(
                    revision.snapshot_id == DramaMetricSnapshot.snapshot_id,
                    visibility,
                ),
            )
            .where(
                DramaMetricSnapshot.drama_platform_id.in_(drama_platform_ids),
                DramaMetricSnapshot.snapshot_time <= analysis_as_of,
            )
            .order_by(
                DramaMetricSnapshot.drama_platform_id.asc(),
                DramaMetricSnapshot.snapshot_time.asc(),
                DramaMetricSnapshot.snapshot_id.asc(),
                revision.changed_at.asc(),
                revision.snapshot_revision_id.asc(),
            )
        )
        grouped: dict[int, dict[str, object]] = {}
        for row in self.session.execute(statement).all():
            snapshot_id = int(row.snapshot_id)
            group = grouped.setdefault(
                snapshot_id,
                {
                    "drama_platform_id": int(row.drama_platform_id),
                    "snapshot_time": row.snapshot_time,
                    "revisions": [],
                },
            )
            if row.snapshot_revision_id is not None:
                revision_id = int(row.snapshot_revision_id)
                normalized_changed_at, time_semantics = (
                    _normalize_revision_changed_at(
                        revision_id=revision_id,
                        changed_at=row.changed_at,
                        policy=self.legacy_time_policy,
                    )
                )
                if normalized_changed_at > analysis_as_of:
                    continue
                group["revisions"].append(
                    SnapshotRevisionEvidence(
                        snapshot_revision_id=revision_id,
                        snapshot_id=snapshot_id,
                        version_no=int(row.version_no),
                        previous_revision_id=(
                            int(row.previous_revision_id)
                            if row.previous_revision_id is not None
                            else None
                        ),
                        revision_action=str(row.revision_action),
                        play_count=row.play_count,
                        like_count=row.like_count,
                        comment_count=row.comment_count,
                        favorite_count=row.favorite_count,
                        share_count=row.share_count,
                        changed_at=normalized_changed_at,
                        raw_changed_at=row.changed_at,
                        time_semantics=time_semantics,
                    )
                )
        slots: list[SnapshotSlotEvidence] = []
        for snapshot_id, group in grouped.items():
            revisions = tuple(
                sorted(
                    group["revisions"],
                    key=lambda item: (
                        item.changed_at,
                        item.snapshot_revision_id,
                    ),
                )
            )
            selected = max(
                revisions,
                key=lambda item: (item.changed_at, item.snapshot_revision_id),
                default=None,
            )
            slots.append(
                SnapshotSlotEvidence(
                    snapshot_id=snapshot_id,
                    drama_platform_id=int(group["drama_platform_id"]),
                    snapshot_time=group["snapshot_time"],
                    visible_revisions=revisions,
                    selected_revision=selected,
                )
            )
        return tuple(
            sorted(
                slots,
                key=lambda item: (
                    item.drama_platform_id,
                    item.snapshot_time,
                    item.snapshot_id,
                ),
            )
        )

    def _validate_legacy_time_policy(self) -> None:
        policy = self.legacy_time_policy
        if policy is None:
            return
        database_name = self.session.scalar(select(func.database()))
        if database_name != policy.database_name:
            raise LegacyRevisionClassificationError(
                "legacy revision policy database does not match the active schema"
            )
        revision = DramaMetricSnapshotRevision
        fingerprint = self.session.execute(
            select(
                func.count(revision.snapshot_revision_id),
                func.min(revision.changed_at),
                func.max(revision.changed_at),
                func.max(revision.snapshot_revision_id),
            ).where(revision.snapshot_revision_id <= policy.max_revision_id)
        ).one()
        actual = (
            int(fingerprint[0]),
            fingerprint[1],
            fingerprint[2],
            int(fingerprint[3]) if fingerprint[3] is not None else None,
        )
        expected = (
            policy.expected_revision_count,
            policy.expected_min_changed_at,
            policy.expected_max_changed_at,
            policy.max_revision_id,
        )
        if actual != expected:
            raise LegacyRevisionClassificationError(
                "legacy revision policy fingerprint does not match this database"
            )


def _normalize_revision_changed_at(
    *,
    revision_id: int,
    changed_at: datetime,
    policy: LegacyRevisionTimePolicy | None,
) -> tuple[datetime, str]:
    if changed_at.tzinfo is not None:
        raise LegacyRevisionClassificationError(
            "revision changed_at must be stored as a naive DATETIME"
        )
    if policy is None or revision_id > policy.max_revision_id:
        return changed_at, UTC_NAIVE
    normalized = (
        changed_at.replace(tzinfo=BUSINESS_TIME_ZONE)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    return normalized, LEGACY_SHANGHAI_WALL_CLOCK


def _utc_naive_to_local_wall_clock(
    value: datetime,
    time_zone: ZoneInfo,
) -> datetime:
    if value.tzinfo is not None:
        raise LegacyRevisionClassificationError(
            "analysis_as_of must be normalized to UTC-naive before repository access"
        )
    return value.replace(tzinfo=UTC).astimezone(time_zone).replace(tzinfo=None)


def _window_bounds(score_date: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(
        score_date - timedelta(days=7),
        time.min,
        tzinfo=BUSINESS_TIME_ZONE,
    )
    end_local = datetime.combine(
        score_date,
        time.min,
        tzinfo=BUSINESS_TIME_ZONE,
    )
    return (
        start_local.astimezone(UTC).replace(tzinfo=None),
        end_local.astimezone(UTC).replace(tzinfo=None),
    )


def _latest_valid_slots(
    *,
    feeds: tuple[EligibleFeedEvidence, ...],
    slots: tuple[SnapshotSlotEvidence, ...],
) -> dict[int, SnapshotSlotEvidence]:
    eligible_ids = {feed.drama_platform_id for feed in feeds}
    latest: dict[int, SnapshotSlotEvidence] = {}
    for slot in slots:
        selected = slot.selected_revision
        if (
            slot.drama_platform_id not in eligible_ids
            or selected is None
            or selected.revision_action == "VOID"
        ):
            continue
        current = latest.get(slot.drama_platform_id)
        if current is None or (slot.snapshot_time, slot.snapshot_id) > (
            current.snapshot_time,
            current.snapshot_id,
        ):
            latest[slot.drama_platform_id] = slot
    return latest


__all__ = (
    "BUSINESS_TIME_ZONE",
    "LEGACY_SHANGHAI_WALL_CLOCK",
    "LIMITED_CURRENT_MASTER",
    "UTC_NAIVE",
    "DataQualityEvidenceRepository",
    "EligibleFeedEvidence",
    "LegacyRevisionClassificationError",
    "LegacyRevisionTimePolicy",
    "QualityEvidenceBundle",
    "SnapshotRevisionEvidence",
    "SnapshotSlotEvidence",
)
