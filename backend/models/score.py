"""Persisted, versioned composite-score ORM mapping."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    desc,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.drama import Drama


class DramaScore(CreatedUpdatedAtMixin, Base):
    """One deterministic composite score for a drama, date, model, and scope."""

    __tablename__ = "drama_scores"
    __table_args__ = (
        UniqueConstraint(
            "drama_id",
            "score_date",
            "algorithm_version",
            "score_scope_type",
            "score_scope_id",
            name="uq_drama_scores_identity",
        ),
        CheckConstraint(
            "score_scope_type = 'ALL' AND score_scope_id = 0",
            name="chk_drama_scores_scope",
        ),
        CheckConstraint(
            "heat_score BETWEEN 0 AND 100 "
            "AND growth_score BETWEEN 0 AND 100 "
            "AND engagement_score BETWEEN 0 AND 100 "
            "AND lifecycle_score BETWEEN 0 AND 100",
            name="chk_drama_scores_components",
        ),
        CheckConstraint(
            "total_score BETWEEN 0 AND 100",
            name="chk_drama_scores_total",
        ),
        CheckConstraint(
            "level IN ('S', 'A', 'B', 'C')",
            name="chk_drama_scores_level",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(algorithm_version)) > 0",
            name="chk_drama_scores_algorithm_version",
        ),
        Index(
            "idx_drama_scores_ranking",
            "score_date",
            "algorithm_version",
            "score_scope_type",
            "score_scope_id",
            desc("total_score"),
            "drama_id",
        ),
        Index(
            "idx_drama_scores_level_distribution",
            "score_date",
            "algorithm_version",
            "score_scope_type",
            "score_scope_id",
            "level",
        ),
    )

    score_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "dramas.drama_id",
            name="fk_drama_scores_drama",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    score_date: Mapped[date] = mapped_column(nullable=False)
    score_scope_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ALL'")
    )
    score_scope_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    analysis_as_of: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False
    )
    heat_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), nullable=False)
    growth_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), nullable=False)
    engagement_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), nullable=False)
    lifecycle_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), nullable=False)
    total_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), nullable=False)
    level: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)

    drama: Mapped["Drama"] = relationship(back_populates="scores")
