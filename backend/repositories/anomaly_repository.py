"""Persistence queries for Phase 4 anomaly findings."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from analytics.anomaly_detection import AnomalyFinding
from models.anomaly import DataAnomalyRecord
from repositories.base import BaseRepository, Page


ANOMALY_SEVERITIES = ("A", "B", "C")
ANOMALY_STATUSES = ("OPEN", "ACKNOWLEDGED", "RESOLVED", "IGNORED")
ANOMALY_METRICS = ("PLAY_COUNT", "ENGAGEMENT_RATE")


@dataclass(frozen=True, slots=True)
class AnomalyTrendPoint:
    """One calendar-day anomaly count for trend presentation."""

    analysis_date: date
    anomaly_count: int


@dataclass(frozen=True, slots=True)
class AnomalyStatistics:
    """Aggregate anomaly counts without deriving any anomaly semantics."""

    total_count: int
    severity_distribution: dict[str, int]
    status_distribution: dict[str, int]
    metric_distribution: dict[str, int]


class AnomalyRepository(BaseRepository[DataAnomalyRecord]):
    """Store and query findings without calculating or committing."""

    model = DataAnomalyRecord

    def save_anomalies(
        self,
        findings: Sequence[AnomalyFinding],
        *,
        detected_at: datetime | None = None,
    ) -> list[DataAnomalyRecord]:
        """Persist and flush a finding collection; the caller owns the transaction."""

        detection_time = detected_at or datetime.now(timezone.utc)
        entities = [
            self._as_entity(finding, detected_at=detection_time)
            for finding in findings
        ]
        self.session.add_all(entities)
        self.session.flush()
        return entities

    def get_anomalies(
        self,
        *,
        page: int,
        page_size: int,
        analysis_as_of: datetime | None = None,
        status: str | None = None,
        severity: str | None = None,
        metric_type: str | None = None,
        anomaly_type: str | None = None,
    ) -> Page[DataAnomalyRecord]:
        """Return a stable, eager-loaded anomaly page with optional filters."""

        statement = self._base_finding_statement()
        filters = []
        if analysis_as_of is not None:
            filters.append(DataAnomalyRecord.analysis_as_of == analysis_as_of)
        if status is not None:
            filters.append(DataAnomalyRecord.status == status)
        if severity is not None:
            filters.append(DataAnomalyRecord.severity == severity)
        if metric_type is not None:
            filters.append(DataAnomalyRecord.metric_type == metric_type)
        if anomaly_type is not None:
            filters.append(DataAnomalyRecord.anomaly_type == anomaly_type)

        statement = statement.where(*filters).order_by(
            DataAnomalyRecord.severity.desc(),
            DataAnomalyRecord.detected_at.desc(),
            DataAnomalyRecord.anomaly_id.desc(),
        )
        return self.paginate(statement, page=page, page_size=page_size)

    def get_by_drama(
        self,
        *,
        drama_id: int,
        limit: int | None = None,
    ) -> list[DataAnomalyRecord]:
        """Return one drama's anomaly history in reverse analysis order."""

        statement = self._base_finding_statement().where(
            DataAnomalyRecord.drama_id == drama_id
        )
        statement = statement.order_by(
            DataAnomalyRecord.analysis_as_of.desc(),
            DataAnomalyRecord.detected_at.desc(),
            DataAnomalyRecord.anomaly_id.desc(),
        )
        if limit is not None:
            self._validate_window(offset=0, limit=limit)
            statement = statement.limit(limit)
        return list(self.session.scalars(statement).unique().all())

    def get_latest_anomalies(self) -> list[DataAnomalyRecord]:
        """Return all findings from the latest available analysis cutoff."""

        latest_as_of = self.session.scalar(
            select(func.max(DataAnomalyRecord.analysis_as_of))
        )
        if latest_as_of is None:
            return []
        statement = self._base_finding_statement().where(
            DataAnomalyRecord.analysis_as_of == latest_as_of
        )
        statement = statement.order_by(
            DataAnomalyRecord.severity.desc(),
            DataAnomalyRecord.detected_at.desc(),
            DataAnomalyRecord.anomaly_id.desc(),
        )
        return list(self.session.scalars(statement).unique().all())

    def get_trend(
        self,
        *,
        start_as_of: datetime | None = None,
        end_as_of: datetime | None = None,
        drama_id: int | None = None,
        metric_type: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> list[AnomalyTrendPoint]:
        """Count findings by the calendar date of analysis_as_of."""

        analysis_date = func.date(DataAnomalyRecord.analysis_as_of).label(
            "analysis_date"
        )
        statement = select(
            analysis_date,
            func.count(DataAnomalyRecord.anomaly_id).label("anomaly_count"),
        )
        filters = []
        if start_as_of is not None:
            filters.append(DataAnomalyRecord.analysis_as_of >= start_as_of)
        if end_as_of is not None:
            filters.append(DataAnomalyRecord.analysis_as_of <= end_as_of)
        if drama_id is not None:
            filters.append(DataAnomalyRecord.drama_id == drama_id)
        if metric_type is not None:
            filters.append(DataAnomalyRecord.metric_type == metric_type)
        if severity is not None:
            filters.append(DataAnomalyRecord.severity == severity)
        if status is not None:
            filters.append(DataAnomalyRecord.status == status)
        statement = statement.where(*filters).group_by(analysis_date).order_by(
            analysis_date.asc()
        )
        return [
            AnomalyTrendPoint(
                analysis_date=self._coerce_date(analysis_day),
                anomaly_count=int(count),
            )
            for analysis_day, count in self.session.execute(statement).all()
        ]

    def update_status(
        self,
        *,
        anomaly_id: int,
        new_status: str,
    ) -> DataAnomalyRecord | None:
        """Update one persisted status and flush without committing."""

        entity = self.get_by_id(anomaly_id)
        if entity is None:
            return None
        entity.status = new_status
        self.session.flush()
        return entity

    def get_statistics(self) -> AnomalyStatistics:
        """Return total, severity, status and metric distributions."""

        total_count = int(
            self.session.scalar(
                select(func.count(DataAnomalyRecord.anomaly_id))
            )
            or 0
        )
        severity_distribution = self._distribution(
            DataAnomalyRecord.severity,
            ANOMALY_SEVERITIES,
        )
        status_distribution = self._distribution(
            DataAnomalyRecord.status,
            ANOMALY_STATUSES,
        )
        metric_distribution = self._distribution(
            DataAnomalyRecord.metric_type,
            ANOMALY_METRICS,
        )
        return AnomalyStatistics(
            total_count=total_count,
            severity_distribution=severity_distribution,
            status_distribution=status_distribution,
            metric_distribution=metric_distribution,
        )

    def _distribution(
        self,
        column: Any,
        expected_values: Sequence[str],
    ) -> dict[str, int]:
        statement = select(column, func.count(DataAnomalyRecord.anomaly_id)).group_by(
            column
        )
        distribution = {value: 0 for value in expected_values}
        for value, count in self.session.execute(statement).all():
            distribution[str(value)] = int(count)
        return distribution

    @staticmethod
    def _base_finding_statement() -> Any:
        return select(DataAnomalyRecord).options(
            joinedload(DataAnomalyRecord.drama)
        )

    @staticmethod
    def _coerce_date(value: date | str) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _as_entity(
        finding: AnomalyFinding,
        *,
        detected_at: datetime,
    ) -> DataAnomalyRecord:
        if not isinstance(finding, AnomalyFinding):
            raise TypeError("findings must contain AnomalyFinding objects")
        return DataAnomalyRecord(
            drama_id=finding.drama_id,
            metric_type=finding.metric_type,
            anomaly_type=finding.anomaly_type,
            severity=finding.severity,
            status="OPEN",
            analysis_as_of=finding.analysis_as_of,
            detected_at=detected_at,
            algorithm_version=finding.algorithm_version,
            baseline_value=finding.baseline_value,
            actual_value=finding.actual_value,
            deviation_value=finding.deviation_value,
            evidence_summary=finding.evidence_summary,
        )


__all__ = (
    "ANOMALY_METRICS",
    "ANOMALY_SEVERITIES",
    "ANOMALY_STATUSES",
    "AnomalyRepository",
    "AnomalyStatistics",
    "AnomalyTrendPoint",
)
