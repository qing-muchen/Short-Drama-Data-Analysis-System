"""Batch-import orchestration ORM mapping."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.import_job import ImportJob
    from models.user import User


class ImportBatch(CreatedUpdatedAtMixin, Base):
    """One administrator-confirmed, dependency-ordered collection of files."""

    __tablename__ = "import_batches"
    __table_args__ = (
        UniqueConstraint("batch_code", name="uq_import_batches_code"),
        CheckConstraint("CHAR_LENGTH(TRIM(batch_code)) > 0", name="chk_import_batches_code"),
        CheckConstraint(
            "status IN ('CREATED', 'UPLOADING', 'VALIDATING', 'READY', "
            "'IMPORTING', 'COMPLETED', 'VALIDATION_FAILED', 'IMPORT_FAILED')",
            name="chk_import_batches_status",
        ),
        CheckConstraint(
            "valid_rows + error_rows <= total_rows AND imported_rows <= valid_rows",
            name="chk_import_batches_row_totals",
        ),
        CheckConstraint(
            "validated_at IS NULL OR validation_started_at IS NOT NULL",
            name="chk_import_batches_validation_times",
        ),
        CheckConstraint(
            "completed_at IS NULL OR status IN "
            "('COMPLETED', 'VALIDATION_FAILED', 'IMPORT_FAILED')",
            name="chk_import_batches_completion_time",
        ),
        Index("idx_import_batches_status_created", "status", "created_at"),
        Index("idx_import_batches_user_created", "created_by_user_id", "created_at"),
    )

    import_batch_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    batch_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'CREATED'")
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_import_batches_user", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    total_files: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    total_rows: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default=text("0"))
    valid_rows: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default=text("0"))
    error_rows: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default=text("0"))
    imported_rows: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default=text("0"))
    validation_started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    import_started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)

    created_by: Mapped["User"] = relationship(back_populates="created_import_batches")
    files: Mapped[list["ImportJob"]] = relationship(
        back_populates="import_batch", order_by="ImportJob.batch_sequence"
    )
