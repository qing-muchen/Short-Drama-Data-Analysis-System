"""Read-only fact queries for the Phase 9 data governance layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from models.anomaly import DataAnomalyRecord
from models.data_quality import DataQualityRule, DataQualityScore
from models.drama import Drama
from models.explanation import AnalysisExplanation, AnalysisLineageRecord
from models.master_data import Platform
from models.operation_action import (
    OperationAction,
    OperationActionHistory,
    OperationActionSource,
)
from models.relations import DramaPlatform
from models.score import DramaScore
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision


@dataclass(frozen=True, slots=True)
class FreshnessReadRecord:
    drama_platform_id: int
    drama_id: int
    platform_id: int
    latest_snapshot_time: datetime | None


@dataclass(frozen=True, slots=True)
class CompletenessTargetRecord:
    drama_id: int
    drama_code: str | None
    drama_name: str | None
    drama_status: str | None
    drama_platform_id: int | None
    platform_id: int | None


@dataclass(frozen=True, slots=True)
class MetricCoverageReadRecord:
    drama_platform_id: int
    snapshot_id: int
    snapshot_revision_id: int
    snapshot_time: datetime
    version_no: int
    revision_action: str
    play_count: int | None
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class ActionSourceReadRecord:
    source_id: int
    action_id: int
    source_type: str
    source_reference_id: int | None
    target_exists: bool


@dataclass(frozen=True, slots=True)
class ActionStatusReadRecord:
    action_id: int
    current_status: str
    latest_history_id: int | None
    latest_history_status: str | None


@dataclass(frozen=True, slots=True)
class LineageReadRecord:
    lineage_id: int
    target_type: str
    target_id: int
    source_type: str
    source_id: int
    lineage_analysis_as_of: datetime
    target_exists: bool | None
    target_as_of_matches: bool | None
    source_exists: bool | None
    source_visible_as_of: bool | None


@dataclass(frozen=True, slots=True)
class RevisionReadRecord:
    snapshot_id: int
    snapshot_time: datetime
    snapshot_revision_id: int
    version_no: int
    revision_action: str
    previous_revision_id: int | None
    previous_snapshot_id: int | None
    previous_version_no: int | None
    changed_at: datetime


class DataGovernanceRepository:
    """Return immutable governance facts without owning a transaction."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_freshness_records(
        self,
        *,
        analysis_as_of: datetime,
    ) -> tuple[FreshnessReadRecord, ...]:
        cutoff = self._database_utc(analysis_as_of)
        latest = self._latest_revision_as_of(cutoff)
        revision = DramaMetricSnapshotRevision
        latest_visible = (
            select(
                DramaMetricSnapshot.drama_platform_id.label("drama_platform_id"),
                func.max(DramaMetricSnapshot.snapshot_time).label(
                    "latest_snapshot_time"
                ),
            )
            .select_from(DramaMetricSnapshot)
            .join(latest, latest.c.snapshot_id == DramaMetricSnapshot.snapshot_id)
            .join(
                revision,
                and_(
                    revision.snapshot_id == latest.c.snapshot_id,
                    revision.version_no == latest.c.version_no,
                ),
            )
            .where(
                DramaMetricSnapshot.snapshot_time <= cutoff,
                revision.revision_action != "VOID",
            )
            .group_by(DramaMetricSnapshot.drama_platform_id)
            .subquery("latest_visible_snapshot_by_feed")
        )
        statement = (
            select(
                DramaPlatform.drama_platform_id,
                DramaPlatform.drama_id,
                DramaPlatform.platform_id,
                latest_visible.c.latest_snapshot_time,
            )
            .select_from(DramaPlatform)
            .join(Drama, Drama.drama_id == DramaPlatform.drama_id)
            .join(Platform, Platform.platform_id == DramaPlatform.platform_id)
            .outerjoin(
                latest_visible,
                latest_visible.c.drama_platform_id
                == DramaPlatform.drama_platform_id,
            )
            .where(
                Drama.status.in_(("SERIALIZING", "COMPLETED")),
                DramaPlatform.status == "ONLINE",
                Platform.status == "ACTIVE",
                Drama.created_at <= cutoff,
                Drama.updated_at <= cutoff,
                DramaPlatform.created_at <= cutoff,
                DramaPlatform.updated_at <= cutoff,
                Platform.created_at <= cutoff,
                Platform.updated_at <= cutoff,
                or_(DramaPlatform.online_at.is_(None), DramaPlatform.online_at <= cutoff),
            )
            .order_by(
                DramaPlatform.drama_id.asc(),
                DramaPlatform.platform_id.asc(),
            )
        )
        return tuple(
            FreshnessReadRecord(*row)
            for row in self.session.execute(statement).all()
        )

    def list_completeness_targets(
        self,
        *,
        analysis_as_of: datetime,
    ) -> tuple[CompletenessTargetRecord, ...]:
        cutoff = self._database_utc(analysis_as_of)
        platform_join = and_(
            DramaPlatform.drama_id == Drama.drama_id,
            DramaPlatform.status == "ONLINE",
            DramaPlatform.created_at <= cutoff,
            DramaPlatform.updated_at <= cutoff,
            or_(DramaPlatform.online_at.is_(None), DramaPlatform.online_at <= cutoff),
        )
        master_join = and_(
            Platform.platform_id == DramaPlatform.platform_id,
            Platform.status == "ACTIVE",
            Platform.created_at <= cutoff,
            Platform.updated_at <= cutoff,
        )
        statement = (
            select(
                Drama.drama_id,
                Drama.drama_code,
                Drama.drama_name,
                Drama.status,
                DramaPlatform.drama_platform_id,
                Platform.platform_id,
            )
            .select_from(Drama)
            .outerjoin(DramaPlatform, platform_join)
            .outerjoin(Platform, master_join)
            .where(
                Drama.status.in_(("SERIALIZING", "COMPLETED")),
                Drama.created_at <= cutoff,
                Drama.updated_at <= cutoff,
            )
            .order_by(
                Drama.drama_id.asc(),
                DramaPlatform.drama_platform_id.asc(),
            )
        )
        return tuple(
            CompletenessTargetRecord(*row)
            for row in self.session.execute(statement).all()
        )

    def list_metric_coverage_records(
        self,
        *,
        drama_platform_ids: Sequence[int],
        start_time: datetime,
        end_time: datetime,
        analysis_as_of: datetime,
    ) -> tuple[MetricCoverageReadRecord, ...]:
        if not drama_platform_ids:
            return ()
        start = self._database_utc(start_time)
        end = self._database_utc(end_time)
        cutoff = self._database_utc(analysis_as_of)
        self._validate_range(start, end)
        latest = self._latest_revision_as_of(cutoff)
        revision = DramaMetricSnapshotRevision
        statement = (
            select(
                DramaMetricSnapshot.drama_platform_id,
                DramaMetricSnapshot.snapshot_id,
                revision.snapshot_revision_id,
                DramaMetricSnapshot.snapshot_time,
                revision.version_no,
                revision.revision_action,
                revision.play_count,
                revision.changed_at,
            )
            .select_from(DramaMetricSnapshot)
            .join(latest, latest.c.snapshot_id == DramaMetricSnapshot.snapshot_id)
            .join(
                revision,
                and_(
                    revision.snapshot_id == latest.c.snapshot_id,
                    revision.version_no == latest.c.version_no,
                ),
            )
            .where(
                DramaMetricSnapshot.drama_platform_id.in_(
                    tuple(drama_platform_ids)
                ),
                DramaMetricSnapshot.snapshot_time >= start,
                DramaMetricSnapshot.snapshot_time < end,
                DramaMetricSnapshot.snapshot_time <= cutoff,
                revision.revision_action != "VOID",
            )
            .order_by(
                DramaMetricSnapshot.drama_platform_id.asc(),
                DramaMetricSnapshot.snapshot_time.asc(),
                DramaMetricSnapshot.snapshot_id.asc(),
            )
        )
        return tuple(
            MetricCoverageReadRecord(*row)
            for row in self.session.execute(statement).all()
        )

    def list_action_source_records(
        self,
        *,
        analysis_as_of: datetime,
    ) -> tuple[ActionSourceReadRecord, ...]:
        cutoff = self._database_utc(analysis_as_of)
        source = OperationActionSource
        target_exists = case(
            (
                source.source_type == "MANUAL",
                source.source_reference_id.is_(None),
            ),
            (
                source.source_type == "ANOMALY",
                exists(
                    select(DataAnomalyRecord.anomaly_id).where(
                        DataAnomalyRecord.anomaly_id == source.source_reference_id,
                        DataAnomalyRecord.created_at <= cutoff,
                    )
                ),
            ),
            (
                source.source_type == "QUALITY",
                exists(
                    select(DataQualityScore.quality_score_id).where(
                        DataQualityScore.quality_score_id
                        == source.source_reference_id,
                        DataQualityScore.created_at <= cutoff,
                    )
                ),
            ),
            (
                source.source_type == "SCORE",
                exists(
                    select(DramaScore.score_id).where(
                        DramaScore.score_id == source.source_reference_id,
                        DramaScore.created_at <= cutoff,
                    )
                ),
            ),
            else_=False,
        ).label("target_exists")
        statement = (
            select(
                source.source_id,
                source.action_id,
                source.source_type,
                source.source_reference_id,
                target_exists,
            )
            .join(OperationAction, OperationAction.action_id == source.action_id)
            .where(
                source.created_at <= cutoff,
                OperationAction.created_at <= cutoff,
                OperationAction.updated_at <= cutoff,
            )
            .order_by(source.action_id.asc(), source.source_id.asc())
        )
        return tuple(
            ActionSourceReadRecord(*row)
            for row in self.session.execute(statement).all()
        )

    def list_action_status_records(
        self,
        *,
        analysis_as_of: datetime,
    ) -> tuple[ActionStatusReadRecord, ...]:
        cutoff = self._database_utc(analysis_as_of)
        history = OperationActionHistory
        latest_history = (
            select(
                history.action_id.label("action_id"),
                func.max(history.history_id).label("history_id"),
            )
            .where(
                history.created_at <= cutoff,
                history.new_status.is_not(None),
            )
            .group_by(history.action_id)
            .subquery("latest_action_status_as_of")
        )
        selected_history = aliased(OperationActionHistory)
        statement = (
            select(
                OperationAction.action_id,
                OperationAction.status,
                selected_history.history_id,
                selected_history.new_status,
            )
            .select_from(OperationAction)
            .outerjoin(
                latest_history,
                latest_history.c.action_id == OperationAction.action_id,
            )
            .outerjoin(
                selected_history,
                selected_history.history_id == latest_history.c.history_id,
            )
            .where(
                OperationAction.created_at <= cutoff,
                OperationAction.updated_at <= cutoff,
            )
            .order_by(OperationAction.action_id.asc())
        )
        return tuple(
            ActionStatusReadRecord(*row)
            for row in self.session.execute(statement).all()
        )

    def list_lineage_records(
        self,
        *,
        analysis_as_of: datetime,
    ) -> tuple[LineageReadRecord, ...]:
        cutoff = self._database_utc(analysis_as_of)
        lineage = AnalysisLineageRecord
        explanation_target_exists = exists(
            select(AnalysisExplanation.explanation_id).where(
                AnalysisExplanation.explanation_id == lineage.target_id,
                AnalysisExplanation.created_at <= cutoff,
            )
        )
        explanation_as_of_matches = exists(
            select(AnalysisExplanation.explanation_id).where(
                AnalysisExplanation.explanation_id == lineage.target_id,
                AnalysisExplanation.analysis_as_of == lineage.analysis_as_of,
                AnalysisExplanation.created_at <= cutoff,
            )
        )
        snapshot_exists = exists(
            select(DramaMetricSnapshot.snapshot_id).where(
                DramaMetricSnapshot.snapshot_id == lineage.source_id
            )
        )
        quality_rule_exists = exists(
            select(DataQualityRule.quality_rule_id).where(
                DataQualityRule.quality_rule_id == lineage.source_id
            )
        )
        anomaly_exists = exists(
            select(DataAnomalyRecord.anomaly_id).where(
                DataAnomalyRecord.anomaly_id == lineage.source_id
            )
        )
        source_exists = case(
            (lineage.source_type == "SNAPSHOT", snapshot_exists),
            (lineage.source_type == "RULE", quality_rule_exists),
            (lineage.source_type == "ANOMALY_EVIDENCE", anomaly_exists),
            else_=None,
        ).label("source_exists")
        source_visible_as_of = case(
            (
                lineage.source_type == "SNAPSHOT",
                exists(
                    select(DramaMetricSnapshot.snapshot_id).where(
                        DramaMetricSnapshot.snapshot_id == lineage.source_id,
                        DramaMetricSnapshot.snapshot_time
                        <= lineage.analysis_as_of,
                    )
                ),
            ),
            (
                lineage.source_type == "RULE",
                exists(
                    select(DataQualityRule.quality_rule_id).where(
                        DataQualityRule.quality_rule_id == lineage.source_id,
                        DataQualityRule.valid_from <= lineage.analysis_as_of,
                        or_(
                            DataQualityRule.valid_to.is_(None),
                            DataQualityRule.valid_to > lineage.analysis_as_of,
                        ),
                    )
                ),
            ),
            (
                lineage.source_type == "ANOMALY_EVIDENCE",
                exists(
                    select(DataAnomalyRecord.anomaly_id).where(
                        DataAnomalyRecord.anomaly_id == lineage.source_id,
                        DataAnomalyRecord.analysis_as_of
                        <= lineage.analysis_as_of,
                    )
                ),
            ),
            else_=None,
        ).label("source_visible_as_of")
        statement = (
            select(
                lineage.lineage_id,
                lineage.target_type,
                lineage.target_id,
                lineage.source_type,
                lineage.source_id,
                lineage.analysis_as_of,
                case(
                    (
                        lineage.target_type == "EXPLANATION",
                        explanation_target_exists,
                    ),
                    else_=None,
                ).label("target_exists"),
                case(
                    (
                        lineage.target_type == "EXPLANATION",
                        explanation_as_of_matches,
                    ),
                    else_=None,
                ).label("target_as_of_matches"),
                source_exists,
                source_visible_as_of,
            )
            .where(
                lineage.analysis_as_of <= cutoff,
                lineage.created_at <= cutoff,
            )
            .order_by(lineage.lineage_id.asc())
        )
        return tuple(
            LineageReadRecord(*row)
            for row in self.session.execute(statement).all()
        )

    def list_revision_records(
        self,
        *,
        analysis_as_of: datetime,
    ) -> tuple[RevisionReadRecord, ...]:
        cutoff = self._database_utc(analysis_as_of)
        latest = self._latest_revision_as_of(cutoff)
        revision = DramaMetricSnapshotRevision
        previous = aliased(DramaMetricSnapshotRevision)
        statement = (
            select(
                DramaMetricSnapshot.snapshot_id,
                DramaMetricSnapshot.snapshot_time,
                revision.snapshot_revision_id,
                revision.version_no,
                revision.revision_action,
                revision.previous_revision_id,
                previous.snapshot_id,
                previous.version_no,
                revision.changed_at,
            )
            .select_from(DramaMetricSnapshot)
            .join(latest, latest.c.snapshot_id == DramaMetricSnapshot.snapshot_id)
            .join(
                revision,
                and_(
                    revision.snapshot_id == latest.c.snapshot_id,
                    revision.version_no == latest.c.version_no,
                ),
            )
            .outerjoin(
                previous,
                and_(
                    previous.snapshot_id == revision.snapshot_id,
                    previous.snapshot_revision_id == revision.previous_revision_id,
                ),
            )
            .where(DramaMetricSnapshot.snapshot_time <= cutoff)
            .order_by(DramaMetricSnapshot.snapshot_id.asc())
        )
        return tuple(
            RevisionReadRecord(*row)
            for row in self.session.execute(statement).all()
        )

    @staticmethod
    def _latest_revision_as_of(analysis_as_of: datetime):
        revision = DramaMetricSnapshotRevision
        return (
            select(
                revision.snapshot_id.label("snapshot_id"),
                func.max(revision.version_no).label("version_no"),
            )
            .where(revision.changed_at <= analysis_as_of)
            .group_by(revision.snapshot_id)
            .subquery("latest_revision_as_of")
        )

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
    "ActionSourceReadRecord",
    "ActionStatusReadRecord",
    "CompletenessTargetRecord",
    "DataGovernanceRepository",
    "FreshnessReadRecord",
    "LineageReadRecord",
    "MetricCoverageReadRecord",
    "RevisionReadRecord",
]
