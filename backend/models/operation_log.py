"""Append-only business operation audit-log ORM mapping."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.drama import Drama
    from models.import_job import ImportJob
    from models.master_data import Actor, Company, Director, Platform, Tag
    from models.quality import DataQualityIssue
    from models.relations import (
        DramaActor,
        DramaCompany,
        DramaDirector,
        DramaPlatform,
        DramaTag,
    )
    from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision
    from models.user import User


class OperationLog(Base):
    """Immutable audit event with one operator and exactly one fixed target."""

    __tablename__ = "operation_logs"
    __table_args__ = (
        CheckConstraint(
            "result_status IN ('SUCCESS', 'FAILURE')",
            name="chk_operation_logs_result",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(operation_type)) > 0",
            name="chk_operation_logs_type",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(summary)) > 0",
            name="chk_operation_logs_summary",
        ),
        CheckConstraint(
            "(target_user_id IS NOT NULL) + (target_drama_id IS NOT NULL) + "
            "(target_actor_id IS NOT NULL) + (target_director_id IS NOT NULL) + "
            "(target_company_id IS NOT NULL) + (target_platform_id IS NOT NULL) + "
            "(target_tag_id IS NOT NULL) + (target_drama_actor_id IS NOT NULL) + "
            "(target_drama_director_id IS NOT NULL) + "
            "(target_drama_company_id IS NOT NULL) + "
            "(target_drama_tag_id IS NOT NULL) + "
            "(target_drama_platform_id IS NOT NULL) + "
            "(target_snapshot_id IS NOT NULL) + "
            "(target_snapshot_revision_id IS NOT NULL) + "
            "(target_import_job_id IS NOT NULL) + "
            "(target_data_quality_issue_id IS NOT NULL) = 1",
            name="chk_operation_logs_one_target",
        ),
        Index("idx_operation_actor_time", "actor_user_id", "occurred_at"),
        Index("idx_operation_type_time", "operation_type", "occurred_at"),
        Index("idx_operation_request", "request_id"),
        Index("idx_operation_target_user_time", "target_user_id", "occurred_at"),
        Index(
            "idx_operation_target_drama_time", "target_drama_id", "occurred_at"
        ),
        Index(
            "idx_operation_target_actor_time", "target_actor_id", "occurred_at"
        ),
        Index(
            "idx_operation_target_director_time",
            "target_director_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_company_time",
            "target_company_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_platform_time",
            "target_platform_id",
            "occurred_at",
        ),
        Index("idx_operation_target_tag_time", "target_tag_id", "occurred_at"),
        Index(
            "idx_operation_target_drama_actor_time",
            "target_drama_actor_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_drama_director_time",
            "target_drama_director_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_drama_company_time",
            "target_drama_company_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_drama_tag_time",
            "target_drama_tag_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_drama_platform_time",
            "target_drama_platform_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_snapshot_time",
            "target_snapshot_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_revision_time",
            "target_snapshot_revision_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_import_time",
            "target_import_job_id",
            "occurred_at",
        ),
        Index(
            "idx_operation_target_quality_time",
            "target_data_quality_issue_id",
            "occurred_at",
        ),
    )

    operation_log_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    actor_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_operation_logs_actor_user", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    target_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_operation_logs_target_user", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=True,
    )
    target_drama_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("dramas.drama_id", name="fk_operation_logs_target_drama", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=True,
    )
    target_actor_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("actors.actor_id", name="fk_operation_logs_target_actor", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=True,
    )
    target_director_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "directors.director_id", name="fk_operation_logs_target_director", ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        nullable=True,
    )
    target_company_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "companies.company_id", name="fk_operation_logs_target_company", ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        nullable=True,
    )
    target_platform_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "platforms.platform_id", name="fk_operation_logs_target_platform", ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        nullable=True,
    )
    target_tag_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("tags.tag_id", name="fk_operation_logs_target_tag", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=True,
    )
    target_drama_actor_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_actors.drama_actor_id",
            name="fk_operation_logs_target_drama_actor",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    target_drama_director_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_directors.drama_director_id",
            name="fk_operation_logs_target_drama_director",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    target_drama_company_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_companies.drama_company_id",
            name="fk_operation_logs_target_drama_company",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    target_drama_tag_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_tags.drama_tag_id", name="fk_operation_logs_target_drama_tag", ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        nullable=True,
    )
    target_drama_platform_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_platforms.drama_platform_id",
            name="fk_operation_logs_target_drama_platform",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    target_snapshot_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_metric_snapshots.snapshot_id",
            name="fk_operation_logs_target_snapshot",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    target_snapshot_revision_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "drama_metric_snapshot_revisions.snapshot_revision_id",
            name="fk_operation_logs_target_revision",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    target_import_job_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "import_jobs.import_job_id", name="fk_operation_logs_target_import_job", ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        nullable=True,
    )
    target_data_quality_issue_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "data_quality_issues.data_quality_issue_id",
            name="fk_operation_logs_target_quality_issue",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    result_status: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )

    actor_user: Mapped["User"] = relationship(
        back_populates="performed_operations", foreign_keys=[actor_user_id]
    )
    target_user: Mapped["User | None"] = relationship(
        back_populates="targeted_operations", foreign_keys=[target_user_id]
    )
    target_drama: Mapped["Drama | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_drama_id]
    )
    target_actor: Mapped["Actor | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_actor_id]
    )
    target_director: Mapped["Director | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_director_id]
    )
    target_company: Mapped["Company | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_company_id]
    )
    target_platform: Mapped["Platform | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_platform_id]
    )
    target_tag: Mapped["Tag | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_tag_id]
    )
    target_drama_actor: Mapped["DramaActor | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_drama_actor_id]
    )
    target_drama_director: Mapped["DramaDirector | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_drama_director_id]
    )
    target_drama_company: Mapped["DramaCompany | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_drama_company_id]
    )
    target_drama_tag: Mapped["DramaTag | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_drama_tag_id]
    )
    target_drama_platform: Mapped["DramaPlatform | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_drama_platform_id]
    )
    target_snapshot: Mapped["DramaMetricSnapshot | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_snapshot_id]
    )
    target_snapshot_revision: Mapped["DramaMetricSnapshotRevision | None"] = (
        relationship(
            back_populates="operation_logs",
            foreign_keys=[target_snapshot_revision_id],
        )
    )
    target_import_job: Mapped["ImportJob | None"] = relationship(
        back_populates="operation_logs", foreign_keys=[target_import_job_id]
    )
    target_data_quality_issue: Mapped["DataQualityIssue | None"] = relationship(
        back_populates="operation_logs",
        foreign_keys=[target_data_quality_issue_id],
    )
