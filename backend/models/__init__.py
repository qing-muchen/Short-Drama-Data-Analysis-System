"""Schema-faithful SQLAlchemy mappings for all frozen MySQL tables."""

from models.drama import Drama
from models.import_job import ImportError, ImportJob
from models.master_data import Actor, Company, Director, Platform, Tag
from models.operation_log import OperationLog
from models.quality import DataQualityIssue
from models.relations import (
    DramaActor,
    DramaCompany,
    DramaDirector,
    DramaPlatform,
    DramaTag,
)
from models.score import DramaScore
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision
from models.user import User

__all__ = [
    "Actor",
    "Company",
    "DataQualityIssue",
    "Director",
    "Drama",
    "DramaActor",
    "DramaCompany",
    "DramaDirector",
    "DramaMetricSnapshot",
    "DramaMetricSnapshotRevision",
    "DramaPlatform",
    "DramaScore",
    "DramaTag",
    "ImportError",
    "ImportJob",
    "OperationLog",
    "Platform",
    "Tag",
    "User",
]
