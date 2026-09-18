"""Persisted drama-level operating trend prediction ORM mapping."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.drama import Drama


class PredictionResult(CreatedUpdatedAtMixin, Base):
    """One versioned next-day cumulative metric prediction for a drama."""

    __tablename__ = "prediction_results"
    __table_args__ = (
        UniqueConstraint(
            "drama_id",
            "metric_type",
            "target_date",
            "algorithm_version",
            name="uq_prediction_results_identity",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(metric_type)) > 0",
            name="chk_prediction_results_metric_type",
        ),
        CheckConstraint(
            "predicted_value >= 0",
            name="chk_prediction_results_predicted_value",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(algorithm_version)) > 0",
            name="chk_prediction_results_algorithm_version",
        ),
        Index(
            "idx_prediction_results_drama_metric_target",
            "drama_id",
            "metric_type",
            "target_date",
        ),
        Index(
            "idx_prediction_results_metric_target",
            "metric_type",
            "target_date",
        ),
    )

    prediction_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "dramas.drama_id",
            name="fk_prediction_results_drama",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prediction_date: Mapped[date] = mapped_column(nullable=False)
    target_date: Mapped[date] = mapped_column(nullable=False)
    predicted_value: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 2), nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_as_of: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False
    )

    drama: Mapped["Drama"] = relationship(back_populates="predictions")


__all__ = ("PredictionResult",)
