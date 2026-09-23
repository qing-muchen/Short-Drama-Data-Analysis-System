"""Read-only projections for the Phase 10 reporting center."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Callable, Mapping, TypeVar

from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Session

from models.anomaly import DataAnomalyRecord
from models.data_quality import DataQualityScore
from models.drama import Drama
from models.master_data import Platform, Tag
from models.operation_action import (
    OperationAction,
    OperationActionHistory,
    OperationActionSource,
)
from models.prediction import PredictionResult
from models.relations import DramaPlatform, DramaTag
from models.score import DramaScore
from services.reporting.contracts import FilterScalar, ReportRequest


@dataclass(frozen=True, slots=True)
class DramaCatalogProjection:
    drama_id: int
    drama_code: str
    drama_name: str
    status: str
    premiere_date: date | None
    episode_count: int | None
    episode_duration_seconds: int | None
    platforms: str | None
    tags: str | None


@dataclass(frozen=True, slots=True)
class ScoreResultsProjection:
    score_id: int
    drama_id: int
    score_date: date
    score_scope_type: str
    score_scope_id: int
    analysis_as_of: datetime
    heat_score: Decimal
    growth_score: Decimal
    engagement_score: Decimal
    lifecycle_score: Decimal
    total_score: Decimal
    level: str
    algorithm_version: str


@dataclass(frozen=True, slots=True)
class DataQualityResultsProjection:
    quality_score_id: int
    score_date: date
    score_scope_type: str
    score_scope_id: int
    analysis_as_of: datetime
    completeness_score: Decimal
    accuracy_score: Decimal
    consistency_score: Decimal
    timeliness_score: Decimal
    total_score: Decimal
    quality_grade: str
    evaluated_entity_count: int
    open_issue_count: int
    algorithm_version: str
    rule_set_version: str
    rule_set_hash: str


@dataclass(frozen=True, slots=True)
class PredictionResultsProjection:
    prediction_id: int
    drama_id: int
    metric_type: str
    prediction_date: date
    target_date: date
    predicted_value: Decimal
    algorithm_version: str
    analysis_as_of: datetime


@dataclass(frozen=True, slots=True)
class AnomalyRecordsProjection:
    anomaly_id: int
    drama_id: int
    metric_type: str
    anomaly_type: str
    severity: str
    status: str
    analysis_as_of: datetime
    detected_at: datetime
    algorithm_version: str
    baseline_value: Decimal | None
    actual_value: Decimal | None
    deviation_value: Decimal | None
    evidence_summary: str


@dataclass(frozen=True, slots=True)
class OperationActionsProjection:
    action_id: int
    drama_id: int | None
    title: str
    description: str | None
    priority: str
    status: str
    assignee_user_id: int | None
    created_by_user_id: int
    due_date: date | None
    created_at: datetime
    updated_at: datetime
    source_count: int
    history_count: int


ProjectionT = TypeVar(
    "ProjectionT",
    DramaCatalogProjection,
    ScoreResultsProjection,
    DataQualityResultsProjection,
    PredictionResultsProjection,
    AnomalyRecordsProjection,
    OperationActionsProjection,
)


class ReportingRepository:
    """Build stable read projections without transaction ownership."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def count_drama_catalog(self, request: ReportRequest) -> int:
        return self._count(self._drama_catalog_statement(request))

    def list_drama_catalog(
        self, request: ReportRequest, *, offset: int = 0, limit: int = 1000
    ) -> tuple[DramaCatalogProjection, ...]:
        return self._list(
            self._drama_catalog_statement(request),
            DramaCatalogProjection,
            offset,
            limit,
        )

    def count_score_results(self, request: ReportRequest) -> int:
        return self._count(self._score_results_statement(request))

    def list_score_results(
        self, request: ReportRequest, *, offset: int = 0, limit: int = 1000
    ) -> tuple[ScoreResultsProjection, ...]:
        return self._list(
            self._score_results_statement(request),
            ScoreResultsProjection,
            offset,
            limit,
        )

    def count_data_quality_results(self, request: ReportRequest) -> int:
        return self._count(self._data_quality_results_statement(request))

    def list_data_quality_results(
        self, request: ReportRequest, *, offset: int = 0, limit: int = 1000
    ) -> tuple[DataQualityResultsProjection, ...]:
        return self._list(
            self._data_quality_results_statement(request),
            DataQualityResultsProjection,
            offset,
            limit,
        )

    def count_prediction_results(self, request: ReportRequest) -> int:
        return self._count(self._prediction_results_statement(request))

    def list_prediction_results(
        self, request: ReportRequest, *, offset: int = 0, limit: int = 1000
    ) -> tuple[PredictionResultsProjection, ...]:
        return self._list(
            self._prediction_results_statement(request),
            PredictionResultsProjection,
            offset,
            limit,
        )

    def count_anomaly_records(self, request: ReportRequest) -> int:
        return self._count(self._anomaly_records_statement(request))

    def list_anomaly_records(
        self, request: ReportRequest, *, offset: int = 0, limit: int = 1000
    ) -> tuple[AnomalyRecordsProjection, ...]:
        return self._list(
            self._anomaly_records_statement(request),
            AnomalyRecordsProjection,
            offset,
            limit,
        )

    def count_operation_actions(self, request: ReportRequest) -> int:
        return self._count(self._operation_actions_statement(request))

    def list_operation_actions(
        self, request: ReportRequest, *, offset: int = 0, limit: int = 1000
    ) -> tuple[OperationActionsProjection, ...]:
        return self._list(
            self._operation_actions_statement(request),
            OperationActionsProjection,
            offset,
            limit,
        )

    def _drama_catalog_statement(self, request: ReportRequest) -> Select:
        filters = self._filters(request)
        self._reject_unknown(filters, {"drama_id", "platform_id", "status", "tag_id"})

        platform_names = (
            select(
                func.group_concat(
                    Platform.platform_name.op("ORDER BY")(Platform.platform_name)
                )
            )
            .select_from(DramaPlatform)
            .join(Platform, Platform.platform_id == DramaPlatform.platform_id)
            .where(
                DramaPlatform.drama_id == Drama.drama_id,
                Platform.status == "ACTIVE",
            )
            .correlate(Drama)
            .scalar_subquery()
        )
        tag_names = (
            select(func.group_concat(Tag.tag_name.op("ORDER BY")(Tag.tag_name)))
            .select_from(DramaTag)
            .join(Tag, Tag.tag_id == DramaTag.tag_id)
            .where(
                DramaTag.drama_id == Drama.drama_id,
                DramaTag.relation_status == "ACTIVE",
                Tag.status == "ACTIVE",
            )
            .correlate(Drama)
            .scalar_subquery()
        )
        statement = select(
            Drama.drama_id,
            Drama.drama_code,
            Drama.drama_name,
            Drama.status,
            Drama.premiere_date,
            Drama.episode_count,
            Drama.episode_duration_seconds,
            platform_names.label("platforms"),
            tag_names.label("tags"),
        )
        if "drama_id" in filters:
            statement = statement.where(Drama.drama_id == filters["drama_id"])
        if "status" in filters:
            statement = statement.where(Drama.status == filters["status"])
        if "platform_id" in filters:
            statement = statement.where(
                exists(
                    select(1).where(
                        DramaPlatform.drama_id == Drama.drama_id,
                        DramaPlatform.platform_id == filters["platform_id"],
                    )
                )
            )
        if "tag_id" in filters:
            statement = statement.where(
                exists(
                    select(1).where(
                        DramaTag.drama_id == Drama.drama_id,
                        DramaTag.tag_id == filters["tag_id"],
                        DramaTag.relation_status == "ACTIVE",
                    )
                )
            )
        return statement.order_by(Drama.drama_id.asc())

    def _score_results_statement(self, request: ReportRequest) -> Select:
        filters = self._filters(request)
        self._reject_unknown(
            filters, {"algorithm_version", "drama_id", "end_time", "start_time"}
        )
        cutoff = self._database_utc(request.analysis_as_of)
        statement = select(
            DramaScore.score_id,
            DramaScore.drama_id,
            DramaScore.score_date,
            DramaScore.score_scope_type,
            DramaScore.score_scope_id,
            DramaScore.analysis_as_of,
            DramaScore.heat_score,
            DramaScore.growth_score,
            DramaScore.engagement_score,
            DramaScore.lifecycle_score,
            DramaScore.total_score,
            DramaScore.level,
            DramaScore.algorithm_version,
        ).where(DramaScore.analysis_as_of <= cutoff)
        statement = self._apply_common_result_filters(
            statement, DramaScore, filters, time_column=DramaScore.analysis_as_of
        )
        return statement.order_by(
            DramaScore.analysis_as_of.asc(),
            DramaScore.score_date.asc(),
            DramaScore.score_id.asc(),
        )

    def _data_quality_results_statement(self, request: ReportRequest) -> Select:
        filters = self._filters(request)
        self._reject_unknown(
            filters,
            {"algorithm_version", "end_time", "rule_set_version", "start_time"},
        )
        cutoff = self._database_utc(request.analysis_as_of)
        statement = select(
            DataQualityScore.quality_score_id,
            DataQualityScore.score_date,
            DataQualityScore.score_scope_type,
            DataQualityScore.score_scope_id,
            DataQualityScore.analysis_as_of,
            DataQualityScore.completeness_score,
            DataQualityScore.accuracy_score,
            DataQualityScore.consistency_score,
            DataQualityScore.timeliness_score,
            DataQualityScore.total_score,
            DataQualityScore.quality_grade,
            DataQualityScore.evaluated_entity_count,
            DataQualityScore.open_issue_count,
            DataQualityScore.algorithm_version,
            DataQualityScore.rule_set_version,
            DataQualityScore.rule_set_hash,
        ).where(DataQualityScore.analysis_as_of <= cutoff)
        statement = self._apply_common_result_filters(
            statement,
            DataQualityScore,
            filters,
            time_column=DataQualityScore.analysis_as_of,
        )
        if "rule_set_version" in filters:
            statement = statement.where(
                DataQualityScore.rule_set_version == filters["rule_set_version"]
            )
        return statement.order_by(
            DataQualityScore.analysis_as_of.asc(),
            DataQualityScore.score_date.asc(),
            DataQualityScore.quality_score_id.asc(),
        )

    def _prediction_results_statement(self, request: ReportRequest) -> Select:
        filters = self._filters(request)
        self._reject_unknown(
            filters, {"algorithm_version", "drama_id", "end_time", "start_time"}
        )
        cutoff = self._database_utc(request.analysis_as_of)
        statement = select(
            PredictionResult.prediction_id,
            PredictionResult.drama_id,
            PredictionResult.metric_type,
            PredictionResult.prediction_date,
            PredictionResult.target_date,
            PredictionResult.predicted_value,
            PredictionResult.algorithm_version,
            PredictionResult.analysis_as_of,
        ).where(PredictionResult.analysis_as_of <= cutoff)
        statement = self._apply_common_result_filters(
            statement,
            PredictionResult,
            filters,
            time_column=PredictionResult.analysis_as_of,
        )
        return statement.order_by(
            PredictionResult.analysis_as_of.asc(),
            PredictionResult.target_date.asc(),
            PredictionResult.prediction_id.asc(),
        )

    def _anomaly_records_statement(self, request: ReportRequest) -> Select:
        filters = self._filters(request)
        self._reject_unknown(
            filters,
            {
                "algorithm_version",
                "drama_id",
                "end_time",
                "severity",
                "start_time",
                "status",
            },
        )
        cutoff = self._database_utc(request.analysis_as_of)
        statement = select(
            DataAnomalyRecord.anomaly_id,
            DataAnomalyRecord.drama_id,
            DataAnomalyRecord.metric_type,
            DataAnomalyRecord.anomaly_type,
            DataAnomalyRecord.severity,
            DataAnomalyRecord.status,
            DataAnomalyRecord.analysis_as_of,
            DataAnomalyRecord.detected_at,
            DataAnomalyRecord.algorithm_version,
            DataAnomalyRecord.baseline_value,
            DataAnomalyRecord.actual_value,
            DataAnomalyRecord.deviation_value,
            DataAnomalyRecord.evidence_summary,
        ).where(DataAnomalyRecord.detected_at <= cutoff)
        statement = self._apply_common_result_filters(
            statement,
            DataAnomalyRecord,
            filters,
            time_column=DataAnomalyRecord.detected_at,
        )
        if "severity" in filters:
            statement = statement.where(
                DataAnomalyRecord.severity == filters["severity"]
            )
        if "status" in filters:
            statement = statement.where(DataAnomalyRecord.status == filters["status"])
        return statement.order_by(
            DataAnomalyRecord.detected_at.asc(),
            DataAnomalyRecord.anomaly_id.asc(),
        )

    def _operation_actions_statement(self, request: ReportRequest) -> Select:
        filters = self._filters(request)
        self._reject_unknown(filters, {"drama_id", "end_time", "start_time", "status"})
        cutoff = self._database_utc(request.analysis_as_of)
        source_count = (
            select(func.count(OperationActionSource.source_id))
            .where(
                OperationActionSource.action_id == OperationAction.action_id,
                OperationActionSource.created_at <= cutoff,
            )
            .correlate(OperationAction)
            .scalar_subquery()
        )
        history_count = (
            select(func.count(OperationActionHistory.history_id))
            .where(
                OperationActionHistory.action_id == OperationAction.action_id,
                OperationActionHistory.created_at <= cutoff,
            )
            .correlate(OperationAction)
            .scalar_subquery()
        )
        statement = select(
            OperationAction.action_id,
            OperationAction.drama_id,
            OperationAction.title,
            OperationAction.description,
            OperationAction.priority,
            OperationAction.status,
            OperationAction.assignee_user_id,
            OperationAction.created_by_user_id,
            OperationAction.due_date,
            OperationAction.created_at,
            OperationAction.updated_at,
            source_count.label("source_count"),
            history_count.label("history_count"),
        ).where(OperationAction.created_at <= cutoff)
        if "drama_id" in filters:
            statement = statement.where(OperationAction.drama_id == filters["drama_id"])
        if "status" in filters:
            statement = statement.where(OperationAction.status == filters["status"])
        statement = self._apply_time_filters(
            statement, OperationAction.created_at, filters
        )
        return statement.order_by(
            OperationAction.created_at.asc(), OperationAction.action_id.asc()
        )

    @staticmethod
    def _apply_common_result_filters(
        statement: Select,
        model: object,
        filters: Mapping[str, FilterScalar],
        *,
        time_column: object,
    ) -> Select:
        if "drama_id" in filters:
            statement = statement.where(
                getattr(model, "drama_id") == filters["drama_id"]
            )
        if "algorithm_version" in filters:
            statement = statement.where(
                getattr(model, "algorithm_version") == filters["algorithm_version"]
            )
        return ReportingRepository._apply_time_filters(
            statement, time_column, filters
        )

    @staticmethod
    def _apply_time_filters(
        statement: Select,
        time_column: object,
        filters: Mapping[str, FilterScalar],
    ) -> Select:
        if "start_time" in filters:
            statement = statement.where(
                time_column >= ReportingRepository._database_utc_value(
                    filters["start_time"]
                )
            )
        if "end_time" in filters:
            statement = statement.where(
                time_column <= ReportingRepository._database_utc_value(
                    filters["end_time"]
                )
            )
        return statement

    def _count(self, statement: Select) -> int:
        count_statement = select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
        return int(self.session.scalar(count_statement) or 0)

    def _list(
        self,
        statement: Select,
        projection_type: Callable[..., ProjectionT],
        offset: int,
        limit: int,
    ) -> tuple[ProjectionT, ...]:
        self._validate_window(offset, limit)
        rows = self.session.execute(statement.offset(offset).limit(limit)).all()
        return tuple(projection_type(*row) for row in rows)

    @staticmethod
    def _filters(request: ReportRequest) -> Mapping[str, FilterScalar]:
        if not isinstance(request, ReportRequest):
            raise TypeError("request must be a ReportRequest")
        return request.filter_mapping()

    @staticmethod
    def _reject_unknown(
        filters: Mapping[str, FilterScalar], allowed: set[str]
    ) -> None:
        unknown = sorted(set(filters) - allowed)
        if unknown:
            raise ValueError(f"unsupported repository filter: {unknown[0]}")

    @staticmethod
    def _validate_window(offset: int, limit: int) -> None:
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")

    @staticmethod
    def _database_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("analysis_as_of must be timezone-aware")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _database_utc_value(value: FilterScalar) -> datetime:
        if not isinstance(value, datetime):
            raise ValueError("time filter must be a datetime")
        return ReportingRepository._database_utc(value)


__all__ = (
    "AnomalyRecordsProjection",
    "DataQualityResultsProjection",
    "DramaCatalogProjection",
    "OperationActionsProjection",
    "PredictionResultsProjection",
    "ReportingRepository",
    "ScoreResultsProjection",
)
