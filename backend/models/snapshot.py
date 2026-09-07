"""Observation-slot and immutable snapshot-revision ORM mappings."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    and_,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship, remote

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.import_job import ImportJob
    from models.operation_log import OperationLog
    from models.quality import DataQualityIssue
    from models.relations import DramaPlatform
    from models.user import User


class DramaMetricSnapshot(CreatedUpdatedAtMixin, Base):
    """Stable observation slot for a drama-platform at one snapshot time."""

    __tablename__ = "drama_metric_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "drama_platform_id",
            "snapshot_time",
            name="uq_snapshots_platform_time",
        ),
        UniqueConstraint(
            "current_revision_id", name="uq_snapshots_current_revision"
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "current_revision_id"],
            [
                "drama_metric_snapshot_revisions.snapshot_id",
                "drama_metric_snapshot_revisions.snapshot_revision_id",
            ],
            name="fk_snapshots_current_revision",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        Index("idx_snapshots_source_import", "source_import_job_id"),
    )

    snapshot_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_platform_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_platforms.drama_platform_id",
            name="fk_snapshots_drama_platform",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    snapshot_time: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    current_revision_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), nullable=True
    )
    source_import_job_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "import_jobs.import_job_id",
            name="fk_snapshots_source_import_job",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )

    drama_platform: Mapped["DramaPlatform"] = relationship(
        back_populates="snapshots"
    )
    revisions: Mapped[list["DramaMetricSnapshotRevision"]] = relationship(
        back_populates="snapshot",
        foreign_keys="DramaMetricSnapshotRevision.snapshot_id",
    )
    current_revision: Mapped["DramaMetricSnapshotRevision | None"] = relationship(
        primaryjoin=lambda: and_(
            DramaMetricSnapshot.snapshot_id
            == foreign(DramaMetricSnapshotRevision.snapshot_id),
            DramaMetricSnapshot.current_revision_id
            == foreign(DramaMetricSnapshotRevision.snapshot_revision_id),
        ),
        viewonly=True,
        uselist=False,
    )
    source_import_job: Mapped["ImportJob | None"] = relationship(
        back_populates="snapshot_slots"
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_snapshot",
        foreign_keys="OperationLog.target_snapshot_id",
    )


class DramaMetricSnapshotRevision(Base):
    """Immutable revision containing the observed operational metrics."""

    __tablename__ = "drama_metric_snapshot_revisions"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "version_no", name="uq_snapshot_revisions_version"
        ),
        UniqueConstraint(
            "snapshot_id",
            "snapshot_revision_id",
            name="uq_snapshot_revisions_identity",
        ),
        UniqueConstraint(
            "previous_revision_id", name="uq_snapshot_revisions_previous"
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "previous_revision_id"],
            [
                "drama_metric_snapshot_revisions.snapshot_id",
                "drama_metric_snapshot_revisions.snapshot_revision_id",
            ],
            name="fk_snapshot_revisions_previous_same_slot",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        CheckConstraint(
            "version_no >= 1", name="chk_snapshot_revisions_version"
        ),
        CheckConstraint(
            "revision_action IN ('INITIAL', 'CORRECTION', 'VOID')",
            name="chk_snapshot_revisions_action",
        ),
        CheckConstraint(
            "(revision_action = 'INITIAL' AND version_no = 1 AND "
            "previous_revision_id IS NULL) OR (revision_action IN "
            "('CORRECTION', 'VOID') AND version_no > 1 AND "
            "previous_revision_id IS NOT NULL)",
            name="chk_snapshot_revisions_chain",
        ),
        CheckConstraint(
            "revision_action = 'VOID' OR play_count IS NOT NULL",
            name="chk_snapshot_revisions_metrics",
        ),
        CheckConstraint(
            "revision_action = 'INITIAL' OR (change_reason IS NOT NULL AND "
            "CHAR_LENGTH(TRIM(change_reason)) > 0)",
            name="chk_snapshot_revisions_reason",
        ),
        CheckConstraint(
            "ranking IS NULL OR ranking > 0",
            name="chk_snapshot_revisions_ranking",
        ),
        Index("idx_snapshot_revisions_changed_at", "snapshot_id", "changed_at"),
        Index(
            "idx_snapshot_revisions_user_changed",
            "changed_by_user_id",
            "changed_at",
        ),
    )

    snapshot_revision_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    snapshot_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_metric_snapshots.snapshot_id",
            name="fk_snapshot_revisions_snapshot",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    previous_revision_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), nullable=True
    )
    revision_action: Mapped[str] = mapped_column(String(16), nullable=False)
    play_count: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), nullable=True)
    like_count: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), nullable=True)
    comment_count: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), nullable=True
    )
    favorite_count: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), nullable=True
    )
    share_count: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), nullable=True)
    ranking: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "users.user_id",
            name="fk_snapshot_revisions_user",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )

    snapshot: Mapped["DramaMetricSnapshot"] = relationship(
        back_populates="revisions",
        foreign_keys=[snapshot_id],
    )
    previous_revision: Mapped["DramaMetricSnapshotRevision | None"] = relationship(
        primaryjoin=lambda: and_(
            foreign(DramaMetricSnapshotRevision.snapshot_id)
            == remote(DramaMetricSnapshotRevision.snapshot_id),
            foreign(DramaMetricSnapshotRevision.previous_revision_id)
            == remote(DramaMetricSnapshotRevision.snapshot_revision_id),
        ),
        remote_side=lambda: [
            DramaMetricSnapshotRevision.snapshot_id,
            DramaMetricSnapshotRevision.snapshot_revision_id,
        ],
        viewonly=True,
        uselist=False,
    )
    changed_by: Mapped["User"] = relationship(
        back_populates="changed_snapshot_revisions"
    )
    quality_issues: Mapped[list["DataQualityIssue"]] = relationship(
        back_populates="target_snapshot_revision",
        foreign_keys="DataQualityIssue.target_snapshot_revision_id",
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_snapshot_revision",
        foreign_keys="OperationLog.target_snapshot_revision_id",
    )
