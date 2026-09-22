"""ORM mappings for persisted analysis explanations and lineage metadata."""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, JSON
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class AnalysisExplanation(Base):
    """One versioned explanation snapshot for an existing analysis result."""

    __tablename__ = "analysis_explanations"
    __table_args__ = (
        UniqueConstraint(
            "module_type", "entity_type", "entity_id", "analysis_as_of",
            "algorithm_version", "rule_set_version",
            name="uq_analysis_explanations_identity",
        ),
        CheckConstraint(
            "entity_type IN ('SCORE', 'QUALITY', 'PREDICTION', 'ANOMALY', 'ACTION')",
            name="chk_analysis_explanations_entity_type",
        ),
        CheckConstraint(
            "module_type IN ('SCORE', 'QUALITY', 'PREDICTION', 'ANOMALY', 'OPERATION_ACTION')",
            name="chk_analysis_explanations_module_type",
        ),
        CheckConstraint("entity_id > 0", name="chk_analysis_explanations_entity_id"),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(summary)) > 0",
            name="chk_analysis_explanations_summary",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(algorithm_version)) > 0",
            name="chk_analysis_explanations_algorithm_version",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(rule_set_version)) > 0",
            name="chk_analysis_explanations_rule_set_version",
        ),
        Index("idx_analysis_explanations_entity", "entity_type", "entity_id", "analysis_as_of"),
        Index("idx_analysis_explanations_module", "module_type", "analysis_as_of"),
        Index("idx_analysis_explanations_created", "created_at"),
    )

    explanation_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    module_type: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="N/A"
    )
    rule_set_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="N/A"
    )
    analysis_as_of: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default="CURRENT_TIMESTAMP(6)"
    )


class AnalysisLineageRecord(Base):
    """Weakly linked input evidence for an analysis target."""

    __tablename__ = "analysis_lineage_records"
    __table_args__ = (
        UniqueConstraint(
            "target_type", "target_id", "source_type", "source_id",
            "relationship_type", "analysis_as_of",
            name="uq_analysis_lineage_records_identity",
        ),
        CheckConstraint(
            "target_type IN ('EXPLANATION', 'SCORE', 'QUALITY', 'PREDICTION', 'ANOMALY', 'ACTION')",
            name="chk_analysis_lineage_records_target_type",
        ),
        CheckConstraint(
            "source_type IN ('METRIC', 'SNAPSHOT', 'RULE', 'PREDICTION_INPUT', 'ANOMALY_EVIDENCE')",
            name="chk_analysis_lineage_records_source_type",
        ),
        CheckConstraint(
            "relationship_type IN ('DERIVED_FROM', 'USES_METRIC', 'USES_RULE', 'USES_WINDOW')",
            name="chk_analysis_lineage_records_relationship_type",
        ),
        CheckConstraint("target_id > 0", name="chk_analysis_lineage_records_target_id"),
        CheckConstraint("source_id > 0", name="chk_analysis_lineage_records_source_id"),
        Index("idx_analysis_lineage_records_target", "target_type", "target_id", "analysis_as_of"),
        Index("idx_analysis_lineage_records_source", "source_type", "source_id"),
        Index("idx_analysis_lineage_records_created", "created_at"),
    )

    lineage_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_as_of: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default="CURRENT_TIMESTAMP(6)"
    )


class MetricDependency(Base):
    """Static, versioned dependency edge between two metrics."""

    __tablename__ = "metric_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "parent_metric", "child_metric", "module_type", "algorithm_version",
            name="uq_metric_dependencies_identity",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(parent_metric)) > 0",
            name="chk_metric_dependencies_parent",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(child_metric)) > 0",
            name="chk_metric_dependencies_child",
        ),
        CheckConstraint(
            "module_type IN ('SCORE', 'QUALITY', 'PREDICTION', 'ANOMALY', 'OPERATION_ACTION')",
            name="chk_metric_dependencies_module_type",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(algorithm_version)) > 0",
            name="chk_metric_dependencies_algorithm_version",
        ),
        CheckConstraint(
            "parent_metric <> child_metric",
            name="chk_metric_dependencies_no_self_reference",
        ),
        Index("idx_metric_dependencies_parent", "parent_metric", "module_type", "algorithm_version"),
        Index("idx_metric_dependencies_child", "child_metric", "module_type", "algorithm_version"),
    )

    dependency_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    parent_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    child_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    module_type: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default="CURRENT_TIMESTAMP(6)"
    )


__all__ = ("AnalysisExplanation", "AnalysisLineageRecord", "MetricDependency")
