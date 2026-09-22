"""Schema-faithful SQLAlchemy mappings for all frozen MySQL tables."""

from models.anomaly import DataAnomalyRecord
from models.drama import Drama
from models.explanation import (
    AnalysisExplanation,
    AnalysisLineageRecord,
    MetricDependency,
)
from models.data_quality import (
    DataQualityRule,
    DataQualityRuleResult,
    DataQualityScore,
)
from models.import_batch import ImportBatch
from models.import_job import ImportError, ImportJob
from models.master_data import Actor, Company, Director, Platform, Tag
from models.operation_log import OperationLog
from models.operation_action import (
    OperationAction,
    OperationActionHistory,
    OperationActionSource,
)
from models.prediction import PredictionResult
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
    "AnalysisExplanation",
    "AnalysisLineageRecord",
    "Company",
    "DataAnomalyRecord",
    "DataQualityIssue",
    "DataQualityRule",
    "DataQualityRuleResult",
    "DataQualityScore",
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
    "ImportBatch",
    "ImportJob",
    "MetricDependency",
    "OperationLog",
    "OperationAction",
    "OperationActionHistory",
    "OperationActionSource",
    "Platform",
    "PredictionResult",
    "Tag",
    "User",
]
