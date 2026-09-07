"""Data-quality governance ORM mapping."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.drama import Drama
    from models.operation_log import OperationLog
    from models.relations import DramaPlatform
    from models.snapshot import DramaMetricSnapshotRevision
    from models.user import User


class DataQualityIssue(CreatedUpdatedAtMixin, Base):
    """Tracked quality issue with exactly one schema-defined business target."""

    __tablename__ = "data_quality_issues"
    __table_args__ = (
        CheckConstraint(
            "(target_snapshot_revision_id IS NOT NULL) + "
            "(target_drama_platform_id IS NOT NULL) + "
            "(target_drama_id IS NOT NULL) = 1",
            name="chk_quality_issues_one_target",
        ),
        CheckConstraint(
            "issue_type IN ('MISSING_REQUIRED_DATA', 'INVALID_NEGATIVE_VALUE', "
            "'INVALID_RANKING', 'INVALID_TIMESTAMP', 'UNKNOWN_REFERENCE', "
            "'DUPLICATE_RECORD', 'CONFLICTING_SNAPSHOT', "
            "'CUMULATIVE_REGRESSION', 'STATISTICAL_SPIKE', "
            "'STATISTICAL_DROP', 'OTHER')",
            name="chk_quality_issues_type",
        ),
        CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'ERROR')",
            name="chk_quality_issues_severity",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'CONFIRMED', 'RESOLVED', 'IGNORED')",
            name="chk_quality_issues_status",
        ),
        CheckConstraint(
            "source IN ('MANUAL_ENTRY', 'IMPORT', 'STATISTICAL_DETECTION', "
            "'BUSINESS_RULE')",
            name="chk_quality_issues_source",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(rule_code)) > 0",
            name="chk_quality_issues_rule",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(evidence_summary)) > 0",
            name="chk_quality_issues_evidence",
        ),
        CheckConstraint(
            "occurrence_count >= 1",
            name="chk_quality_issues_occurrences",
        ),
        CheckConstraint(
            "last_detected_at >= first_detected_at",
            name="chk_quality_issues_detection_time",
        ),
        CheckConstraint(
            "(handled_by_user_id IS NULL AND handled_at IS NULL AND "
            "handling_note IS NULL) OR (handled_by_user_id IS NOT NULL AND "
            "handled_at IS NOT NULL AND handling_note IS NOT NULL AND "
            "CHAR_LENGTH(TRIM(handling_note)) > 0)",
            name="chk_quality_issues_handling_tuple",
        ),
        CheckConstraint(
            "status NOT IN ('RESOLVED', 'IGNORED') OR "
            "(handled_by_user_id IS NOT NULL AND handled_at IS NOT NULL AND "
            "handling_note IS NOT NULL)",
            name="chk_quality_issues_closed_handling",
        ),
        Index(
            "idx_quality_status_severity_detected",
            "status",
            "severity",
            "last_detected_at",
        ),
        Index(
            "idx_quality_revision_type_status",
            "target_snapshot_revision_id",
            "issue_type",
            "status",
        ),
        Index(
            "idx_quality_platform_type_status",
            "target_drama_platform_id",
            "issue_type",
            "status",
        ),
        Index(
            "idx_quality_drama_type_status",
            "target_drama_id",
            "issue_type",
            "status",
        ),
        Index("idx_quality_handler_time", "handled_by_user_id", "handled_at"),
    )

    data_quality_issue_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    target_snapshot_revision_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_metric_snapshot_revisions.snapshot_revision_id",
            name="fk_quality_issues_snapshot_revision",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    target_drama_platform_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_platforms.drama_platform_id",
            name="fk_quality_issues_drama_platform",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    target_drama_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "dramas.drama_id",
            name="fk_quality_issues_drama",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    issue_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'OPEN'")
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False
    )
    occurrence_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("1")
    )
    handled_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "users.user_id",
            name="fk_quality_issues_handler",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    handled_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    handling_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    target_snapshot_revision: Mapped["DramaMetricSnapshotRevision | None"] = (
        relationship(
            back_populates="quality_issues",
            foreign_keys=[target_snapshot_revision_id],
        )
    )
    target_drama_platform: Mapped["DramaPlatform | None"] = relationship(
        back_populates="quality_issues",
        foreign_keys=[target_drama_platform_id],
    )
    target_drama: Mapped["Drama | None"] = relationship(
        back_populates="quality_issues",
        foreign_keys=[target_drama_id],
    )
    handled_by: Mapped["User | None"] = relationship(
        back_populates="handled_quality_issues",
        foreign_keys=[handled_by_user_id],
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_data_quality_issue",
        foreign_keys="OperationLog.target_data_quality_issue_id",
    )
