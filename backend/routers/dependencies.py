"""Request-scoped composition root for Service and Repository objects."""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Iterator, Mapping, NoReturn
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.session import get_db_session
from repositories.actor_repository import ActorRepository
from repositories.analytics_repository import AnalyticsRepository
from repositories.anomaly_repository import AnomalyRepository
from repositories.company_repository import CompanyRepository
from repositories.data_governance_repository import DataGovernanceRepository
from repositories.data_quality_repository import (
    DataQualityRuleRepository,
    DataQualityRuleResultRepository,
    DataQualityScoreRepository,
)
from repositories.data_quality_evidence_repository import (
    DataQualityEvidenceRepository,
)
from repositories.director_repository import DirectorRepository
from repositories.drama_repository import DramaRepository
from repositories.import_repository import (
    ImportBatchRepository,
    ImportDataRepository,
    ImportErrorRepository,
    ImportJobRepository,
    OperationLogRepository,
)
from repositories.platform_repository import PlatformRepository
from repositories.operation_action_repository import (
    OperationActionHistoryRepository,
    OperationActionRepository,
    OperationActionSourceRepository,
)
from repositories.operation_analytics_repository import OperationAnalyticsRepository
from repositories.prediction_repository import PredictionRepository
from repositories.reporting_repository import ReportingRepository
from repositories.explanation_query_repository import (
    AnalysisExplanationQueryRepository,
    AnalysisLineageQueryRepository,
)
from repositories.score_repository import ScoreRepository
from repositories.tag_repository import TagRepository
from repositories.user_repository import UserRepository
from services.drama_service import DramaService
from services.anomaly_service import AnomalyObservation, AnomalyService
from services.analytics_service import AnalyticsService
from dashboard.service import DashboardService
from repositories.dashboard_repository import DashboardRepository
from services.import_service import ImportService
from services.batch_import_service import BatchImportService
from services.data_quality_service import DataQualityService
from analytics.data_quality_rules import production_evaluator_registry
from services.data_governance.providers import (
    CompletenessProvider as GovernanceCompletenessProvider,
    ConsistencyProvider as GovernanceConsistencyProvider,
    FreshnessProvider as GovernanceFreshnessProvider,
)
from services.data_governance.rules import (
    CompletenessRule as GovernanceCompletenessRule,
    ConsistencyRule as GovernanceConsistencyRule,
    FreshnessRule as GovernanceFreshnessRule,
)
from services.data_governance.service import (
    DataGovernanceService,
    SystemClock as GovernanceSystemClock,
)
from services.master_data_service import MasterDataService
from services.platform_service import PlatformService
from services.prediction_service import PredictionObservation, PredictionService
from services.score_service import ScoreService
from services.user_service import UserService
from services.operation_action_service import OperationActionService
from services.operation_analytics.providers import (
    BenchmarkProvider,
    LifecycleInputProvider,
    OperationEffectivenessProvider,
)
from services.operation_analytics.rules import (
    ActionEffectCalculator,
    AnalysisRevisionBuilder,
    BenchmarkCalculator,
    LifecycleClassifier,
)
from services.operation_analytics.service import (
    OperationAnalyticsService,
    SystemClock,
)
from services.exceptions import ConflictException, ValidationException
from services.reporting.contracts import (
    ExportFormat,
    ReportAvailabilityStatus,
    ReportResponse,
    ReportSchema,
    ReportType,
)
from services.reporting.policies import (
    ExportDecisionStatus,
    ExportLimitPolicy,
    FilterValidationError,
    ReportFilterPolicy,
)
from services.reporting.providers import create_default_provider_registry
from services.reporting.registry import create_default_registry
from services.reporting.serializers import ReportSerializer, SerializedReport
from services.reporting.serializers.csv_serializer import CsvReportSerializer
from services.reporting.serializers.xlsx_serializer import XlsxReportSerializer
from services.reporting.service import (
    ReportExportPreparation,
    ReportingService,
    SystemClock as ReportingSystemClock,
)
from services.drama_profile import (
    ActionProfileProvider,
    AnomalyProfileProvider,
    DramaProfileBasic,
    DramaProfileService,
    ExplanationProfileProvider,
    PredictionProfileProvider,
    QualityProfileProvider,
    ScoreProfileProvider,
)
from services.explanation.query_service import AnalysisExplanationQueryService
from models.master_data import Platform
from models.relations import DramaPlatform
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision
from models.quality import DataQualityIssue

DatabaseSession = Annotated[Session, Depends(get_db_session)]
BUSINESS_TIME_ZONE = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)


class _PredictionHistoryProvider:
    """Compose strict as-of revision input without changing existing Analytics APIs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_prediction_history(
        self,
        *,
        drama_id: int,
        analysis_as_of: datetime,
    ) -> list[PredictionObservation]:
        statement = (
            select(
                DramaMetricSnapshot,
                DramaMetricSnapshotRevision,
                DramaPlatform,
                Platform,
            )
            .join(
                DramaMetricSnapshotRevision,
                DramaMetricSnapshotRevision.snapshot_id
                == DramaMetricSnapshot.snapshot_id,
            )
            .join(
                DramaPlatform,
                DramaPlatform.drama_platform_id
                == DramaMetricSnapshot.drama_platform_id,
            )
            .join(Platform, Platform.platform_id == DramaPlatform.platform_id)
            .where(
                DramaPlatform.drama_id == drama_id,
                DramaMetricSnapshot.snapshot_time <= analysis_as_of,
                DramaMetricSnapshotRevision.changed_at <= analysis_as_of,
            )
            .order_by(
                DramaMetricSnapshot.snapshot_time,
                DramaMetricSnapshot.snapshot_id,
                DramaMetricSnapshotRevision.changed_at,
                DramaMetricSnapshotRevision.version_no,
            )
        )
        rows = self.session.execute(statement).all()
        observations: list[PredictionObservation] = []
        for row in rows:
            snapshot = row.DramaMetricSnapshot
            revision = row.DramaMetricSnapshotRevision
            snapshot_time = snapshot.snapshot_time
            if snapshot_time.tzinfo is None:
                snapshot_time = snapshot_time.replace(tzinfo=UTC)
            observations.append(
                PredictionObservation(
                    observation_date=snapshot_time.astimezone(
                        BUSINESS_TIME_ZONE
                    ).date(),
                    platform_id=row.DramaPlatform.platform_id,
                    play_count=revision.play_count,
                    changed_at=revision.changed_at,
                    revision_id=revision.snapshot_revision_id,
                    revision_action=revision.revision_action,
                    platform_active=(
                        row.DramaPlatform.status == "ONLINE"
                        and row.Platform.status == "ACTIVE"
                    ),
                )
            )
        return observations


class _AnomalyHistoryProvider:
    """Compose revision-aware multi-platform inputs for anomaly detection."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_anomaly_history(
        self,
        *,
        analysis_as_of: datetime,
    ) -> list[AnomalyObservation]:
        statement = (
            select(
                DramaMetricSnapshot,
                DramaMetricSnapshotRevision,
                DramaPlatform,
                Platform,
            )
            .join(
                DramaMetricSnapshotRevision,
                DramaMetricSnapshotRevision.snapshot_id
                == DramaMetricSnapshot.snapshot_id,
            )
            .join(
                DramaPlatform,
                DramaPlatform.drama_platform_id
                == DramaMetricSnapshot.drama_platform_id,
            )
            .join(Platform, Platform.platform_id == DramaPlatform.platform_id)
            .where(
                DramaMetricSnapshot.snapshot_time <= analysis_as_of,
                DramaMetricSnapshotRevision.changed_at <= analysis_as_of,
            )
            .order_by(
                DramaMetricSnapshot.snapshot_time,
                DramaMetricSnapshot.snapshot_id,
                DramaMetricSnapshotRevision.changed_at,
                DramaMetricSnapshotRevision.version_no,
            )
        )
        rows = self.session.execute(statement).all()
        if not rows:
            return []

        revision_ids = {
            row.DramaMetricSnapshotRevision.snapshot_revision_id
            for row in rows
        }
        platform_ids = {
            row.DramaPlatform.drama_platform_id for row in rows
        }
        drama_ids = {
            row.DramaPlatform.drama_id for row in rows
        }
        issues = self.session.scalars(
            select(DataQualityIssue).where(
                DataQualityIssue.status.in_(("OPEN", "CONFIRMED")),
                or_(
                    DataQualityIssue.target_snapshot_revision_id.in_(revision_ids),
                    DataQualityIssue.target_drama_platform_id.in_(platform_ids),
                    DataQualityIssue.target_drama_id.in_(drama_ids),
                ),
            )
        ).all()
        revision_quality: dict[int, tuple[int, int]] = {}
        platform_quality: dict[int, tuple[int, int]] = {}
        drama_quality: dict[int, tuple[int, int]] = {}
        for issue in issues:
            key = (
                1 if issue.severity == "ERROR" else 0,
                1 if issue.severity == "WARNING" else 0,
            )
            if issue.target_snapshot_revision_id is not None:
                revision_quality[issue.target_snapshot_revision_id] = _quality_add(
                    revision_quality.get(issue.target_snapshot_revision_id), key
                )
            if issue.target_drama_platform_id is not None:
                platform_quality[issue.target_drama_platform_id] = _quality_add(
                    platform_quality.get(issue.target_drama_platform_id), key
                )
            if issue.target_drama_id is not None:
                drama_quality[issue.target_drama_id] = _quality_add(
                    drama_quality.get(issue.target_drama_id), key
                )

        observations: list[AnomalyObservation] = []
        for row in rows:
            snapshot = row.DramaMetricSnapshot
            revision = row.DramaMetricSnapshotRevision
            snapshot_time = snapshot.snapshot_time
            if snapshot_time.tzinfo is None:
                snapshot_time = snapshot_time.replace(tzinfo=UTC)
            error_count, warning_count = (0, 0)
            for counts in (
                revision_quality.get(revision.snapshot_revision_id),
                platform_quality.get(row.DramaPlatform.drama_platform_id),
                drama_quality.get(row.DramaPlatform.drama_id),
            ):
                if counts is not None:
                    error_count += counts[0]
                    warning_count += counts[1]
            observations.append(
                AnomalyObservation(
                    drama_id=row.DramaPlatform.drama_id,
                    observation_date=snapshot_time.astimezone(
                        BUSINESS_TIME_ZONE
                    ).date(),
                    changed_at=revision.changed_at,
                    platform_id=row.DramaPlatform.platform_id,
                    play_count=revision.play_count,
                    like_count=revision.like_count,
                    comment_count=revision.comment_count,
                    favorite_count=revision.favorite_count,
                    share_count=revision.share_count,
                    revision_id=revision.snapshot_revision_id,
                    revision_action=revision.revision_action,
                    platform_active=(
                        row.DramaPlatform.status == "ONLINE"
                        and row.Platform.status == "ACTIVE"
                    ),
                    error_count=error_count,
                    warning_count=warning_count,
                )
            )
        return observations


def _quality_add(
    current: tuple[int, int] | None,
    value: tuple[int, int],
) -> tuple[int, int]:
    previous = current or (0, 0)
    return previous[0] + value[0], previous[1] + value[1]


def get_user_service(session: DatabaseSession) -> UserService:
    return UserService(session, UserRepository(session))


def get_drama_service(session: DatabaseSession) -> DramaService:
    return DramaService(
        session,
        DramaRepository(session),
        TagRepository(session),
    )


def get_master_data_service(session: DatabaseSession) -> MasterDataService:
    return MasterDataService(
        session,
        ActorRepository(session),
        DirectorRepository(session),
        CompanyRepository(session),
        TagRepository(session),
    )


def get_platform_service(session: DatabaseSession) -> PlatformService:
    return PlatformService(session, PlatformRepository(session))


def get_import_service(session: DatabaseSession) -> ImportService:
    return ImportService(
        session,
        ImportJobRepository(session),
        ImportErrorRepository(session),
        ImportDataRepository(session),
        OperationLogRepository(session),
    )


def get_batch_import_service(session: DatabaseSession) -> BatchImportService:
    return BatchImportService(
        session,
        ImportBatchRepository(session),
        ImportJobRepository(session),
        ImportErrorRepository(session),
        ImportDataRepository(session),
    )


def get_analytics_service(session: DatabaseSession) -> AnalyticsService:
    return AnalyticsService(
        session,
        AnalyticsRepository(session),
        DramaRepository(session),
    )


def get_dashboard_service(session: DatabaseSession) -> DashboardService:
    return DashboardService(
        session,
        DashboardRepository(session),
        get_analytics_service(session),
    )


def get_score_service(session: DatabaseSession) -> ScoreService:
    dramas = DramaRepository(session)
    analytics = AnalyticsService(
        session,
        AnalyticsRepository(session),
        dramas,
    )
    return ScoreService(
        session,
        analytics,
        ScoreRepository(session),
        dramas,
        OperationLogRepository(session),
    )


def get_prediction_service(session: DatabaseSession) -> PredictionService:
    """Compose PredictionService with one Session and strict as-of input reads."""

    return PredictionService(
        session,
        _PredictionHistoryProvider(session),
        PredictionRepository(session),
        OperationLogRepository(session),
    )


def get_anomaly_service(session: DatabaseSession) -> AnomalyService:
    """Compose AnomalyService with one Session and as-of history provider."""

    return AnomalyService(
        session,
        _AnomalyHistoryProvider(session),
        AnomalyRepository(session),
        OperationLogRepository(session),
    )


def get_data_quality_service(session: DatabaseSession) -> DataQualityService:
    """Compose the production quality workflow with one request-scoped Session."""

    return DataQualityService(
        session,
        DataQualityRuleRepository(session),
        DataQualityRuleResultRepository(session),
        DataQualityScoreRepository(session),
        OperationLogRepository(session),
        production_evaluator_registry(),
        evidence=DataQualityEvidenceRepository(session),
    )


def get_operation_action_service(session: DatabaseSession) -> OperationActionService:
    """Compose the action workflow with one request-scoped Session."""
    return OperationActionService(
        session,
        OperationActionRepository(session),
        OperationActionSourceRepository(session),
        OperationActionHistoryRepository(session),
        OperationLogRepository(session),
    )


def get_explanation_query_service(
    session: DatabaseSession,
) -> AnalysisExplanationQueryService:
    return AnalysisExplanationQueryService(
        session,
        AnalysisExplanationQueryRepository(session),
        AnalysisLineageQueryRepository(session),
    )


class _DramaProfileBasicProvider:
    """Adapt the existing DramaRepository to the profile basic DTO boundary."""

    def __init__(self, repository: DramaRepository) -> None:
        self.repository = repository

    def get_profile_basic(self, drama_id: int) -> DramaProfileBasic:
        drama = self.repository.get_by_id(drama_id)
        if drama is None:
            from services.exceptions import NotFoundException

            raise NotFoundException("Drama not found")
        return DramaProfileBasic(
            drama_id=drama.drama_id,
            title=drama.drama_name,
            platform=None,
            tags=(),
        )


def get_drama_profile_service(session: DatabaseSession) -> DramaProfileService:
    return DramaProfileService(
        ScoreProfileProvider(ScoreRepository(session)),
        QualityProfileProvider(DataQualityScoreRepository(session)),
        PredictionProfileProvider(PredictionRepository(session)),
        AnomalyProfileProvider(AnomalyRepository(session)),
        ActionProfileProvider(OperationActionRepository(session)),
        ExplanationProfileProvider(
            AnalysisExplanationQueryRepository(session),
            AnalysisLineageQueryRepository(session),
        ),
        basic_provider=_DramaProfileBasicProvider(DramaRepository(session)),
    )


def get_operation_analytics_service(
    session: DatabaseSession,
) -> OperationAnalyticsService:
    """Compose the read-only Phase 8 analytics graph for one request."""

    repository = OperationAnalyticsRepository(session)
    return OperationAnalyticsService(
        OperationEffectivenessProvider(repository),
        LifecycleInputProvider(repository),
        BenchmarkProvider(repository),
        ActionEffectCalculator(),
        LifecycleClassifier(),
        BenchmarkCalculator(),
        AnalysisRevisionBuilder(),
        SystemClock(),
    )


def get_data_governance_service(
    session: DatabaseSession,
) -> DataGovernanceService:
    """Compose the read-only Phase 9 governance graph for one request."""

    repository = DataGovernanceRepository(session)
    return DataGovernanceService(
        GovernanceFreshnessProvider(repository),
        GovernanceCompletenessProvider(repository),
        GovernanceConsistencyProvider(repository),
        GovernanceFreshnessRule(),
        GovernanceCompletenessRule(),
        GovernanceConsistencyRule(),
        GovernanceSystemClock(),
    )


@dataclass(slots=True)
class ReportingExportStream:
    """Owned binary export stream closed after response iteration."""

    serialized: SerializedReport
    media_type: str
    filename: str
    headers: dict[str, str]

    def iter_bytes(self) -> Iterator[bytes]:
        try:
            yield from self.serialized.iter_bytes()
        finally:
            self.serialized.close()

    def close(self) -> None:
        self.serialized.close()


class ReportingApiService:
    """Request-scoped HTTP export flow around the transport-neutral Service."""

    def __init__(
        self,
        service: ReportingService,
        serializers: Mapping[ExportFormat, ReportSerializer],
        export_limit_policy: ExportLimitPolicy,
    ) -> None:
        self._service = service
        self._serializers = dict(serializers)
        self._export_limit_policy = export_limit_policy

    def get_catalog(self) -> tuple[ReportSchema, ...]:
        return self._service.get_catalog()

    def preview_report(
        self,
        *,
        report_type: object,
        filters: Mapping[str, object] | None,
        analysis_as_of: datetime | None,
        page_size: int,
    ) -> ReportResponse:
        try:
            return self._service.preview_report(
                report_type=self._report_type(report_type),
                filters=filters,
                analysis_as_of=analysis_as_of,
                limit=page_size,
            )
        except (FilterValidationError, TypeError, ValueError) as exc:
            raise self._validation_error(exc) from exc

    def export_report(
        self,
        *,
        report_type: object,
        filters: Mapping[str, object] | None,
        analysis_as_of: datetime | None,
        export_format: object,
        confirmation: int | None,
    ) -> ReportingExportStream:
        internal_format = self._export_format(export_format)
        try:
            preparation = self._service.prepare_export(
                report_type=self._report_type(report_type),
                export_format=internal_format,
                filters=filters,
                analysis_as_of=analysis_as_of,
                confirmed_row_count=confirmation,
            )
        except (FilterValidationError, TypeError, ValueError) as exc:
            raise self._validation_error(exc) from exc

        decision = preparation.decision
        if decision is None:
            self._raise_unavailable(preparation.report.availability.status.value)
        if decision.status is ExportDecisionStatus.REQUIRE_CONFIRMATION:
            raise ConflictException(
                "Export confirmation is required",
                code=decision.code or "EXPORT_CONFIRMATION_REQUIRED",
                details={"confirmed_row_count": decision.total_rows},
            )
        if decision.status is ExportDecisionStatus.REJECT:
            raise ValidationException(
                "Report export is not permitted",
                code=decision.code or "EXPORT_LIMIT_EXCEEDED",
                details={
                    "total_rows": decision.total_rows,
                    "max_rows": decision.max_rows,
                },
            )
        if (
            preparation.report.availability.status
            is not ReportAvailabilityStatus.AVAILABLE
        ):
            self._raise_unavailable(
                preparation.report.availability.status.value
            )

        serializer = self._serializers.get(internal_format)
        if serializer is None:
            raise ValidationException(
                "Report export format is not configured",
                code="UNSUPPORTED_EXPORT_FORMAT",
            )
        try:
            serialized = serializer.serialize(
                preparation.report.rows,
                preparation.schema,
            )
        except Exception as exc:
            logger.exception("report serialization failed")
            raise ValidationException(
                "Report export could not be generated",
                code="EXPORT_FAILED",
            ) from exc

        size_decision = self._export_limit_policy.evaluate_file_size(
            serialized.byte_length
        )
        if size_decision.status is not ExportDecisionStatus.ALLOW:
            serialized.close()
            raise ValidationException(
                "Report export exceeds the file size limit",
                code=size_decision.code or "EXPORT_SIZE_LIMIT_EXCEEDED",
                details={"byte_length": serialized.byte_length},
            )
        if (
            serialized.mime_type != preparation.descriptor.mime_type
            or serialized.file_extension != preparation.descriptor.extension
        ):
            serialized.close()
            raise ValidationException(
                "Report serializer output does not match its descriptor",
                code="EXPORT_DESCRIPTOR_MISMATCH",
            )

        try:
            filename = self._filename(preparation)
        except Exception:
            serialized.close()
            raise
        snapshot = preparation.report.metadata.snapshot
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(serialized.byte_length),
            "X-Report-Schema-Version": self._ascii_header(
                preparation.schema.schema_version
            ),
            "X-Analysis-As-Of": snapshot.analysis_as_of.isoformat(),
            "X-Snapshot-Semantics": snapshot.semantics.value,
        }
        return ReportingExportStream(
            serialized=serialized,
            media_type=serialized.mime_type,
            filename=filename,
            headers=headers,
        )

    @staticmethod
    def _report_type(value: object) -> ReportType:
        raw = getattr(value, "value", value)
        try:
            return ReportType(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationException(
                "Unsupported report type",
                code="UNSUPPORTED_REPORT_TYPE",
            ) from exc

    @staticmethod
    def _export_format(value: object) -> ExportFormat:
        raw = getattr(value, "value", value)
        try:
            return ExportFormat(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationException(
                "Unsupported export format",
                code="UNSUPPORTED_EXPORT_FORMAT",
            ) from exc

    @staticmethod
    def _validation_error(error: Exception) -> ValidationException:
        if isinstance(error, FilterValidationError):
            return ValidationException(
                error.message,
                code=error.code,
                details={"field": error.field} if error.field else None,
            )
        return ValidationException(str(error), code="INVALID_REPORT_REQUEST")

    @staticmethod
    def _raise_unavailable(status: str) -> NoReturn:
        raise ValidationException(
            "Report data is unavailable",
            code="REPORT_NOT_AVAILABLE",
            details={"availability": status},
        )

    @staticmethod
    def _ascii_header(value: str) -> str:
        return "".join(char for char in value if 32 <= ord(char) <= 126)

    @staticmethod
    def _filename(preparation: ReportExportPreparation) -> str:
        snapshot = preparation.report.metadata.snapshot.analysis_as_of
        schema_version = re.sub(
            r"[^A-Za-z0-9._-]+",
            "-",
            preparation.schema.schema_version,
        ).strip("-._")
        filename = preparation.descriptor.filename_template.format(
            analysis_as_of=snapshot.strftime("%Y%m%dT%H%M%SZ"),
            schema_version=schema_version,
        )
        if not filename.isascii() or any(char in filename for char in "/\\\r\n"):
            raise ValidationException(
                "Report filename is unsafe",
                code="UNSAFE_EXPORT_FILENAME",
            )
        return filename


def get_reporting_service(session: DatabaseSession) -> ReportingApiService:
    """Compose one read-only reporting graph and its safe export flow."""

    schema_registry = create_default_registry()
    repository = ReportingRepository(session)
    provider_registry = create_default_provider_registry(
        repository,
        schema_registry,
    )
    export_limit_policy = ExportLimitPolicy()
    service = ReportingService(
        schema_registry=schema_registry,
        provider_registry=provider_registry,
        filter_policy=ReportFilterPolicy(schema_registry),
        export_limit_policy=export_limit_policy,
        clock=ReportingSystemClock(),
    )
    return ReportingApiService(
        service,
        {
            ExportFormat.CSV: CsvReportSerializer(),
            ExportFormat.XLSX: XlsxReportSerializer(),
        },
        export_limit_policy,
    )


UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
DramaServiceDependency = Annotated[DramaService, Depends(get_drama_service)]
MasterDataServiceDependency = Annotated[
    MasterDataService,
    Depends(get_master_data_service),
]
PlatformServiceDependency = Annotated[
    PlatformService,
    Depends(get_platform_service),
]
ImportServiceDependency = Annotated[ImportService, Depends(get_import_service)]
BatchImportServiceDependency = Annotated[
    BatchImportService, Depends(get_batch_import_service)
]
AnalyticsServiceDependency = Annotated[
    AnalyticsService,
    Depends(get_analytics_service),
]
DashboardServiceDependency = Annotated[
    DashboardService,
    Depends(get_dashboard_service),
]
ScoreServiceDependency = Annotated[ScoreService, Depends(get_score_service)]
PredictionServiceDependency = Annotated[
    PredictionService,
    Depends(get_prediction_service),
]
AnomalyServiceDependency = Annotated[
    AnomalyService,
    Depends(get_anomaly_service),
]
DataQualityServiceDependency = Annotated[
    DataQualityService,
    Depends(get_data_quality_service),
]
OperationActionServiceDependency = Annotated[
    OperationActionService,
    Depends(get_operation_action_service),
]
AnalysisExplanationQueryServiceDependency = Annotated[
    AnalysisExplanationQueryService,
    Depends(get_explanation_query_service),
]
DramaProfileServiceDependency = Annotated[
    DramaProfileService,
    Depends(get_drama_profile_service),
]
OperationAnalyticsServiceDependency = Annotated[
    OperationAnalyticsService,
    Depends(get_operation_analytics_service),
]
DataGovernanceServiceDependency = Annotated[
    DataGovernanceService,
    Depends(get_data_governance_service),
]
ReportingServiceDependency = Annotated[
    ReportingApiService,
    Depends(get_reporting_service),
]
