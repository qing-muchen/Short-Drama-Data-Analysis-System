"""Request-scoped composition root for Service and Repository objects."""

from datetime import UTC, datetime
from typing import Annotated
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
    """Compose the quality workflow with one request-scoped Session.

    V1 rule evaluators are registered separately from the HTTP layer. Until a
    configured registry is supplied, the Service still provides its persisted
    read APIs and reports unsupported evaluator keys during calculation.
    """

    return DataQualityService(
        session,
        DataQualityRuleRepository(session),
        DataQualityRuleResultRepository(session),
        DataQualityScoreRepository(session),
        OperationLogRepository(session),
        {},
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
