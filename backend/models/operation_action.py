"""ORM mappings for operation actions and their audit records."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATE, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.drama import Drama
    from models.user import User


class OperationAction(CreatedUpdatedAtMixin, Base):
    """Current state of an operator-owned action."""

    __tablename__ = "operation_actions"
    __table_args__ = (
        CheckConstraint("CHAR_LENGTH(TRIM(title)) > 0", name="chk_operation_actions_title"),
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH')",
            name="chk_operation_actions_priority",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')",
            name="chk_operation_actions_status",
        ),
        Index("idx_operation_actions_status_priority_due", "status", "priority", "due_date"),
        Index("idx_operation_actions_assignee_status", "assignee_user_id", "status", "due_date"),
        Index("idx_operation_actions_drama_status", "drama_id", "status", "created_at"),
    )

    action_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    drama_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("dramas.drama_id", name="fk_operation_actions_drama", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, server_default="MEDIUM")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="OPEN")
    assignee_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_operation_actions_assignee", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=True,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_operation_actions_creator", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    due_date: Mapped[date | None] = mapped_column(DATE, nullable=True)

    drama: Mapped["Drama | None"] = relationship(back_populates="operation_actions")
    assignee: Mapped["User | None"] = relationship(
        back_populates="assigned_actions", foreign_keys=[assignee_user_id]
    )
    created_by: Mapped["User"] = relationship(
        back_populates="created_actions", foreign_keys=[created_by_user_id]
    )
    sources: Mapped[list["OperationActionSource"]] = relationship(
        back_populates="action", cascade="all, delete-orphan"
    )
    history: Mapped[list["OperationActionHistory"]] = relationship(
        back_populates="action", cascade="all, delete-orphan"
    )


class OperationActionSource(Base):
    """Logical source and immutable evidence snapshot for an action."""

    __tablename__ = "operation_action_sources"
    __table_args__ = (
        UniqueConstraint(
            "action_id", "source_type", "source_reference_id",
            name="uq_operation_action_sources_identity",
        ),
        CheckConstraint(
            "source_type IN ('ANOMALY', 'QUALITY', 'SCORE', 'MANUAL')",
            name="chk_operation_action_sources_type",
        ),
        CheckConstraint(
            "(source_type = 'MANUAL' AND source_reference_id IS NULL) OR "
            "(source_type <> 'MANUAL' AND source_reference_id IS NOT NULL AND source_reference_id > 0)",
            name="chk_operation_action_sources_reference",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(source_evidence_summary)) > 0",
            name="chk_operation_action_sources_summary",
        ),
        CheckConstraint(
            "source_algorithm_version IS NULL OR CHAR_LENGTH(TRIM(source_algorithm_version)) > 0",
            name="chk_operation_action_sources_algorithm",
        ),
        Index("idx_operation_action_sources_reference", "source_type", "source_reference_id", "action_id"),
        Index("idx_operation_action_sources_action", "action_id", "created_at"),
    )

    source_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    action_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("operation_actions.action_id", name="fk_operation_action_sources_action", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_reference_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), nullable=True)
    source_evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_analysis_as_of: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    source_algorithm_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default="CURRENT_TIMESTAMP(6)"
    )

    action: Mapped["OperationAction"] = relationship(back_populates="sources")


class OperationActionHistory(Base):
    """Immutable action lifecycle and processing events."""

    __tablename__ = "operation_action_history"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('CREATE', 'ASSIGN', 'STATUS_CHANGE', 'COMMENT', 'CLOSE')",
            name="chk_operation_action_history_event_type",
        ),
        CheckConstraint(
            "old_status IS NULL OR old_status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')",
            name="chk_operation_action_history_old_status",
        ),
        CheckConstraint(
            "new_status IS NULL OR new_status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')",
            name="chk_operation_action_history_new_status",
        ),
        Index("idx_operation_action_history_action_created", "action_id", "created_at", "history_id"),
    )

    history_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    action_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("operation_actions.action_id", name="fk_operation_action_history_action", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    operator_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.user_id", name="fk_operation_action_history_operator", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default="CURRENT_TIMESTAMP(6)"
    )

    action: Mapped["OperationAction"] = relationship(back_populates="history")
    operator: Mapped["User"] = relationship(back_populates="action_history")


__all__ = ("OperationAction", "OperationActionSource", "OperationActionHistory")
