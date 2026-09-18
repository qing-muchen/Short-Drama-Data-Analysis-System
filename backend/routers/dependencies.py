"""Request-scoped composition root for Service and Repository objects."""

from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.session import get_db_session
from repositories.actor_repository import ActorRepository
from repositories.analytics_repository import AnalyticsRepository
from repositories.company_repository import CompanyRepository
from repositories.data_quality_repository import (
    DataQualityRuleRepository,
    DataQualityRuleResultRepository,
    DataQualityScoreRepository,
)
from repositories.director_repository import DirectorRepository
from repositories.drama_repository import DramaRepository
from repositories.import_repository import (
    ImportDataRepository,
    ImportErrorRepository,
    ImportJobRepository,
    OperationLogRepository,
)
from repositories.platform_repository import PlatformRepository
from repositories.prediction_repository import PredictionRepository
from repositories.score_repository import ScoreRepository
from repositories.tag_repository import TagRepository
from repositories.user_repository import UserRepository
from services.drama_service import DramaService
from services.analytics_service import AnalyticsService
from dashboard.service import DashboardService
from repositories.dashboard_repository import DashboardRepository
from services.import_service import ImportService
from services.data_quality_service import DataQualityService
from services.master_data_service import MasterDataService
from services.platform_service import PlatformService
from services.prediction_service import PredictionObservation, PredictionService
from services.score_service import ScoreService
from services.user_service import UserService
from models.master_data import Platform
from models.relations import DramaPlatform
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision

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


def get_user_service(session: DatabaseSession) -> UserService:
    return UserService(session, UserRepository(session))


def get_drama_service(session: DatabaseSession) -> DramaService:
    return DramaService(session, DramaRepository(session))


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
DataQualityServiceDependency = Annotated[
    DataQualityService,
    Depends(get_data_quality_service),
]
