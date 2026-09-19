"""Persisted rule-based anomaly detection findings."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.drama import Drama


class DataAnomalyRecord(CreatedUpdatedAtMixin, Base):
    """One versioned anomaly finding for a drama metric."""

    __tablename__ = "data_anomaly_records"
    __table_args__ = (
        UniqueConstraint(
            "drama_id",
            "metric_type",
            "anomaly_type",
            "analysis_as_of",
            "algorithm_version",
            name="uq_data_anomaly_records_identity",
        ),
        CheckConstraint(
            "metric_type IN ('PLAY_COUNT', 'ENGAGEMENT_RATE')",
            name="chk_data_anomaly_records_metric_type",
        ),
        CheckConstraint(
            "anomaly_type IN ("
            "'PLAY_COUNT_GROWTH_ANOMALY',"
            "'PLAY_COUNT_DROP_ANOMALY',"
            "'ENGAGEMENT_RATE_ANOMALY',"
            "'DATA_SPIKE_ANOMALY'"
            ")",
            name="chk_data_anomaly_records_anomaly_type",
        ),
        CheckConstraint(
            "severity IN ('A', 'B', 'C')",
            name="chk_data_anomaly_records_severity",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'IGNORED')",
            name="chk_data_anomaly_records_status",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(algorithm_version)) > 0",
            name="chk_data_anomaly_records_algorithm_version",
        ),
        Index(
            "idx_anomaly_query",
            "analysis_as_of",
            "status",
            "severity",
            "metric_type",
        ),
        Index("idx_anomaly_trend", "drama_id", "analysis_as_of"),
    )

    anomaly_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "dramas.drama_id",
            name="fk_data_anomaly_records_drama",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="OPEN"
    )
    analysis_as_of: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_value: Mapped[Decimal | None] = mapped_column(
        DECIMAL(18, 4), nullable=True
    )
    actual_value: Mapped[Decimal | None] = mapped_column(
        DECIMAL(18, 4), nullable=True
    )
    deviation_value: Mapped[Decimal | None] = mapped_column(
        DECIMAL(18, 4), nullable=True
    )
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)

    drama: Mapped["Drama"] = relationship(back_populates="anomaly_records")


__all__ = ("DataAnomalyRecord",)
