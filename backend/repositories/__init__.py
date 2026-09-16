"""Transport-neutral SQLAlchemy repositories."""

from repositories.actor_repository import ActorRepository
from repositories.analytics_repository import AnalyticsRecord, AnalyticsRepository
from repositories.dashboard_repository import DashboardCounts, DashboardRepository
from repositories.base import BaseRepository, Page
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
from repositories.score_repository import ScoreRepository
from repositories.snapshot_repository import SnapshotRepository
from repositories.tag_repository import TagRepository
from repositories.user_repository import UserRepository

__all__ = [
    "AnalyticsRecord",
    "AnalyticsRepository",
    "ActorRepository",
    "BaseRepository",
    "CompanyRepository",
    "DataQualityRuleRepository",
    "DataQualityRuleResultRepository",
    "DataQualityScoreRepository",
    "DashboardCounts",
    "DashboardRepository",
    "DirectorRepository",
    "DramaRepository",
    "ImportDataRepository",
    "ImportErrorRepository",
    "ImportJobRepository",
    "OperationLogRepository",
    "Page",
    "PlatformRepository",
    "ScoreRepository",
    "SnapshotRepository",
    "TagRepository",
    "UserRepository",
]
