"""Import-only verification for the current 31-table ORM mapping."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, inspect
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import configure_mappers

import models
from database.base import Base


EXPECTED_TABLES = {
    "users",
    "dramas",
    "actors",
    "directors",
    "companies",
    "platforms",
    "tags",
    "drama_actors",
    "drama_directors",
    "drama_companies",
    "drama_tags",
    "drama_platforms",
    "drama_metric_snapshots",
    "drama_metric_snapshot_revisions",
    "drama_scores",
    "import_jobs",
    "import_batches",
    "import_errors",
    "data_quality_issues",
    "data_quality_rules",
    "data_quality_rule_results",
    "data_quality_scores",
    "operation_logs",
    "prediction_results",
    "data_anomaly_records",
    "operation_actions",
    "operation_action_sources",
    "operation_action_history",
    "analysis_explanations",
    "analysis_lineage_records",
    "metric_dependencies",
}


def test_all_models_import_and_configure() -> None:
    """All model classes load and every relationship resolves without a DB."""

    assert len(models.__all__) == 31
    configure_mappers()
    assert {
        "actor_relations",
        "director_relations",
        "company_relations",
        "tag_relations",
        "platform_relations",
    }.issubset(inspect(models.Drama).relationships.keys())
    assert "snapshots" in inspect(models.DramaPlatform).relationships
    assert {
        "revisions",
        "current_revision",
        "source_import_job",
    }.issubset(inspect(models.DramaMetricSnapshot).relationships.keys())
    assert "scores" in inspect(models.Drama).relationships
    assert "drama" in inspect(models.DramaScore).relationships
    assert "errors" in inspect(models.ImportJob).relationships
    assert "results" in inspect(models.DataQualityRule).relationships
    assert {"rule", "score"}.issubset(
        inspect(models.DataQualityRuleResult).relationships.keys()
    )
    assert "rule_results" in inspect(models.DataQualityScore).relationships
    assert "files" in inspect(models.ImportBatch).relationships
    assert "predictions" in inspect(models.Drama).relationships
    assert "drama" in inspect(models.PredictionResult).relationships
    assert "anomaly_records" in inspect(models.Drama).relationships
    assert "drama" in inspect(models.DataAnomalyRecord).relationships
    assert "operation_actions" in inspect(models.Drama).relationships
    assert {"sources", "history", "drama", "assignee", "created_by"}.issubset(
        inspect(models.OperationAction).relationships.keys()
    )
    assert "action" in inspect(models.OperationActionSource).relationships
    assert "action" in inspect(models.OperationActionHistory).relationships


def test_metadata_matches_frozen_schema_shape() -> None:
    """Metadata preserves table, PK, FK, CHECK, and UNIQUE baseline counts."""

    assert set(Base.metadata.tables) == EXPECTED_TABLES

    tables = tuple(Base.metadata.tables.values())
    assert all(len(table.primary_key.columns) == 1 for table in tables)
    assert all(
        isinstance(next(iter(table.primary_key.columns)).type, BIGINT)
        and next(iter(table.primary_key.columns)).type.unsigned
        and next(iter(table.primary_key.columns)).autoincrement is True
        for table in tables
    )

    foreign_keys = sum(
        isinstance(constraint, ForeignKeyConstraint)
        for table in tables
        for constraint in table.constraints
    )
    checks = sum(
        isinstance(constraint, CheckConstraint)
        for table in tables
        for constraint in table.constraints
    )
    uniques = sum(
        isinstance(constraint, UniqueConstraint)
        and constraint.name is not None
        for table in tables
        for constraint in table.constraints
    )

    assert foreign_keys == 52
    assert all(
        constraint.name is not None
        for table in tables
        for constraint in table.foreign_key_constraints
    )
    assert checks == 126
    assert uniques == 29
    assert sum(len(table.indexes) for table in tables) == 78
    assert all(
        foreign_key.ondelete in {"RESTRICT", "CASCADE"}
        and foreign_key.onupdate == "RESTRICT"
        for table in tables
        for foreign_key in table.foreign_keys
    )

    cascade_foreign_keys = [
        foreign_key
        for table in tables
        for foreign_key in table.foreign_keys
        if foreign_key.ondelete == "CASCADE"
    ]
    assert len(cascade_foreign_keys) == 3
    cascade_pairs = {
        (foreign_key.parent.table.name, foreign_key.column.table.name)
        for foreign_key in cascade_foreign_keys
    }
    assert ("data_quality_rule_results", "data_quality_scores") in cascade_pairs
    assert ("operation_action_sources", "operation_actions") in cascade_pairs
    assert ("operation_action_history", "operation_actions") in cascade_pairs

    for table_name in (
        "analysis_explanations",
        "analysis_lineage_records",
        "metric_dependencies",
    ):
        assert len(Base.metadata.tables[table_name].foreign_keys) == 0


def test_snapshot_and_governance_models_remain_separate() -> None:
    """Special schema designs remain explicit rather than JSON/polymorphic fields."""

    snapshot = Base.metadata.tables["drama_metric_snapshots"]
    revision = Base.metadata.tables["drama_metric_snapshot_revisions"]
    quality = Base.metadata.tables["data_quality_issues"]
    operation = Base.metadata.tables["operation_logs"]
    score = Base.metadata.tables["drama_scores"]

    assert "current_revision_id" in snapshot.c
    assert "revision_action" in revision.c
    assert {
        "target_snapshot_revision_id",
        "target_drama_platform_id",
        "target_drama_id",
    }.issubset(quality.c.keys())
    assert "target_type" not in quality.c
    assert "target_id" not in quality.c
    assert "target_json" not in operation.c
    assert {
        "score_scope_type",
        "score_scope_id",
        "analysis_as_of",
        "algorithm_version",
    }.issubset(score.c.keys())
    assert "calculated_by_user_id" not in score.c
    assert set(score.c.keys()).isdisjoint(
        {"drama_name", "play_count", "like_count", "comment_count"}
    )
