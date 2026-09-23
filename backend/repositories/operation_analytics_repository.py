"""Read-only historical queries for Phase 8 operation analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from models.anomaly import DataAnomalyRecord
from models.drama import Drama
from models.operation_action import OperationAction, OperationActionHistory
from models.relations import DramaPlatform
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision


@dataclass(frozen=True, slots=True)
class ActionReadRecord:
    action_id: int
    drama_id: int | None
    anchor_time: datetime


@dataclass(frozen=True, slots=True)
class ActionReadPage:
    page: int
    page_size: int
    total: int
    items: tuple[ActionReadRecord, ...]


@dataclass(frozen=True, slots=True)
class DramaReadRecord:
    drama_id: int
    status: str
    premiere_date: date | None
    online_at: datetime | None


@dataclass(frozen=True, slots=True)
class MetricRevisionReadRecord:
    drama_id: int
    platform_id: int
    snapshot_id: int
    snapshot_revision_id: int
    snapshot_time: datetime
    version_no: int
    revision_action: str
    play_count: int
    like_count: int | None
    comment_count: int | None
    favorite_count: int | None
    share_count: int | None
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class AnomalyReadRecord:
    anomaly_id: int
    drama_id: int
    analysis_as_of: datetime
    algorithm_version: str


class OperationAnalyticsRepository:
    """Return immutable projections without owning the transaction."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_completed_actions(
        self,
        *,
        analysis_as_of: datetime,
        action_id: int | None = None,
        drama_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ActionReadPage:
        self._validate_page(page, page_size)
        analysis_as_of = self._database_utc(analysis_as_of)
        statement = self._completed_action_statement(analysis_as_of)
        if action_id is not None:
            statement = statement.where(OperationAction.action_id == action_id)
        if drama_id is not None:
            statement = statement.where(OperationAction.drama_id == drama_id)

        total = int(
            self.session.scalar(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
            or 0
        )
        rows = self.session.execute(
            statement
            .order_by(
                statement.selected_columns.anchor_time.desc(),
                OperationAction.action_id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return ActionReadPage(
            page=page,
            page_size=page_size,
            total=total,
            items=tuple(ActionReadRecord(*row) for row in rows),
        )

    def list_completed_actions_in_range(
        self,
        *,
        drama_ids: Sequence[int],
        start_time: datetime,
        end_time: datetime,
        analysis_as_of: datetime,
    ) -> tuple[ActionReadRecord, ...]:
        if not drama_ids:
            return ()
        start_time = self._database_utc(start_time)
        end_time = self._database_utc(end_time)
        analysis_as_of = self._database_utc(analysis_as_of)
        self._validate_range(start_time, end_time)
        completed = self._completion_anchor(analysis_as_of)
        statement = (
            select(
                OperationAction.action_id,
                OperationAction.drama_id,
                completed.c.anchor_time,
            )
            .join(completed, completed.c.action_id == OperationAction.action_id)
            .where(
                OperationAction.created_at <= analysis_as_of,
                OperationAction.drama_id.in_(tuple(drama_ids)),
                completed.c.anchor_time >= start_time,
                completed.c.anchor_time < end_time,
            )
            .order_by(completed.c.anchor_time.asc(), OperationAction.action_id.asc())
        )
        return tuple(
            ActionReadRecord(*row) for row in self.session.execute(statement).all()
        )

    def list_drama_records(
        self,
        *,
        drama_ids: Sequence[int],
        analysis_as_of: datetime,
        platform_id: int | None = None,
    ) -> tuple[DramaReadRecord, ...]:
        if not drama_ids:
            return ()
        analysis_as_of = self._database_utc(analysis_as_of)
        join_condition = and_(
            DramaPlatform.drama_id == Drama.drama_id,
            DramaPlatform.created_at <= analysis_as_of,
            DramaPlatform.updated_at <= analysis_as_of,
            or_(
                DramaPlatform.online_at.is_(None),
                DramaPlatform.online_at <= analysis_as_of,
            ),
        )
        if platform_id is not None:
            join_condition = and_(
                join_condition,
                DramaPlatform.platform_id == platform_id,
            )
        statement = (
            select(
                Drama.drama_id,
                Drama.status,
                Drama.premiere_date,
                func.min(DramaPlatform.online_at),
            )
            .select_from(Drama)
            .outerjoin(DramaPlatform, join_condition)
            .where(
                Drama.drama_id.in_(tuple(drama_ids)),
                Drama.created_at <= analysis_as_of,
                Drama.updated_at <= analysis_as_of,
            )
            .group_by(Drama.drama_id, Drama.status, Drama.premiere_date)
            .order_by(Drama.drama_id.asc())
        )
        return tuple(
            DramaReadRecord(*row) for row in self.session.execute(statement).all()
        )

    def list_metric_revisions(
        self,
        *,
        drama_ids: Sequence[int],
        start_time: datetime,
        end_time: datetime,
        analysis_as_of: datetime,
        platform_id: int | None = None,
    ) -> tuple[MetricRevisionReadRecord, ...]:
        if not drama_ids:
            return ()
        start_time = self._database_utc(start_time)
        end_time = self._database_utc(end_time)
        analysis_as_of = self._database_utc(analysis_as_of)
        self._validate_range(start_time, end_time)
        revision = DramaMetricSnapshotRevision
        latest = (
            select(
                revision.snapshot_id.label("snapshot_id"),
                func.max(revision.version_no).label("version_no"),
            )
            .where(revision.changed_at <= analysis_as_of)
            .group_by(revision.snapshot_id)
            .subquery("latest_revision_as_of")
        )
        statement = (
            select(
                DramaPlatform.drama_id,
                DramaPlatform.platform_id,
                DramaMetricSnapshot.snapshot_id,
                revision.snapshot_revision_id,
                DramaMetricSnapshot.snapshot_time,
                revision.version_no,
                revision.revision_action,
                revision.play_count,
                revision.like_count,
                revision.comment_count,
                revision.favorite_count,
                revision.share_count,
                revision.changed_at,
            )
            .select_from(DramaMetricSnapshot)
            .join(
                DramaPlatform,
                DramaPlatform.drama_platform_id
                == DramaMetricSnapshot.drama_platform_id,
            )
            .join(latest, latest.c.snapshot_id == DramaMetricSnapshot.snapshot_id)
            .join(
                revision,
                and_(
                    revision.snapshot_id == latest.c.snapshot_id,
                    revision.version_no == latest.c.version_no,
                ),
            )
            .where(
                DramaPlatform.drama_id.in_(tuple(drama_ids)),
                DramaMetricSnapshot.snapshot_time >= start_time,
                DramaMetricSnapshot.snapshot_time < end_time,
                DramaMetricSnapshot.snapshot_time <= analysis_as_of,
                revision.revision_action != "VOID",
                revision.play_count.is_not(None),
            )
        )
        if platform_id is not None:
            statement = statement.where(DramaPlatform.platform_id == platform_id)
        statement = statement.order_by(
            DramaPlatform.drama_id.asc(),
            DramaPlatform.platform_id.asc(),
            DramaMetricSnapshot.snapshot_time.asc(),
            DramaMetricSnapshot.snapshot_id.asc(),
        )
        return tuple(
            MetricRevisionReadRecord(*row)
            for row in self.session.execute(statement).all()
        )

    def list_anomalies(
        self,
        *,
        drama_ids: Sequence[int],
        start_time: datetime,
        end_time: datetime,
        analysis_as_of: datetime,
    ) -> tuple[AnomalyReadRecord, ...]:
        if not drama_ids:
            return ()
        start_time = self._database_utc(start_time)
        end_time = self._database_utc(end_time)
        analysis_as_of = self._database_utc(analysis_as_of)
        self._validate_range(start_time, end_time)
        statement = (
            select(
                DataAnomalyRecord.anomaly_id,
                DataAnomalyRecord.drama_id,
                DataAnomalyRecord.analysis_as_of,
                DataAnomalyRecord.algorithm_version,
            )
            .where(
                DataAnomalyRecord.drama_id.in_(tuple(drama_ids)),
                DataAnomalyRecord.analysis_as_of >= start_time,
                DataAnomalyRecord.analysis_as_of < end_time,
                DataAnomalyRecord.analysis_as_of <= analysis_as_of,
            )
            .order_by(
                DataAnomalyRecord.drama_id.asc(),
                DataAnomalyRecord.analysis_as_of.asc(),
                DataAnomalyRecord.anomaly_id.asc(),
            )
        )
        return tuple(
            AnomalyReadRecord(*row) for row in self.session.execute(statement).all()
        )

    @staticmethod
    def _completion_anchor(analysis_as_of: datetime):
        history = OperationActionHistory
        return (
            select(
                history.action_id.label("action_id"),
                func.min(history.created_at).label("anchor_time"),
            )
            .where(
                history.created_at <= analysis_as_of,
                or_(
                    and_(
                        history.event_type == "STATUS_CHANGE",
                        history.new_status == "COMPLETED",
                    ),
                    and_(
                        history.event_type == "CLOSE",
                        history.new_status == "COMPLETED",
                    ),
                ),
            )
            .group_by(history.action_id)
            .subquery("completed_action_as_of")
        )

    @classmethod
    def _completed_action_statement(
        cls, analysis_as_of: datetime
    ) -> Select[tuple[int, int | None, datetime]]:
        completed = cls._completion_anchor(analysis_as_of)
        return (
            select(
                OperationAction.action_id,
                OperationAction.drama_id,
                completed.c.anchor_time,
            )
            .join(completed, completed.c.action_id == OperationAction.action_id)
            .where(
                OperationAction.created_at <= analysis_as_of,
                OperationAction.drama_id.is_not(None),
            )
        )

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")

    @staticmethod
    def _validate_range(start_time: datetime, end_time: datetime) -> None:
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

    @staticmethod
    def _database_utc(value: datetime) -> datetime:
        """Normalize an instant for the schema's UTC, timezone-naive DATETIME."""

        if value.tzinfo is None or value.utcoffset() is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)


__all__ = [
    "ActionReadPage",
    "ActionReadRecord",
    "AnomalyReadRecord",
    "DramaReadRecord",
    "MetricRevisionReadRecord",
    "OperationAnalyticsRepository",
]
