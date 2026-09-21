"""User ORM mapping."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.import_batch import ImportBatch
    from models.import_job import ImportJob
    from models.operation_log import OperationLog
    from models.operation_action import OperationAction, OperationActionHistory
    from models.quality import DataQualityIssue
    from models.snapshot import DramaMetricSnapshotRevision


class User(CreatedUpdatedAtMixin, Base):
    """Administrator or read-only analysis user."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(username)) > 0",
            name="chk_users_username_nonempty",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(password_hash)) > 0",
            name="chk_users_password_hash_nonempty",
        ),
        CheckConstraint(
            "role_code IN ('ADMINISTRATOR', 'USER')",
            name="chk_users_role",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="chk_users_status",
        ),
        Index("idx_users_status", "status"),
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role_code: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'USER'")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True
    )

    initiated_import_jobs: Mapped[list["ImportJob"]] = relationship(
        back_populates="initiated_by"
    )
    created_import_batches: Mapped[list["ImportBatch"]] = relationship(
        back_populates="created_by"
    )
    changed_snapshot_revisions: Mapped[list["DramaMetricSnapshotRevision"]] = (
        relationship(back_populates="changed_by")
    )
    handled_quality_issues: Mapped[list["DataQualityIssue"]] = relationship(
        back_populates="handled_by"
    )
    performed_operations: Mapped[list["OperationLog"]] = relationship(
        back_populates="actor_user",
        foreign_keys="OperationLog.actor_user_id",
    )
    targeted_operations: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_user",
        foreign_keys="OperationLog.target_user_id",
    )
    assigned_actions: Mapped[list["OperationAction"]] = relationship(
        back_populates="assignee",
        foreign_keys="OperationAction.assignee_user_id",
    )
    created_actions: Mapped[list["OperationAction"]] = relationship(
        back_populates="created_by",
        foreign_keys="OperationAction.created_by_user_id",
    )
    action_history: Mapped[list["OperationActionHistory"]] = relationship(
        back_populates="operator",
        foreign_keys="OperationActionHistory.operator_user_id",
    )
