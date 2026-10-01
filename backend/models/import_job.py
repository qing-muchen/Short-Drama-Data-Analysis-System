"""Import governance ORM mappings."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME, SMALLINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.import_batch import ImportBatch
    from models.operation_log import OperationLog
    from models.snapshot import DramaMetricSnapshot
    from models.user import User


class ImportJob(CreatedUpdatedAtMixin, Base):
    """One two-stage CSV or XLSX import task."""

    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint(
            "import_type IN ('MASTER_DATA', 'SNAPSHOT')",
            name="chk_import_jobs_type",
        ),
        CheckConstraint(
            "status IN ('PENDING_VALIDATION', 'VALIDATION_FAILED', 'READY', "
            "'IMPORTING', 'COMPLETED', 'COMPLETED_WITH_ERRORS', 'FAILED')",
            name="chk_import_jobs_status",
        ),
        CheckConstraint(
            "file_format IN ('CSV', 'XLSX')", name="chk_import_jobs_format"
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(original_filename)) > 0",
            name="chk_import_jobs_filename",
        ),
        CheckConstraint(
            "valid_rows + error_rows <= total_rows AND imported_rows <= valid_rows",
            name="chk_import_jobs_row_totals",
        ),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NOT NULL",
            name="chk_import_jobs_times",
        ),
        Index("idx_import_jobs_status_created", "status", "created_at"),
        Index(
            "idx_import_jobs_user_created", "initiated_by_user_id", "created_at"
        ),
        Index("idx_import_jobs_file_hash", "file_hash"),
        Index("idx_import_jobs_batch_status", "import_batch_id", "status"),
        UniqueConstraint(
            "import_batch_id", "batch_sequence", name="uq_import_jobs_batch_sequence"
        ),
        UniqueConstraint(
            "import_batch_id", "batch_file_type", name="uq_import_jobs_batch_file_type"
        ),
        CheckConstraint(
            "(import_batch_id IS NULL AND batch_sequence IS NULL AND batch_file_type IS NULL) "
            "OR (import_batch_id IS NOT NULL AND batch_sequence IS NOT NULL "
            "AND batch_sequence > 0 AND batch_file_type IN "
            "('MASTER_DATA', 'DRAMA_TAGS', 'DRAMA_PLATFORMS', 'SNAPSHOT'))",
            name="chk_import_jobs_batch_fields",
        ),
    )

    import_job_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    import_batch_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "import_batches.import_batch_id",
            name="fk_import_jobs_batch",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
    )
    batch_sequence: Mapped[int | None] = mapped_column(
        SMALLINT(unsigned=True), nullable=True
    )
    batch_file_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    initiated_by_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "users.user_id",
            name="fk_import_jobs_user",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    import_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'PENDING_VALIDATION'"),
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(16), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    total_rows: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    valid_rows: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    error_rows: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    imported_rows: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)

    initiated_by: Mapped["User"] = relationship(back_populates="initiated_import_jobs")
    import_batch: Mapped["ImportBatch | None"] = relationship(back_populates="files")
    errors: Mapped[list["ImportError"]] = relationship(back_populates="import_job")
    snapshot_slots: Mapped[list["DramaMetricSnapshot"]] = relationship(
        back_populates="source_import_job"
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_import_job",
        foreign_keys="OperationLog.target_import_job_id",
    )


class ImportError(Base):
    """Row- or field-level validation error owned by one import job."""

    __tablename__ = "import_errors"
    __table_args__ = (
        CheckConstraint(
            "source_row_number IS NULL OR source_row_number > 0",
            name="chk_import_errors_row",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(error_code)) > 0",
            name="chk_import_errors_code",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(error_message)) > 0",
            name="chk_import_errors_message",
        ),
        Index("idx_import_errors_job_row", "import_job_id", "source_row_number"),
        Index("idx_import_errors_job_code", "import_job_id", "error_code"),
    )

    import_error_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    import_job_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "import_jobs.import_job_id",
            name="fk_import_errors_job",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    source_row_number: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), nullable=True
    )
    column_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str] = mapped_column(String(1000), nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )

    import_job: Mapped["ImportJob"] = relationship(back_populates="errors")
